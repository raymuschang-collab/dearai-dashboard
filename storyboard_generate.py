#!/usr/bin/env python3
"""
Generate stick-figure storyboards via Higgsfield CLI (gpt_image_2) for every
Pending set in the Storyboard Prompts tab. Two iterations per set; uploads
to the matching Drive folder, sets sharing to anyone-with-link reader, writes
URLs back to the sheet.

(Provider history: this script was originally fal.ai nano-banana-2; switched
to Higgsfield gpt_image_2 — see MODEL constant below — for $0 marginal cost
under the team's Higgsfield MCP. The CLI binary lives at ~/.npm-global/bin/higgs;
install with `npm install -g @higgsfield/cli` if missing.)

Idempotent — sets with Status="Done" are skipped unless --force is passed.
A failed run leaves Status="Failed" + the error in column I; re-running will
retry only failed/pending sets.

Usage:
    python3 storyboard_generate.py --sheet <sheet-id-or-url>
    python3 storyboard_generate.py --sheet <id> --set 5         # one specific set
    python3 storyboard_generate.py --sheet <id> --force         # regenerate Done too
    python3 storyboard_generate.py --sheet <id> --aspect 16:9   # override default 21:9
"""
from __future__ import annotations

import argparse
import builtins
import io
import json
import os
import re
import subprocess
import sys
import time

import gspread
import requests
from dotenv import load_dotenv

# Make print() resilient to a parent-process restart killing our stdout pipe.
# Without this, any print() after pipe death raises BrokenPipeError which
# kills the iter loop mid-way, losing iter 2.
_orig_print = builtins.print


def _safe_print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    except BrokenPipeError:
        # Parent's stdout reader is gone — silently swap to /dev/null so
        # subsequent prints never raise again.
        try:
            sys.stdout = open(os.devnull, "w")
            sys.stderr = open(os.devnull, "w")
        except Exception:
            pass


builtins.print = _safe_print
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from auth import get_credentials


HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

MODEL = "gpt_image_2"  # Higgsfield via CLI
DEFAULT_ASPECT = "16:9"  # landscape storyboard page (5 stick-figure panels)
DEFAULT_RESOLUTION = "1k"
DEFAULT_QUALITY = "high"
ITERATIONS = 2
HIGGS_BIN = os.path.expanduser("~/.npm-global/bin/higgs")

SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def parse_sheet_id(s: str) -> str:
    m = SHEETS_URL_RE.search(s)
    return m.group(1) if m else s.strip()


def generate_image(prompt: str, aspect: str, resolution: str) -> bytes:
    """Fire gpt_image_2 via the Higgsfield CLI, poll until completed,
    download the PNG. The CLI's `higgs generate get <id> --json` returns
    the result URL at the top-level key `result_url`."""
    if not os.path.exists(HIGGS_BIN):
        raise RuntimeError(
            f"Higgsfield CLI not found at {HIGGS_BIN}. "
            f"Install with: npm install -g @higgsfield/cli")
    sub = subprocess.run([
        HIGGS_BIN, "generate", "create", MODEL,
        "--prompt", prompt,
        "--aspect_ratio", aspect,
        "--quality", DEFAULT_QUALITY,
        "--resolution", resolution,
        "--json",
    ], capture_output=True, text=True, timeout=120)
    if sub.returncode != 0:
        raise RuntimeError(f"higgs submit failed: {sub.stderr[:300]}")
    job_ids = json.loads(sub.stdout)
    if not job_ids:
        raise RuntimeError(f"no job id returned: {sub.stdout[:200]}")
    job_id = job_ids[0]
    # Poll
    deadline = time.time() + 360
    while time.time() < deadline:
        get = subprocess.run([HIGGS_BIN, "generate", "get", job_id, "--json"],
                             capture_output=True, text=True, timeout=30)
        if get.returncode == 0:
            try:
                data = json.loads(get.stdout)
            except json.JSONDecodeError:
                data = {}
            status = data.get("status")
            if status == "completed":
                url = data.get("result_url") or data.get("rawUrl") \
                    or (data.get("results", {}).get("rawUrl") if isinstance(data.get("results"), dict) else None)
                if not url:
                    raise RuntimeError(f"no result_url in completed job: {json.dumps(data)[:300]}")
                resp = requests.get(url, timeout=180)
                resp.raise_for_status()
                return resp.content
            if status == "failed":
                raise RuntimeError(f"higgs job failed: {json.dumps(data)[:300]}")
        time.sleep(8)
    raise RuntimeError(f"higgs job {job_id} timed out after 360s")


def upload_and_share(drive, folder_id: str, filename: str, content: bytes) -> str:
    media = MediaIoBaseUpload(
        io.BytesIO(content), mimetype="image/png", resumable=False
    )
    file = drive.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id,webViewLink",
    ).execute()
    drive.permissions().create(
        fileId=file["id"],
        body={"role": "reader", "type": "anyone"},
        fields="id",
    ).execute()
    return file["webViewLink"]


def process_row(
    sb,
    drive,
    sheet_row: int,
    row_data: list,
    *,
    aspect: str,
    resolution: str,
    storyboard_globals: str = "",
    force: bool = False,
) -> dict:
    """row_data layout (living-doc schema):
    [0] Set#
    [1] Shot Range
    [2] Storyboard Prompt — body only (5-shot list); globals are at top of tab
    [3] Bahasa Prompt — body only
    [4] Drive Folder
    [5] Status
    [6] Iter 1 URL
    [7] Iter 2 URL
    [8] Error
    storyboard_globals: assembled global preamble from B1-B4, prepended at runtime.
    """
    set_num = row_data[0] if len(row_data) > 0 else ""
    shot_range = row_data[1] if len(row_data) > 1 else ""
    body = row_data[2] if len(row_data) > 2 else ""
    # Assemble full prompt = globals + blank line + body
    if storyboard_globals and body:
        prompt = f"{storyboard_globals}\n\n{body}"
    else:
        prompt = body
    folder_url = row_data[4] if len(row_data) > 4 else ""
    status = row_data[5] if len(row_data) > 5 else ""

    print(f"\n=== Set {set_num} — shots {shot_range} (row {sheet_row}) ===")

    if status == "Done" and not force:
        print(f"  SKIP — already Done. Use --force to regenerate.")
        return {"status": "skip"}

    if not prompt:
        print(f"  SKIP — empty prompt cell")
        return {"status": "skip"}

    if "/folders/" not in folder_url:
        msg = f"bad folder url: {folder_url}"
        print(f"  FAIL — {msg}")
        sb.update(
            range_name=f"F{sheet_row}:I{sheet_row}",
            values=[["Failed", "", "", msg]],
        )
        return {"status": "fail", "error": msg}

    folder_id = folder_url.split("/folders/")[1].rstrip("/")
    sb.update(range_name=f"F{sheet_row}", values=[["Generating"]])

    # Track per-iter results so iter 2 success persists even if iter 1 errored.
    urls_by_iter = {}  # {1: url, 2: url}
    err = None
    for it in range(1, ITERATIONS + 1):
        t0 = time.time()
        print(f"  iter {it}: generating...", end="", flush=True)
        try:
            img = generate_image(prompt, aspect, resolution)
            gen_dt = time.time() - t0
            print(f" {len(img)//1024}KB in {gen_dt:.1f}s", end="", flush=True)
            fname = f"set-{int(set_num):02d}-iter-{it}.png"
            url = upload_and_share(drive, folder_id, fname, img)
            print(f" → uploaded")
            urls_by_iter[it] = url
        except Exception as e:
            print(f"\n    FAILED iter {it}: {type(e).__name__}: {e}")
            err = f"iter {it}: {type(e).__name__}: {e}"
            continue  # keep trying next iter

    iter1 = urls_by_iter.get(1, "")
    iter2 = urls_by_iter.get(2, "")
    if iter1 and iter2:
        status = "Done"
        err_msg = ""
    elif iter1 or iter2:
        status = "Done"  # Done with the iter(s) that succeeded
        err_msg = err or ""
    else:
        status = "Failed"
        err_msg = err or "unknown error"
    sb.update(
        range_name=f"F{sheet_row}:I{sheet_row}",
        values=[[status, iter1, iter2, err_msg]],
        value_input_option="USER_ENTERED",
    )
    print(f"  → row {sheet_row}: {status} (iter1={'✓' if iter1 else '✗'}, iter2={'✓' if iter2 else '✗'})")
    return {"status": "done" if status == "Done" else "fail",
            "urls": [u for u in (iter1, iter2) if u], "error": err}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True, help="Sheet ID or URL")
    ap.add_argument("--set", type=int, help="Generate only this set number")
    ap.add_argument("--force", action="store_true", help="Regenerate Done sets")
    ap.add_argument("--aspect", default=DEFAULT_ASPECT, help="Aspect ratio (default 21:9)")
    ap.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="Resolution (default 1K)")
    args = ap.parse_args()

    # Higgsfield CLI provides its own auth (~/.config/higgsfield credentials).
    # Confirm the binary is present + a token exists.
    if not os.path.exists(HIGGS_BIN):
        sys.exit(f"higgs CLI not found at {HIGGS_BIN}. "
                 f"Run: npm install -g @higgsfield/cli")
    auth_check = subprocess.run([HIGGS_BIN, "auth", "token"],
                                 capture_output=True, text=True, timeout=10)
    if auth_check.returncode != 0:
        sys.exit("higgs CLI not authenticated. Run: higgs auth login")

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_id = parse_sheet_id(args.sheet)
    sh = gc.open_by_key(sheet_id)
    print(f"Sheet: {sh.title}")
    print(f"Aspect: {args.aspect}  Resolution: {args.resolution}  Iterations/set: {ITERATIONS}")

    sb = sh.worksheet("Storyboard Prompts")

    # Living-doc schema: globals in rows 1-8, headers in row 10, data row 11+.
    # Headers (row 10): A=Set #, B=Shot Range, C=Storyboard Prompt (body only),
    #                   D=Bahasa Prompt (body only), E=Drive Folder, F=Status,
    #                   G=Iter 1 URL, H=Iter 2 URL, I=Error
    # The C/D cells contain just the per-set 5-shot body; globals (camera,
    # music, drawing style, panel instruction) live in B1-B4 and are prepended
    # at runtime so the image gen sees the full assembled prompt.
    headers = sb.row_values(10)
    if len(headers) < 9 or headers[3] != "Bahasa Prompt":
        sys.exit(
            "Storyboard Prompts tab schema is not the living-doc v3 format "
            "(globals at top, headers at row 10). "
            "Run `python3 living_doc_migrate.py` to migrate."
        )

    # Read EN globals once (B1-B4) and assemble the preamble. The image gen
    # script prepends this to each set's body at process_row time.
    globals_block = sb.get("B1:B4", value_render_option="FORMATTED_VALUE")
    storyboard_globals = "\n".join(
        row[0] for row in globals_block if row and row[0]
    )

    data = sb.get(
        f"A11:I{sb.row_count}",
        value_render_option="FORMATTED_VALUE",
    )
    data = [r for r in data if len(r) > 0 and r[0]]

    overall_start = time.time()
    results = []
    for i, row in enumerate(data):
        sheet_row = i + 11
        try:
            set_num_int = int(row[0])
        except (ValueError, IndexError):
            continue
        if args.set is not None and set_num_int != args.set:
            continue
        result = process_row(
            sb,
            drive,
            sheet_row,
            row,
            aspect=args.aspect,
            resolution=args.resolution,
            storyboard_globals=storyboard_globals,
            force=args.force,
        )
        results.append((set_num_int, result))

    total_dt = time.time() - overall_start
    print(f"\n\n=== SUMMARY ({total_dt:.1f}s) ===")
    counts = {"done": 0, "skip": 0, "fail": 0}
    for _, r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    for set_num, r in results:
        print(f"  Set {set_num}: {r['status']}")
    print(
        f"\n  TOTAL: {counts.get('done', 0)} done, "
        f"{counts.get('skip', 0)} skipped, {counts.get('fail', 0)} failed"
    )


if __name__ == "__main__":
    main()

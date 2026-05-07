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
import shutil
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


def resolve_higgs_bin() -> str:
    """Find the higgs CLI binary. Order:
      1. $HIGGS_BIN env var (explicit override)
      2. Render's project-local install path (where build.sh puts it)
      3. PATH lookup
      4. Local-dev defaults under $HOME (Mac/Linux dev machines)
    """
    configured = os.environ.get("HIGGS_BIN")
    if configured:
        return shutil.which(configured) or os.path.expanduser(configured)
    # Render: build.sh installs into the repo checkout (only path that
    # survives the build → runtime container handoff).
    render_path = "/opt/render/project/src/.npm-global/bin/higgs"
    if os.path.exists(render_path):
        return render_path
    on_path = shutil.which("higgs")
    if on_path:
        return on_path
    # Local dev fallbacks
    for p in ("~/.npm-global/bin/higgs", "~/npm-global/bin/higgs"):
        expanded = os.path.expanduser(p)
        if os.path.exists(expanded):
            return expanded
    return os.path.expanduser("~/.npm-global/bin/higgs")


HIGGS_BIN = resolve_higgs_bin()

SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def parse_sheet_id(s: str) -> str:
    m = SHEETS_URL_RE.search(s)
    return m.group(1) if m else s.strip()


# Fal.ai endpoint for OpenAI's GPT Image 2 (released Apr 21 2026, photoreal +
# pixel-perfect text rendering + built-in reasoning). Stateless API key auth
# via FAL_KEY env var; picks up .env automatically via load_dotenv at import.
# fal.ai queue API pattern:
#   POST /fal-ai/gpt-image-2 → {"request_id": "..."}
#   GET  /fal-ai/gpt-image-2/requests/{id}/status → {"status": "IN_PROGRESS"|"COMPLETED"|...}
#   GET  /fal-ai/gpt-image-2/requests/{id}        → final response with images[].url
FAL_QUEUE_BASE = "https://queue.fal.run/fal-ai/gpt-image-2"

# Aspect → fal's image_size enum mapping. gpt-image-2 supports preset names
# rather than free-form aspect strings; landscape_16_9 covers our 21:9 storyboards.
FAL_IMAGE_SIZE_MAP = {
    "16:9":   "landscape_16_9",
    "21:9":   "landscape_16_9",
    "9:16":   "portrait_9_16",
    "1:1":    "square_hd",
    "4:3":    "landscape_4_3",
    "3:4":    "portrait_4_3",
}


def generate_image(prompt: str, aspect: str, resolution: str) -> bytes:
    """Fire fal.ai/gpt-image-2 via the queue API, poll until COMPLETED,
    download the PNG. Stateless API-key auth — no CLI/OAuth, never expires.

    Replaces the Higgsfield CLI subprocess flow that broke on Render every
    few hours when the OAuth session expired. Same OpenAI engine,
    autonomous on Render."""
    fal_key = os.environ.get("FAL_KEY", "").strip()
    if not fal_key:
        raise RuntimeError(
            "FAL_KEY env var not set. Add it to .env (local) or Render's "
            "environment variables. Get a key from https://fal.ai/dashboard/keys"
        )
    headers = {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json",
    }
    image_size = FAL_IMAGE_SIZE_MAP.get(aspect, "landscape_16_9")

    # Submit. resolution arg is mapped to fal's "quality" tier (high default).
    submit = requests.post(
        FAL_QUEUE_BASE,
        headers=headers,
        json={
            "prompt": prompt,
            "image_size": image_size,
            "quality": "high",          # low | medium | high
            "num_images": 1,
            "output_format": "png",
        },
        timeout=60,
    )
    if submit.status_code != 200:
        raise RuntimeError(f"fal submit failed: HTTP {submit.status_code} — {submit.text[:300]}")
    request_id = submit.json().get("request_id")
    if not request_id:
        raise RuntimeError(f"no request_id in submit response: {submit.text[:200]}")

    # Poll status
    status_url = f"{FAL_QUEUE_BASE}/requests/{request_id}/status"
    deadline = time.time() + 360
    while time.time() < deadline:
        s = requests.get(status_url, headers=headers, timeout=30)
        if s.status_code != 200:
            time.sleep(4)
            continue
        st = s.json().get("status", "")
        if st == "COMPLETED":
            break
        if st in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"fal job {st.lower()}: {s.text[:300]}")
        time.sleep(4)
    else:
        raise RuntimeError(f"fal job {request_id} timed out after 360s")

    # Fetch result
    result_url = f"{FAL_QUEUE_BASE}/requests/{request_id}"
    r = requests.get(result_url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    images = data.get("images") or []
    if not images:
        raise RuntimeError(f"fal completed but no images: {json.dumps(data)[:300]}")
    img_url = images[0].get("url")
    if not img_url:
        raise RuntimeError(f"fal images[0] has no url: {json.dumps(data)[:300]}")
    resp = requests.get(img_url, timeout=180)
    resp.raise_for_status()
    return resp.content


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

    # Track per-iter results so a successful iter persists even if the other
    # iter errored. Both iters fire in PARALLEL via a thread pool — each one
    # is a 30-60s fal.ai gpt-image-2 call, so concurrent dispatch roughly
    # halves wall time (60-120s sequential → 30-60s parallel).
    #
    # googleapi's Drive client is thread-safe for distinct file uploads
    # (each thread builds its own MediaIoBaseUpload from a fresh BytesIO),
    # so concurrent upload_and_share calls don't trample each other.
    import concurrent.futures
    urls_by_iter = {}  # {1: url, 2: url}
    errs_by_iter = {}  # {1: error_str, 2: error_str}

    def _gen_one(it: int):
        t0 = time.time()
        try:
            img = generate_image(prompt, aspect, resolution)
            gen_dt = time.time() - t0
            fname = f"set-{int(set_num):02d}-iter-{it}.png"
            url = upload_and_share(drive, folder_id, fname, img)
            return (it, url, None, len(img), gen_dt)
        except Exception as e:
            return (it, None, f"iter {it}: {type(e).__name__}: {e}", 0, 0)

    print(f"  firing {ITERATIONS} iters in parallel…", flush=True)
    t_parallel = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=ITERATIONS) as ex:
        futures = [ex.submit(_gen_one, it) for it in range(1, ITERATIONS + 1)]
        for fut in concurrent.futures.as_completed(futures):
            it, url, err_msg, img_size, gen_dt = fut.result()
            if url:
                print(f"  iter {it}: ✓ {img_size//1024}KB in {gen_dt:.1f}s → uploaded", flush=True)
                urls_by_iter[it] = url
            else:
                print(f"  iter {it}: ✗ {err_msg}", flush=True)
                errs_by_iter[it] = err_msg
    print(f"  parallel batch done in {time.time() - t_parallel:.1f}s wall time", flush=True)
    err = next(iter(errs_by_iter.values()), None)  # first error for sheet col I

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

    # fal.ai uses a static API key (FAL_KEY env var). No CLI / OAuth /
    # session-expiry dance like Higgsfield required.
    if not os.environ.get("FAL_KEY", "").strip():
        sys.exit("FAL_KEY env var not set. Add it to .env (local) or "
                 "Render env vars. Get a key from https://fal.ai/dashboard/keys")

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_id = parse_sheet_id(args.sheet)
    from sheets_retry import with_429_retry
    sh = with_429_retry(lambda: gc.open_by_key(sheet_id))
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

#!/usr/bin/env python3
"""
Generate stick-figure storyboards via Higgsfield CLI (gpt_image_2) for every
Pending set in the Storyboard Prompts tab. Two iterations per set; uploads
to the matching Drive folder, sets sharing to anyone-with-link reader, writes
URLs back to the sheet.

Provider routing: storyboards use Higgsfield gpt_image_2 via higgs_gen.py.
The CLI binary lives at ~/.npm-global/bin/higgs; install with
`npm install -g @higgsfield/cli` if missing.

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
import higgs_gen


HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

MODEL_PROVIDER = "higgsfield"
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


def generate_image(prompt: str, aspect: str, resolution: str) -> bytes:
    """Higgsfield gpt_image_2 via shared CLI wrapper."""
    return higgs_gen.generate(
        prompt=prompt,
        model=MODEL,
        aspect_ratio=aspect,
        quality=DEFAULT_QUALITY,
        resolution=resolution,
    )


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
    # is a 30-60s Higgsfield gpt_image_2 call, so concurrent dispatch roughly
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


STYLE_PREAMBLES = {
    "stick": (
        "Shot with arri 35.\n"
        "No Music.\n"
        "Stick figure pencil storyboard with foreground, midground and background depth. "
        "Figures must be ROUGH STICK FIGURES with NO FACIAL FEATURES — no eyes, "
        "no mouth, no detailed hair, no skin tone, no clothing texture. Black "
        "ballpoint-pen / 2B pencil line on white paper aesthetic. Imprecise, "
        "loose, gestural. Hands are mittens, not detailed. The point of the "
        "drawing is BLOCKING + CAMERA + STAGING ONLY — never likeness, never "
        "performance, never lighting, never wardrobe. Anyone studying this "
        "frame should immediately know it is a coverage sketch, not a still.\n"
        "Create a 5 panel storyboard based on the following shots. Ensure each "
        "shot is labelled by number, with a label of the camera angle/movement "
        "centred at the bottom of the panel. The storyboard should be divided "
        "by black lines. And the panels should flow sequentially:"
    ),
    "pencil": (
        "Shot with arri 35.\n"
        "No Music.\n"
        "Pencil sketch storyboard with foreground, midground and background "
        "depth. Sketched in graphite pencil with light cross-hatching for "
        "shading. Loose, characterful linework — but features readable: faces, "
        "hands, props all rendered with quick gesture. Aesthetic = a director's "
        "personal storyboard pad. NOT photoreal. NOT colored.\n"
        "Create a 5 panel storyboard based on the following shots. Ensure each "
        "shot is labelled by number, with a label of the camera angle/movement "
        "centred at the bottom of the panel. The storyboard should be divided "
        "by black lines. And the panels should flow sequentially:"
    ),
    "photoreal": (
        "Shot with Arri Alexa 35, anamorphic 1.55x lenses, Kodak Vision3 250D "
        "color science. Documentary editorial photography aesthetic. Full "
        "photoreal frames with natural skin texture, subtle 35mm film grain, "
        "muted desaturated palette, cinéma vérité framing. Each panel reads as "
        "a finished still, not a sketch.\n"
        "Create a 5 panel storyboard based on the following shots. Ensure each "
        "shot is labelled by number, with a label of the camera angle/movement "
        "centred at the bottom of the panel. The storyboard should be divided "
        "by black lines. And the panels should flow sequentially:"
    ),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", help="Sheet ID or URL")
    ap.add_argument("--set", type=int, help="Generate only this set number")
    ap.add_argument("--force", action="store_true", help="Regenerate Done sets")
    ap.add_argument("--aspect", default=DEFAULT_ASPECT, help="Aspect ratio (default 21:9)")
    ap.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="Resolution (default 1K)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the Higgsfield request payload and exit before provider calls")
    ap.add_argument(
        "--style",
        choices=["stick", "pencil", "photoreal", "sheet"],
        default="stick",
        help=(
            "Aesthetic preamble to prepend before the per-set body. "
            "stick (default) = featureless stick figures, sajangnim aesthetic. "
            "pencil = director-pad sketch. "
            "photoreal = full photoreal stills. "
            "sheet = use whatever's in the SP tab globals (B1:B4) — legacy behavior."
        ),
    )
    ap.add_argument(
        "--concurrency", type=int, default=1,
        help=("Max parallel SETS (default 1 = sequential). Each set internally "
              "fires its 2 iters in parallel, so --concurrency 4 = up to 8 "
              "simultaneous Higgsfield calls. Use with account-level unlimited tier."),
    )
    args = ap.parse_args()

    if args.dry_run:
        dry_prompt = STYLE_PREAMBLES[args.style if args.style != "sheet" else "stick"]
        payload = {
            "provider": MODEL_PROVIDER,
            "model": MODEL,
            "aspect_ratio": args.aspect,
            "resolution": args.resolution,
            "quality": DEFAULT_QUALITY,
            "iterations": ITERATIONS,
            "prompt": dry_prompt,
        }
        print("DRY RUN: would submit Higgsfield storyboard request:")
        print(json.dumps(payload, indent=2))
        return

    if not args.sheet:
        ap.error("--sheet is required unless --dry-run is set")

    higgs_gen.assert_authed()

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

    # Style preamble — by default, FORCE stick-figure aesthetic regardless of
    # what the sheet's B1:B4 globals say. Sheet globals are only used when
    # --style sheet is passed (legacy behavior).
    if args.style == "sheet":
        globals_block = sb.get("B1:B4", value_render_option="FORMATTED_VALUE")
        storyboard_globals = "\n".join(
            row[0] for row in globals_block if row and row[0]
        )
        print(f"Style: sheet (using B1:B4 globals)")
    else:
        storyboard_globals = STYLE_PREAMBLES[args.style]
        print(f"Style: {args.style} (forced preamble; sheet globals ignored)")

    data = sb.get(
        f"A11:I{sb.row_count}",
        value_render_option="FORMATTED_VALUE",
    )
    data = [r for r in data if len(r) > 0 and r[0]]

    # Build the job queue
    jobs = []
    for i, row in enumerate(data):
        sheet_row = i + 11
        try:
            set_num_int = int(row[0])
        except (ValueError, IndexError):
            continue
        if args.set is not None and set_num_int != args.set:
            continue
        jobs.append((set_num_int, sheet_row, row))

    overall_start = time.time()
    results = []
    concurrency = max(1, int(args.concurrency))
    print(f"\nProcessing {len(jobs)} sets · concurrency={concurrency}\n", flush=True)

    if concurrency == 1:
        for set_num_int, sheet_row, row in jobs:
            r = process_row(
                sb, drive, sheet_row, row,
                aspect=args.aspect, resolution=args.resolution,
                storyboard_globals=storyboard_globals, force=args.force,
            )
            results.append((set_num_int, r))
    else:
        # Each thread gets its own Drive client (httplib2 isn't thread-safe);
        # gspread (sheets) ws calls share the existing client + are short.
        import threading
        _thread_local = threading.local()
        def _thread_drive():
            if not hasattr(_thread_local, "drive"):
                _thread_local.drive = build("drive", "v3", credentials=get_credentials())
            return _thread_local.drive
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def _run(set_num_int, sheet_row, row):
            return (set_num_int, process_row(
                sb, _thread_drive(), sheet_row, row,
                aspect=args.aspect, resolution=args.resolution,
                storyboard_globals=storyboard_globals, force=args.force,
            ))
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(_run, sn, sr, rr) for sn, sr, rr in jobs]
            for fut in as_completed(futures):
                results.append(fut.result())

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

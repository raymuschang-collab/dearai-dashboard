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


LOCREF_PATH = None  # optional local path to a location reference image (--locref)


def generate_image(prompt: str, aspect: str, resolution: str) -> bytes:
    """Higgsfield gpt_image_2 via shared CLI wrapper.

    When LOCREF_PATH is set (via --locref), the location reference image is
    threaded through as a media reference so the model honors the real
    location's architecture while drawing in the stick-figure pencil style.
    """
    return higgs_gen.generate(
        prompt=prompt,
        model=MODEL,
        aspect_ratio=aspect,
        quality=DEFAULT_QUALITY,
        resolution=resolution,
        image_ref_path=LOCREF_PATH,
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


# Master-shot mode (--style master): a SINGLE wide photoreal establishing /
# master frame per scene, rendered in the show's chosen global film look (the
# preset the producer picked at project creation, written to camera B1). This
# REPLACES stick-figure storyboards — the master shot is the real coverage frame
# the scene is built from. The show's B1 camera look is prepended at runtime.
MASTER_INSTRUCTION = (
    "Render ONE single, wide, cinematic ESTABLISHING / MASTER shot of the scene "
    "described below — a finished photoreal film frame, full-bleed, no borders. "
    "NOT a storyboard, NOT a panel grid, NO dividing lines, NO shot-number labels, "
    "NO camera-movement captions. A single master coverage frame that establishes "
    "the location, the staging/blocking of the characters, and the mood of the "
    "scene, in the film look described above. Cinematic composition with clear "
    "foreground / midground / background depth:"
)


# Location-conditioned mode (--locref): detailed pencil ENVIRONMENT that honors
# a real location reference image + featureless STICK-FIGURE people. Validated
# to hold the pencil look on gpt_image_2 without photoreal drift.
LOCREF_PREAMBLE = (
    "Shot with arri 35.\n"
    "No Music.\n"
    "REFERENCE IMAGE: the attached photo sheet shows the real location from multiple "
    "angles (exterior and interior) plus a top-down floor plan. Use it as the "
    "architectural / layout reference — match the storefront, counter, furniture, "
    "fixtures, window placement, materials and spatial depth. Do NOT copy its "
    "photographic rendering, color or lighting.\n"
    "Render the LOCATION and ENVIRONMENT in detailed graphite pencil with light "
    "cross-hatching — architecture, furniture, props and depth (foreground / midground "
    "/ background) all sketched with care. BUT every HUMAN FIGURE must be a ROUGH STICK "
    "FIGURE ONLY: a simple circle head with NO facial features (no eyes, no mouth, no "
    "hair), a simple line / gesture body, mitten hands. No likeness, no clothing detail, "
    "no skin tone. People are pure blocking / staging markers; the ENVIRONMENT is the "
    "detailed part. NOT photoreal. NOT colored.\n"
    "Create a 5 panel storyboard based on the following shots. Ensure each shot is "
    "labelled by number, with a label of the camera angle/movement centred at the bottom "
    "of the panel. The storyboard should be divided by black lines. And the panels should "
    "flow sequentially:"
)


def main():
    global ITERATIONS, MODEL, LOCREF_PATH
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
        choices=["stick", "pencil", "photoreal", "sheet", "master"],
        default="stick",
        help=(
            "Aesthetic preamble to prepend before the per-set body. "
            "stick (default) = featureless stick figures, sajangnim aesthetic. "
            "pencil = director-pad sketch. "
            "photoreal = full photoreal stills. "
            "sheet = use whatever's in the SP tab globals (B1:B4) — legacy behavior. "
            "master = ONE wide photoreal MASTER/establishing shot per scene in the "
            "show's chosen global film look (reads camera B1) — no panels, no grid. "
            "This is the storyboard-replacement: 1-2 master shots per scene."
        ),
    )
    ap.add_argument(
        "--concurrency", type=int, default=1,
        help=("Max parallel SETS (default 1 = sequential). Each set internally "
              "fires its iters in parallel, so --concurrency 4 with --iters 2 = up to 8 "
              "simultaneous Higgsfield calls. Use with account-level unlimited tier."),
    )
    ap.add_argument(
        "--iters", type=int, default=ITERATIONS, choices=[1, 2],
        help=("Storyboard iterations per set (default 2). Use --iters 1 for ONE "
              "board per set — faster, cheaper, simpler review. Writes iter 1 URL; "
              "iter 2 column left blank."),
    )
    ap.add_argument(
        "--model", default=MODEL,
        help=("Higgsfield model for the boards (default gpt_image_2). "
              "e.g. --model nano_banana_pro for the higher-quality Gemini-3-pro image model."),
    )
    ap.add_argument(
        "--locref", default=None,
        help=("Location reference image (local path or Drive/HTTP URL). When set, ALL "
              "sets use the location-conditioned pencil + stick-figure preamble and the "
              "image is threaded to the model as an architectural reference, so boards "
              "match the real location while people stay featureless stick figures. "
              "Best with --model gpt_image_2."),
    )
    ap.add_argument(
        "--auto-locref", action="store_true",
        help=("Automatically pick EACH set's location reference from the SP 'Location' "
              "column (the indicator shown below the globals) and thread it as that set's "
              "storyboard ref, using the location-conditioned pencil + stick-figure "
              "preamble. Per-set: each set gets its own matched location bible iter-1 image. "
              "No manual --locref needed."),
    )
    args = ap.parse_args()
    ITERATIONS = args.iters
    MODEL = args.model

    # Resolve --locref to a local file path (download Drive/HTTP refs to a temp file).
    if args.locref:
        ref = args.locref
        if ref.startswith("http"):
            import tempfile
            import requests as _rq
            m = re.search(r"/d/([A-Za-z0-9_-]+)", ref)
            ref_dl = (f"https://drive.google.com/uc?export=download&id={m.group(1)}"
                      if m else ref)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(_rq.get(ref_dl, timeout=180).content)
            tmp.close()
            LOCREF_PATH = tmp.name
        else:
            LOCREF_PATH = os.path.expanduser(ref)
        if not os.path.exists(LOCREF_PATH):
            sys.exit(f"--locref file not found: {LOCREF_PATH}")
        print(f"Locref: {LOCREF_PATH}")

    if args.dry_run:
        if args.style == "master":
            dry_prompt = "<show camera B1 global>\n" + MASTER_INSTRUCTION
        else:
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
    elif args.style == "master":
        # Master shot = the show's chosen global film look (camera B1) + a
        # single-frame establishing instruction. No stick-figure panel grid.
        b1 = sb.get("B1", value_render_option="FORMATTED_VALUE")
        camera_look = (b1[0][0] if b1 and b1[0] else "").strip() \
            or "Shot on ARRI Alexa, 35mm film look. Cinematic, photoreal."
        storyboard_globals = f"{camera_look}\n{MASTER_INSTRUCTION}"
        print(f"Style: master (single establishing shot in the show's global look)")
    else:
        storyboard_globals = STYLE_PREAMBLES[args.style]
        print(f"Style: {args.style} (forced preamble; sheet globals ignored)")

    # --locref overrides any --style: location-conditioned pencil + stick figures.
    if args.locref:
        storyboard_globals = LOCREF_PREAMBLE
        print("Style: locref (location-conditioned pencil + stick figures; ref threaded as --image)")

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

    # --auto-locref: resolve a PER-SET location reference from the SP "Location"
    # column (L). Each set's label is matched (in bible row order) against the
    # LOCATIONS bible names; the matched row's iter-1 image is downloaded once
    # and threaded as that set's --image. Uses the location-conditioned preamble.
    auto_ref_by_row = {}
    if args.auto_locref:
        storyboard_globals = LOCREF_PREAMBLE
        print("Style: auto-locref (per-set location ref from SP!L + pencil/stick preamble)")
        loc_ws = sb.spreadsheet.worksheet("LOCATIONS")
        loc_rows = loc_ws.get("A5:J60", value_render_option="FORMATTED_VALUE")
        bible = []  # (name, iter1_view_url) in bible row order
        for lr in loc_rows:
            nm = lr[0].strip() if len(lr) > 0 else ""
            iturl = lr[9].strip() if len(lr) > 9 else ""
            if nm and iturl and "montage" not in nm.lower() and "/d/" in iturl:
                bible.append((nm, iturl))
        last_row = jobs[-1][1] if jobs else 11
        lcol = sb.get(f"L11:L{last_row}", value_render_option="FORMATTED_VALUE")
        labels = {11 + i: (lv[0].strip() if lv and lv[0] else "") for i, lv in enumerate(lcol)}
        import tempfile
        import requests as _rq
        _dl_cache = {}
        def _dl_ref(view_url):
            if view_url in _dl_cache:
                return _dl_cache[view_url]
            m = re.search(r"/d/([A-Za-z0-9_-]+)", view_url)
            if not m:
                return None
            dl = f"https://drive.google.com/uc?export=download&id={m.group(1)}"
            t = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            t.write(_rq.get(dl, timeout=180).content)
            t.close()
            _dl_cache[view_url] = t.name
            return t.name
        for _, sheet_row, _ in jobs:
            lbl = labels.get(sheet_row, "").lower()
            chosen = next((u for nm, u in bible if nm.lower() in lbl), None)
            auto_ref_by_row[sheet_row] = _dl_ref(chosen) if chosen else (LOCREF_PATH if args.locref else None)
        print("Auto-locref map: " + ", ".join(
            f"set@{r}:{'✓' if auto_ref_by_row.get(r) else '—'}" for _, r, _ in jobs))
        if concurrency != 1:
            print("  (forcing concurrency=1 so per-set refs don't race)")
            concurrency = 1

    if concurrency == 1:
        for set_num_int, sheet_row, row in jobs:
            if args.auto_locref:
                LOCREF_PATH = auto_ref_by_row.get(sheet_row)
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

#!/usr/bin/env python3
"""blocking_generate.py — pencil BLOCKING MASTERS for a v2.2 microdrama LOCATIONS bible.

For each LOCATIONS row that has a "Blocking Prompt" (col Q) + an "Iter 1 URL"
(col J, the location reference image) but no "Blocking (pencil) URL" (col R),
this fires Higgsfield gpt_image_2 with:
  - the location reference image threaded as --image (architecture/layout anchor)
  - a SINGLE wide-master, detailed-pencil + featureless-stick-figure preamble
  - the row's Blocking Prompt (the synthesized actor blocking) as the body
…then uploads the resulting pencil master to Drive and writes its URL back to col R.

The "Blocking Prompt" (col Q) is synthesised upstream (by Claude, from the shots
that occur in that location) — this script only renders + writes back.

USAGE:
  python3 blocking_generate.py --sheet <id> [--location "<name substring>"] [--force]

Idempotent: rows that already have a Blocking URL are skipped unless --force.
"""
from __future__ import annotations
import argparse, io, os, re, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
env = HERE / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import gspread
from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import higgs_gen

LOCREF_FOLDER = "116pf9pQ19zGEoRmx7n6-Q_jAGWevhbuY"  # Good Light location-refs

BLOCKING_PREAMBLE = (
    "Shot with arri 35.\n"
    "No Music.\n"
    "PENCIL BLOCKING MASTER — a SINGLE wide establishing shot (WS master), drawn in "
    "detailed graphite pencil with light cross-hatching. Render the LOCATION and "
    "ENVIRONMENT in detail, honoring the attached reference image (architecture, "
    "furniture, fixtures, materials, spatial depth). Place the actors as ROUGH "
    "FEATURELESS STICK FIGURES — circle heads with NO facial features, simple line "
    "bodies, mitten hands — at their blocking positions. Add a small handwritten text "
    "label beside each figure with the character's name. This is a top-of-scene "
    "director's blocking diagram: ONE single wide frame (NOT a multi-panel grid), "
    "NOT photoreal, NOT colored. Blocking to render:\n"
)


def drive_id(url: str) -> str | None:
    m = re.search(r"/d/([A-Za-z0-9_-]+)", url or "") or re.search(r"[?&]id=([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else None


def download_ref(drive, file_id: str) -> str:
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, drive.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = dl.next_chunk()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(buf.getvalue()); tmp.close()
    return tmp.name


def upload_share(drive, name: str, content: bytes) -> str:
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="image/png", resumable=False)
    f = drive.files().create(body={"name": name, "parents": [LOCREF_FOLDER]},
                             media_body=media, fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"},
                               fields="id").execute()
    return f["webViewLink"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True, help="Sheet ID or URL")
    ap.add_argument("--location", default=None, help="Only this location (name substring, case-insensitive)")
    ap.add_argument("--force", action="store_true", help="Regenerate rows that already have a Blocking URL")
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--resolution", default="1k")
    args = ap.parse_args()

    sheet_id = re.search(r"/d/([A-Za-z0-9_-]+)", args.sheet)
    sheet_id = sheet_id.group(1) if sheet_id else args.sheet.strip()

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    loc = gc.open_by_key(sheet_id).worksheet("LOCATIONS")

    rows = loc.get("A5:R200", value_render_option="FORMULA")
    done = skipped = failed = 0
    for i, r in enumerate(rows, start=5):
        r = list(r) + [""] * 18
        name = r[0].strip()
        iter1 = r[9].strip()           # J
        blk_prompt = r[16].strip()     # Q
        blk_url = r[17].strip()        # R
        if not name or not blk_prompt:
            continue
        if args.location and args.location.lower() not in name.lower():
            continue
        if blk_url and not args.force:
            print(f"  SKIP {name} — already has blocking"); skipped += 1; continue
        fid = drive_id(iter1)
        if not fid:
            print(f"  ✗ {name} — no usable Iter 1 reference image"); failed += 1; continue
        print(f"  ◦ {name}: rendering blocking master…", flush=True)
        try:
            ref_path = download_ref(drive, fid)
            prompt = BLOCKING_PREAMBLE + blk_prompt
            t0 = time.time()
            png = higgs_gen.generate(prompt=prompt, model="gpt_image_2",
                                     aspect_ratio=args.aspect, resolution=args.resolution,
                                     image_ref_path=ref_path)
            url = upload_share(drive, f"BLOCKING - {name}.png", png)
            loc.update_acell(f"R{i}", url)
            print(f"    ✓ {name} → {url}  ({len(png)//1024}KB, {time.time()-t0:.1f}s)")
            done += 1
        except Exception as e:
            print(f"    ✗ {name}: {type(e).__name__}: {e}"); failed += 1

    print(f"\nTOTAL: {done} done, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()

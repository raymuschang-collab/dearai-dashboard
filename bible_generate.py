#!/usr/bin/env python3
"""
Generate costume / prop / effect reference images via fal.ai nano-banana-2.

Reads from one of the 3 bible tabs (COSTUME, PROPS, EFFECTS), generates 1 image
per row using the rendered prompt from column F, uploads to a per-asset-type
Drive folder, writes URL back to column G (Iter 1 URL).

Schema (identical for all 3 tabs):
  Row 1-3: globals (Type of reference, Style, Layout)
  Row 5: headers
  Row 6+: data
  Columns: A=Name, B=Worn By/Used By, C=Description, D=First Shot, E=Notes,
           F=Prompt (formula), G=Iter 1 URL, H=Iter 2 URL, I=Status, J=Error

Drive folder per asset type:
  COSTUME → costume-refs/
  PROPS   → prop-refs/
  EFFECTS → effect-refs/

1 iteration per row by default (cheaper, faster). Use --iters 2 to add iter 2.

Usage:
    python3 bible_generate.py --sheet <id> --tab COSTUME
    python3 bible_generate.py --sheet <id> --tab PROPS --row 7
    python3 bible_generate.py --sheet <id> --tab EFFECTS --force
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time

import gspread
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from auth import get_credentials
import higgs_gen


HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

MODEL = "nano_banana_2"  # Higgsfield CLI
DEFAULT_ASPECT = "1:1"
DEFAULT_RESOLUTION = "1k"
DEFAULT_QUALITY = "high"

SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")

FOLDER_MAP = {
    "COSTUME": "costume-refs",
    "PROPS": "prop-refs",
    "EFFECTS": "effect-refs",
}

# Column letters in the bible tab schema (data rows start at sheet row 6)
COL_NAME = "A"
COL_PROMPT = "F"
COL_ITER1 = "G"
COL_ITER2 = "H"
COL_STATUS = "I"
COL_ERROR = "J"


def parse_sheet_id(s: str) -> str:
    m = SHEETS_URL_RE.search(s)
    return m.group(1) if m else s.strip()


def slugify(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", s)[:60].strip("_")


def get_or_create_folder(drive, parent_id: str, name: str) -> str:
    safe = name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and trashed=false "
        f"and mimeType='application/vnd.google-apps.folder' and name='{safe}'"
    )
    res = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()
    if res.get("files"):
        return res["files"][0]["id"]
    return drive.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()["id"]


def generate_image(prompt: str, aspect: str, resolution: str) -> bytes:
    """Higgsfield nano_banana_2 via CLI for costume / prop / effect refs."""
    return higgs_gen.generate(
        prompt=prompt, model=MODEL,
        aspect_ratio=aspect, quality=DEFAULT_QUALITY,
        resolution=resolution,
    )


def upload_and_share(drive, folder_id: str, filename: str, content: bytes) -> str:
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="image/png", resumable=False)
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
    ws, drive, sheet_row: int, name: str, prompt: str, status: str,
    folder_id: str, aspect: str, resolution: str, *,
    iters: int = 1, force: bool = False,
) -> dict:
    if not name:
        return {"status": "skip", "reason": "empty name"}
    if not prompt:
        return {"status": "skip", "reason": "empty prompt"}
    if status == "Done" and not force:
        print(f"\n=== {name} (row {sheet_row}) — SKIP (already Done) ===")
        return {"status": "skip", "reason": "already Done"}

    print(f"\n=== {name} (row {sheet_row}) ===")
    print(f"  prompt: {len(prompt)} chars")
    ws.update(range_name=f"{COL_STATUS}{sheet_row}", values=[["Generating"]])

    iter_urls = [None, None]
    err = None
    for it in range(1, iters + 1):
        t0 = time.time()
        print(f"  iter {it}: generating...", end="", flush=True)
        try:
            img = generate_image(prompt, aspect, resolution)
            print(f" {len(img)//1024}KB in {time.time()-t0:.1f}s", end="", flush=True)

            slug = slugify(name)
            fname = f"{slug}.png" if iters == 1 else f"{slug}-iter-{it}.png"
            url = upload_and_share(drive, folder_id, fname, img)
            print(f" → uploaded")
            print(f"    {url}")
            iter_urls[it - 1] = url
        except Exception as e:
            err = f"iter {it}: {type(e).__name__}: {e}"
            print(f"\n  FAILED: {err}")
            # Don't break — keep trying the next iter.
            continue

    iter1, iter2 = iter_urls[0] or "", iter_urls[1] or ""
    expected = sum(1 for u in iter_urls[:iters] if u)
    if expected == iters:
        sheet_status, err_msg = "Done", ""
    elif expected > 0:
        sheet_status, err_msg = "Done", err or ""  # partial success
    else:
        sheet_status, err_msg = "Failed", err or "unknown"
    ws.update(
        range_name=f"{COL_ITER1}{sheet_row}:{COL_ERROR}{sheet_row}",
        values=[[iter1, iter2, sheet_status, err_msg]],
        value_input_option="USER_ENTERED",
    )
    print(f"  → row {sheet_row}: {sheet_status} (iter1={'✓' if iter1 else '✗'}, iter2={'✓' if iter2 else '✗'})")
    return {"status": "done" if sheet_status == "Done" else "fail",
            "urls": iter_urls, "error": err}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--tab", required=True, choices=list(FOLDER_MAP.keys()))
    ap.add_argument("--row", type=int, help="Process only this sheet row")
    ap.add_argument("--name", help="Filter to only the row whose col A matches this name (case-insensitive)")
    ap.add_argument("--iters", type=int, default=1, choices=[1, 2], help="Iterations per row (default 1)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--aspect", default=DEFAULT_ASPECT,
                    choices=["auto", "21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16"])
    ap.add_argument("--resolution", default=DEFAULT_RESOLUTION,
                    choices=["1K", "2K", "4K", "512x512"])
    args = ap.parse_args()

    higgs_gen.assert_authed()

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_id = parse_sheet_id(args.sheet)
    sh = gc.open_by_key(sheet_id)
    print(f"Sheet: {sh.title}  Tab: {args.tab}")
    print(f"Aspect: {args.aspect}  Resolution: {args.resolution}  Iterations: {args.iters}")

    ws = sh.worksheet(args.tab)

    meta = drive.files().get(fileId=sheet_id, fields="parents").execute()
    parent_id = meta["parents"][0]
    folder_name = FOLDER_MAP[args.tab]
    folder_id = get_or_create_folder(drive, parent_id, folder_name)
    print(f"{folder_name}/ id={folder_id}")

    data = ws.get(f"A6:J{ws.row_count}", value_render_option="FORMATTED_VALUE")

    overall_start = time.time()
    results = []
    for i, row in enumerate(data):
        sheet_row = 6 + i
        if not row or len(row) < 1 or not row[0]:
            continue
        if args.row and sheet_row != args.row:
            continue
        name = row[0] if len(row) > 0 else ""
        if args.name and (name or "").strip().lower() != args.name.strip().lower():
            continue
        prompt = row[5] if len(row) > 5 else ""
        status = row[8] if len(row) > 8 else ""
        result = process_row(
            ws, drive, sheet_row, name, prompt, status,
            folder_id, args.aspect, args.resolution,
            iters=args.iters, force=args.force,
        )
        results.append((name, result))

    total_dt = time.time() - overall_start
    print(f"\n\n=== SUMMARY for {args.tab} ({total_dt:.1f}s) ===")
    counts = {"done": 0, "skip": 0, "fail": 0}
    for name, r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        line = f"  {name}: {r['status']}"
        if r.get("reason"):
            line += f" ({r['reason']})"
        print(line)
    print(f"\n  TOTAL: {counts.get('done', 0)} done, {counts.get('skip', 0)} skipped, {counts.get('fail', 0)} failed")


if __name__ == "__main__":
    main()

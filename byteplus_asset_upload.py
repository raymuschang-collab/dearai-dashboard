#!/usr/bin/env python3
"""
byteplus_asset_upload.py — Upload bibles → BytePlus Private Avatar Library.

Per user directive: ONE asset per bible entry. The composite ref sheet (or video)
IS the reference. No cropping into individual head/expression panels.

Workflow:
  1. Read 'Asset Library' tab from sheet
  2. For each row with Status='Pending' AND Source URL populated:
       a. Download source from Drive
       b. Upload to BytePlus Private Avatar Library
       c. Get back asset_id (avatar_id)
       d. Write asset_id back to col C, Status='Uploaded', timestamp col G
  3. Report

Usage:
  python3 byteplus_asset_upload.py --sheet <SHEET_ID> [--row N] [--media-file path] [--media-type image|video] [--bible-name "MIN-JUN"]

Modes:
  --row N                       Upload only the entry at Asset Library row N
  --media-file + --bible-name   Upload a one-off file (ad-hoc smoke test) without sheet
  (default)                     Walk all Pending rows
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import gspread
import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

# Resolve auth.py
def _resolve_auth():
    candidates = [
        os.path.join(os.getcwd(), "auth.py"),
        os.path.join(str(HERE), "auth.py"),
        os.path.expanduser("~/Desktop/Shotlist Workflows/auth.py"),
    ]
    for c in candidates:
        if os.path.exists(c):
            sys.path.insert(0, os.path.dirname(c))
            from auth import get_credentials  # type: ignore
            return get_credentials
    raise SystemExit("Could not find auth.py")

get_credentials = _resolve_auth()

ARK_API_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
BP_AK = os.getenv("BYTEPLUS_ACCESS_KEY")
BP_SK = os.getenv("BYTEPLUS_SECRET_KEY")

# Best-known endpoints (will iterate during smoke test)
ARK_BASE = os.getenv("BYTEPLUS_ARK_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3")
# CN region fallback if Singapore doesn't accept the keys:
ARK_BASE_CN = "https://ark.cn-beijing.volces.com/api/v3"

# TODO: Set these when the dashboard and Source-of-Truth Asset Library tabs
# live in different spreadsheets. The upload script always writes the primary
# --sheet, then mirrors to any configured IDs below.
DASHBOARD_ASSET_LIBRARY_SHEET_ID = os.getenv("DASHBOARD_ASSET_LIBRARY_SHEET_ID", "").strip()
SOT_ASSET_LIBRARY_SHEET_ID = os.getenv("SOT_ASSET_LIBRARY_SHEET_ID", "").strip()
ASSET_LIBRARY_SYNC_SHEETS = [
    s.strip() for s in os.getenv("ASSET_LIBRARY_SYNC_SHEET_IDS", "").split(",")
    if s.strip()
]


def drive_id(url: str) -> str | None:
    if not url: return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m: return m.group(1)
    m = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if m: return m.group(1)
    return None


def download_drive_to_tmp(file_id: str) -> Path:
    """Download Drive file_id to /tmp/. Returns local path."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    drive = build("drive", "v3", credentials=get_credentials())
    meta = drive.files().get(fileId=file_id, fields="name,mimeType").execute()
    name = meta["name"]
    tmp = Path(f"/tmp/byteplus_upload_{file_id}_{name}")
    req = drive.files().get_media(fileId=file_id)
    with open(tmp, "wb") as f:
        from googleapiclient.http import MediaIoBaseDownload
        dl = MediaIoBaseDownload(f, req)
        done = False
        while not done: _, done = dl.next_chunk()
    return tmp


def upload_to_byteplus_avatar_library(file_path: Path, bible_name: str, media_type: str = "image"):
    """
    Upload an asset to BytePlus Private Avatar Library.
    Returns dict {asset_id, status, raw_response} on success, or None + error.

    NOTE: BytePlus asset library API specifics are not publicly documented.
    This function tries the most likely endpoint pattern and reports what
    happened. Smoke test will reveal exact endpoint to lock.
    """
    if not ARK_API_KEY:
        return None, "BYTEPLUS_ARK_API_KEY not set in .env"

    # Try Bearer auth with the ARK key first (most common pattern)
    candidates = [
        # Singapore region — Avatar API
        f"{ARK_BASE}/contents/avatar_library/avatars",
        f"{ARK_BASE}/avatar_library/create",
        f"{ARK_BASE}/private_avatar/create",
        # CN fallback
        f"{ARK_BASE_CN}/contents/avatar_library/avatars",
    ]

    last_err = None
    for endpoint in candidates:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                data = {
                    "name": bible_name,
                    "type": media_type,  # 'image' or 'video'
                    "description": f"Bible reference for {bible_name}",
                }
                headers = {"Authorization": f"Bearer {ARK_API_KEY}"}
                r = requests.post(endpoint, headers=headers, files=files, data=data, timeout=120)
            if r.status_code == 200:
                resp = r.json()
                asset_id = (resp.get("asset_id") or resp.get("avatar_id")
                            or resp.get("data", {}).get("id") or resp.get("id"))
                if asset_id:
                    return {"asset_id": asset_id, "endpoint": endpoint, "raw": resp}, None
            else:
                last_err = f"  {endpoint} → {r.status_code}: {r.text[:200]}"
                print(last_err)
        except Exception as e:
            last_err = f"  {endpoint} → exception: {e}"
            print(last_err)
            continue

    return None, last_err or "All endpoint candidates failed. Smoke test must lock the correct one."


def _asset_library_updates(row: int, asset_id: str):
    """Write asset_id, status, timestamp to Asset Library row."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        {"range": f"C{row}", "values": [[asset_id]]},      # Asset Code
        {"range": f"F{row}", "values": [["Uploaded"]]},    # Status
        {"range": f"G{row}", "values": [[now]]},           # Uploaded At
    ]


def update_asset_library_row(ws, row: int, asset_id: str):
    """Write asset_id, status, timestamp to Asset Library row."""
    updates = _asset_library_updates(row, asset_id)
    ws.spreadsheet.values_batch_update(body={
        "valueInputOption": "USER_ENTERED",
        "data": [{"range": f"'{ws.title}'!{u['range']}", "values": u["values"]} for u in updates],
    })


def find_asset_library_row(ws, name: str, bible_tab: str, source_url: str, fallback_row: int) -> int | None:
    rows = ws.get("A5:L500", value_render_option="FORMATTED_VALUE")
    for i, r in enumerate(rows, start=5):
        r = (r + [""] * 12)[:12]
        if not r[0].strip():
            continue
        same_name = r[0].strip() == name
        same_bible = not bible_tab or r[1].strip() == bible_tab
        same_source = not source_url or r[3].strip() == source_url
        if same_name and (same_bible or same_source):
            return i
    if 5 <= fallback_row < 500:
        try:
            row = (ws.row_values(fallback_row) + [""] * 12)[:12]
            if row[0].strip() == name:
                return fallback_row
        except Exception:
            pass
    return None


def mirror_asset_library_writes(gc, primary_sheet_id: str, name: str, bible_tab: str,
                                source_url: str, row: int, asset_id: str):
    sheet_ids = [primary_sheet_id]
    sheet_ids.extend([DASHBOARD_ASSET_LIBRARY_SHEET_ID, SOT_ASSET_LIBRARY_SHEET_ID])
    sheet_ids.extend(ASSET_LIBRARY_SYNC_SHEETS)
    seen = set()
    for sheet_id in sheet_ids:
        sheet_id = parse_sheet_id(sheet_id)
        if not sheet_id or sheet_id in seen:
            continue
        seen.add(sheet_id)
        try:
            sh = gc.open_by_key(sheet_id)
            ws = sh.worksheet("Asset Library")
            target_row = row if sheet_id == primary_sheet_id else find_asset_library_row(
                ws, name, bible_tab, source_url, row
            )
            if not target_row:
                print(f"  ⚠ Asset Library mirror skipped {sheet_id[:8]}…: no row for {name}")
                continue
            update_asset_library_row(ws, target_row, asset_id)
            if sheet_id != primary_sheet_id:
                print(f"  ✓ mirrored Asset Library → {sheet_id[:8]}… row {target_row}")
        except Exception as e:
            print(f"  ⚠ Asset Library mirror failed {sheet_id[:8]}…: {e}")


def parse_sheet_id(s: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", s)
    return m.group(1) if m else s.strip()


def main():
    ap = argparse.ArgumentParser(description="Upload bibles → BytePlus Private Avatar Library")
    ap.add_argument("--sheet", help="Sheet ID with Asset Library tab")
    ap.add_argument("--row", type=int, help="Upload only this Asset Library row")
    ap.add_argument("--media-file", help="One-off: local file path to upload (skip sheet)")
    ap.add_argument("--media-type", default="image", choices=["image", "video"])
    ap.add_argument("--bible-name", help="Required if --media-file: name to register asset under")
    args = ap.parse_args()

    # Mode 1: ad-hoc upload of a local file (smoke test)
    if args.media_file:
        if not args.bible_name:
            sys.exit("--bible-name required when using --media-file")
        path = Path(args.media_file)
        if not path.exists():
            sys.exit(f"File not found: {path}")
        print(f"Uploading {path.name} ({path.stat().st_size//1024}KB) as '{args.bible_name}' (type={args.media_type})")
        result, err = upload_to_byteplus_avatar_library(path, args.bible_name, args.media_type)
        if err:
            print(f"\n✗ FAILED: {err}")
            sys.exit(1)
        print(f"\n✓ Uploaded. asset_id={result['asset_id']}")
        print(f"  endpoint: {result['endpoint']}")
        print(f"  raw response: {json.dumps(result['raw'], indent=2)[:500]}")
        return

    # Mode 2: walk Asset Library tab
    if not args.sheet:
        sys.exit("Provide --sheet <ID> OR --media-file + --bible-name for ad-hoc test")
    sheet_id = parse_sheet_id(args.sheet)
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet("Asset Library")
    rows = ws.get("A5:L500", value_render_option="FORMATTED_VALUE")

    targets = []
    for i, r in enumerate(rows, start=5):
        if not r or not r[0].strip(): continue
        if args.row and i != args.row: continue
        name = r[0].strip()
        bible_tab = r[1].strip() if len(r) > 1 else ""
        asset_code = r[2].strip() if len(r) > 2 else ""
        source_url = r[3].strip() if len(r) > 3 else ""
        status = r[5].strip() if len(r) > 5 else ""
        if asset_code or status == "Uploaded":
            print(f"  → row {i} ({name}): already uploaded, skipping")
            continue
        if not source_url:
            print(f"  → row {i} ({name}): no Source URL, skipping (manually populate col D first)")
            continue
        targets.append((i, name, bible_tab, source_url))

    if not targets:
        print("No pending uploads found.")
        return

    print(f"\n=== Uploading {len(targets)} assets ===\n")
    for row_num, name, tab, url in targets:
        print(f"[row {row_num}] {name} ({tab})")
        fid = drive_id(url)
        if not fid:
            print(f"  ✗ bad source URL: {url}")
            continue
        local = download_drive_to_tmp(fid)
        media_type = "video" if local.suffix.lower() in (".mp4", ".mov", ".webm") else "image"
        result, err = upload_to_byteplus_avatar_library(local, name, media_type)
        if err:
            print(f"  ✗ {err}")
            continue
        mirror_asset_library_writes(gc, sheet_id, name, tab, url, row_num, result["asset_id"])
        print(f"  ✓ asset_id={result['asset_id']}")
        time.sleep(0.5)  # gentle on the API

    print(f"\n✓ Done.")


if __name__ == "__main__":
    main()

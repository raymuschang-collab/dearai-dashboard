"""Upload Pending CHARACTERS + LOCATIONS assets to BytePlus Asset Library
using the WORKING Volcengine API (byteplus_asset_v2.call), not the stale
REST avatar_library probes that returned 404 earlier.

Per user spec: only chars + locations get asset codes. Costumes/props/effects
stay as plain Drive URLs in vidgen ref slots.

Step 1: ensure a 'sajangnim-bibles' group exists; cache group_id in .env
Step 2: for each Pending row in Asset Library where Bible Tab in {CHARACTERS,LOCATIONS}
        and Source URL populated:
        - convert Drive URL → lh3.googleusercontent.com/d/<id> (BytePlus
          can fetch this directly; standard image binary)
        - call CreateAsset(group_id, url, "Image", Name=row's Bible Entry Name)
        - poll until Active
        - write asset_id back to col C, Status=Uploaded, timestamp col G
        - mirror to DASHBOARD_ASSET_LIBRARY_SHEET_ID + SOT_ASSET_LIBRARY_SHEET_ID
          (no-op when those equal the primary sheet)
"""
from __future__ import annotations
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import gspread
from dotenv import load_dotenv

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
load_dotenv(HERE / ".env")

from auth import get_credentials
import byteplus_asset_v2 as bp

PRIMARY_SHEET = "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"

DASHBOARD_AL = os.getenv("DASHBOARD_ASSET_LIBRARY_SHEET_ID", "").strip()
SOT_AL = os.getenv("SOT_ASSET_LIBRARY_SHEET_ID", "").strip()
EXTRA = [s.strip() for s in os.getenv("ASSET_LIBRARY_SYNC_SHEET_IDS", "").split(",") if s.strip()]

GROUP_ID_ENV = os.getenv("BYTEPLUS_GROUP_ID", "").strip()


def drive_id(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def lh3_url(file_id: str) -> str:
    """Direct binary URL for a Drive-public image — BytePlus can fetch this."""
    return f"https://lh3.googleusercontent.com/d/{file_id}"


def ensure_group_id() -> str:
    """Reuse BYTEPLUS_GROUP_ID env if set; otherwise create a fresh group
    named 'sajangnim-bibles' and append it to .env."""
    if GROUP_ID_ENV:
        print(f"Using cached group_id from .env: {GROUP_ID_ENV}", flush=True)
        return GROUP_ID_ENV
    print("Creating fresh asset group 'sajangnim-bibles'...", flush=True)
    gid = bp.create_asset_group("sajangnim-bibles",
                                  "Diam Diam Aku Cinta Sajangnim — characters + locations")
    print(f"  → group_id = {gid}", flush=True)
    # persist
    env_path = HERE / ".env"
    text = env_path.read_text() if env_path.exists() else ""
    if not text.endswith("\n") and text:
        text += "\n"
    text += f"BYTEPLUS_GROUP_ID={gid}\n"
    env_path.write_text(text)
    return gid


def main():
    print("Cool 30s for sheets quota...", flush=True)
    time.sleep(30)
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(PRIMARY_SHEET)
    al = sh.worksheet("Asset Library")

    print("Reading Asset Library...", flush=True)
    rows = al.get("A4:G60", value_render_option="FORMATTED_VALUE")
    if not rows:
        sys.exit("No data on Asset Library")

    header = rows[0]
    name_i = header.index("Bible Entry Name")
    tab_i = header.index("Bible Tab")
    code_i = header.index("Asset Code")
    url_i = header.index("Source URL")
    type_i = header.index("Asset Type") if "Asset Type" in header else 4
    status_i = header.index("Status") if "Status" in header else 5

    print(f"Header: {header}", flush=True)
    pending = []
    for ridx, row in enumerate(rows[1:], start=5):
        row = (row + [""] * 7)[:7]
        name = row[name_i]
        bible_tab = row[tab_i]
        code = row[code_i]
        src = row[url_i]
        status = row[status_i]
        if bible_tab not in ("CHARACTERS", "LOCATIONS"):
            continue
        if not src:
            continue
        if code:
            print(f"  • row {ridx} {name}: already has code ({code}), skipping", flush=True)
            continue
        if status not in ("Pending", "", "Failed"):
            continue
        pending.append((ridx, name, bible_tab, src))

    if not pending:
        print("No pending CHARACTERS or LOCATIONS rows to upload.", flush=True)
        return
    print(f"\n{len(pending)} pending → uploading...", flush=True)

    group_id = ensure_group_id()
    print()

    successes = []
    failures = []
    for ridx, name, bible_tab, src in pending:
        fid = drive_id(src)
        if not fid:
            print(f"  ✗ row {ridx} {name}: bad Drive URL '{src[:60]}'", flush=True)
            failures.append((ridx, name, "bad-drive-url"))
            continue
        url = lh3_url(fid)
        print(f"\n[row {ridx}] {name} ({bible_tab})", flush=True)
        print(f"  url = {url}", flush=True)
        try:
            aid = bp.create_asset(group_id, url, "Image", name=name)
            print(f"  → asset_id = {aid}, polling for Active...", flush=True)
            result = bp.poll_asset(aid, timeout=300)
            ts = datetime.now(timezone.utc).strftime("%m/%d/%Y %H:%M:%S")
            print(f"  ✓ {aid} Active", flush=True)
            successes.append((ridx, name, aid, ts))
        except SystemExit as e:
            print(f"  ✗ create/poll failed: {e}", flush=True)
            failures.append((ridx, name, str(e)[:100]))
        except Exception as e:
            print(f"  ✗ unexpected: {type(e).__name__}: {e}", flush=True)
            failures.append((ridx, name, f"{type(e).__name__}: {e}")[:100])

    # Write back successes (single batchUpdate per sheet)
    print("\nWriting asset codes back to Asset Library...", flush=True)
    target_sheets = [PRIMARY_SHEET]
    for s in [DASHBOARD_AL, SOT_AL] + EXTRA:
        if s and s not in target_sheets:
            target_sheets.append(s)
    for tsid in target_sheets:
        if not successes:
            break
        try:
            tsh = gc.open_by_key(tsid)
            tal = tsh.worksheet("Asset Library")
            updates = []
            for ridx, name, aid, ts in successes:
                updates.append({"range": f"'Asset Library'!C{ridx}", "values": [[aid]]})
                updates.append({"range": f"'Asset Library'!F{ridx}", "values": [["Uploaded"]]})
                updates.append({"range": f"'Asset Library'!G{ridx}", "values": [[ts]]})
            tsh.values_batch_update(body={
                "valueInputOption": "RAW",
                "data": updates,
            })
            print(f"  ✓ wrote {len(successes)} codes to {tsid[:8]}…", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"  ✗ writeback to {tsid[:8]}… failed: {e}", flush=True)

    # Summary
    print("\n=== SUMMARY ===")
    print(f"  successes: {len(successes)}")
    for ridx, name, aid, _ in successes:
        print(f"    row {ridx} {name}  → {aid}")
    if failures:
        print(f"  failures: {len(failures)}")
        for ridx, name, err in failures:
            print(f"    row {ridx} {name}: {err}")


if __name__ == "__main__":
    main()

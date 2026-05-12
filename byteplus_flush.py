#!/usr/bin/env python3
"""Delete BytePlus assets listed in Asset Library.

Default mode is a dry-run over Status=Replaced rows. Passing --confirm is
required to call DeleteAsset and mark rows Deleted.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import gspread
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))
from auth import get_credentials  # type: ignore


def parse_sheet_id(value: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", value or "")
    return m.group(1) if m else (value or "").strip()


def normalize_code(code: str) -> str:
    return (code or "").strip().replace("asset://", "")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--scope", default="replaced", choices=["replaced", "all"])
    ap.add_argument("--confirm", action="store_true", help="Actually delete; otherwise dry-run")
    args = ap.parse_args()

    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(parse_sheet_id(args.sheet))
    al = sh.worksheet("Asset Library")
    rows = al.get("A5:L500", value_render_option="FORMATTED_VALUE")
    targets = []
    for idx, r in enumerate(rows, start=5):
        r = (r + [""] * 12)[:12]
        if not r[0].strip():
            continue
        status = r[5].strip()
        code = normalize_code(r[2])
        if not code:
            continue
        if args.scope == "replaced" and status != "Replaced":
            continue
        if args.scope == "all" and status == "Deleted":
            continue
        targets.append({"row": idx, "name": r[0], "tab": r[1], "code": code, "status": status})

    mode = "DELETE" if args.confirm else "DRY RUN"
    print(f"{mode}: {len(targets)} Asset Library rows matched scope={args.scope}")
    for t in targets:
        print(f"  row {t['row']}: {t['name']} [{t['status']}] {t['code']}")
    if not args.confirm:
        print("No assets deleted. Re-run with --confirm to execute.")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    deleted = 0
    import byteplus_asset_v2 as bp  # type: ignore

    for t in targets:
        resp = bp.call("DeleteAsset", {"Id": t["code"]})
        err = resp.get("ResponseMetadata", {}).get("Error")
        if err:
            print(f"  ✗ row {t['row']} {t['code']}: {err.get('Code')}")
            continue
        al.update(range_name=f"F{t['row']}:G{t['row']}", values=[["Deleted", now]], value_input_option="USER_ENTERED")
        deleted += 1
        print(f"  ✓ row {t['row']} deleted")
    print(f"Deleted {deleted}/{len(targets)} assets")


if __name__ == "__main__":
    main()

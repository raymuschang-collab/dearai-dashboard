#!/usr/bin/env python3
"""
asset_library_build.py — Idempotent builder for the "Asset Library" tab on
any v2.2-schema microdrama Sheet.

The Asset Library is the central registry mapping bible entry names →
BytePlus Private Avatar Library asset codes. vidgen reads col C (Asset Code)
to resolve "TARA" → asset_id when generating shots.

Usage:
    python3 asset_library_build.py --sheet <SHEET_ID_OR_URL>
    python3 asset_library_build.py --sheet <ID> --rebuild   # nuke + recreate
    python3 asset_library_build.py --sheet <ID> --seed-from-bibles  # auto-populate empty rows from CHARACTERS/LOCATIONS/etc.

Idempotent: re-runs preserve existing rows, only update headers if schema changed.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import gspread
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

# Resolve auth.py from likely locations
def _resolve_auth():
    candidates = [
        os.path.join(os.getcwd(), "auth.py"),
        os.path.join(str(HERE), "auth.py"),
        os.path.expanduser("~/Documents/Shotlist Workflows/auth.py"),
    ]
    for c in candidates:
        if os.path.exists(c):
            sys.path.insert(0, os.path.dirname(c))
            from auth import get_credentials  # type: ignore
            return get_credentials
    raise SystemExit("Could not find auth.py")

get_credentials = _resolve_auth()


TAB_NAME = "Asset Library"

# Header rows (rows 1-4). Data starts row 5.
META_ROWS = [
    ["ASSET LIBRARY — BytePlus Private Avatar Library Tracker"],
    ["Last sync", "=NOW()"],
    ["Source of truth", "vidgen reads col C (Asset Code) for each detected bible entry. Upload script writes A-G. Producer edits J/K freely."],
    [
        "Bible Entry Name",  # A
        "Bible Tab",          # B
        "Asset Code",         # C — foreign key
        "Source URL",         # D
        "Asset Type",         # E
        "Status",             # F
        "Uploaded At",        # G
        "First Used Shot",    # H
        "Used In Eps",        # I
        "Tags",               # J
        "Notes",              # K
        "Last Used",          # L
    ],
]

# Bible tab → (data start row, name col index, iter1 url col index, asset_type)
BIBLE_SOURCES = {
    "CHARACTERS": {"data_start": 2, "name_col": 0, "iter1_url_col": 19, "asset_type": "avatar"},  # T col = idx 19
    "LOCATIONS":  {"data_start": 5, "name_col": 0, "iter1_url_col": 9,  "asset_type": "scene"},   # J col = idx 9
    "PROPS":      {"data_start": 6, "name_col": 0, "iter1_url_col": 6,  "asset_type": "prop"},    # G col = idx 6
    "COSTUME":    {"data_start": 6, "name_col": 0, "iter1_url_col": 6,  "asset_type": "costume"},
    "EFFECTS":    {"data_start": 6, "name_col": 0, "iter1_url_col": 6,  "asset_type": "effect"},
}


def parse_sheet_id(s: str) -> str:
    """Accept full URL or bare ID."""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", s)
    return m.group(1) if m else s.strip()


def build_asset_library_tab(sh, rebuild: bool = False):
    """Create or refresh the Asset Library tab."""
    existing = {w.title: w for w in sh.worksheets()}
    if TAB_NAME in existing:
        if rebuild:
            sh.del_worksheet(existing[TAB_NAME])
            print(f"  → removed existing '{TAB_NAME}' tab (rebuild flag)")
            existing.pop(TAB_NAME)

    if TAB_NAME not in existing:
        ws = sh.add_worksheet(title=TAB_NAME, rows=200, cols=14)
        # Write header rows
        for i, row in enumerate(META_ROWS, start=1):
            range_a = f"A{i}"
            ws.update(values=[row], range_name=range_a, value_input_option="USER_ENTERED")
        # Format header (row 4)
        ws.format("A4:L4", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 1.0},
        })
        # Title formatting
        ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})
        ws.format("A2:A3", {"textFormat": {"bold": True}})
        # Sticky header row
        sh.batch_update({
            "requests": [{
                "updateSheetProperties": {
                    "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 4}},
                    "fields": "gridProperties.frozenRowCount",
                }
            }]
        })
        print(f"  ✓ created '{TAB_NAME}' tab — schema applied, header row frozen")
        return ws, []
    else:
        ws = existing[TAB_NAME]
        # Idempotent: just refresh meta rows if header changed
        current_header = ws.row_values(4)
        expected_header = META_ROWS[3]
        if current_header != expected_header:
            ws.update(values=[expected_header], range_name="A4", value_input_option="USER_ENTERED")
            print(f"  ✓ refreshed header row (schema drift)")
        else:
            print(f"  → '{TAB_NAME}' tab already exists with correct schema, leaving rows intact")
        # Existing rows
        existing_rows = ws.get("A5:L500", value_render_option="FORMATTED_VALUE")
        existing_names = set()
        for r in existing_rows:
            if r and r[0].strip():
                existing_names.add(r[0].strip())
        return ws, sorted(existing_names)


def seed_from_bibles(sh, ws, existing_names: list[str]):
    """Walk CHARACTERS / LOCATIONS / PROPS / COSTUME / EFFECTS bible tabs and add
    a row to Asset Library for each entry that's not already present.
    Status = 'Pending' (no upload yet)."""
    all_tabs = {w.title for w in sh.worksheets()}
    new_rows = []
    for tab, cfg in BIBLE_SOURCES.items():
        if tab not in all_tabs:
            continue
        bible_ws = sh.worksheet(tab)
        rows = bible_ws.get_all_values()
        for r in rows[cfg["data_start"] - 1:]:
            if not r or len(r) <= cfg["name_col"]:
                continue
            name = r[cfg["name_col"]].strip()
            if not name:
                continue
            if name in existing_names:
                continue
            # Pull source URL if present
            src_url = ""
            if cfg["iter1_url_col"] < len(r):
                src_url = r[cfg["iter1_url_col"]].strip()
            new_rows.append([
                name,                  # A
                tab,                   # B
                "",                    # C asset code (empty until uploaded)
                src_url,               # D source URL
                cfg["asset_type"],     # E asset type
                "Pending",             # F status
                "",                    # G uploaded at
                "",                    # H first used shot
                "",                    # I used in eps
                "",                    # J tags
                "",                    # K notes
                "",                    # L last used
            ])
            existing_names.append(name)

    if new_rows:
        # Write to next free row
        existing_data = ws.get("A5:A500", value_render_option="FORMATTED_VALUE")
        next_row = 5 + len([r for r in existing_data if r and r[0].strip()])
        ws.update(values=new_rows, range_name=f"A{next_row}",
                  value_input_option="USER_ENTERED")
        print(f"  ✓ seeded {len(new_rows)} new rows from bible tabs (rows {next_row}–{next_row + len(new_rows) - 1})")
    else:
        print(f"  → no new bible entries to seed (all already in Asset Library)")
    return new_rows


def main():
    ap = argparse.ArgumentParser(description="Build or refresh the Asset Library tab")
    ap.add_argument("--sheet", required=True, help="Sheet ID or full URL")
    ap.add_argument("--rebuild", action="store_true", help="Delete + recreate (DANGER)")
    ap.add_argument("--seed-from-bibles", action="store_true",
                    help="After tab creation, walk all bibles and seed rows for entries not yet tracked")
    args = ap.parse_args()

    sheet_id = parse_sheet_id(args.sheet)
    print(f"Sheet ID: {sheet_id}")

    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    print(f"Sheet name: {sh.title}\n")

    print(f"=== Building Asset Library tab ===")
    ws, existing_names = build_asset_library_tab(sh, rebuild=args.rebuild)
    print(f"  existing rows: {len(existing_names)}")

    if args.seed_from_bibles:
        print(f"\n=== Seeding from bibles ===")
        seed_from_bibles(sh, ws, existing_names)

    print(f"\n✓ Done. Tab URL:")
    print(f"  https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={ws.id}")


if __name__ == "__main__":
    main()

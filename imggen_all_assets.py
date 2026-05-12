#!/usr/bin/env python3
"""Generate missing bible reference images for all selected bible tabs."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import gspread

HERE = Path(__file__).parent
# Use the same Python interpreter that's running this script so subprocess
# generators inherit the venv (gspread, googleapiclient, etc.). Hardcoding
# /usr/bin/python3 breaks on Macs and on Render where the venv lives at
# /opt/render/project/src/.venv/bin/python3.
PY = sys.executable
sys.path.insert(0, str(HERE))
from auth import get_credentials  # type: ignore

ALL_BIBLES = ["characters", "locations", "props", "costume", "effects"]


def parse_sheet_id(value: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", value or "")
    return m.group(1) if m else (value or "").strip()


def run(cmd: list[str], dry_run: bool) -> int:
    print("+ " + " ".join(cmd), flush=True)
    if dry_run:
        return 0
    return subprocess.run(cmd, cwd=HERE).returncode


def selected(value: str) -> list[str]:
    if not value or value == "all":
        return ALL_BIBLES
    out = [v.strip().lower() for v in value.split(",") if v.strip()]
    bad = [v for v in out if v not in ALL_BIBLES]
    if bad:
        raise SystemExit(f"Unknown bible(s): {', '.join(bad)}")
    return out


def missing_counts(sheet_id: str) -> dict[str, int]:
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(parse_sheet_id(sheet_id))
    counts = dict.fromkeys(ALL_BIBLES, 0)
    rows = sh.worksheet("CHARACTERS").get("A2:W500", value_render_option="FORMATTED_VALUE")
    counts["characters"] = sum(1 for r in rows if r and r[0].strip() and not ((r + [""] * 23)[19].strip()))
    rows = sh.worksheet("LOCATIONS").get("A5:M500", value_render_option="FORMATTED_VALUE")
    counts["locations"] = sum(1 for r in rows if r and r[0].strip() and (not ((r + [""] * 13)[9].strip()) or not ((r + [""] * 13)[10].strip())))
    for key, tab in [("props", "PROPS"), ("costume", "COSTUME"), ("effects", "EFFECTS")]:
        rows = sh.worksheet(tab).get("A6:J500", value_render_option="FORMATTED_VALUE")
        counts[key] = sum(1 for r in rows if r and r[0].strip() and not ((r + [""] * 10)[6].strip()))
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--bibles", default="all", help="characters,locations,props,costume,effects")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    bibles = selected(args.bibles)
    if args.dry_run:
        print(f"DRY RUN: selected bibles: {', '.join(bibles)}")
        print("DRY RUN: existing generators are idempotent; commands below would run sequentially.")
    else:
        counts = missing_counts(args.sheet)
        for b in bibles:
            print(f"{b}: {counts[b]} missing refs")

    commands = []
    if "characters" in bibles:
        commands.append([PY, "character_generate.py", "--sheet", args.sheet])
    if "locations" in bibles:
        commands.append([PY, "location_generate.py", "--sheet", args.sheet])
    for key, tab in [("props", "PROPS"), ("costume", "COSTUME"), ("effects", "EFFECTS")]:
        if key in bibles:
            commands.append([PY, "bible_generate.py", "--sheet", args.sheet, "--tab", tab])
    if args.force:
        for cmd in commands:
            cmd.append("--force")

    for cmd in commands:
        rc = run(cmd, args.dry_run)
        if rc != 0:
            raise SystemExit(rc)


if __name__ == "__main__":
    main()

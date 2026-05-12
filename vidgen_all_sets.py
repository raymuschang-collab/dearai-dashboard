#!/usr/bin/env python3
"""Sequentially generate BytePlus videos for Pending storyboard sets."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import gspread

HERE = Path(__file__).parent
PY = "/usr/bin/python3"
sys.path.insert(0, str(HERE))
from auth import get_credentials  # type: ignore


def parse_sheet_id(value: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", value or "")
    return m.group(1) if m else (value or "").strip()


def pending_sets(sheet_id: str, max_set: int | None) -> list[int]:
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(parse_sheet_id(sheet_id))
    rows = sh.worksheet("Storyboard Prompts").get("A11:N500", value_render_option="FORMATTED_VALUE")
    out = []
    for r in rows:
        r = (r + [""] * 14)[:14]
        if not r[0].strip():
            continue
        try:
            set_num = int(r[0])
        except ValueError:
            continue
        if max_set is not None and set_num > max_set:
            continue
        if r[5].strip().lower() == "pending":
            out.append(set_num)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--max-set", type=int)
    ap.add_argument("--slot", type=int, default=1, choices=[1, 2])
    ap.add_argument("--mentions", nargs="+", default=None,
                    help="Explicit @name refs to pass to every set's vidgen run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sets = pending_sets(args.sheet, args.max_set) if not args.dry_run else list(range(1, (args.max_set or 1) + 1))
    if not sets:
        print("No Pending sets found.")
        return
    print(f"{'DRY RUN: would generate' if args.dry_run else 'Generating'} sets: {sets}")
    for set_num in sets:
        cmd = [PY, "byteplus_vidgen.py", "--sheet", args.sheet, "--set", str(set_num), "--slot", str(args.slot)]
        if args.mentions:
            cmd.extend(["--mentions", *args.mentions])
        print("+ " + " ".join(cmd), flush=True)
        if args.dry_run:
            continue
        rc = subprocess.run(cmd, cwd=HERE).returncode
        if rc != 0:
            raise SystemExit(rc)


if __name__ == "__main__":
    main()

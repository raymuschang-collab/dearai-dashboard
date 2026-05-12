#!/usr/bin/env python3
"""Run the DearAI episode production pipeline step by step."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
PY = "/usr/bin/python3"


def parse_skip(value: str) -> set[int]:
    if not value:
        return set()
    return {int(v.strip()) for v in value.split(",") if v.strip()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--script", help="Locked script path; if omitted, step 1 is skipped")
    ap.add_argument("--name", default="DearAI Episode", help="Show name for shotlist-gen")
    ap.add_argument("--locale", default="generic", choices=["jakarta", "manila", "seoul", "generic"])
    ap.add_argument("--from-step", type=int, default=1)
    ap.add_argument("--to-step", type=int, default=5)
    ap.add_argument("--skip", default="", help="Comma-separated step numbers to skip")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    steps = [
        ("shotlist-gen", [PY, "shotlist_gen.py", "--sheet", args.sheet, "--name", args.name, "--locale", args.locale] + (["--script", args.script] if args.script else [])),
        ("imggen-all-assets", [PY, "imggen_all_assets.py", "--sheet", args.sheet]),
        ("byteplus-upload-all", [PY, "byteplus_asset_upload.py", "--sheet", args.sheet, "--all-bibles"]),
        ("imggen-all-storyboards", [PY, "storyboard_generate.py", "--sheet", args.sheet]),
        ("vidgen-all-sets", [PY, "vidgen_all_sets.py", "--sheet", args.sheet]),
    ]
    skip = parse_skip(args.skip)
    for i, (name, cmd) in enumerate(steps, start=1):
        if i < args.from_step or i > args.to_step or i in skip:
            print(f"{i}. {name}: skipped")
            continue
        if i == 1 and not args.script:
            print("1. shotlist-gen: skipped (no --script)")
            continue
        if args.dry_run and name in {"shotlist-gen", "imggen-all-assets", "vidgen-all-sets"}:
            cmd.append("--dry-run")
        print(f"\n{i}. {name}")
        print("+ " + " ".join(cmd), flush=True)
        if args.dry_run and name in {"byteplus-upload-all", "imggen-all-storyboards"}:
            continue
        rc = subprocess.run(cmd, cwd=HERE).returncode
        if rc != 0:
            raise SystemExit(rc)


if __name__ == "__main__":
    main()

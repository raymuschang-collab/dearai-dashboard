#!/usr/bin/env python3
"""End-to-end ingest pipeline.

Assumes Stage 1 (script → Shotlist atomization) has been done by the
microdrama-shotlist skill in a Claude session. From a populated Shotlist,
this script runs the rest of the pipeline:

  Stage 2 — storyboard_build.py: scaffold Storyboard Prompts tab + Drive
            set-NN/ folders + Asset Library tab if missing
  Stage 3 — refs_audit.py:       per-shot Refs Detected — Chars (col S)
                                 + Loc/Prop/Costume/FX (col T)
  Stage 4 — SP!L rollup:         per-set canonical location, majority vote
                                 across the 5 shots' loc:<canonical> tags
  Stage 5 — Forward-fill:        fill any "Unspecified" SP!L cell from the
                                 prior matched set (face-CU sets inherit)

Idempotent end-to-end. Re-run after any Shotlist edit.

Usage:
  python3 _ingest_script.py --sheet <episode-sheet-id>
  python3 _ingest_script.py --sheet <id> --skip-build         # if SP already exists
  python3 _ingest_script.py --sheet <id> --skip-refs          # skip refs_audit
  python3 _ingest_script.py --sheet <id> --status-cb <fname>  # write per-stage progress JSON

The --status-cb arg makes this dashboard-friendly: status pollers read the
JSON to render live progress.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import gspread

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials


def write_status(path: str | None, stage: int, name: str, state: str,
                 message: str = "", total: int = 5):
    """state: queued | running | done | failed | skipped"""
    if not path:
        return
    try:
        existing = {}
        p = Path(path)
        if p.exists():
            try:
                existing = json.loads(p.read_text())
            except Exception:
                existing = {}
        existing.setdefault("stages", {})
        existing["stages"][str(stage)] = {
            "name": name, "state": state, "message": message,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        existing["total"] = total
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(existing, indent=2))
    except Exception:
        pass


def stage2_storyboard_build(sheet_id: str, status_cb: str | None) -> bool:
    write_status(status_cb, 2, "Storyboard Prompts scaffold", "running")
    cmd = ["python3", str(HERE / "storyboard_build.py"), "--sheet", sheet_id]
    print(f"  $ {' '.join(cmd)}", flush=True)
    try:
        proc = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True,
                              timeout=300)
        ok = proc.returncode == 0
        out = proc.stdout[-1000:]
        write_status(status_cb, 2, "Storyboard Prompts scaffold",
                     "done" if ok else "failed", out)
        print(out, flush=True)
        return ok
    except Exception as e:
        write_status(status_cb, 2, "Storyboard Prompts scaffold", "failed", str(e))
        print(f"  ! {e}", flush=True)
        return False


def stage3_refs_audit(sheet_id: str, status_cb: str | None) -> bool:
    write_status(status_cb, 3, "Refs detection (Shotlist!S+T)", "running")
    cmd = ["python3", str(HERE / "refs_audit.py"), "--sheet", sheet_id]
    print(f"  $ {' '.join(cmd)}", flush=True)
    try:
        proc = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True,
                              timeout=300)
        ok = proc.returncode == 0
        out = proc.stdout[-1000:]
        write_status(status_cb, 3, "Refs detection (Shotlist!S+T)",
                     "done" if ok else "failed", out)
        print(out, flush=True)
        return ok
    except Exception as e:
        write_status(status_cb, 3, "Refs detection (Shotlist!S+T)", "failed", str(e))
        print(f"  ! {e}", flush=True)
        return False


def stage4_sp_rollup(sheet_id: str, status_cb: str | None) -> tuple[bool, list[str]]:
    """Per-set rollup: Shotlist!T loc:* → SP!L. Majority vote across 5 shots.
    Returns (ok, per_set_locations)."""
    write_status(status_cb, 4, "SP!L rollup", "running")
    try:
        gc = gspread.authorize(get_credentials())
        sh = gc.open_by_key(sheet_id)
        time.sleep(2)
        sl = sh.worksheet("Shotlist")
        all_rows = sl.get_all_values()
        time.sleep(2)
        if not all_rows:
            raise RuntimeError("empty Shotlist")
        header = all_rows[0]
        loc_t_i = None
        for i, h in enumerate(header):
            if h.strip().startswith("Refs Detected — Loc"):
                loc_t_i = i
                break
        if loc_t_i is None:
            raise RuntimeError("no 'Refs Detected — Loc...' col on Shotlist")
        per_shot = []
        for row in all_rows[1:]:
            if not row or len(row) <= loc_t_i:
                per_shot.append("")
                continue
            m = re.search(r"loc:([^;]+)", row[loc_t_i] or "")
            per_shot.append(m.group(1).strip() if m else "")

        sp = sh.worksheet("Storyboard Prompts")
        time.sleep(2)
        # Ensure col L header exists
        if sp.col_count < 14:
            sp.resize(rows=max(sp.row_count, 50), cols=14)
            time.sleep(2)
        hdr = sp.get("L10:N10", value_render_option="FORMATTED_VALUE")
        cur = (hdr[0] if hdr else []) + ["", "", ""]
        if cur[0] != "Location":
            sp.update(values=[["Location"]], range_name="L10",
                      value_input_option="RAW")
            time.sleep(2)
        if len(cur) < 2 or cur[1] != "Video Iter 1 URL":
            sp.update(values=[["Video Iter 1 URL"]], range_name="M10",
                      value_input_option="RAW")
            time.sleep(2)
        if len(cur) < 3 or cur[2] != "Video Iter 2 URL":
            sp.update(values=[["Video Iter 2 URL"]], range_name="N10",
                      value_input_option="RAW")
            time.sleep(2)

        # rollup
        sets_n = (len(per_shot) + 4) // 5
        L_values = []
        for set_n in range(1, sets_n + 1):
            slice_locs = [l for l in per_shot[(set_n-1)*5: set_n*5] if l]
            if slice_locs:
                top = Counter(slice_locs).most_common(1)[0][0]
                L_values.append([top])
            else:
                L_values.append(["Unspecified"])
        if L_values:
            sp.update(values=L_values, range_name=f"L11:L{10+len(L_values)}",
                      value_input_option="RAW")
        matched = sum(1 for v in L_values if v[0] != "Unspecified")
        msg = f"{matched}/{len(L_values)} sets matched"
        write_status(status_cb, 4, "SP!L rollup", "done", msg)
        print(f"  Stage 4: {msg}", flush=True)
        for i, v in enumerate(L_values, start=11):
            print(f"    L{i}: {v[0]}", flush=True)
        return True, [v[0] for v in L_values]
    except Exception as e:
        write_status(status_cb, 4, "SP!L rollup", "failed", str(e))
        print(f"  ! {e}", flush=True)
        return False, []


def stage5_forward_fill(sheet_id: str, status_cb: str | None,
                          set_locs: list[str]) -> bool:
    """Replace any Unspecified entry with the previous matched location."""
    write_status(status_cb, 5, "Forward-fill Unspecified", "running")
    try:
        last = ""
        new_l = []
        changed = 0
        for v in set_locs:
            if v.lower() == "unspecified" and last:
                new_l.append([last])
                changed += 1
            else:
                new_l.append([v])
                if v.lower() != "unspecified":
                    last = v
        if changed:
            gc = gspread.authorize(get_credentials())
            sh = gc.open_by_key(sheet_id)
            time.sleep(2)
            sp = sh.worksheet("Storyboard Prompts")
            sp.update(values=new_l,
                      range_name=f"L11:L{10+len(new_l)}",
                      value_input_option="RAW")
        msg = f"filled {changed} Unspecified → previous match"
        write_status(status_cb, 5, "Forward-fill Unspecified", "done", msg)
        print(f"  Stage 5: {msg}", flush=True)
        return True
    except Exception as e:
        write_status(status_cb, 5, "Forward-fill Unspecified", "failed", str(e))
        print(f"  ! {e}", flush=True)
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True, help="Episode sheet ID")
    ap.add_argument("--skip-build", action="store_true",
                    help="Skip Stage 2 (storyboard_build) — SP tab already exists")
    ap.add_argument("--skip-refs", action="store_true",
                    help="Skip Stage 3 (refs_audit)")
    ap.add_argument("--status-cb", default=None,
                    help="Path to write JSON progress for the dashboard poller")
    args = ap.parse_args()

    print(f"\n=== Ingest pipeline → sheet {args.sheet[:8]}…  ===", flush=True)
    write_status(args.status_cb, 1, "Shotlist atomization (skill, manual)",
                 "skipped", "run microdrama-shotlist skill in chat first")

    if not args.skip_build:
        print("\n— Stage 2: storyboard_build.py", flush=True)
        if not stage2_storyboard_build(args.sheet, args.status_cb):
            sys.exit(2)
    else:
        write_status(args.status_cb, 2, "Storyboard Prompts scaffold", "skipped")
        print("— Stage 2: skipped (--skip-build)", flush=True)

    if not args.skip_refs:
        print("\n— Stage 3: refs_audit.py", flush=True)
        if not stage3_refs_audit(args.sheet, args.status_cb):
            sys.exit(3)
    else:
        write_status(args.status_cb, 3, "Refs detection", "skipped")
        print("— Stage 3: skipped (--skip-refs)", flush=True)

    print("\n— Stage 4: SP!L rollup", flush=True)
    ok, set_locs = stage4_sp_rollup(args.sheet, args.status_cb)
    if not ok:
        sys.exit(4)

    print("\n— Stage 5: forward-fill", flush=True)
    if not stage5_forward_fill(args.sheet, args.status_cb, set_locs):
        sys.exit(5)

    matched = sum(1 for v in set_locs if v.lower() != "unspecified")
    print(f"\n✓ Pipeline done — {matched}/{len(set_locs)} sets have canonical locations", flush=True)


if __name__ == "__main__":
    main()

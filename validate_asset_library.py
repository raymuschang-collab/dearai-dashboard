#!/usr/bin/env python3
"""
validate_asset_library.py — Probe every Asset Library row against BytePlus
and clean up stale entries.

Three failure modes this catches:
  1. BytePlus garbage-collected an asset that's still marked Uploaded
     in the sheet → mark it Replaced
  2. Asset Library code points at a NotFound asset → mark Replaced
  3. Orphan BytePlus assets that aren't in Asset Library at all → optionally
     delete from BytePlus (frees up project quota)

Usage:
    # Validate only (read-only, prints report)
    python3 validate_asset_library.py --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc

    # Validate + auto-mark stale rows as Replaced
    python3 validate_asset_library.py --sheet <ID> --apply

    # Also delete orphan BytePlus assets not referenced by Asset Library
    python3 validate_asset_library.py --sheet <ID> --apply --delete-orphans

Run monthly or after any major asset change (re-uploads, character renames,
bulk swaps). Idempotent.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))
from auth import get_credentials  # type: ignore
import byteplus_asset_v2 as bp  # type: ignore


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sheet", required=True,
                    help="Bible sheet ID (the one with the Asset Library tab)")
    ap.add_argument("--group-id", default=os.getenv("BYTEPLUS_GROUP_ID"),
                    help="BytePlus asset group ID (default: BYTEPLUS_GROUP_ID env)")
    ap.add_argument("--apply", action="store_true",
                    help="Mark stale Asset Library rows as Replaced (write changes)")
    ap.add_argument("--delete-orphans", action="store_true",
                    help="Also delete orphan BytePlus assets not in Asset Library")
    args = ap.parse_args()

    if not args.group_id:
        sys.exit("BYTEPLUS_GROUP_ID required (env var or --group-id)")

    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(args.sheet)
    al = sh.worksheet("Asset Library")

    # 1) Read Asset Library
    print(f"=== Validating Asset Library on {sh.title!r} ===\n")
    rows = al.get("A5:F500", value_render_option="FORMATTED_VALUE")
    al_entries = []  # [(row_idx, name, code, status), ...]
    for i, r in enumerate(rows, start=5):
        if not r or not r[0].strip():
            continue
        r = r + [""] * 6
        al_entries.append({
            "row": i, "name": r[0].strip(),
            "bible_tab": r[1].strip(), "code": r[2].strip(),
            "type": r[4].strip().lower(), "status": r[5].strip(),
        })
    uploaded = [e for e in al_entries if e["status"] == "Uploaded"]
    replaced = [e for e in al_entries if e["status"] == "Replaced"]
    other = [e for e in al_entries if e["status"] not in ("Uploaded", "Replaced")]
    print(f"  Asset Library: {len(al_entries)} rows total")
    print(f"    Uploaded: {len(uploaded)}")
    print(f"    Replaced: {len(replaced)}")
    if other:
        print(f"    Other status: {len(other)}")
        for o in other:
            print(f"      row {o['row']}: {o['name']} → {o['status']!r}")

    # 2) Probe each Uploaded code against BytePlus GetAsset
    print(f"\n=== Probing BytePlus for {len(uploaded)} Uploaded codes ===")
    stale = []
    valid = []
    for e in uploaded:
        if not e["code"]:
            stale.append((e, "missing-code"))
            continue
        resp = bp.call("GetAsset", {"Id": e["code"]})
        err = resp.get("ResponseMetadata", {}).get("Error")
        if err:
            stale.append((e, err.get("Code", "unknown")))
            print(f"  ✗ row {e['row']:>3}: {e['name']:<40} {e['code']:<35} {err.get('Code')}")
        else:
            valid.append(e)
    print(f"\n  Valid: {len(valid)} / {len(uploaded)}")
    print(f"  Stale: {len(stale)}")

    # 3) Mark stale as Replaced (if --apply)
    if stale and args.apply:
        print(f"\n=== Marking {len(stale)} stale rows as Replaced ===")
        for e, why in stale:
            al.update(values=[["Replaced"]], range_name=f"F{e['row']}",
                       value_input_option="USER_ENTERED")
            note = (al.acell(f"K{e['row']}").value or "").strip()
            new_note = f"Auto-marked Replaced ({why})"
            if note:
                new_note = f"{note}; {new_note}"
            al.update(values=[[new_note]], range_name=f"K{e['row']}",
                       value_input_option="USER_ENTERED")
            print(f"  ✓ row {e['row']}: {e['name']} → Replaced")
    elif stale:
        print(f"\n  (rerun with --apply to mark these {len(stale)} rows Replaced)")

    # 4) Detect orphan BytePlus assets (not referenced by Asset Library)
    print(f"\n=== Probing BytePlus group for orphans ===")
    valid_codes = {e["code"] for e in valid}
    all_byteplus = []
    page = 1
    while True:
        resp = bp.call("ListAssets", {
            "Filter": {"GroupType": "AIGC", "GroupIds": [args.group_id]},
            "PageSize": 100, "PageNumber": page,
        })
        items = resp.get("Result", {}).get("Items", [])
        if not items:
            break
        all_byteplus.extend(items)
        if len(items) < 100:
            break
        page += 1
    print(f"  BytePlus group has {len(all_byteplus)} active assets")
    orphans = [a for a in all_byteplus if a.get("Id") not in valid_codes]
    print(f"  Orphans (in BytePlus but not in Asset Library): {len(orphans)}")
    for a in orphans[:20]:
        print(f"    {a.get('Id'):<40} {a.get('AssetType'):<8} {a.get('Name','?')}")
    if len(orphans) > 20:
        print(f"    …and {len(orphans) - 20} more")

    # 5) Delete orphans (if --delete-orphans + --apply)
    if orphans and args.delete_orphans and args.apply:
        print(f"\n=== Deleting {len(orphans)} orphan BytePlus assets ===")
        deleted = 0
        for a in orphans:
            r = bp.call("DeleteAsset", {"Id": a["Id"]})
            err = r.get("ResponseMetadata", {}).get("Error")
            if err:
                print(f"  ✗ {a['Id']}: {err.get('Code')}")
            else:
                deleted += 1
        print(f"  ✓ deleted {deleted}/{len(orphans)} orphans")
    elif orphans and not args.delete_orphans:
        print(f"\n  (rerun with --apply --delete-orphans to clean up these {len(orphans)} BytePlus assets)")

    # 6) Final summary
    print(f"\n=== Summary ===")
    print(f"  Asset Library rows:       {len(al_entries)}")
    print(f"  Valid (probed OK):        {len(valid)}")
    print(f"  Stale (would mark):       {len(stale)}")
    print(f"  BytePlus group total:     {len(all_byteplus)}")
    print(f"  Orphans (in BP, not AL):  {len(orphans)}")
    if not args.apply and (stale or orphans):
        print(f"\n  No changes written. Rerun with --apply to act on findings.")
    sys.exit(0 if not stale and not orphans else 1)


if __name__ == "__main__":
    main()

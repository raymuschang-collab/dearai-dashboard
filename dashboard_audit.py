#!/usr/bin/env python3
"""
dashboard_audit.py — Verify a series' sheet-set matches the dashboard standard.

Usage:
  python3 dashboard_audit.py                    # audits the active SERIES from dash_app/app.py
  python3 dashboard_audit.py --series sajangnim
  python3 dashboard_audit.py --series pharaoh

Standard (locked):
  - Episode sheet has: Shotlist, Storyboard Prompts, Video Prompts
  - Series bible sheet has: CHARACTERS, LOCATIONS, COSTUME, PROPS, EFFECTS, Asset Library
  - Episode shotlists use the v2.2 + Bahasa column = 18-col schema (incl. Tone of Voice at H, Bahasa Prompt at R)
  - Bibles live ONCE at the series-level bible_sheet, NOT per-episode
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "dash_app"))

from auth import get_credentials
from googleapiclient.discovery import build

# Pull the same SERIES_CONFIG the dashboard uses
from app import SERIES_CONFIG


EXPECTED_EPISODE_TABS = ["Shotlist", "Storyboard Prompts", "Video Prompts"]
EXPECTED_BIBLE_TABS = ["CHARACTERS", "LOCATIONS", "COSTUME", "PROPS", "EFFECTS"]
OPTIONAL_TABS = ["Asset Library"]


def audit_series(slug: str):
    if slug not in SERIES_CONFIG:
        sys.exit(f"Unknown series: {slug}. Known: {list(SERIES_CONFIG)}")
    s = SERIES_CONFIG[slug]
    drive = build("drive", "v3", credentials=get_credentials())
    sheets = build("sheets", "v4", credentials=get_credentials())

    print(f"\n{'='*70}\nSERIES: {s['name']}  (slug: {slug})\n{'='*70}")

    bible_sheet = s.get("bible_sheet") or next(iter(s["episodes"].values()))
    print(f"\n● BIBLE SHEET: {bible_sheet}")
    try:
        meta = drive.files().get(fileId=bible_sheet, fields="name,modifiedTime").execute()
        print(f"  drive name: {meta['name']}")
        smeta = sheets.spreadsheets().get(spreadsheetId=bible_sheet).execute()
        tabs = [t["properties"]["title"] for t in smeta["sheets"]]
        print(f"  tabs:       {tabs}")
        for tab in EXPECTED_BIBLE_TABS:
            if tab in tabs:
                rng = "A2:A40" if tab == "CHARACTERS" else (
                    "A5:A60" if tab == "LOCATIONS" else "A6:A60")
                vals = sheets.spreadsheets().values().get(
                    spreadsheetId=bible_sheet, range=f"{tab}!{rng}"
                ).execute().get("values", [])
                count = sum(1 for r in vals if r and r[0].strip())
                print(f"  {tab}: ✓ {count} entries")
            else:
                print(f"  {tab}: ✗ MISSING — bibles tab will appear empty in dashboard")
        for tab in OPTIONAL_TABS:
            present = "✓ present" if tab in tabs else "(optional, not present)"
            print(f"  {tab}: {present}")
    except Exception as e:
        print(f"  ✗ ERROR reading bible sheet: {str(e)[:140]}")

    print(f"\n● EPISODES ({len(s['episodes'])})")
    for label, sid in s["episodes"].items():
        print(f"\n  ▸ {label}")
        print(f"    sheet: {sid}")
        try:
            meta = drive.files().get(fileId=sid, fields="name,modifiedTime").execute()
            print(f"    drive name: {meta['name']}")
            print(f"    modified:   {meta['modifiedTime'][:10]}")
            smeta = sheets.spreadsheets().get(spreadsheetId=sid).execute()
            tabs = [t["properties"]["title"] for t in smeta["sheets"]]
            for t in EXPECTED_EPISODE_TABS:
                mark = "✓" if t in tabs else "✗ MISSING"
                print(f"    {t}: {mark}")
            sl = sheets.spreadsheets().values().get(
                spreadsheetId=sid, range="Shotlist!A2:A200"
            ).execute().get("values", [])
            sl_count = sum(1 for r in sl if r and str(r[0]).strip().isdigit())
            print(f"    shotlist:   {sl_count} shots {'✓' if sl_count >= 50 else '⚠ low (skill expects ≥50 for 75-90s)'}")
            # Verify v2.2 schema — header row 1
            hdr = sheets.spreadsheets().values().get(
                spreadsheetId=sid, range="Shotlist!A1:R1"
            ).execute().get("values", [[]])
            hdr = hdr[0] if hdr else []
            has_bahasa = any("Bahasa" in str(c) for c in hdr)
            has_tone = any("Tone" in str(c) for c in hdr)
            print(f"    schema:     {len(hdr)} cols  bahasa={'✓' if has_bahasa else '✗'}  tone={'✓' if has_tone else '✗'}")
        except Exception as e:
            print(f"    ✗ ERROR: {str(e)[:140]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--series", default=None,
                    help="Series slug (default: active series in app.py)")
    args = ap.parse_args()
    slug = args.series or list(SERIES_CONFIG.keys())[0]
    audit_series(slug)


if __name__ == "__main__":
    main()

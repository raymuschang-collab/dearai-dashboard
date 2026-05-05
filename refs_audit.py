#!/usr/bin/env python3
"""Audit per-shot bible refs and write to shotlist tab.

Sweeps the shotlist tab (the show-name tab, NOT Storyboard Prompts), runs the
same auto-detect logic that fal_vidgen.py / flora_run.py use, and writes the
detected refs into:
  - col S = Refs Detected — Chars         (comma-separated names)
  - col T = Refs Detected — Loc/Prop/Costume/FX

Run after any body edit. Audit visually before firing video gen — catches
refs that shouldn't be pulled (e.g. MERCHANT showing up in a KHENSU-only
shot because his name appears in some unrelated context).

Usage:
  python3 refs_audit.py [--sheet <sheet-id>]
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import gspread
from dotenv import load_dotenv

from auth import get_credentials


HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

DEFAULT_SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"


_LOC_ALIAS_CACHE: dict[str, list[tuple[str, str]]] = {}

def _load_location_aliases(sh: gspread.Spreadsheet) -> list[tuple[str, str]]:
    """Read LOCATIONS bible col O (Aliases) per row, build a sorted alias list.

    Schema: row 4 = headers, rows 5+ = data. Col A = Name (canonical),
    col O = "alias1; alias2; alias3" (lowercase, semicolon-separated).
    Multiple rows can share a name (one per shot size) — we accept whichever
    row has aliases. Returns [(alias_lower, canonical), ...] sorted by
    alias length DESCENDING so most-specific match wins first.

    Falls back to building aliases from the canonical name itself if col O
    is empty for a row, so a fresh bible without aliases still works at
    a basic level (e.g. "kitchen" matches "Hanbyeol Bistro Kitchen").

    Cached per spreadsheet ID so subsequent shot scans don't re-read."""
    sid = getattr(sh, "id", None) or sh.id
    cached = _LOC_ALIAS_CACHE.get(sid)
    if cached is not None:
        return cached
    pairs: dict[str, str] = {}  # alias_lower → canonical (last-write-wins)
    try:
        ws = sh.worksheet("LOCATIONS")
        rows = ws.get("A5:O100", value_render_option="FORMATTED_VALUE")
        seen_canonicals = set()
        for row in rows:
            row = (row + [""] * 15)[:15]
            name = (row[0] or "").strip()
            if not name:
                continue
            seen_canonicals.add(name)
            aliases_str = (row[14] or "").strip()  # col O
            if aliases_str:
                for a in aliases_str.split(";"):
                    a = a.strip().lower()
                    if a:
                        pairs.setdefault(a, name)
        # safety net: every canonical matches itself (full lowercased name).
        # Single-word fallback was too eager — words like "hanbyeol" appear
        # in 5 canonicals so the first-seen canonical wins by accident.
        # Bible authors should write explicit aliases in col O for partial
        # matches; the canonical name alone is the only auto-fallback.
        for name in seen_canonicals:
            pairs.setdefault(name.lower(), name)
    except Exception:
        pass
    result = sorted(pairs.items(), key=lambda p: -len(p[0]))
    _LOC_ALIAS_CACHE[sid] = result
    return result


def detect_refs_for_shot(shot_text: str, sh: gspread.Spreadsheet) -> tuple[list[str], list[str]]:
    """Returns (chars_list, others_list) of bible refs detected in this shot text."""
    chars_found = []
    others_found = []

    # Characters — whole-word match, ISFET SPAWN → ISFET SPAWN (2) override
    chars = sh.worksheet("CHARACTERS").get("A2:U20", value_render_option="FORMATTED_VALUE")
    seen_chars = set()
    for r in chars:
        if not r or not r[0]:
            continue
        name = r[0].strip()
        if name == "ISFET SPAWN":
            # Skip — let (2) variant catch
            continue
        if re.search(r"\b" + re.escape(name) + r"\b", shot_text, re.IGNORECASE):
            chars_found.append(name)
            seen_chars.add(name)
    # Check (2) variants
    for r in chars:
        if not r or not r[0]:
            continue
        name = r[0].strip()
        if "(2)" not in name:
            continue
        base = name.replace("(2)", "").strip()
        if re.search(r"\b" + re.escape(base) + r"\b", shot_text, re.IGNORECASE):
            if name not in seen_chars:
                chars_found.append(name)
                seen_chars.add(name)

    # Locations — alias table is read DIRECTLY from this show's LOCATIONS
    # bible (col O = Aliases, semicolon-separated lowercase substrings).
    # Each location row's name (col A) becomes the canonical that aliases
    # resolve to. New shows just need to fill col O; no code changes.
    location_aliases = _load_location_aliases(sh)

    body_lc = shot_text.lower()
    seen_locs = set()
    for alias, canonical in location_aliases:
        if alias in body_lc and canonical not in seen_locs:
            seen_locs.add(canonical)
            others_found.append(f"loc:{canonical}")
            break  # cap 1 location per shot

    # Props (substring match)
    try:
        props = sh.worksheet("PROPS").get("A6:G50", value_render_option="FORMATTED_VALUE")
        for r in props:
            if not r or not r[0]:
                continue
            if r[0].strip().lower() in body_lc:
                others_found.append(f"prop:{r[0].strip()}")
    except Exception:
        pass

    # Costume (first-word match)
    try:
        costumes = sh.worksheet("COSTUME").get("A6:G50", value_render_option="FORMATTED_VALUE")
        for r in costumes:
            if not r or not r[0]:
                continue
            first_word = r[0].split()[0] if r[0] else ""
            if first_word and re.search(r"\b" + re.escape(first_word) + r"\b", shot_text, re.IGNORECASE):
                others_found.append(f"costume:{r[0].strip()}")
                break  # cap 1
    except Exception:
        pass

    # Effects (substring match)
    try:
        fx = sh.worksheet("EFFECTS").get("A6:G30", value_render_option="FORMATTED_VALUE")
        for r in fx:
            if not r or not r[0]:
                continue
            if r[0].strip().lower() in body_lc:
                others_found.append(f"fx:{r[0].strip()}")
                break  # cap 1
    except Exception:
        pass

    return chars_found, others_found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=DEFAULT_SHEET_ID, help="Sheet ID")
    ap.add_argument("--shotlist-tab", default=None,
                    help="Shotlist tab name (auto-detected if omitted)")
    args = ap.parse_args()

    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(args.sheet)

    # Auto-detect shotlist tab (the tab that's NOT Storyboard Prompts / Video Prompts / bibles)
    if args.shotlist_tab:
        shotlist_name = args.shotlist_tab
    else:
        bible_names = {"Storyboard Prompts", "Video Prompts", "CHARACTERS", "LOCATIONS",
                       "PROPS", "COSTUME", "EFFECTS"}
        candidates = [w.title for w in sh.worksheets() if w.title not in bible_names]
        if not candidates:
            sys.exit("Could not auto-detect shotlist tab")
        shotlist_name = candidates[0]
    print(f"Shotlist tab: {shotlist_name}")

    ws = sh.worksheet(shotlist_name)
    # Read all rows (header + data)
    all_rows = ws.get_all_values()
    if not all_rows:
        sys.exit("Empty shotlist")

    header = all_rows[0]
    # Find col indices — exact match first, then prefix-tolerant fallback so
    # variants like "Refs Detected — Loc/Prop/Costume/FX/Type" still resolve.
    def col_idx(name, *prefixes):
        for i, h in enumerate(header):
            if h.strip() == name:
                return i
        for i, h in enumerate(header):
            hs = h.strip()
            for p in prefixes:
                if hs.startswith(p):
                    return i
        return None

    desc_idx = col_idx("Shot Description")
    diag_idx = col_idx("Dialogue/VO")
    tone_idx = col_idx("Tone of Voice")
    s_idx = col_idx("Refs Detected — Chars", "Refs Detected — Chars")
    t_idx = col_idx("Refs Detected — Loc/Prop/Costume/FX",
                    "Refs Detected — Loc")

    if desc_idx is None or s_idx is None or t_idx is None:
        sys.exit(f"Missing required columns. Found header: {header}")

    print(f"Cols: desc={desc_idx} diag={diag_idx} tone={tone_idx} S={s_idx} T={t_idx}")
    print(f"Auditing {len(all_rows) - 1} shots...")

    updates = []
    for i, row in enumerate(all_rows[1:], start=2):  # row 2 onwards
        if not row or len(row) <= desc_idx:
            continue
        desc = row[desc_idx] if desc_idx < len(row) else ""
        diag = row[diag_idx] if diag_idx is not None and diag_idx < len(row) else ""
        tone = row[tone_idx] if tone_idx is not None and tone_idx < len(row) else ""
        if not desc and not diag:
            continue
        # Combine all text fields for ref scanning
        scan_text = "\n".join([desc, diag, tone])
        chars, others = detect_refs_for_shot(scan_text, sh)
        chars_str = ", ".join(chars) if chars else ""
        others_str = "; ".join(others) if others else ""
        # Compute A1 col letters
        s_col = chr(65 + s_idx) if s_idx < 26 else "A" + chr(65 + s_idx - 26)
        t_col = chr(65 + t_idx) if t_idx < 26 else "A" + chr(65 + t_idx - 26)
        updates.append({
            "range": f"'{shotlist_name}'!{s_col}{i}",
            "values": [[chars_str]],
        })
        updates.append({
            "range": f"'{shotlist_name}'!{t_col}{i}",
            "values": [[others_str]],
        })

    if updates:
        ws.spreadsheet.values_batch_update(body={
            "valueInputOption": "RAW",
            "data": updates,
        })
        print(f"✓ Wrote {len(updates) // 2} shots × 2 cols = {len(updates)} cells")
    else:
        print("(nothing to write)")


if __name__ == "__main__":
    main()

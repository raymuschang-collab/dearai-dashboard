#!/usr/bin/env python3
"""
audit_protected_ranges.py — Compare protected-range schemas across the
episode sheets of a series, using ep01 as the reference. Reports any
protected range present in ep01 but missing from later eps (or vice
versa) so we can hand-fix drift before the team comes back.

Read-only by default. Pass --apply to write the missing protections to
later eps via the Sheets API (matches editor list + warningOnly state).

Usage:
    # Audit a series via the master Projects sheet (auto-discovers eps)
    python3 audit_protected_ranges.py --master <MASTER_SHEET_ID> --series sajangnim

    # Audit a hand-picked set of episode sheets
    python3 audit_protected_ranges.py --sheets ep01_id ep02_id ep03_id …

    # Apply fixes to later eps to match ep01's protections
    python3 audit_protected_ranges.py --master <MASTER_SHEET_ID> \\
        --series sajangnim --apply

Output format: per-tab diff, with each missing / extra range listed by
its A1 range string + description. Non-zero exit when drift is detected
(unless --apply was used and all fixes succeeded).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import gspread
from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).parent))
from auth import get_credentials  # type: ignore


SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def parse_sheet_id(s: str) -> str:
    m = SHEETS_URL_RE.search(s)
    return m.group(1) if m else s.strip()


@dataclass(frozen=True)
class Protection:
    """Identity of a protected range. Matched on (tab, range_a1) — the
    description / editors list is reported but not part of the equality
    test, so two eps can use slightly different descriptions and still
    be considered 'in sync'."""
    tab: str           # e.g. "Storyboard Prompts"
    range_a1: str      # e.g. "B1:B8"
    description: str
    warning_only: bool

    def key(self) -> tuple[str, str]:
        return (self.tab, self.range_a1)


def list_protections(sheets_api, sheet_id: str) -> list[Protection]:
    """Pull every protected range on a sheet via the Sheets API.
    Returns a list keyed by (tab name, A1 range)."""
    meta = sheets_api.spreadsheets().get(
        spreadsheetId=sheet_id,
        includeGridData=False,
        fields="sheets(properties(sheetId,title),protectedRanges)",
    ).execute()

    out: list[Protection] = []
    sheet_id_to_title: dict[int, str] = {}
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        sheet_id_to_title[props.get("sheetId")] = props.get("title", "?")

    for s in meta.get("sheets", []):
        title = s.get("properties", {}).get("title", "?")
        for pr in s.get("protectedRanges") or []:
            r = pr.get("range") or {}
            # When `range` is missing, the protection covers the whole tab.
            if not r:
                a1 = "ALL"
            else:
                a1 = _range_to_a1(r)
            out.append(Protection(
                tab=title,
                range_a1=a1,
                description=pr.get("description", "") or "",
                warning_only=bool(pr.get("warningOnly", False)),
            ))
    return out


def _col_letter(idx: int) -> str:
    """0-based col index → A1 letter."""
    s = ""
    n = idx + 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _range_to_a1(r: dict) -> str:
    """Convert a Sheets API GridRange to an A1 string. Open-ended sides
    are filled with the obvious unbounded marker (e.g. "A2:A" if no end
    row was set)."""
    sr = r.get("startRowIndex")
    er = r.get("endRowIndex")
    sc = r.get("startColumnIndex")
    ec = r.get("endColumnIndex")
    start_col = _col_letter(sc) if sc is not None else "A"
    end_col = _col_letter(ec - 1) if ec is not None else ""
    start_row = (sr + 1) if sr is not None else 1
    end_row = er if er is not None else ""
    a = f"{start_col}{start_row}"
    b = f"{end_col}{end_row}"
    return f"{a}:{b}" if (end_col or end_row) else a


def diff_protections(reference: list[Protection],
                     target: list[Protection]) -> tuple[list[Protection], list[Protection]]:
    """Returns (missing_in_target, extra_in_target).

    Matching is by (tab, range_a1) — the description text doesn't have
    to match between eps."""
    ref_keys = {p.key(): p for p in reference}
    tgt_keys = {p.key(): p for p in target}
    missing = [ref_keys[k] for k in ref_keys.keys() - tgt_keys.keys()]
    extra = [tgt_keys[k] for k in tgt_keys.keys() - ref_keys.keys()]
    return missing, extra


def episodes_from_master(gc, master_id: str, series: str) -> list[tuple[str, str]]:
    """Read the master Projects sheet and return [(slug, sheet_id), ...]
    for episodes of the named series. Slug filter is case-insensitive
    substring match against the row's project slug or show name."""
    sh = gc.open_by_key(master_id)
    try:
        ws = sh.worksheet("Projects")
    except gspread.WorksheetNotFound:
        ws = sh.sheet1
    rows = ws.get_all_records()
    series_lc = series.lower()
    out: list[tuple[str, str]] = []
    for r in rows:
        slug = (r.get("Slug") or r.get("slug") or "").strip().lower()
        show = (r.get("Show") or r.get("show") or "").strip().lower()
        ep = (r.get("Episode") or r.get("episode") or "").strip()
        sheet_id = (r.get("Sheet ID") or r.get("sheet_id") or "").strip()
        if not sheet_id:
            continue
        if series_lc in slug or series_lc in show:
            out.append((f"{slug or show}_{ep or '?'}", sheet_id))
    out.sort()
    return out


def apply_missing(sheets_api, sheet_id: str, missing: list[Protection]) -> int:
    """Add missing protected ranges to a target sheet. Returns count
    successfully applied. Editors are NOT copied — caller must hand
    over editor permissions separately (Sheets API requires explicit
    email lists; we don't have those without an extra round-trip)."""
    if not missing:
        return 0
    # Need a sheet_id (numeric tab id) per tab name
    meta = sheets_api.spreadsheets().get(
        spreadsheetId=sheet_id,
        includeGridData=False,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    title_to_sid = {s["properties"]["title"]: s["properties"]["sheetId"]
                     for s in meta.get("sheets", [])}

    requests = []
    for p in missing:
        tab_sid = title_to_sid.get(p.tab)
        if tab_sid is None:
            print(f"    ✗ tab {p.tab!r} doesn't exist on this sheet — skip")
            continue
        # Parse the A1 range back into a GridRange
        gr = _a1_to_range(p.range_a1, tab_sid)
        if gr is None:
            print(f"    ✗ couldn't parse range {p.range_a1!r} — skip")
            continue
        requests.append({
            "addProtectedRange": {
                "protectedRange": {
                    "range": gr,
                    "description": p.description or "auto-applied via audit_protected_ranges.py",
                    "warningOnly": p.warning_only,
                }
            }
        })
    if not requests:
        return 0
    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": requests},
    ).execute()
    return len(requests)


def _a1_to_range(a1: str, sheet_id: int) -> dict | None:
    """Inverse of _range_to_a1. Returns a GridRange dict or None on
    parse failure. Doesn't handle whole-tab ('ALL') protections."""
    if a1 == "ALL":
        return {"sheetId": sheet_id}
    m = re.match(r"^([A-Z]+)(\d+)(?::([A-Z]*)(\d*))?$", a1.strip())
    if not m:
        return None
    sc, sr, ec, er = m.group(1), m.group(2), m.group(3), m.group(4)

    def col_to_idx(s: str) -> int:
        n = 0
        for ch in s:
            n = n * 26 + (ord(ch) - 64)
        return n - 1

    out = {"sheetId": sheet_id}
    out["startColumnIndex"] = col_to_idx(sc)
    out["startRowIndex"] = int(sr) - 1
    if ec:
        out["endColumnIndex"] = col_to_idx(ec) + 1
    else:
        # Open-ended col → assume single column
        out["endColumnIndex"] = col_to_idx(sc) + 1
    if er:
        out["endRowIndex"] = int(er)
    # Open-ended row → leave endRowIndex unset (means "to end of grid")
    return out


def fmt_protections(ps: list[Protection]) -> str:
    if not ps:
        return "    (none)"
    return "\n".join(
        f"    [{p.tab}] {p.range_a1}  ({'warning-only' if p.warning_only else 'enforced'})"
        f"  — {p.description[:80]}" for p in ps)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--master", help="Master Projects sheet ID (auto-discovers eps)")
    g.add_argument("--sheets", nargs="+",
                    help="Hand-picked sheet IDs / URLs in episode order (first is reference)")
    ap.add_argument("--series", help="Series slug filter (with --master)")
    ap.add_argument("--apply", action="store_true",
                    help="Write missing protections to later eps so they match the reference")
    args = ap.parse_args()

    creds = get_credentials()
    gc = gspread.authorize(creds)
    sheets_api = build("sheets", "v4", credentials=creds)

    if args.master:
        if not args.series:
            ap.error("--series required when --master is used")
        eps = episodes_from_master(gc, parse_sheet_id(args.master), args.series)
        if not eps:
            sys.exit(f"No eps found for series {args.series!r} in master")
    else:
        eps = [(parse_sheet_id(s), parse_sheet_id(s)) for s in args.sheets]

    print(f"\nAuditing {len(eps)} episode sheet(s)…")
    for slug, sid in eps:
        print(f"  - {slug}: {sid}")

    if len(eps) < 2:
        sys.exit("Need at least 2 sheets to compare")

    ref_slug, ref_id = eps[0]
    print(f"\nReference: {ref_slug} ({ref_id})")
    try:
        ref_protections = list_protections(sheets_api, ref_id)
    except Exception as e:
        sys.exit(f"Couldn't read reference protections: {e}")
    print(f"  → {len(ref_protections)} protected range(s) on reference")
    print(fmt_protections(ref_protections))

    drift_total = 0
    fixed_total = 0
    for slug, sid in eps[1:]:
        print(f"\n=== {slug} ===")
        try:
            tgt = list_protections(sheets_api, sid)
        except Exception as e:
            print(f"  ✗ couldn't read: {e}")
            drift_total += 1
            continue
        missing, extra = diff_protections(ref_protections, tgt)
        if not missing and not extra:
            print(f"  ✓ in sync ({len(tgt)} protections)")
            continue
        drift_total += 1
        if missing:
            print(f"  MISSING from {slug} (present in reference):")
            print(fmt_protections(missing))
        if extra:
            print(f"  EXTRA on {slug} (not in reference):")
            print(fmt_protections(extra))
        if args.apply and missing:
            try:
                applied = apply_missing(sheets_api, sid, missing)
                print(f"  → applied {applied} missing protection(s)")
                fixed_total += applied
            except Exception as e:
                print(f"  ✗ apply failed: {e}")

    print(f"\nSummary: {drift_total} ep(s) drifted from reference"
          f"{f', {fixed_total} fixes applied' if args.apply else ''}")
    sys.exit(0 if drift_total == 0 else 2)


if __name__ == "__main__":
    main()

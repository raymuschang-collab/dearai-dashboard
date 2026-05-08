#!/usr/bin/env python3
"""
migrate_sp_byrow.py — Migrate Storyboard Prompts!C and !D to single-cell
BYROW arrayformulas that auto-extend when the team inserts new rows.

The legacy schema put a per-row formula in every C{r} and D{r}, so when a
producer broke a set into more sets (added rows in column A), columns C/D
stayed blank for the new rows until somebody manually dragged the formula
down. This migration replaces N per-row formulas with ONE formula at C2
(and one at D2) that spreads down based on column A.

Idempotent: detects whether the target cell already holds a BYROW formula
and skips re-writes when nothing has drifted.

Usage:
    python3 migrate_sp_byrow.py --sheet <SHEET_ID_OR_URL>
    python3 migrate_sp_byrow.py --sheet <SHEET_ID> --dry-run
    python3 migrate_sp_byrow.py --all-in-folder <PARENT_FOLDER_ID>

Schema assumption: 9-col SP (A=Set#, B=Shot Range, C=Storyboard Prompt,
D=Bahasa Prompt, E=Drive Folder, F=Status, G=Iter1, H=Iter2, I=Error).
The migration only touches C and D; everything else is preserved.

After migration, columns C and D each hold a SINGLE formula at row 2 that
fills down to the last row with a Set # in column A. New rows added to A
auto-populate C and D with no producer action.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import gspread
from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).parent))
from auth import get_credentials  # type: ignore


SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
FOLDER_URL_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")


def parse_id(s: str, kind: str) -> str:
    pat = SHEETS_URL_RE if kind == "sheet" else FOLDER_URL_RE
    m = pat.search(s)
    return m.group(1) if m else s.strip()


def find_shotlist_tab_name(sh) -> str | None:
    """Whatever non-Storyboard-Prompts tab holds the per-shot rows."""
    skip = {"Storyboard Prompts", "Video Prompts", "CHARACTERS", "LOCATIONS",
            "PROPS", "COSTUME", "EFFECTS", "Asset Library", "README", "_README"}
    for ws in sh.worksheets():
        if ws.title.startswith("_"):
            continue
        if ws.title not in skip:
            return ws.title
    return None


def storyboard_prompt_byrow(shotlist_tab: str) -> str:
    """Single cell formula for C2 — BYROW over A2:A returns one storyboard
    prompt per row. Open-ended range A2:A means future inserts auto-fill.
    Empty rows in A produce empty strings (BYROW evaluates LAMBDA but the
    IF skips them)."""
    safe = shotlist_tab.replace("'", "''")
    # Build the per-set body that walks shots offset 1..5 from the set #.
    # Each offset uses INDIRECT against the shotlist tab so it tracks new
    # rows added to the shotlist as well.
    parts = []
    for offset in range(1, 6):
        parts.append(
            f'IF(INDIRECT("\'{safe}\'!A"&((setN-1)*5+{offset}))<>"",'
            f'"Shot "&INDIRECT("\'{safe}\'!A"&((setN-1)*5+{offset}))&": "'
            f'&INDIRECT("\'{safe}\'!P"&((setN-1)*5+{offset})),"")'
        )
    body = ",".join(parts)
    return (
        '=BYROW(A2:A,LAMBDA(setN,IF(setN="","","Shot with arri 35."&CHAR(10)'
        '&"No Music."&CHAR(10)'
        '&"Stick figure pencil storyboard with foreground, midground and background depth."&CHAR(10)'
        '&"Create a 5 panel storyboard based on the following shots. '
        'Ensure each shot is labelled by number, with a label of the camera '
        'angle/movement centred at the bottom of the panel. The storyboard '
        'should be divided by black lines. And the panels should flow '
        'sequentially:"&CHAR(10)&CHAR(10)'
        f'&TEXTJOIN(CHAR(10)&CHAR(10),TRUE,{body}))))'
    )


def bahasa_byrow() -> str:
    """Single cell formula for D2 — translates each row's C value into id.
    GOOGLETRANSLATE vectorizes cleanly inside ARRAYFORMULA, so we use that
    pattern instead of BYROW (BYROW's LAMBDA receives only the cell value,
    not the row index, which makes pulling the matching C{row} awkward).
    Spreads down for as long as A has values."""
    return (
        '=ARRAYFORMULA(IF(A2:A="","",'
        'GOOGLETRANSLATE(C2:C,"en","id")))'
    )


def detect_existing_byrow(ws) -> tuple[bool, bool]:
    """Returns (c2_is_byrow, d2_is_byrow). Reads via FORMULA render so we
    see literal '=BYROW(...)' rather than the evaluated string."""
    try:
        c2 = ws.acell("C2", value_render_option="FORMULA").value or ""
        d2 = ws.acell("D2", value_render_option="FORMULA").value or ""
    except Exception:
        return False, False
    return c2.upper().startswith("=BYROW("), d2.upper().startswith("=BYROW(")


def last_set_row(ws) -> int:
    """Last row index (1-based) where column A holds a numeric set #.
    Used to scope the wipe before writing the new array formula."""
    col_a = ws.col_values(1)
    last = 1
    for i, v in enumerate(col_a, start=1):
        if i == 1:
            continue
        s = (v or "").strip()
        # A is either "=ROW()-1" formula (resolves to 1, 2, …) or a literal
        # integer. Either way, FORMATTED_VALUE returns the digit string.
        if s.isdigit():
            last = i
    return last


def migrate_sheet(gc, sheet_id: str, *, dry_run: bool = False) -> bool:
    sh = gc.open_by_key(sheet_id)
    print(f"\n=== {sh.title} ===")
    print(f"  id={sheet_id}")

    try:
        ws = sh.worksheet("Storyboard Prompts")
    except gspread.WorksheetNotFound:
        print(f"  ✗ no 'Storyboard Prompts' tab — skipping")
        return False

    shotlist_tab = find_shotlist_tab_name(sh)
    if not shotlist_tab:
        print(f"  ✗ no shotlist tab detected — skipping")
        return False
    print(f"  shotlist tab: {shotlist_tab!r}")

    c2_byrow, d2_arrayformula = detect_existing_byrow(ws)
    last = last_set_row(ws)
    print(f"  last set row: {last}  C2={'BYROW' if c2_byrow else 'legacy'}  "
          f"D2={'ARRAYFORMULA/BYROW' if d2_arrayformula else 'legacy'}")

    # Re-detect D2 against ARRAYFORMULA too (current preferred form)
    try:
        d2_raw = ws.acell("D2", value_render_option="FORMULA").value or ""
    except Exception:
        d2_raw = ""
    d2_already = d2_raw.upper().startswith("=ARRAYFORMULA(") or d2_arrayformula

    if c2_byrow and d2_already:
        print(f"  ✓ already migrated — no-op")
        return True

    new_c = storyboard_prompt_byrow(shotlist_tab)
    new_d = bahasa_byrow()

    if dry_run:
        print(f"  [dry-run] would clear C3:D{max(last, 200)} and write BYROW at C2/D2")
        print(f"  [dry-run] C2 = {new_c[:120]}…")
        print(f"  [dry-run] D2 = {new_d[:120]}…")
        return True

    # Wipe C3:D{lastrow_safety} so the array formula has a clean spread
    # zone. Use a generous bottom (200) so future row-inserts up to that
    # depth still auto-fill without re-running the migration.
    wipe_bottom = max(last + 50, 200)
    print(f"  → wiping C3:D{wipe_bottom} (so BYROW can spread cleanly)…")
    empty = [["", ""] for _ in range(wipe_bottom - 2)]
    if empty:
        ws.update(range_name=f"C3:D{wipe_bottom}", values=empty,
                  value_input_option="USER_ENTERED")

    # Write the two BYROW anchors. USER_ENTERED so the leading `=` is
    # interpreted as a formula and not a string literal.
    print(f"  → writing BYROW formula to C2…")
    ws.update(range_name="C2", values=[[new_c]],
              value_input_option="USER_ENTERED")
    print(f"  → writing BYROW formula to D2…")
    ws.update(range_name="D2", values=[[new_d]],
              value_input_option="USER_ENTERED")
    print(f"  ✓ migrated — C/D now auto-extend on row-inserts to A")
    return True


def list_sheets_in_folder(drive, folder_id: str) -> list[tuple[str, str]]:
    """Returns [(sheet_id, name), ...] for all spreadsheets in the folder."""
    q = (f"'{folder_id}' in parents and trashed=false "
         f"and mimeType='application/vnd.google-apps.spreadsheet'")
    files = drive.files().list(q=q, fields="files(id,name)",
                                pageSize=100).execute().get("files", [])
    return [(f["id"], f["name"]) for f in files]


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sheet", help="Single sheet ID or URL")
    g.add_argument("--all-in-folder", help="Folder ID containing episode sheets")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print planned changes without writing")
    args = ap.parse_args()

    creds = get_credentials()
    gc = gspread.authorize(creds)

    if args.sheet:
        ok = migrate_sheet(gc, parse_id(args.sheet, "sheet"),
                            dry_run=args.dry_run)
        sys.exit(0 if ok else 1)

    drive = build("drive", "v3", credentials=creds)
    folder_id = parse_id(args.all_in_folder, "folder")
    sheets = list_sheets_in_folder(drive, folder_id)
    print(f"Found {len(sheets)} sheet(s) in folder {folder_id}")
    failures = 0
    for sid, name in sheets:
        try:
            ok = migrate_sheet(gc, sid, dry_run=args.dry_run)
            if not ok:
                failures += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failures += 1
    print(f"\nDone — {len(sheets)-failures}/{len(sheets)} migrated successfully")
    sys.exit(0 if failures == 0 else 2)


if __name__ == "__main__":
    main()

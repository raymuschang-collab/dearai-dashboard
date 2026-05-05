#!/usr/bin/env python3
"""
Build the Storyboard Prompts tab + Drive `storyboards/set-NN/` subfolders for a
microdrama episode shotlist (v2.2 schema).

Also adds the Bahasa Prompt column to both tabs:
  - Tab 1 (Shotlist): column Q = GOOGLETRANSLATE of column P
  - Tab 2 (Storyboard Prompts): column D = GOOGLETRANSLATE of column C

Idempotent. Existing folders are reused. Missing columns are added in place.
The Storyboard Prompts tab is fully rebuilt only with --force; otherwise an
existing tab is migrated to the 9-column schema non-destructively.

9-column Storyboard Prompts schema:
    A: Set #
    B: Shot Range
    C: Storyboard Prompt   (English, formula)
    D: Bahasa Prompt       (formula, GOOGLETRANSLATE)
    E: Drive Folder
    F: Status              (Pending / Generating / Done / Failed)
    G: Iter 1 URL
    H: Iter 2 URL
    I: Error

Usage:
    python3 storyboard_build.py --sheet <sheet-id-or-url>
    python3 storyboard_build.py --all-in-folder <parent-folder-id>
    python3 storyboard_build.py --sheet <id> --force
"""
from __future__ import annotations

import argparse
import math
import re
import sys

import gspread
from googleapiclient.discovery import build

from auth import get_credentials


SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
FOLDER_URL_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")

TAB2_HEADERS = [
    "Set #",
    "Shot Range",
    "Storyboard Prompt",
    "Bahasa Prompt",
    "Drive Folder",
    "Status",
    "Iter 1 URL",
    "Iter 2 URL",
    "Error",
]

TAB3_HEADERS = [
    "Shot #",
    "Video Prompt",
    "Bahasa Prompt",
    "Drive Folder",
    "Status",
    "Iter 1 URL",
    "Iter 2 URL",
    "Error",
]


def parse_sheet_id(s: str) -> str:
    m = SHEETS_URL_RE.search(s)
    return m.group(1) if m else s.strip()


def parse_folder_id(s: str) -> str:
    m = FOLDER_URL_RE.search(s)
    return m.group(1) if m else s.strip()


def derive_episode_folder_name(sheet_name: str) -> str:
    """Derive a per-episode folder name from a sheet name by stripping common suffixes.

    Examples:
      "EP01_Pelarian_Pertama_shotlist_v2_2"           → "EP01_Pelarian_Pertama"
      "Ep 1 - The Isfet Spawn (v2.2)"                 → "Ep 1 - The Isfet Spawn"
      "Ep 1 - Ponsel Itu (v2.1 Atomized)"             → "Ep 1 - Ponsel Itu"
      "NLB - Can AI Help You"                         → "NLB - Can AI Help You"
    """
    name = sheet_name
    # Strip trailing parenthetical version markers like " (v2.2)" or " (v2.1 Atomized)"
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    # Strip trailing "_shotlist", "_v2_2", "_v2.2", etc. (any combination)
    while True:
        new = re.sub(r"(_shotlist)?(_v\d+[._]\d+)?$", "", name, flags=re.IGNORECASE)
        if new == name:
            break
        name = new
    return name.strip() or sheet_name  # fall back to original if we stripped everything


def storyboard_prompt_formula(shotlist_tab: str) -> str:
    """Column C formula — V1 stick-figure preamble + 5 per-shot prompts."""
    safe = shotlist_tab.replace("'", "''")
    parts = []
    for offset in range(2, 7):
        parts.append(
            f'IF(INDIRECT("\'{safe}\'!A"&((ROW()-2)*5+{offset}))<>"",'
            f'"Shot "&INDIRECT("\'{safe}\'!A"&((ROW()-2)*5+{offset}))&": "'
            f'&INDIRECT("\'{safe}\'!P"&((ROW()-2)*5+{offset})),"")'
        )
    body = ",".join(parts)
    return (
        '="Shot with arri 35."&CHAR(10)'
        '&"No Music."&CHAR(10)'
        '&"Stick figure pencil storyboard with foreground, midground and background depth."&CHAR(10)'
        '&"Create a 5 panel storyboard based on the following shots. '
        'Ensure each shot is labelled by number, with a label of the camera '
        'angle/movement centred at the bottom of the panel. The storyboard '
        'should be divided by black lines. And the panels should flow '
        'sequentially:"&CHAR(10)&CHAR(10)'
        f'&TEXTJOIN(CHAR(10)&CHAR(10),TRUE,{body})'
    )


def get_or_create_folder(drive, parent_id: str, name: str) -> tuple[str, bool]:
    safe = name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and trashed=false "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and name='{safe}'"
    )
    res = drive.files().list(q=q, fields="files(id,name)", pageSize=10).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"], False
    body = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = drive.files().create(body=body, fields="id").execute()
    return created["id"], True


def find_shotlist_tab(sh) -> "gspread.Worksheet | None":
    for ws in sh.worksheets():
        if ws.title != "Storyboard Prompts":
            return ws
    return None


def count_shots(ws) -> int:
    col_a = ws.col_values(1)
    n = 0
    for v in col_a[1:]:
        v = (v or "").strip()
        if v.isdigit():
            n = max(n, int(v))
    return n


def shotlist_prompt_formula(r: int) -> str:
    """v2.2 Prompt formula for column P, row r."""
    return (
        f'="No music. Dialogue in "&H{r}&" accent."&CHAR(10)'
        f'&A{r}&", "&B{r}&"s, "&C{r}&", "&D{r}&", "&F{r}'
        f'&IF(G{r}="",IF(I{r}="","",", ("&I{r}&")"),", "&G{r}&IF(I{r}="",""," ("&I{r}&")"))'
        f'&IF(J{r}="",".", ", "&J{r}&".")'
    )


def ensure_shotlist_prompt_col(ws) -> str:
    """Tab 1: backfill column P (Prompt) with the v2.2 formula on rows missing it.

    Self-healing for sheets where the shotlist creator forgot to drop the
    Prompt formula. Returns one of: "filled_N", "already_present", "skipped_no_data".
    """
    shot_count = count_shots(ws)
    if shot_count == 0:
        return "skipped_no_data"

    # Read current column P (formulas, not rendered)
    current_p = ws.batch_get(
        [f"P2:P{shot_count + 1}"], value_render_option="FORMULA"
    )[0]
    # Pad to length
    while len(current_p) < shot_count:
        current_p.append([])

    rows_to_fill = []
    for i, row in enumerate(current_p):
        cell = (row[0] if row else "").strip()
        if not cell:
            rows_to_fill.append(i + 2)  # sheet row number

    if not rows_to_fill:
        return "already_present"

    # Batch-write only the missing rows
    updates = [
        {
            "range": f"P{r}",
            "values": [[shotlist_prompt_formula(r)]],
        }
        for r in rows_to_fill
    ]
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    return f"filled_{len(rows_to_fill)}"


def ensure_shotlist_bahasa_col(ws, *, hide: bool = True) -> str:
    """Tab 1: add column Q = Bahasa Prompt (GOOGLETRANSLATE of P) if missing.

    Hides column Q by default — it's a reference for the team, not the active
    edit surface. Pass hide=False to keep visible.

    Returns one of: "added", "already_present", "skipped_no_p".
    """
    headers = ws.row_values(1)
    # P is column 16; Q is column 17
    already = len(headers) >= 17 and headers[16] == "Bahasa Prompt"

    shot_count = count_shots(ws)
    if shot_count == 0:
        return "skipped_no_p"

    if not already:
        # Make sure the worksheet has at least 17 columns
        if ws.col_count < 17:
            ws.add_cols(17 - ws.col_count)

        ws.update(range_name="Q1", values=[["Bahasa Prompt"]])
        formulas = [[f'=GOOGLETRANSLATE(P{r},"en","id")'] for r in range(2, shot_count + 2)]
        ws.update(
            range_name=f"Q2:Q{shot_count + 1}",
            values=formulas,
            value_input_option="USER_ENTERED",
        )

    if hide:
        _hide_column(ws, col_index_zero_based=16)  # column Q

    return "already_present" if already else "added"


def _hide_column(ws, *, col_index_zero_based: int):
    """Hide a single column (idempotent — no-op if already hidden)."""
    sh = ws.spreadsheet
    sh.batch_update({
        "requests": [{
            "updateDimensionProperties": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "COLUMNS",
                    "startIndex": col_index_zero_based,
                    "endIndex": col_index_zero_based + 1,
                },
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        }]
    })


def detect_tab2_schema(ws) -> str:
    """Return one of: "v9" (current), "v6" (legacy), "empty", "unknown"."""
    headers = ws.row_values(1)
    if not headers:
        return "empty"
    if len(headers) >= 9 and headers[3] == "Bahasa Prompt":
        return "v9"
    if (
        len(headers) >= 6
        and headers[2] == "Storyboard Prompt"
        and headers[3] == "Drive Folder"
    ):
        return "v6"
    return "unknown"


def migrate_tab2_v6_to_v9(sh, ws):
    """Insert column D + add columns H/I headers + add Bahasa formulas.

    Test data in old F (Iter 1) shifts to new G — gspread handles it.
    """
    sheet_id = ws.id
    # Insert one column at index 3 (0-based — this becomes column D)
    body = {
        "requests": [
            {
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 3,
                        "endIndex": 4,
                    },
                    "inheritFromBefore": False,
                }
            }
        ]
    }
    sh.batch_update(body)

    # Refresh col_count
    ws = sh.worksheet(ws.title)
    if ws.col_count < 9:
        ws.add_cols(9 - ws.col_count)

    # Update headers: D = Bahasa Prompt, G = Iter 1 URL (renamed), H = Iter 2 URL, I = Error
    ws.update(
        range_name="D1:I1",
        values=[
            [
                "Bahasa Prompt",
                "Drive Folder",  # was D before insert; preserved value
                "Status",         # was E
                "Iter 1 URL",     # was F (Generated Image URL); rename
                "Iter 2 URL",
                "Error",
            ]
        ],
    )

    # Backfill Bahasa formula for all data rows
    a_col = ws.col_values(1)
    n_rows = sum(1 for v in a_col[1:] if (v or "").strip())
    if n_rows > 0:
        formulas = [[f'=GOOGLETRANSLATE(C{r},"en","id")'] for r in range(2, n_rows + 2)]
        ws.update(
            range_name=f"D2:D{n_rows + 1}",
            values=formulas,
            value_input_option="USER_ENTERED",
        )


def video_prompt_formula(shotlist_tab: str) -> str:
    """Column B formula for Video Prompts tab — adds video preamble to per-shot P."""
    safe = shotlist_tab.replace("'", "''")
    return (
        '="Shot with arri 35."&CHAR(10)'
        f'&INDIRECT("\'{safe}\'!P"&ROW())'
    )


def detect_tab3_schema(ws) -> str:
    """Return 'v8' (current) / 'empty' / 'unknown'."""
    headers = ws.row_values(1)
    if not headers:
        return "empty"
    if (
        len(headers) >= 8
        and headers[0] == "Shot #"
        and headers[1] == "Video Prompt"
        and headers[2] == "Bahasa Prompt"
    ):
        return "v8"
    return "unknown"


def build_tab3_fresh(sh, shotlist_tab_name: str, shot_count: int, shot_folder_ids: list[str]):
    """Returns the newly created Video Prompts worksheet."""
    new_ws = sh.add_worksheet(title="Video Prompts", rows=shot_count + 5, cols=8)
    new_ws.update(range_name="A1:H1", values=[TAB3_HEADERS])

    formula_b = video_prompt_formula(shotlist_tab_name)
    rows = []
    for i in range(shot_count):
        sheet_row = i + 2
        rows.append([
            "=ROW()-1",
            formula_b,
            f'=GOOGLETRANSLATE(B{sheet_row},"en","id")',
            f"https://drive.google.com/drive/folders/{shot_folder_ids[i]}",
            "Pending",
            "",
            "",
            "",
        ])
    new_ws.update(
        range_name=f"A2:H{shot_count + 1}",
        values=rows,
        value_input_option="USER_ENTERED",
    )
    return new_ws


def build_tab2_fresh(sh, shotlist_tab_name: str, set_count: int, set_folder_ids: list[str]):
    """Returns the newly created worksheet so the caller can apply formatting (e.g. hide cols)."""
    new_ws = sh.add_worksheet(title="Storyboard Prompts", rows=set_count + 5, cols=9)
    new_ws.update(range_name="A1:I1", values=[TAB2_HEADERS])

    formula_c = storyboard_prompt_formula(shotlist_tab_name)
    rows = [
        [
            "=ROW()-1",
            '=((ROW()-2)*5+1)&"-"&((ROW()-2)*5+5)',
            formula_c,
            f'=GOOGLETRANSLATE(C{i + 2},"en","id")',
            f"https://drive.google.com/drive/folders/{set_folder_ids[i]}",
            "Pending",
            "",
            "",
            "",
        ]
        for i in range(set_count)
    ]
    new_ws.update(
        range_name=f"A2:I{set_count + 1}",
        values=rows,
        value_input_option="USER_ENTERED",
    )
    return new_ws




def build_for_sheet(
    gc,
    drive,
    sheet_id: str,
    *,
    force: bool = False,
    dry_run: bool = False,
    per_sheet_folder: bool = False,
    episode_name: str | None = None,
    asset_parent_id: str | None = None,
) -> bool:
    sh = gc.open_by_key(sheet_id)
    print(f"\n=== {sh.title} ===")
    print(f"  id={sheet_id}")

    shotlist_ws = find_shotlist_tab(sh)
    if shotlist_ws is None:
        print("  ERROR: no shotlist tab found")
        return False
    print(f"  shotlist tab: {shotlist_ws.title!r}")

    shot_count = count_shots(shotlist_ws)
    if shot_count == 0:
        print("  ERROR: no atomized shots detected in column A")
        return False
    set_count = math.ceil(shot_count / 5)
    last = shot_count - (set_count - 1) * 5
    partial = "" if last == 5 else f" (last set has {last} shots)"
    print(f"  shots: {shot_count}  →  sets: {set_count}{partial}")

    meta = drive.files().get(fileId=sheet_id, fields="parents,name").execute()
    if not meta.get("parents"):
        print("  ERROR: sheet has no parent folder")
        return False
    parent_id = meta["parents"][0]

    # Resolve where storyboards/ and videos/ should live
    if asset_parent_id:
        effective_parent = asset_parent_id
        print(f"  asset parent: {effective_parent} (--asset-parent override)")
    elif per_sheet_folder:
        ep_name = episode_name or derive_episode_folder_name(meta["name"])
        ep_folder, ep_created = get_or_create_folder(drive, parent_id, ep_name)
        effective_parent = ep_folder
        print(f"  per-sheet asset folder: {ep_name!r}  {'CREATED' if ep_created else 'reused'}  id={ep_folder}")
    else:
        effective_parent = parent_id

    if dry_run:
        print(f"  [dry-run] would ensure storyboards/ + {set_count} set folders under {parent_id}")
        existing = next((w for w in sh.worksheets() if w.title == "Storyboard Prompts"), None)
        if existing:
            schema = detect_tab2_schema(existing)
            print(f"  [dry-run] tab 2 schema: {schema}")
        else:
            print(f"  [dry-run] would create tab 2 with 9-col schema")
        # Tab 1 Bahasa
        headers = shotlist_ws.row_values(1)
        if len(headers) >= 17 and headers[16] == "Bahasa Prompt":
            print(f"  [dry-run] tab 1 column Q (Bahasa) already present")
        else:
            print(f"  [dry-run] would add tab 1 column Q (Bahasa Prompt)")
        return True

    # Create / reuse storyboards folder
    sb_folder, sb_created = get_or_create_folder(drive, effective_parent, "storyboards")
    print(f"  storyboards/ {'CREATED' if sb_created else 'reused'}  id={sb_folder}")

    # Create / reuse set folders
    set_folder_ids = []
    n_created = 0
    for i in range(1, set_count + 1):
        fid, created = get_or_create_folder(drive, sb_folder, f"set-{i:02d}")
        set_folder_ids.append(fid)
        if created:
            n_created += 1
    print(f"  set folders: {set_count} ready ({n_created} created, {set_count - n_created} reused)")

    # Tab 1: ensure Prompt formula in column P (self-healing for partial shotlists)
    prompt_status = ensure_shotlist_prompt_col(shotlist_ws)
    print(f"  tab 1 Prompt col (P): {prompt_status}")

    # Tab 1: ensure Bahasa column Q (and hide it — reference column, not active edit surface)
    bahasa_status = ensure_shotlist_bahasa_col(shotlist_ws)
    print(f"  tab 1 Bahasa col (Q): {bahasa_status} (hidden)")

    # Tab 2: build fresh / migrate / leave alone
    existing = next((w for w in sh.worksheets() if w.title == "Storyboard Prompts"), None)
    if existing and force:
        sh.del_worksheet(existing)
        existing = None
        print("  removed existing tab (--force)")

    if existing is None:
        new_ws = build_tab2_fresh(sh, shotlist_ws.title, set_count, set_folder_ids)
        _hide_column(new_ws, col_index_zero_based=3)  # column D = Bahasa Prompt
        print(f"  ✓ tab 2 built fresh: 9 cols × {set_count} rows (Bahasa col D hidden)")
        # Fall through to tab 3 logic
    else:
        schema = detect_tab2_schema(existing)
        if schema == "v9":
            a_col = existing.col_values(1)
            n_rows = sum(1 for v in a_col[1:] if (v or "").strip())
            _hide_column(existing, col_index_zero_based=3)
            if n_rows == set_count:
                print(f"  tab 2 already v9 with {n_rows} rows — leaving alone, ensured Bahasa col D hidden")
            else:
                print(f"  tab 2 v9 but row count {n_rows} ≠ expected {set_count}; use --force to rebuild")
                return False
        elif schema == "v6":
            print(f"  tab 2 detected as v6 (legacy 6-col); migrating to v9...")
            migrate_tab2_v6_to_v9(sh, existing)
            existing = sh.worksheet("Storyboard Prompts")
            _hide_column(existing, col_index_zero_based=3)
            print(f"  ✓ tab 2 migrated v6 → v9 (Bahasa col D hidden)")
        else:
            print(f"  tab 2 schema unrecognized ({schema}); use --force to rebuild")
            return False

    # ============================================================
    # Tab 3: Video Prompts (one row per shot)
    # ============================================================

    # Create / reuse videos/ folder
    videos_folder, videos_created = get_or_create_folder(drive, effective_parent, "videos")
    print(f"  videos/ {'CREATED' if videos_created else 'reused'}  id={videos_folder}")

    # Create / reuse per-shot folders (videos/shot-NN/)
    print(f"  ensuring {shot_count} per-shot folders (videos/shot-NN/)...")
    shot_folder_ids = []
    n_shot_created = 0
    for i in range(1, shot_count + 1):
        fid, created = get_or_create_folder(drive, videos_folder, f"shot-{i:02d}")
        shot_folder_ids.append(fid)
        if created:
            n_shot_created += 1
    print(f"  shot folders: {shot_count} ready ({n_shot_created} created, {shot_count - n_shot_created} reused)")

    # Tab 3 build / migrate
    existing_tab3 = next((w for w in sh.worksheets() if w.title == "Video Prompts"), None)
    if existing_tab3 and force:
        sh.del_worksheet(existing_tab3)
        existing_tab3 = None
        print("  removed existing tab 3 (--force)")

    if existing_tab3 is None:
        new_ws3 = build_tab3_fresh(sh, shotlist_ws.title, shot_count, shot_folder_ids)
        _hide_column(new_ws3, col_index_zero_based=2)  # column C = Bahasa Prompt
        print(f"  ✓ tab 3 built fresh: 8 cols × {shot_count} rows (Bahasa col C hidden)")
    else:
        schema3 = detect_tab3_schema(existing_tab3)
        if schema3 == "v8":
            a_col3 = existing_tab3.col_values(1)
            n_rows3 = sum(1 for v in a_col3[1:] if (v or "").strip())
            _hide_column(existing_tab3, col_index_zero_based=2)
            if n_rows3 == shot_count:
                print(f"  tab 3 already v8 with {n_rows3} rows — leaving alone, ensured Bahasa col C hidden")
            else:
                print(f"  tab 3 v8 but row count {n_rows3} ≠ expected {shot_count}; use --force to rebuild")
                return False
        else:
            print(f"  tab 3 schema unrecognized ({schema3}); use --force to rebuild")
            return False

    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--sheet", help="Sheet ID or URL")
    src.add_argument("--all-in-folder", help="Parent Drive folder ID — process every Sheet inside")
    ap.add_argument("--force", action="store_true", help="Rebuild Storyboard Prompts tab even if populated")
    ap.add_argument("--dry-run", action="store_true", help="Plan only; do not write")
    # Asset folder placement
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument(
        "--per-sheet-folder", action="store_true",
        help="Create a per-episode subfolder for storyboards/ + videos/ (default for --all-in-folder)",
    )
    grp.add_argument(
        "--no-per-sheet-folder", action="store_true",
        help="Don't create per-episode subfolder; use sheet's parent directly (default for --sheet)",
    )
    grp.add_argument(
        "--asset-parent",
        help="Override: drop storyboards/ + videos/ inside this exact folder ID",
    )
    ap.add_argument(
        "--episode-name",
        help="Override the per-episode subfolder name (default: auto-derived from sheet name)",
    )
    args = ap.parse_args()

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    # Resolve per-sheet-folder default based on mode
    if args.per_sheet_folder:
        per_sheet = True
    elif args.no_per_sheet_folder:
        per_sheet = False
    elif args.asset_parent:
        per_sheet = False  # asset_parent overrides everything
    else:
        # Default: True for --all-in-folder, False for single --sheet
        per_sheet = bool(args.all_in_folder)

    asset_parent_id = parse_folder_id(args.asset_parent) if args.asset_parent else None

    if args.sheet:
        sheet_id = parse_sheet_id(args.sheet)
        ok = build_for_sheet(
            gc, drive, sheet_id,
            force=args.force, dry_run=args.dry_run,
            per_sheet_folder=per_sheet,
            episode_name=args.episode_name,
            asset_parent_id=asset_parent_id,
        )
        sys.exit(0 if ok else 1)

    folder_id = parse_folder_id(args.all_in_folder)
    res = drive.files().list(
        q=(
            f"'{folder_id}' in parents and trashed=false "
            f"and mimeType='application/vnd.google-apps.spreadsheet'"
        ),
        fields="files(id,name)",
        pageSize=200,
    ).execute()
    sheets = res.get("files", [])
    print(f"Found {len(sheets)} sheets in folder {folder_id}")
    print(f"Mode: per-sheet-folder={per_sheet}  asset-parent-override={asset_parent_id or 'none'}")
    results = []
    for f in sheets:
        ok = build_for_sheet(
            gc, drive, f["id"],
            force=args.force, dry_run=args.dry_run,
            per_sheet_folder=per_sheet,
            episode_name=args.episode_name,
            asset_parent_id=asset_parent_id,
        )
        results.append((f["name"], ok))
    print("\n=== SUMMARY ===")
    for name, ok in results:
        print(f"  {'OK ' if ok else 'FAIL'}  {name}")
    sys.exit(0 if all(ok for _, ok in results) else 1)


if __name__ == "__main__":
    main()

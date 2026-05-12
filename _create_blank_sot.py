"""Create a blank SOT Google Sheet + Drive folder structure for a new show.

What this builds (one-shot):

  Drive
   └── <SHOW_NAME>/
        ├── storyboards/     ← per-set folders land here when storyboard_build.py runs
        ├── videos/          ← per-set vidgen MP4s land here
        └── <show>_SOT       ← the spreadsheet (returned for SERIES_CONFIG wiring)

  Spreadsheet tabs:
    Shotlist               — v2.2 + Bahasa + Refs Detected (20 cols, empty rows)
    Storyboard Prompts     — 14-col extended (header at row 10, globals B1-B8)
    Video Prompts          — 8-col (camera/audio/setting globals B1-B3 + Bahasa B4-B6)
    CHARACTERS             — bible (rows 1+, w/ Iter 1/2 URL cols + Aliases pre-stub)
    LOCATIONS              — bible (header row 4, Aliases col O)
    COSTUME / PROPS / EFFECTS — bibles (header row 5)
    Asset Library          — BytePlus tracker (header row 4)

  Live formulas:
    Shotlist!Q       = v2.2 prompt assembler (per-row)
    Shotlist!R       = GOOGLETRANSLATE(Q, "en", "id")
    Storyboard Prompts!C — pencil-on-paper prompt formula (per-set 5 shots)
    Storyboard Prompts!D — GOOGLETRANSLATE(C, "en", "id")

  Locked global text (placeholder — show team customizes per show):
    Storyboard Prompts!B1-B8 — "Shot with Arri 35.", "No Music.", style anchor, etc.
    Video Prompts!B1-B6 — camera + audio + setting (EN + Bahasa)

  Output: spreadsheet ID + show-folder ID printed at the end. Wire those into
  SERIES_CONFIG in dash_app/app.py to make the dashboard render the empty state.

Usage:
    python3 _create_blank_sot.py --name "Test Blank Show"

Idempotent? NO — creates new files each run. Run once per new show.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import gspread
from googleapiclient.discovery import build

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials


# -------- Schema definitions --------

SHOTLIST_HEADERS = [
    "Shot #", "Duration (s)", "Shot Type", "Camera Movement", "Merge Candidate",
    "Shot Description", "Dialogue/VO", "Tone of Voice", "Accent", "Microexpression",
    "SFX", "Props/Wardrobe", "Brand Integration", "Transition", "Beat",
    "English Translation", "Prompt", "Bahasa Prompt",
    "Refs Detected — Chars",
    "Refs Detected — Loc/Prop/Costume/FX/Type",
]

STORYBOARD_PROMPTS_HEADERS = [
    "Set #", "Shot Range", "Storyboard Prompt", "Bahasa Prompt", "Drive Folder",
    "Status", "Iter 1 URL", "Iter 2 URL", "Error",
    "Body", "Bahasa Body",
    "Location", "Video Iter 1 URL", "Video Iter 2 URL",
]

# Storyboard Prompts globals locked at B1-B8 (pencil-on-paper preamble).
SP_GLOBALS = [
    ("A1", "Camera Global"),       ("B1", "Shot with Arri 35."),
    ("A2", "Music"),                ("B2", "No music."),
    ("A3", "Drawing Style"),        ("B3", "Pencil-on-paper storyboard sketch. Characters drawn as TRUE stick figures: simple circle heads with NO facial features, simple line bodies, foreground/midground/background depth cues. NO text, NO color."),
    ("A4", "Panel Framing"),        ("B4", "5-panel storyboard. Each panel labelled by shot number. Camera angle/movement label centered at the bottom of each panel. Panels divided by black lines, flowing left-to-right then top-to-bottom."),
    ("A5", "Aspect"),               ("B5", "16:9 storyboard panel aspect."),
    ("A6", "Language"),             ("B6", "English shot description text only."),
    ("A7", "Accent"),                ("B7", "<edit per show — e.g. Jakarta Bahasa with Korean code-switch>"),
    ("A8", "Style Anchor"),          ("B8", "Pencil texture, light hand-drawn, no shading beyond simple cross-hatch. NO photorealistic detail."),
]

# Video Prompts globals at B1-B6 (EN + Bahasa).
VP_GLOBALS = [
    ("A1", "Camera Global"),                    ("B1", "Shot with Arri 35."),
    ("A2", "Audio/Dialogue Global"),            ("B2", "<edit per show — language directive, mood>"),
    ("A3", "Setting Global"),                   ("B3", "<edit per show — locations, era, geography>"),
    ("A4", "Bahasa Camera"),                    ("B4", "Difilmkan dengan Arri 35."),
    ("A5", "Bahasa Audio/Dialogue"),            ("B5", "<edit per show>"),
    ("A6", "Bahasa Setting"),                   ("B6", "<edit per show>"),
]

# CHARACTERS schema — 23 cols, validated by character_generate.py at:
#   col 0  = "Name"
#   col 15 = "Speech accent"
#   col 19 = "Iter 1 URL"
#   col 20 = "Iter 2 URL"
# Order locked to match production (Sajangnim Ep 1 bible).
CHARACTERS_HEADERS = [
    "Name", "Alias", "Role / Archetype", "Age", "Gender / Pronouns",
    "Ethnicity / Heritage", "Height", "Weight / Build", "Hair", "Eyes",
    "Distinguishing features", "Wardrobe", "Signature accessory / prop",
    "Personality", "Core theme", "Speech accent", "Mood / aura",
    "First Shot #", "Notes",
    "Iter 1 URL (white bg)", "Iter 2 URL (white bg)",
    "Status", "Error",
]

LOCATIONS_HEADERS_ROW4 = [
    "Name", "Shot Size", "Type (INT/EXT)", "Description",
    "Lighting / Mood", "Time of Day", "First Shot #", "Notes", "Prompt",
    "Iter 1 URL", "Iter 2 URL",
    "Status", "Error", "Feedback",
    "Aliases",
]

# COSTUME / PROPS / EFFECTS bibles — 11 cols, header at row 5.
# Production uses "Worn By / Used By" (covers both costume + prop semantics).
SIMPLE_BIBLE_HEADERS_ROW5 = [
    "Name", "Worn By / Used By", "Description", "First Shot #", "Notes",
    "Prompt", "Iter 1 URL", "Iter 2 URL", "Status", "Error", "Feedback",
]

ASSET_LIBRARY_HEADERS_ROW4 = [
    "Bible Entry Name", "Bible Tab", "Asset Code", "Source URL", "Asset Type",
    "Status", "Uploaded At", "First Used Shot", "Used In Eps", "Tags",
    "Notes", "Last Used",
]


def shotlist_q_formula(row: int) -> str:
    """v2.2 Prompt formula for Shotlist!Q on a specific row. Cell-relative
    refs auto-adjust if user fills-down. Same shape used by the
    microdrama-shotlist-bahasa skill. Wrapped in IF(A{row}="","",…) so
    empty rows resolve to "" instead of garbled string-with-empty-fields."""
    r = row
    return (
        f'=IF(A{r}="","","No music. Dialogue in "&I{r}&" accent."&CHAR(10)'
        f'&A{r}&", "&B{r}&"s, "&C{r}&", "&D{r}&", "&F{r}'
        f'&IF(G{r}="",IF(J{r}="","",", ("&J{r}&")"),", "&G{r}&IF(J{r}="",""," ("&J{r}&")"))'
        f'&IF(K{r}="",".", ", "&K{r}&"."))'
    )


def storyboard_prompt_formula() -> str:
    """Storyboard Prompts!C formula — assembles globals B1-B8 + 5 shots' Q from
    Shotlist via INDIRECT. Lives on row 11+ (set 1 = row 11).

    Math: set N at SP row 10+N references Shotlist rows ((N-1)*5+2)..(N*5+1)
    i.e. shots ((N-1)*5+1)..(N*5). For ROW=10+N, offset 2..6 maps via
    (ROW()-11)*5+offset → Shotlist row 2..6 for set 1 (shots 1..5).

    The 5 IF() parts must be concatenated via TEXTJOIN — Sheets does NOT
    accept comma-separated top-level expressions; the previous version's
    `,`.join(parts) was emitting `#ERROR!` everywhere. Use TEXTJOIN's
    variadic-args form so the parts become arguments, not raw concat."""
    parts = []
    for offset in range(2, 7):
        parts.append(
            f'IF(INDIRECT("Shotlist!A"&((ROW()-11)*5+{offset}))<>"",'
            f'"Shot "&INDIRECT("Shotlist!A"&((ROW()-11)*5+{offset}))&": "'
            f'&INDIRECT("Shotlist!Q"&((ROW()-11)*5+{offset})),"")'
        )
    body = ",".join(parts)
    return (
        '=$B$1&CHAR(10)'
        '&$B$2&CHAR(10)'
        '&$B$3&CHAR(10)'
        '&$B$4&CHAR(10)'
        '&$B$5&CHAR(10)'
        '&$B$6&CHAR(10)'
        '&$B$7&CHAR(10)'
        '&$B$8&CHAR(10)&CHAR(10)'
        f'&TEXTJOIN(CHAR(10)&CHAR(10),TRUE,{body})'
    )


def storyboard_body_formula() -> str:
    """Storyboard Prompts!J — per-set body (concat of 5 shots' Q from Shotlist),
    used by vidgen as the prompt body. Different from C: no globals, just shots.

    Same row-math fix as storyboard_prompt_formula(): set N at SP row 10+N
    references Shotlist rows ((N-1)*5+2)..(N*5+1). Uses TEXTJOIN to combine
    the 5 IF() parts (raw `,`.join was producing #ERROR!)."""
    parts = []
    for offset in range(2, 7):
        parts.append(
            f'IF(INDIRECT("Shotlist!A"&((ROW()-11)*5+{offset}))<>"",'
            f'INDIRECT("Shotlist!Q"&((ROW()-11)*5+{offset})),"")'
        )
    return f'=TEXTJOIN(CHAR(10)&CHAR(10),TRUE,{",".join(parts)})'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True,
                    help="Show display name, e.g. 'Test Blank Show'")
    ap.add_argument("--parent-folder",
                    help="Drive folder ID to create the show folder inside. "
                         "If omitted, creates in My Drive root.")
    ap.add_argument("--in-folder",
                    help="Existing show-folder Drive ID. When set, skips folder "
                         "creation and drops the spreadsheet directly into that "
                         "folder. Useful for adding extra episode sheets to an "
                         "existing show (multi-episode pattern).")
    ap.add_argument("--sheet-name",
                    help="Override the spreadsheet name (default: '<name> — SOT'). "
                         "Use this with --in-folder to create 'Ep N — Title' sheets.")
    args = ap.parse_args()

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    gc = gspread.authorize(creds)

    print(f"Building blank SOT for: {args.name}", flush=True)

    # ---- 1. Drive folder structure -----------------------------------------
    if args.in_folder:
        # Reuse-existing-folder mode — skip folder creation entirely
        show_folder_id = args.in_folder
        print(f"\n1/5 Drive folders (reusing existing)…", flush=True)
        print(f"   show folder: https://drive.google.com/drive/folders/{show_folder_id}", flush=True)
    else:
        print("\n1/5 Drive folders…", flush=True)
        folder_metadata = {
            "name": args.name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if args.parent_folder:
            folder_metadata["parents"] = [args.parent_folder]
        show_folder = drive.files().create(body=folder_metadata,
                                            fields="id,webViewLink",
                                            supportsAllDrives=True).execute()
        show_folder_id = show_folder["id"]
        print(f"   show folder: {show_folder['webViewLink']}", flush=True)

        for sub in ["storyboards", "videos"]:
            kid = drive.files().create(body={
                "name": sub,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [show_folder_id],
            }, fields="id", supportsAllDrives=True).execute()
            print(f"   {sub}/ {kid['id']}", flush=True)

    # ---- 2. Create the spreadsheet inside the show folder ------------------
    print("\n2/5 Spreadsheet…", flush=True)
    sheet_display_name = args.sheet_name or f"{args.name} — SOT"
    sheet_meta = drive.files().create(body={
        "name": sheet_display_name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [show_folder_id],
    }, fields="id,webViewLink", supportsAllDrives=True).execute()
    sheet_id = sheet_meta["id"]
    print(f"   spreadsheet: {sheet_meta['webViewLink']}", flush=True)

    sh = gc.open_by_key(sheet_id)
    time.sleep(2)

    # ---- 3. Rename Sheet1 → Shotlist + add the rest ------------------------
    print("\n3/5 Tabs + headers…", flush=True)
    default_sheet = sh.sheet1
    default_sheet.update_title("Shotlist")
    default_sheet.resize(rows=200, cols=20)
    time.sleep(1)

    new_tabs = [
        ("Storyboard Prompts", 50, 14),
        ("Video Prompts", 200, 8),
        ("CHARACTERS", 50, 23),
        ("LOCATIONS", 50, 15),
        ("COSTUME", 50, 11),
        ("PROPS", 50, 11),
        ("EFFECTS", 50, 11),
        ("Asset Library", 200, 12),
    ]
    for title, rows, cols in new_tabs:
        sh.add_worksheet(title=title, rows=rows, cols=cols)
        time.sleep(0.5)

    # ---- 4. Headers + globals + formulas -----------------------------------
    print("\n4/5 Schema + formulas…", flush=True)
    batch = []
    # Shotlist row 1 headers + Q+R formulas on row 2 (placeholder data row)
    batch.append({"range": "Shotlist!A1:T1", "values": [SHOTLIST_HEADERS]})
    # Storyboard Prompts: globals A1:B8 + headers A10:N10
    sp_globals_data = []
    for cell, val in SP_GLOBALS:
        sp_globals_data.append({"range": f"'Storyboard Prompts'!{cell}",
                                 "values": [[val]]})
    batch.extend(sp_globals_data)
    batch.append({"range": "'Storyboard Prompts'!A10:N10",
                   "values": [STORYBOARD_PROMPTS_HEADERS]})
    # Video Prompts globals
    vp_globals_data = []
    for cell, val in VP_GLOBALS:
        vp_globals_data.append({"range": f"'Video Prompts'!{cell}",
                                 "values": [[val]]})
    batch.extend(vp_globals_data)
    # Bibles
    batch.append({"range": "CHARACTERS!A1:W1",
                   "values": [CHARACTERS_HEADERS]})
    batch.append({"range": "LOCATIONS!A4:O4",
                   "values": [LOCATIONS_HEADERS_ROW4]})
    for tab in ("COSTUME", "PROPS", "EFFECTS"):
        batch.append({"range": f"{tab}!A5:K5",
                       "values": [SIMPLE_BIBLE_HEADERS_ROW5]})
    # Asset Library row 4 headers (rows 1-3 reserved for metadata banner)
    batch.append({"range": "'Asset Library'!A1:B3",
                   "values": [
                       ["ASSET LIBRARY — BytePlus Private Avatar Library Tracker", ""],
                       ["Last sync", ""],
                       ["Source of truth",
                        "vidgen reads col C (Asset Code) for each detected bible entry. Upload script writes A-G. Producer edits J/K freely."],
                   ]})
    batch.append({"range": "'Asset Library'!A4:L4",
                   "values": [ASSET_LIBRARY_HEADERS_ROW4]})

    sh.values_batch_update(body={"valueInputOption": "RAW", "data": batch})
    time.sleep(2)

    # Live formulas (separate batch with USER_ENTERED so formulas resolve)
    print("\n5/5 Formulas (live)…", flush=True)
    # Shotlist Q+R — pre-fill formulas on rows 2-101 (100 shots) so when
    # the microdrama-shotlist skill drops shot data into cols A-O, Q+R
    # resolve immediately. Each formula is wrapped in IF(A{r}="", "", …)
    # so empty rows render as "" not as garbled "No music. Dialogue in  accent…".
    SHOTLIST_FORMULA_ROWS = 100  # bumpable — episodes typically ≤80 shots
    q_values = [[shotlist_q_formula(r)] for r in range(2, 2 + SHOTLIST_FORMULA_ROWS)]
    r_values = [[f'=IF(A{r}="","",GOOGLETRANSLATE(Q{r},"en","id"))']
                 for r in range(2, 2 + SHOTLIST_FORMULA_ROWS)]
    formula_batch = [
        {"range": f"Shotlist!Q2:Q{1 + SHOTLIST_FORMULA_ROWS}", "values": q_values},
        {"range": f"Shotlist!R2:R{1 + SHOTLIST_FORMULA_ROWS}", "values": r_values},
        # Storyboard Prompts!C11 + D11 + J11 — sample row for set 1.
        # storyboard_build.py extends these formulas to all sets when an
        # episode ships (one row per 5-shot set).
        {"range": "'Storyboard Prompts'!C11",
         "values": [[storyboard_prompt_formula()]]},
        {"range": "'Storyboard Prompts'!D11",
         "values": [['=GOOGLETRANSLATE(C11,"en","id")']]},
        {"range": "'Storyboard Prompts'!J11",
         "values": [[storyboard_body_formula()]]},
        {"range": "'Storyboard Prompts'!K11",
         "values": [['=GOOGLETRANSLATE(J11,"en","id")']]},
    ]
    sh.values_batch_update(body={"valueInputOption": "USER_ENTERED",
                                  "data": formula_batch})

    # ---- Final report -------------------------------------------------------
    print("\n" + "=" * 70)
    print("✓ Blank SOT created")
    print("=" * 70)
    print(f"  Show folder:  https://drive.google.com/drive/folders/{show_folder_id}")
    print(f"  Spreadsheet:  https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    print(f"  Sheet ID:     {sheet_id}")
    print(f"  Folder ID:    {show_folder_id}")
    print()
    print("Next step — wire SERIES_CONFIG in dash_app/app.py:")
    print(f'    "blanktest": {{')
    print(f'        "name": "{args.name}",')
    print(f'        "bible_sheet": "{sheet_id}",')
    print(f'        "episodes": {{')
    print(f'            "Ep 1 — (blank)": "{sheet_id}",')
    print(f'        }},')
    print(f'    }},')
    print()
    print("Then restart the dashboard with:")
    print(f"    SERIES=blanktest python3 dash_app/app.py")


if __name__ == "__main__":
    main()

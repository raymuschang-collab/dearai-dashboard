#!/usr/bin/env python3
"""Create the master `Projects` sheet — single source of truth for every show
the dashboard knows about. One-shot setup.

Output: a Google Sheet with one tab (`Projects`) and a 12-column schema. The
sheet ID is printed at the end — paste it into Render as MASTER_PROJECTS_SHEET_ID
so the dashboard can read this on every gallery request.

Schema (row 1 = header, data rows 2+):

  A  slug                URL-safe identifier; appears in /gallery/<slug>_ep<NN>
                         routes. Producers must type-confirm uniqueness.
  B  title               Human display name for project list grid.
  C  type                series | poc | concept | client
                         Drives the badge color + landing-page filter.
  D  status              draft | generating | review | active | archived
                         draft     = master row exists, no script yet
                         generating= Anthropic API parsing script → shotlist
                         review    = shotlist done, awaiting producer "Approve"
                         active    = full pipeline ran, gallery live
                         archived  = hidden from default list
  E  bible_sheet_id      Sheet ID of the show's bible (CHARACTERS, LOCATIONS,
                         …). For series, also holds episode tabs. For spinoffs,
                         points to the parent's bible sheet (see column G).
  F  drive_folder_id     Show's root Drive folder. Contains storyboards/,
                         videos/, scripts/, the SOT sheet, etc.
  G  parent_show         If non-empty, this project inherits its bible from
                         that parent show's slug (spinoff pattern). Most rows
                         are empty.
  H  owner_email         Producer who created the project (auto-filled from
                         OAuth identity).
  I  created_at          ISO 8601 UTC timestamp.
  J  script_drive_url    The original uploaded script (PDF/Word/GDoc) in the
                         show's scripts/ subfolder. Permanent audit trail.
  K  shotlist_status     pending | generated | approved
                         Tracks the script→shotlist flow specifically. Useful
                         when the overall project status is `review` and you
                         need to know the shotlist's substate.
  L  notes               Free-text producer notes. Optional.

The sajangnim show is pre-populated as the first data row so the dashboard
has a real entry to migrate to. Run via:

    python3 _create_master_projects_sheet.py

Idempotent: if a sheet titled `DearAI Projects (Master)` already exists in
the OAuth user's Drive root, prints its ID instead of creating a new one.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import gspread
from googleapiclient.discovery import build

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials


SHEET_TITLE = "DearAI Projects (Master)"

HEADER_ROW = [
    "slug",
    "title",
    "type",
    "status",
    "bible_sheet_id",
    "drive_folder_id",
    "parent_show",
    "owner_email",
    "created_at",
    "script_drive_url",
    "shotlist_status",
    "notes",
]

# Pre-populate the existing show so the dashboard has a real row to read on
# day one. The drive_folder_id is the parent of the sajangnim ep01 sheet
# (already discovered earlier in dash_app/app.py via SERIES_BIBLE_SHEETS).
SEED_ROWS = [
    [
        "sajangnim",                                                     # slug
        "Diam Diam Aku Cinta Sajangnim",                                 # title
        "series",                                                        # type
        "active",                                                        # status
        "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc",                   # bible_sheet_id (ep01 sheet)
        "1iG-TjuQVli_WsEHxHFtSt0QdzYz4bt_g",                              # drive_folder_id (show folder)
        "",                                                              # parent_show (none)
        "raymus@dearai.com",                                             # owner_email
        "2026-04-29T00:00:00Z",                                          # created_at (project's actual age, approx)
        "",                                                              # script_drive_url (legacy — pre-CMS)
        "approved",                                                      # shotlist_status (already in production)
        "Pre-CMS legacy project; bibles serve all 6 episodes via SERIES_BIBLE_SHEETS routing",
    ],
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true",
                    help="Create a fresh sheet even if one with the same title exists.")
    args = ap.parse_args()

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    # ---- Idempotency: look for an existing sheet with the same title ------
    if not args.force:
        existing = drive.files().list(
            q=f"name='{SHEET_TITLE}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
            fields="files(id,name,webViewLink)",
            supportsAllDrives=True,
        ).execute().get("files", [])
        if existing:
            f = existing[0]
            print(f"Existing master projects sheet found:")
            print(f"  Title:  {f['name']}")
            print(f"  Link:   {f['webViewLink']}")
            print()
            print(f"MASTER_PROJECTS_SHEET_ID={f['id']}")
            print()
            print("If you want a fresh one, re-run with --force.")
            return

    # ---- Create the sheet (in My Drive root) -------------------------------
    print(f"Creating master projects sheet: {SHEET_TITLE!r}…", flush=True)
    meta = drive.files().create(
        body={
            "name": SHEET_TITLE,
            "mimeType": "application/vnd.google-apps.spreadsheet",
        },
        fields="id,webViewLink",
        supportsAllDrives=True,
    ).execute()
    sheet_id = meta["id"]
    print(f"  Created: {meta['webViewLink']}", flush=True)

    # Open + rename Sheet1 → Projects + size to 13 cols × 200 rows
    sh = gc.open_by_key(sheet_id)
    time.sleep(2)
    ws = sh.sheet1
    ws.update_title("Projects")
    ws.resize(rows=200, cols=12)
    time.sleep(1)

    # ---- Header row + seed rows --------------------------------------------
    rows = [HEADER_ROW] + SEED_ROWS
    ws.update(
        range_name=f"A1:L{len(rows)}",
        values=rows,
        value_input_option="USER_ENTERED",
    )
    print(f"  Wrote header + {len(SEED_ROWS)} seed row(s)", flush=True)

    # ---- Format the header row (bold, frozen) ------------------------------
    ws.format("A1:L1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
    })
    sh.batch_update({
        "requests": [{
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }]
    })

    # ---- Column widths so producers can read it ----------------------------
    col_widths = {
        0: 130,  # slug
        1: 280,  # title
        2: 90,   # type
        3: 110,  # status
        4: 350,  # bible_sheet_id
        5: 350,  # drive_folder_id
        6: 130,  # parent_show
        7: 200,  # owner_email
        8: 170,  # created_at
        9: 350,  # script_drive_url
        10: 130, # shotlist_status
        11: 300, # notes
    }
    sh.batch_update({
        "requests": [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "COLUMNS",
                        "startIndex": idx,
                        "endIndex": idx + 1,
                    },
                    "properties": {"pixelSize": w},
                    "fields": "pixelSize",
                }
            } for idx, w in col_widths.items()
        ]
    })

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Sheet:  {meta['webViewLink']}")
    print()
    print("Add this to Render env vars (Edit → Add variable):")
    print()
    print(f"  MASTER_PROJECTS_SHEET_ID={sheet_id}")
    print()
    print("Then proceed to commit 2 (read_projects helper).")


if __name__ == "__main__":
    main()

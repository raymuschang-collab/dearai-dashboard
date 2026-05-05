#!/usr/bin/env python3
"""
Migrate LOCATIONS tab on Strike! Pharaoh King to the Reve-API-ready format.

LAYOUT
======
  Row 1: A="Type of reference"   | B="Location reference"
  Row 2: A="Style master prompt" | B="Shot with Arri Alexa 35. Filmic. Film grain. 35MM film. prestige movie colour palette."
  Row 3: (empty)
  Row 4: column headers
  Row 5+: 12 data rows (6 locations × 2 shot sizes)

PROMPT FORMULA (column I, per row)
==================================
  =$B$1 & " - " & $B$2 & ", " & {Shot Size} & ", " & {Type} & ", " & {Name} & ", " & {Description} & ", " & {Lighting/Mood} & ", " & {Time of Day}

Outputs e.g.:
  "Location reference - Shot with Arri Alexa 35. Filmic. Film grain. 35MM film.
  prestige movie colour palette., wide, EXT, Peasant Bazaar,
  Ruthless white sun midday glare with harsh shadows..., Day midday"

13 columns:
  A: Name | B: Shot Size | C: Type | D: Description | E: Lighting/Mood
  F: Time of Day | G: First Shot # | H: Notes | I: Prompt
  J: Iter 1 URL | K: Iter 2 URL | L: Status | M: Error

Each row gets 2 iterations via Reve. So per location: 2 shot sizes × 2 iters = 4 files.
6 locations × 4 = 24 generations total per episode.
"""
from __future__ import annotations
import gspread
from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"

# === Globals (rows 1-2) ===
GLOBAL_TYPE_LABEL = "Type of reference"
GLOBAL_TYPE_VALUE = "Location reference"
GLOBAL_STYLE_LABEL = "Style master prompt"
GLOBAL_STYLE_VALUE = "Shot with Arri Alexa 35. Filmic. Film grain. 35MM film. prestige movie colour palette."

# === Headers (row 4) ===
LOCATIONS_HEADERS = [
    "Name",              # A
    "Shot Size",         # B  ← wide / mid
    "Type (INT/EXT)",    # C
    "Description",       # D  (in prompt)
    "Lighting / Mood",   # E
    "Time of Day",       # F
    "First Shot #",      # G
    "Notes",             # H
    "Prompt",            # I  ← auto-formula
    "Iter 1 URL",        # J
    "Iter 2 URL",        # K
    "Status",            # L  (hidden)
    "Error",             # M  (hidden)
    "Feedback",          # N  ← team-editable, free text
]

# === Source locations (will expand to wide+mid per location) ===
LOCATION_BASE = [
    {
        "name": "Peasant Bazaar",
        "type": "EXT",
        "desc": "Sprawling desert marketplace. Narrow aisles twist between rows of low wooden stalls draped in faded cloth canopies. Goats, copper trinkets, dyed fabrics, salted fish, clay jars.",
        "lighting": "Ruthless white sun midday glare with harsh shadows; dust haze",
        "time": "Day midday",
        "first_shot": "1",
        "notes": "HOOK setting; attacked by Isfet Spawn",
    },
    {
        "name": "Desert Plateau / Great Pyramid",
        "type": "EXT",
        "desc": "A half-finished Great Pyramid towers over the desert, pale limestone blocks glowing under the sun. Sun-Guard arrayed in formation in front of it.",
        "lighting": "High noon glare; sand reflecting light; Spawn's death-shadow falling across the pyramid mid-battle",
        "time": "Day",
        "first_shot": "13",
        "notes": "Sacred site the Sun-Guard is protecting",
    },
    {
        "name": "Rooftop above the Bazaar",
        "type": "EXT",
        "desc": "Flat mud-brick rooftop above the bazaar. Khensu's vantage point looking down on the slaughter, with Tehuti and Seshet behind him.",
        "lighting": "Direct sun + dust haze rising from the chaos below; wind through cloth",
        "time": "Day",
        "first_shot": "22",
        "notes": "Site of the call-to-action dialogue; Khensu leaps from here",
    },
    {
        "name": "Pyramid Field (Battlefield)",
        "type": "EXT",
        "desc": "Open battlefield between the bazaar and the pyramid. Sand floor; debris of war — shattered spears, overturned bodies, war chariots in pieces.",
        "lighting": "Dust haze; dramatic shadows from the Spawn; magical fire-arrow glow at the volley moment",
        "time": "Day",
        "first_shot": "38",
        "notes": "Main battle space; Khensu's solar whip strike happens here",
    },
    {
        "name": "Base of the Pyramid",
        "type": "EXT",
        "desc": "Sand floor at the foot of the pyramid. Fallen supply carts, broken oxen yokes, scattered wreckage.",
        "lighting": "Long pyramid shadow + Spawn shadow both falling across the space",
        "time": "Day",
        "first_shot": "53",
        "notes": "Where Khensu finds the ox-hide whip and channels solar magic",
    },
    {
        "name": "Impact Crater",
        "type": "EXT",
        "desc": "Crater of broken stone and dust from Khensu's earlier impact. Half-buried in rubble.",
        "lighting": "Dim and dusty, claustrophobic vs. the bright battle around it",
        "time": "Day",
        "first_shot": "67",
        "notes": "Khensu's awakening / recovery moment before final strike",
    },
]


def build_data_rows() -> list[list]:
    """Expand LOCATION_BASE into 12 rows (each location × 2 shot sizes)."""
    rows = []
    for loc in LOCATION_BASE:
        for shot_size in ["wide", "mid"]:
            rows.append([
                loc["name"],
                shot_size,
                loc["type"],
                loc["desc"],
                loc["lighting"],
                loc["time"],
                loc["first_shot"],
                loc["notes"],
                "",          # Prompt placeholder (filled with formula below)
                "", "",      # Iter 1, Iter 2
                "Pending",   # Status
                "",          # Error
                "",          # Feedback (team-editable, free text)
            ])
    return rows


def main():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    print(f"Sheet: {sh.title}")

    # Delete existing LOCATIONS tab
    existing = next((w for w in sh.worksheets() if w.title == "LOCATIONS"), None)
    if existing:
        sh.del_worksheet(existing)
        print("  removed existing LOCATIONS tab")

    data = build_data_rows()
    n_data = len(data)
    n_cols = len(LOCATIONS_HEADERS)
    last_col = chr(ord("A") + n_cols - 1)  # 'M'
    total_rows = 4 + n_data

    ws = sh.add_worksheet(title="LOCATIONS", rows=total_rows + 5, cols=n_cols)

    # Row 1: Type of reference
    ws.update(range_name="A1:B1", values=[[GLOBAL_TYPE_LABEL, GLOBAL_TYPE_VALUE]])
    # Row 2: Style master prompt
    ws.update(range_name="A2:B2", values=[[GLOBAL_STYLE_LABEL, GLOBAL_STYLE_VALUE]])
    # Row 4: column headers
    ws.update(range_name=f"A4:{last_col}4", values=[LOCATIONS_HEADERS])

    # Row 5+: data with prompt formulas
    rows_with_formula = []
    for i, row in enumerate(data):
        sheet_row = 5 + i
        prompt_formula = (
            f'=$B$1&" - "&$B$2&", "&B{sheet_row}&", "&C{sheet_row}'
            f'&", "&A{sheet_row}&", "&D{sheet_row}&", "&E{sheet_row}&", "&F{sheet_row}'
        )
        new_row = list(row)
        new_row[8] = prompt_formula  # column I
        rows_with_formula.append(new_row)

    ws.update(
        range_name=f"A5:{last_col}{4 + n_data}",
        values=rows_with_formula,
        value_input_option="USER_ENTERED",
    )

    # Formatting:
    sh.batch_update({
        "requests": [
            # Bold the global label cells (A1, A2)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": 0, "endRowIndex": 2,
                        "startColumnIndex": 0, "endColumnIndex": 1,
                    },
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            },
            # Soft fill on the global value cells (B1, B2) so they stand out as editable defaults
            {
                "repeatCell": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": 0, "endRowIndex": 2,
                        "startColumnIndex": 1, "endColumnIndex": 2,
                    },
                    "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.96, "green": 0.96, "blue": 0.92}}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            },
            # Bold header row (row 4)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": 3, "endRowIndex": 4,
                        "startColumnIndex": 0, "endColumnIndex": n_cols,
                    },
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            },
            # Freeze rows 1-4 so globals + headers stay pinned during scroll
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": ws.id,
                        "gridProperties": {"frozenRowCount": 4},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # Hide Status (col L, idx 11) and Error (col M, idx 12)
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "COLUMNS",
                        "startIndex": 11, "endIndex": 13,
                    },
                    "properties": {"hiddenByUser": True},
                    "fields": "hiddenByUser",
                }
            },
        ]
    })

    print(f"  ✓ LOCATIONS rebuilt: {n_cols} cols × {n_data} data rows ({len(LOCATION_BASE)} locations × 2 shot sizes)")
    print("  Row 1 / Row 2: globals (Type of reference, Style master prompt)")
    print("  Row 4: headers; Row 5+: data; rows 1-4 frozen")
    print("  Prompt formula in column I auto-assembles the Reve API prompt")
    print("  Status + Error columns hidden")
    print()
    print("  Sample prompt for Peasant Bazaar wide (row 5):")
    print(f"    {GLOBAL_TYPE_VALUE} - {GLOBAL_STYLE_VALUE}, wide, EXT, Peasant Bazaar, "
          f"{LOCATION_BASE[0]['lighting']}, {LOCATION_BASE[0]['time']}")


if __name__ == "__main__":
    main()

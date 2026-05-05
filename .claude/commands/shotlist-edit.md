---
description: Edit cells, insert/delete rows, or generatively rewrite shots in a microdrama shotlist.
argument-hint: [<sheet-id>] <description of the change>
---

User wants to make a change to a microdrama shotlist (v2.2 schema).

Their request:

```
$ARGUMENTS
```

## Workflow — diff-then-confirm-then-write

### 1. Identify target sheet + shotlist tab

If the user named a Sheet ID or Sheets URL, use it. Otherwise ask. Do NOT default to the canonical reference Sheet `1-EPcY1YXstCfJm81MpVCpmuCdvN6O3awXWZ5H885T78` — it must not be modified.

The shotlist tab is the first tab in the Sheet whose name is not `Storyboard Prompts`.

### 2. Classify the edit

| Type | Example | gspread move |
|------|---------|--------------|
| **Cell edit** | "Fix typo in shot 12 dialogue" | `update("F12", new_value)` — column-targeted |
| **Bulk transform** | "Tighten every CU description to under 12 words" | Read affected rows → rewrite each → batch_update |
| **Generative rewrite** | "Rewrite shot 24 to land harder" | You write new content; show before/after; user confirms |
| **Insert row** | "Add a reaction CU after shot 24" | `insert_row(values, index=...)` — note the row-shift impact |
| **Delete row** | "Remove shot 17" | `delete_rows(idx)` — note shift |
| **Merge candidate** | "Flag shots 38–40 as merge candidate" | Set column E with the v2.2 merge note format |
| **Beat color** | "Mark shot 27 as JOLT 2" | Set column N text + apply fill via batchUpdate spreadsheets API |

### 3. Read the affected rows BEFORE planning

Use the gspread helpers in this directory:

```python
import gspread
from auth import get_credentials
gc = gspread.authorize(get_credentials())
sh = gc.open_by_key(SHEET_ID)
ws = sh.worksheet(SHOTLIST_TAB)
# Read with FORMULA option for column P so you don't accidentally overwrite the formula
row_data = ws.get(f"A{r}:P{r}", value_render_option="FORMULA")
```

### 4. Plan the edits

Build a list of `(A1_range, new_value)` operations. For inserts/deletes, include the row-shift impact (column A renumbering).

### 5. Show a diff to the user

Use this format:

```
Target: <Sheet name> / <Tab name>
Operation: <classified type>

Cell  | Before                          | After
------|---------------------------------|---------------------------------
F12   | Henry's hands stuff papers...   | Henry frantically stuffs papers...
J12   | Paper shuffle; briefcase zipper | Paper shuffle; briefcase zipper; muffled phone

Cascade: P12 (Prompt) auto-regenerates. Storyboard Prompts row 4 auto-updates.
```

For row inserts, show the new row content + which row it goes at + which existing rows shift down. For bulk/generative rewrites, list every changed row.

### 6. Ask "apply?" — wait for explicit yes

Do not write until the user says yes / apply / go. If they say "tweak X first", iterate the diff until they're satisfied.

### 7. Apply via gspread, then verify

Use `batch_update` for multi-cell ops. After writing, re-read the affected ranges and confirm values landed.

For row inserts: use `worksheet.insert_row(values, index, value_input_option="USER_ENTERED")` so the formula in column P (which contains relative references to that row) propagates correctly. Then re-read P{new_row} to confirm the formula resolved.

### 8. Cascade is automatic — explain only when asked

The Prompt column (P) is a live formula. Edit any of A/B/C/D/F/G/H/I/J → P updates. The Storyboard Prompts tab pulls from P via INDIRECT → it updates too. No regeneration step is needed.

### 9. Final report

One line: sheet name, what changed, how many cells/rows touched.

## v2.2 schema — locked, do not violate

| Col | Header | Notes |
|-----|--------|-------|
| A | Shot # | sequential int |
| B | Duration (s) | 3 or 4 ONLY |
| C | Shot Type | CU, MCU, MS, WS, OTS, Insert, POV |
| D | Camera Movement | Static, Dolly In, Pan R/L, Tilt U/D, Handheld, Tracking, Rack Focus |
| E | Merge Candidate | Format: `Merge w/ {N}; {camera move}.` Empty if not a merge. |
| F | Shot Description | Imperative present, English, ONE action |
| G | Dialogue/VO | Source language; prefix with character name |
| H | Accent | Per-row (e.g., "Jakarta Bahasa") |
| I | Microexpression | English, only if face is visible |
| J | SFX | English, semicolon-separated |
| K | Props/Wardrobe | Metadata |
| L | Brand Integration | Metadata |
| M | Transition | Cut, Smash Cut, Fade to Black |
| N | Beat | HOOK, JOLT 1-4, CLIFF, PAYOFF, FLASHBACK, BRIDGE — apply fill color |
| O | English Translation | Only if dialogue isn't English |
| **P** | **Prompt** | **LIVE FORMULA — never overwrite with text** |
| **Q** | **Bahasa Prompt** | **LIVE FORMULA — `=GOOGLETRANSLATE(P{r},"en","id")` — never overwrite** |

### Beat color legend (column N fill)

| Beat | Hex |
|------|-----|
| HOOK | `#FCD34D` (amber) |
| JOLT 1 / 2 / 3 / 4 | `#93C5FD` (blue) |
| CLIFF | `#FCA5A5` (red) |
| CLIFF SETUP / TAG | `#FECACA` (pale red) |
| PAYOFF | `#A7F3D0` (green) |
| FLASHBACK | `#DDD6FE` (purple) |
| BRIDGE | `#E5E7EB` (gray) |

To apply fill, use the Sheets API directly (gspread doesn't expose cell formatting cleanly for batch ops):

```python
from googleapiclient.discovery import build
service = build("sheets", "v4", credentials=get_credentials())
service.spreadsheets().batchUpdate(
    spreadsheetId=SHEET_ID,
    body={"requests": [{
        "repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": r-1, "endRowIndex": r,
                      "startColumnIndex": 13, "endColumnIndex": 14},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.99, "green": 0.83, "blue": 0.27}}},
            "fields": "userEnteredFormat.backgroundColor"
        }
    }]},
).execute()
```

### Generative rewrite — follow the microdrama-shotlist skill

For "rewrite shot X" or "make scene punchier" requests:

- Imperative present tense, English shot description
- One action per row — atomize, don't bunch
- Source-language dialogue (Bahasa for Jakarta shows; keep code-switch tags in column H)
- Microexpressions are 1–2 clauses, only when face is visible
- SFX are short, semicolon-separated
- Duration stays 3 or 4

If the rewrite warrants splitting one row into two (atomization), propose that as an INSERT operation, not just a CELL EDIT.

## Authentication

Use `auth.get_credentials()` from this directory. Token is valid; don't re-run OAuth.

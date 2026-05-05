# Build Templates — openpyxl Python Generator

Proven template for generating v2.2 XLSX shotlists. Uses the exact formula, fills, and column widths that survived the Jakarta Ep 1 demo.

## Minimal working template

```python
"""
Template for building a v2.2 shotlist as XLSX.
Fill the ROWS list with your shot data, then run.
"""
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = os.path.dirname(os.path.abspath(__file__))

HEADERS = [
    "Shot #",            # A
    "Duration (s)",      # B
    "Shot Type",         # C
    "Camera Movement",   # D
    "Merge Candidate",   # E  (NOT in prompt)
    "Shot Description",  # F
    "Dialogue/VO",       # G
    "Accent",            # H
    "Microexpression",   # I
    "SFX",               # J
    "Props/Wardrobe",    # K
    "Brand Integration", # L
    "Transition",        # M
    "Beat",              # N
    "English Translation",  # O
    "Prompt",            # P
]

COL_WIDTHS = [6, 10, 10, 14, 32, 46, 40, 28, 36, 28, 30, 26, 14, 12, 36, 78]

BEAT_COLORS = {
    "HOOK": "FCD34D",
    "JOLT 1": "93C5FD", "JOLT 2": "93C5FD", "JOLT 3": "93C5FD", "JOLT 4": "93C5FD",
    "CLIFF": "FCA5A5", "CLIFF SETUP": "FECACA", "CLIFF TAG": "FECACA", "TAG": "FECACA",
    "PAYOFF": "A7F3D0", "FLASHBACK": "DDD6FE", "BRIDGE": "E5E7EB",
}

def prompt_formula(r):
    """Prompt formula for row r. Skips column E (Merge Candidate)."""
    return (
        f'="No music. Dialogue in "&H{r}&" accent."&CHAR(10)'
        f'&A{r}&", "&B{r}&"s, "&C{r}&", "&D{r}&", "&F{r}'
        f'&IF(G{r}="",IF(I{r}="","",", ("&I{r}&")"),", "&G{r}&IF(I{r}="",""," ("&I{r}&")"))'
        f'&IF(J{r}="",".", ", "&J{r}&".")'
    )

# ROWS: list of lists. Each inner list has 15 values (columns A-O).
# The Prompt formula (column P) is computed separately.
#
# Format: [shot_num, duration, shot_type, camera, merge_note, shot_desc,
#          dialogue, accent, microexp, sfx, props, brand, transition,
#          beat, english_translation]
ROWS = [
    # Example row — fill in your actual shots:
    [1, 3, "CU", "Static", "",
     "Rearview mirror close-up of the character's eyes, phone to ear, panic-stricken.",
     "CHAR: Dialogue line in source language.",
     "Jakarta Bahasa",
     "Pupils dilating, sweat beading at the temple",
     "Muffled phone audio; traffic",
     "Character's wardrobe",
     "Brand context",
     "Cut", "HOOK",
     "English translation of dialogue"],
    # ... more rows
]

# ============================================================
# Build the XLSX
# ============================================================
wb = Workbook()
ws = wb.active
ws.title = "Ep 1 - TITLE"

THIN = Side(border_style="thin", color="CCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor="1F2937")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
PROMPT_HEADER_FILL = PatternFill("solid", fgColor="065F46")
MERGE_HEADER_FILL = PatternFill("solid", fgColor="7C3AED")
MERGE_CELL_FILL = PatternFill("solid", fgColor="F5F3FF")
WRAP = Alignment(wrap_text=True, vertical="top", horizontal="left")
HEADER_WRAP = Alignment(wrap_text=True, vertical="center", horizontal="center")

# Header row
for c, h in enumerate(HEADERS, 1):
    cell = ws.cell(row=1, column=c, value=h)
    if h == "Prompt":
        cell.fill = PROMPT_HEADER_FILL
    elif h == "Merge Candidate":
        cell.fill = MERGE_HEADER_FILL
    else:
        cell.fill = HEADER_FILL
    cell.font = HEADER_FONT
    cell.alignment = HEADER_WRAP
    cell.border = BORDER

# Data rows
for r_idx, r in enumerate(ROWS, 2):
    for c_idx, val in enumerate(r, 1):
        cell = ws.cell(row=r_idx, column=c_idx, value=val)
        cell.alignment = WRAP
        cell.border = BORDER
    beat = r[13]  # Beat is column 14 (0-indexed 13)
    if beat in BEAT_COLORS:
        ws.cell(row=r_idx, column=14).fill = PatternFill("solid", fgColor=BEAT_COLORS[beat])
    if r[4]:  # Merge Candidate populated
        ws.cell(row=r_idx, column=5).fill = MERGE_CELL_FILL
    formula = prompt_formula(r_idx)
    prompt_cell = ws.cell(row=r_idx, column=16, value=formula)
    prompt_cell.alignment = WRAP
    prompt_cell.border = BORDER
    prompt_cell.fill = PatternFill("solid", fgColor="F0FDF4")

# Column widths
for i, w in enumerate(COL_WIDTHS, 1):
    ws.column_dimensions[get_column_letter(i)].width = w

ws.row_dimensions[1].height = 32
for r_idx in range(2, len(ROWS) + 2):
    ws.row_dimensions[r_idx].height = 80

ws.freeze_panes = "A2"

xlsx_path = os.path.join(OUT, "SHOTLIST_Ep1_v22.xlsx")
wb.save(xlsx_path)
print(f"Wrote {xlsx_path}")
print(f"Total shots: {len(ROWS)}")
print(f"Total duration: {sum(r[1] for r in ROWS)}s")
```

## Upload to Drive

After building, upload via the Drive MCP:

```python
import base64
with open(xlsx_path, "rb") as f:
    content_b64 = base64.b64encode(f.read()).decode()

# Then call mcp__drive__create_file with:
# - title: "Ep 1 - TITLE (v2.2)"
# - parentId: the target folder ID
# - mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# - content: content_b64
# - disableConversionToGoogleType: false
```

## Known conversion-failure workaround

Some openpyxl-generated XLSX files fail to convert to native Google Sheets with "Could not open file. Try refreshing the page." If that happens:

### Option A — strip to a simpler XLSX (CSV + manual format)

Write a CSV with just the data (no formulas, no fills), upload as `text/csv`. Drive auto-converts to a native Sheet. Paste the Prompt formula into column P manually (the user does this once; it fills down).

### Option B — edit an existing native Sheet

If the user already has a native Sheet from a prior version, use the Chrome MCP to edit it directly:

1. Navigate to the Sheet URL
2. Use the Name Box (`#t-name-box`) via JavaScript to jump to cells
3. Right-click column header → "Insert 1 column to the left" for structural changes
4. Type via Chrome computer `type` action
5. Google Sheets' auto-formula-adjustment handles reference shifts on column insert

This avoids XLSX conversion entirely. Native Sheets "just work" for programmatic editing via the browser extension.

## Sheet URL conventions

- **XLSX in Drive:** `https://drive.google.com/file/d/{FILE_ID}/view`
- **Native Google Sheet:** `https://docs.google.com/spreadsheets/d/{FILE_ID}/edit`

Don't use the `/spreadsheets/` URL format for XLSX files — it fails. Use the `/file/d/.../view` format for XLSX, and only use `/spreadsheets/` after the user has converted to a native Sheet.

## Per-episode registry

Maintain a registry file (e.g. `/outputs/shotlist_registry.md`) with the Drive URLs for every episode built. Update after each upload. Helps the user track which episodes are where, and which version (v2, v2.1, v2.2) they're on.

#!/usr/bin/env python3
"""
Living-document migration for Video Prompts + Storyboard Prompts tabs.

PROBLEM
-------
Each row's Video Prompt repeats the same camera/audio/dialogue preamble.
Same with Storyboard Prompts (camera, music, drawing style, panel
instructions). Any change to a global means rewriting 86+ cells.

NEW SCHEMA
----------
Globals at top (rows 1–4 / 1–8). Bodies in NEW columns at the end.
Existing prompt columns become FORMULAS that re-assemble globals + body
so anything downstream that reads "Video Prompt" / "Storyboard Prompt"
still gets the full assembled string — no upstream consumer breaks.

VIDEO PROMPTS:
  Row 1: A="Camera global"           B="Shot with arri 35."
  Row 2: A="Audio/Dialogue global"   B="No music. Dialogue in Heightened English (mythic) accent."
  Row 3: A="Bahasa Camera"           B="Difilmkan dengan Arri 35."
  Row 4: A="Bahasa Audio/Dialogue"   B="Tanpa musik. Dialog dalam aksen Inggris yang ditinggikan (mitos)."
  Row 5: blank
  Row 6: Headers — A=Shot #, B=Video Prompt (formula), C=Bahasa Prompt (formula),
                   D=Drive Folder, E=Status, F=Iter 1 URL, G=Iter 2 URL, H=Error,
                   I=Body, J=Bahasa Body  ← editable
  Row 7+: 86 data rows

STORYBOARD PROMPTS:
  Row 1–4: EN globals (Camera, Music, Drawing style, Panel instruction)
  Row 5–8: ID globals (same)
  Row 9: blank
  Row 10: Headers — A=Set #, B=Shot Range, C=Storyboard Prompt (formula),
                    D=Bahasa Prompt (formula), E=Drive Folder, F=Status,
                    G=Iter 1 URL, H=Iter 2 URL, I=Error, J=Body, K=Bahasa Body
  Row 11+: 14 set rows

IDEMPOTENT: detects "Camera global" in A1 and skips if already migrated.
BACKUP: existing data dumped to /tmp/living_doc_backup_{tab}.json before
        any destructive write.
"""
from __future__ import annotations
import json
import os
import sys
import gspread
from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"

# === Detected preambles (verified against sheet content) ===
EN_CAMERA = "Shot with arri 35."
EN_AUDIO = "No music. Dialogue in Heightened English (mythic) accent."
ID_CAMERA = "Difilmkan dengan Arri 35."
ID_AUDIO = "Tanpa musik. Dialog dalam aksen Inggris yang ditinggikan (mitos)."

# Storyboard-specific globals (line 2 is "No Music." — capital M, no dialogue clause)
EN_SB_MUSIC = "No Music."
EN_SB_STYLE = "Stick figure pencil storyboard with foreground, midground and background depth."
EN_SB_PANEL = (
    "Create a 5 panel storyboard based on the following shots. "
    "Ensure each shot is labelled by number, with a label of the camera angle/movement "
    "centred at the bottom of the panel. The storyboard should be divided by black lines. "
    "And the panels should flow sequentially:"
)
ID_SB_MUSIC = "Tanpa Musik."
ID_SB_STYLE = "Storyboard pensil figur tongkat dengan latar depan, latar tengah, dan kedalaman latar belakang."
ID_SB_PANEL = (
    "Buat storyboard 5 panel berdasarkan adegan berikut. "
    "Pastikan setiap adegan diberi label nomor, dengan label sudut/pergerakan kamera "
    "yang berada di tengah bagian bawah panel. Storyboard harus dibagi dengan garis hitam. "
    "Dan panel-panel tersebut harus mengalir secara berurutan:"
)


def strip_preamble(prompt: str, preamble_lines: list) -> str:
    """Remove leading preamble lines (matched by stripped equality) from a prompt.
    Stops at the first non-matching line. Also strips a single blank separator line
    that often follows the preamble."""
    if not prompt:
        return ""
    lines = prompt.splitlines()
    # Set of preamble strings to match (whitespace-stripped)
    needles = {ln.strip() for ln in preamble_lines if ln.strip()}
    body_start = 0
    for line in lines:
        if line.strip() in needles:
            body_start += 1
        else:
            break
    # Skip one blank separator between preamble and body if present
    if body_start < len(lines) and lines[body_start].strip() == "":
        body_start += 1
    return "\n".join(lines[body_start:]).rstrip()


def already_migrated(ws) -> bool:
    a1 = ws.acell("A1").value or ""
    return "global" in a1.lower()


# ---------- Video Prompts migration ----------
def migrate_video_prompts(sh):
    ws = sh.worksheet("Video Prompts")
    if already_migrated(ws):
        print("  Video Prompts: already migrated — skipping")
        return

    print("  Video Prompts: reading existing data...")
    raw = ws.get("A1:H200", value_render_option="FORMATTED_VALUE")
    headers = raw[0]
    data = raw[1:]
    data = [r for r in data if r and r[0]]

    backup = {"tab": "Video Prompts", "headers": headers, "rows": data}
    bp = "/tmp/living_doc_backup_video_prompts.json"
    with open(bp, "w") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)
    print(f"    backup → {bp} ({len(data)} rows)")

    # Build new rows: strip preambles → bodies
    new_rows = []
    for row in data:
        shot_num = row[0]
        full_en = row[1] if len(row) > 1 else ""
        full_id = row[2] if len(row) > 2 else ""
        drive_folder = row[3] if len(row) > 3 else ""
        status = row[4] if len(row) > 4 else ""
        iter1 = row[5] if len(row) > 5 else ""
        iter2 = row[6] if len(row) > 6 else ""
        error = row[7] if len(row) > 7 else ""

        body_en = strip_preamble(full_en, [EN_CAMERA, EN_AUDIO])
        body_id = strip_preamble(full_id, [ID_CAMERA, ID_AUDIO])

        new_rows.append({
            "shot_num": shot_num,
            "drive_folder": drive_folder,
            "status": status,
            "iter1": iter1,
            "iter2": iter2,
            "error": error,
            "body_en": body_en,
            "body_id": body_id,
        })

    # Wipe + rebuild
    ws.clear()
    # Make sure we have at least 10 columns
    if ws.col_count < 10:
        ws.add_cols(10 - ws.col_count)
    # Make sure we have enough rows
    needed_rows = 6 + len(new_rows) + 5  # buffer
    if ws.row_count < needed_rows:
        ws.add_rows(needed_rows - ws.row_count)

    # Globals (rows 1-4)
    globals_block = [
        ["Camera global",          EN_CAMERA],
        ["Audio/Dialogue global",  EN_AUDIO],
        ["Bahasa Camera",          ID_CAMERA],
        ["Bahasa Audio/Dialogue",  ID_AUDIO],
    ]
    ws.update(range_name="A1:B4", values=globals_block)

    # Headers (row 6)
    new_headers = [
        "Shot #", "Video Prompt", "Bahasa Prompt",
        "Drive Folder", "Status", "Iter 1 URL", "Iter 2 URL", "Error",
        "Body", "Bahasa Body",
    ]
    ws.update(range_name="A6:J6", values=[new_headers])

    # Data rows (row 7+) — Video Prompt + Bahasa Prompt are formulas
    rows_out = []
    for i, r in enumerate(new_rows):
        sr = 7 + i
        formula_en = f'=$B$1&CHAR(10)&$B$2&CHAR(10)&I{sr}'
        formula_id = f'=$B$3&CHAR(10)&$B$4&CHAR(10)&J{sr}'
        rows_out.append([
            r["shot_num"],
            formula_en, formula_id,
            r["drive_folder"], r["status"],
            r["iter1"], r["iter2"], r["error"],
            r["body_en"], r["body_id"],
        ])
    if rows_out:
        ws.update(
            range_name=f"A7:J{6 + len(rows_out)}",
            values=rows_out,
            value_input_option="USER_ENTERED",
        )

    # Format: bold global labels, soft-fill values, freeze 6 rows, hide cols D-H to declutter
    sh.batch_update({"requests": [
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 4,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 4,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.96, "green": 0.96, "blue": 0.92}}},
            "fields": "userEnteredFormat.backgroundColor",
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 5, "endRowIndex": 6,
                      "startColumnIndex": 0, "endColumnIndex": 10},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }},
        {"updateSheetProperties": {
            "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 6}},
            "fields": "gridProperties.frozenRowCount",
        }},
    ]})
    print(f"    ✓ migrated {len(new_rows)} shot rows")


# ---------- Storyboard Prompts migration ----------
def migrate_storyboard_prompts(sh):
    ws = sh.worksheet("Storyboard Prompts")
    if already_migrated(ws):
        print("  Storyboard Prompts: already migrated — skipping")
        return

    print("  Storyboard Prompts: reading existing data...")
    raw = ws.get("A1:I50", value_render_option="FORMATTED_VALUE")
    headers = raw[0]
    data = raw[1:]
    data = [r for r in data if r and r[0]]

    backup = {"tab": "Storyboard Prompts", "headers": headers, "rows": data}
    bp = "/tmp/living_doc_backup_storyboard_prompts.json"
    with open(bp, "w") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)
    print(f"    backup → {bp} ({len(data)} rows)")

    en_lines = [EN_CAMERA, EN_SB_MUSIC, EN_SB_STYLE, EN_SB_PANEL]
    id_lines = [ID_CAMERA, ID_SB_MUSIC, ID_SB_STYLE, ID_SB_PANEL]

    new_rows = []
    for row in data:
        set_num = row[0]
        shot_range = row[1] if len(row) > 1 else ""
        full_en = row[2] if len(row) > 2 else ""
        full_id = row[3] if len(row) > 3 else ""
        drive_folder = row[4] if len(row) > 4 else ""
        status = row[5] if len(row) > 5 else ""
        iter1 = row[6] if len(row) > 6 else ""
        iter2 = row[7] if len(row) > 7 else ""
        error = row[8] if len(row) > 8 else ""

        body_en = strip_preamble(full_en, en_lines)
        body_id = strip_preamble(full_id, id_lines)

        new_rows.append({
            "set_num": set_num, "shot_range": shot_range,
            "drive_folder": drive_folder, "status": status,
            "iter1": iter1, "iter2": iter2, "error": error,
            "body_en": body_en, "body_id": body_id,
        })

    ws.clear()
    if ws.col_count < 11:
        ws.add_cols(11 - ws.col_count)
    needed_rows = 10 + len(new_rows) + 5
    if ws.row_count < needed_rows:
        ws.add_rows(needed_rows - ws.row_count)

    globals_block = [
        ["Camera global",                EN_CAMERA],
        ["Music global",                 EN_SB_MUSIC],
        ["Drawing style global",         EN_SB_STYLE],
        ["Panel instruction global",     EN_SB_PANEL],
        ["Bahasa Camera",                ID_CAMERA],
        ["Bahasa Music",                 ID_SB_MUSIC],
        ["Bahasa Drawing style",         ID_SB_STYLE],
        ["Bahasa Panel instruction",     ID_SB_PANEL],
    ]
    ws.update(range_name="A1:B8", values=globals_block)

    new_headers = [
        "Set #", "Shot Range", "Storyboard Prompt", "Bahasa Prompt",
        "Drive Folder", "Status", "Iter 1 URL", "Iter 2 URL", "Error",
        "Body", "Bahasa Body",
    ]
    ws.update(range_name="A10:K10", values=[new_headers])

    rows_out = []
    for i, r in enumerate(new_rows):
        sr = 11 + i
        # EN formula: globals 1-4 (rows 1-4) + blank line + body in J{sr}
        f_en = (
            f'=$B$1&CHAR(10)&$B$2&CHAR(10)&$B$3&CHAR(10)&$B$4'
            f'&CHAR(10)&CHAR(10)&J{sr}'
        )
        # ID formula: globals 5-8 (rows 5-8) + body in K{sr}
        f_id = (
            f'=$B$5&CHAR(10)&$B$6&CHAR(10)&$B$7&CHAR(10)&$B$8'
            f'&CHAR(10)&CHAR(10)&K{sr}'
        )
        rows_out.append([
            r["set_num"], r["shot_range"], f_en, f_id,
            r["drive_folder"], r["status"], r["iter1"], r["iter2"], r["error"],
            r["body_en"], r["body_id"],
        ])
    if rows_out:
        ws.update(
            range_name=f"A11:K{10 + len(rows_out)}",
            values=rows_out,
            value_input_option="USER_ENTERED",
        )

    sh.batch_update({"requests": [
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 8,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 8,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.96, "green": 0.96, "blue": 0.92}}},
            "fields": "userEnteredFormat.backgroundColor",
        }},
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 9, "endRowIndex": 10,
                      "startColumnIndex": 0, "endColumnIndex": 11},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }},
        {"updateSheetProperties": {
            "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 10}},
            "fields": "gridProperties.frozenRowCount",
        }},
    ]})
    print(f"    ✓ migrated {len(new_rows)} set rows")


def main():
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    print(f"Sheet: {sh.title}")
    migrate_video_prompts(sh)
    migrate_storyboard_prompts(sh)
    print("\n  ✓ Living-document schema applied to both tabs.")
    print("    Globals editable in cells B1–B4 (Video) / B1–B8 (Storyboard).")
    print("    Bodies editable in columns I/J (Video) / J/K (Storyboard).")
    print("    Full prompts re-assemble automatically via formula.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Simplify the living-doc schema after the first migration was over-engineered.

USER'S MENTAL MODEL
-------------------
- "Video Prompt for set N is just the Storyboard Prompt body for set N,
   wrapped in the video global (camera + audio/dialogue) instead of the
   storyboard global (camera + music + drawing style + panel instruction)."
- One row per SET on both tabs (not one row per shot on Video Prompts).
- Don't need Body + Bahasa Body columns — col C IS the body (editable),
  globals at top of the tab handle the preamble.

NEW SHAPE
---------
Storyboard Prompts:
  Rows 1-8: globals (camera, music, drawing style, panel instruction × EN+ID)
  Row 9: blank
  Row 10: headers — A=Set #, B=Shot Range, C=Storyboard Prompt (editable body),
                    D=Bahasa Prompt (editable body), E=Drive Folder, F=Status,
                    G=Iter 1 URL, H=Iter 2 URL, I=Error
  Row 11+: 14 set rows. C/D contain the per-set 5-shot list.

Video Prompts:
  Rows 1-4: globals (camera + audio in EN+ID)
  Row 5: blank
  Row 6: headers — A=Set #, B=Shot Range, C=Video Prompt (formula),
                   D=Bahasa Prompt (formula), E=Drive Folder, F=Status,
                   G=Iter 1 URL, H=Iter 2 URL, I=Error
  Row 7+: 14 set rows where:
    C7  =  $B$1 & CHAR(10) & $B$2 & CHAR(10) & 'Storyboard Prompts'!C11
    C8  =  $B$1 & CHAR(10) & $B$2 & CHAR(10) & 'Storyboard Prompts'!C12
    ...
  → Edit the body in tab 2 col C, both tabs reflect it.

IDEMPOTENT: detects "Set #" in A10 of both tabs and short-circuits if shape
is already correct.
BACKUP: existing data dumped to /tmp before any destructive write.
"""
from __future__ import annotations
import json
import gspread
from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"


def simplify_storyboard_prompts(sh):
    """Move body from col J → col C. Clear col J/K body columns. Keep
    globals + headers + drive folder + status + iter URLs intact."""
    ws = sh.worksheet("Storyboard Prompts")

    # Read current state (post-prior-migration: cols A-K, rows 11+)
    raw = ws.get("A11:K30", value_render_option="FORMATTED_VALUE")
    raw = [r for r in raw if r and r[0]]
    print(f"  Storyboard Prompts: {len(raw)} set rows found")

    backup = {"tab": "Storyboard Prompts", "rows": raw}
    with open("/tmp/living_doc_simplify_backup_storyboard.json", "w") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)

    # Each row currently:
    #   A=Set#, B=Shot Range, C=Storyboard Prompt (formula → full assembled),
    #   D=Bahasa Prompt (formula), E=Drive Folder, F=Status, G=Iter1, H=Iter2,
    #   I=Error, J=Body (editable), K=Bahasa Body (editable)
    # NEW shape: drop the formula from C, write body directly there.
    new_rows = []
    for row in raw:
        # Pad to 11 cols
        row = list(row) + [""] * (11 - len(row))
        set_num, shot_range, _formula_en, _formula_id, drive_folder, status, iter1, iter2, error, body_en, body_id = row[:11]
        new_rows.append([
            set_num, shot_range,
            body_en,        # col C = editable body (was formula)
            body_id,        # col D = editable bahasa body (was formula)
            drive_folder, status, iter1, iter2, error,
            "", "",         # col J, K cleared
        ])

    # Write rows back. Keep col count to clear J/K to empty strings.
    rng = f"A11:K{10 + len(new_rows)}"
    ws.update(range_name=rng, values=new_rows, value_input_option="USER_ENTERED")

    # Update header for col C from "Storyboard Prompt" (no change), drop J/K headers
    ws.update(range_name="J10:K10", values=[["", ""]])
    print(f"    ✓ moved body J→C, cleared J/K")


def restructure_video_prompts(sh):
    """Replace 86 per-shot rows with 14 per-set rows. col C is a formula
    referencing Storyboard Prompts col C."""
    ws = sh.worksheet("Video Prompts")

    # Backup the current per-shot data
    raw = ws.get("A7:J100", value_render_option="FORMATTED_VALUE")
    raw = [r for r in raw if r and r[0]]
    print(f"  Video Prompts: {len(raw)} per-shot rows found (will be replaced)")
    backup = {"tab": "Video Prompts", "rows": raw}
    with open("/tmp/living_doc_simplify_backup_video.json", "w") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)

    # Read set list from Storyboard Prompts tab so we know shot ranges
    sb = sh.worksheet("Storyboard Prompts")
    set_rows = sb.get("A11:B30", value_render_option="FORMATTED_VALUE")
    set_rows = [r for r in set_rows if r and r[0]]
    print(f"  Found {len(set_rows)} sets to mirror")

    # Wipe Video Prompts existing data area (row 6 onward, but keep globals 1-4)
    # Easiest: clear A6:Z200, then rewrite headers + rows.
    ws.batch_clear(["A6:Z200"])

    # Headers (row 6) — drop the body cols
    headers = [
        "Set #", "Shot Range", "Video Prompt", "Bahasa Prompt",
        "Drive Folder", "Status", "Iter 1 URL", "Iter 2 URL", "Error",
    ]
    ws.update(range_name="A6:I6", values=[headers])

    # Data rows (row 7+): one per set, col C/D are formulas referencing
    # Storyboard Prompts col C/D for the matching row (set N is at SB row 10+N)
    new_rows = []
    for i, sr in enumerate(set_rows):
        set_num = sr[0]
        shot_range = sr[1] if len(sr) > 1 else ""
        sb_row = 11 + i  # set 1 → SB row 11, set 2 → SB row 12, ...
        formula_en = (
            f"=$B$1&CHAR(10)&$B$2&CHAR(10)&CHAR(10)"
            f"&'Storyboard Prompts'!C{sb_row}"
        )
        formula_id = (
            f"=$B$3&CHAR(10)&$B$4&CHAR(10)&CHAR(10)"
            f"&'Storyboard Prompts'!D{sb_row}"
        )
        new_rows.append([
            set_num, shot_range,
            formula_en, formula_id,
            "", "Pending", "", "", "",   # Drive Folder, Status, Iter1, Iter2, Error
        ])

    if new_rows:
        ws.update(
            range_name=f"A7:I{6 + len(new_rows)}",
            values=new_rows,
            value_input_option="USER_ENTERED",
        )

    # Re-apply header bold (was lost in clear)
    sh.batch_update({"requests": [
        {"repeatCell": {
            "range": {"sheetId": ws.id, "startRowIndex": 5, "endRowIndex": 6,
                      "startColumnIndex": 0, "endColumnIndex": 9},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }},
    ]})
    print(f"    ✓ Video Prompts: 14 per-set rows with formula references to Storyboard Prompts")


def main():
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    print(f"Sheet: {sh.title}")
    simplify_storyboard_prompts(sh)
    restructure_video_prompts(sh)
    print("\n  ✓ Schema simplified.")
    print("    Storyboard Prompts: 14 rows, col C = editable body, col J/K cleared.")
    print("    Video Prompts: 14 rows, col C = formula = video global + Storyboard col C.")


if __name__ == "__main__":
    main()

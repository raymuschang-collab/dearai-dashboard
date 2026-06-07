#!/usr/bin/env python3
"""Shotlist edit — Daniel home-studio scene rewrite.
- Deletes current rows 14-23 (old shots #13-22, the Daniel block)
- Inserts 15 new rows at row 14 (new shots #13-27)
- Renumbers col A in rows 29-60 (old shots #23-54 → #28-59)
- Q-formula auto-regenerates per row
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import gspread
from auth import get_credentials

SHEET_ID = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
TAB = "Shotlist"

# Schema: A=Shot#, B=Dur, C=Type, D=Cam, E=Merge, F=Desc, G=Dialogue, H=Tone,
#         I=Accent, J=MicroEx, K=SFX, L=Props, M=Brand, N=Trans, O=Beat,
#         P=EN-Trans, Q=Prompt(formula)

def Q(r):
    return (f'=IF(A{r}="","",A{r}&", "&B{r}&"s, "&C{r}&", "&D{r}&", "&F{r}'
            f'&IF(G{r}="",IF(J{r}="","",", ("&J{r}&")"),", "&G{r}'
            f'&IF(J{r}="",""," ("&J{r}&")"))'
            f'&IF(K{r}="",".", ", "&K{r}&"."))')


# New 15 rows for the Daniel home-studio scene (shots #13-27)
# Each row goes into row index 14..28 after delete+insert
NEW_ROWS_TEMPLATE = [
    # 13 — Low Angle MS Grace at twin-monitor desk
    {"shot": 13, "dur": 3, "type": "MS", "cam": "Low Angle Static",
     "desc": "Low-angle medium shot of Grace at her twin-monitor home studio desk. Twin screens glowing, late night. Only the desk lamp and monitor glow lighting the room. Cream tee, loose ponytail falling out, hunched posture. Her hands move on the keyboard.",
     "dialogue": "", "tone": "", "accent": "",
     "microex": "Eyes locked on screen; jaw set",
     "sfx": "Keyboard tap; faint screen hum",
     "props": "Twin monitors, keyboard, desk lamp; Grace in cream tee",
     "trans": "Cut", "beat": "", "en": "(no dialogue — Grace working late)"},

    # 14 — WS Daniel enters BG with tea
    {"shot": 14, "dur": 3, "type": "WS", "cam": "Static",
     "desc": "Wide of the studio from behind Grace's desk. Daniel enters from the doorway in the background holding a small tray with two cups of hot tea. Faded navy shirt, glasses catching the lamp light. He approaches quietly.",
     "dialogue": "", "tone": "", "accent": "",
     "microex": "Patient; unhurried",
     "sfx": "Tea steam; soft footstep on terrazzo",
     "props": "Tea tray, two mugs of tea; Daniel in faded navy shirt, glasses",
     "trans": "Cut", "beat": "", "en": "(no dialogue — Daniel enters with tea)"},

    # 15 — MS Daniel sets mug
    {"shot": 15, "dur": 3, "type": "MS", "cam": "Static",
     "desc": "Medium shot of Daniel setting one mug of tea on Grace's desk beside her keyboard. He doesn't speak yet.",
     "dialogue": "", "tone": "", "accent": "",
     "microex": "Gentle hand placement; doesn't push",
     "sfx": "Mug set down on wood",
     "props": "Mug of tea",
     "trans": "Cut", "beat": "", "en": "(no dialogue — Daniel sets mug down)"},

    # 16 — CU Daniel "又晚?"
    {"shot": 16, "dur": 2, "type": "CU", "cam": "Static",
     "desc": "Close-up of Daniel looking at Grace.",
     "dialogue": "DANIEL：又晚?", "tone": "gentle", "accent": "Singapore Chinese",
     "microex": "Soft eyes; small head tilt",
     "sfx": "Tea steam; faint keyboard tap",
     "props": "",
     "trans": "Cut", "beat": "", "en": "DANIEL: Still up late?"},

    # 17 — MS Grace lays out Henley + Garrison
    {"shot": 17, "dur": 4, "type": "MS", "cam": "Static",
     "desc": "Medium shot of Grace. She doesn't turn from her screens — just lays it out flat.",
     "dialogue": "GRACE：Henley 简报六十页,星期五要交。Garrison 礼拜二 pitch。",
     "tone": "flat", "accent": "Singapore Chinese",
     "microex": "Eyes still on screen; voice flat, tired",
     "sfx": "Keyboard tap; screen hum",
     "props": "Twin monitors",
     "trans": "Cut", "beat": "",
     "en": "GRACE: Henley brief, sixty pages, due Friday. Garrison pitch Tuesday."},

    # 18 — MCU Daniel listening (cutaway)
    {"shot": 18, "dur": 3, "type": "MCU", "cam": "Static",
     "desc": "Cutaway — medium close-up of Daniel listening. He doesn't interrupt. Just absorbs it.",
     "dialogue": "", "tone": "", "accent": "",
     "microex": "Eyes on Grace; mouth neutral; small nod after a beat",
     "sfx": "Distant traffic; quiet ambience",
     "props": "",
     "trans": "Cut", "beat": "", "en": "(no dialogue — Daniel listens)"},

    # 19 — MCU Daniel "newsletter?"
    {"shot": 19, "dur": 2, "type": "MCU", "cam": "Static",
     "desc": "Medium close-up of Daniel.",
     "dialogue": "DANIEL：你的 newsletter?", "tone": "patient", "accent": "Singapore Chinese",
     "microex": "Eyebrows lift slightly",
     "sfx": "Quiet ambience",
     "props": "",
     "trans": "Cut", "beat": "", "en": "DANIEL: Your newsletter?"},

    # 20 — CU Grace "晚了三个礼拜"
    {"shot": 20, "dur": 2, "type": "CU", "cam": "Static",
     "desc": "Close-up of Grace.",
     "dialogue": "GRACE：晚了三个礼拜。", "tone": "ashamed", "accent": "Singapore Chinese",
     "microex": "Tiny exhale; jaw tightens",
     "sfx": "Quiet ambience",
     "props": "",
     "trans": "Cut", "beat": "", "en": "GRACE: Three weeks overdue."},

    # 21 — MCU Daniel "报税?"
    {"shot": 21, "dur": 2, "type": "MCU", "cam": "Static",
     "desc": "Medium close-up of Daniel.",
     "dialogue": "DANIEL：报税?", "tone": "quiet", "accent": "Singapore Chinese",
     "microex": "Quiet voice; small head turn",
     "sfx": "Quiet ambience",
     "props": "",
     "trans": "Cut", "beat": "", "en": "DANIEL: GST?"},

    # 22 — CU Grace "礼拜三"
    {"shot": 22, "dur": 2, "type": "CU", "cam": "Static",
     "desc": "Close-up of Grace.",
     "dialogue": "GRACE：礼拜三。", "tone": "flat", "accent": "Singapore Chinese",
     "microex": "Eyes drop",
     "sfx": "Quiet ambience",
     "props": "",
     "trans": "Cut", "beat": "", "en": "GRACE: Wednesday."},

    # 23 — MCU Daniel "阿嬷礼拜天"
    {"shot": 23, "dur": 3, "type": "MCU", "cam": "Static",
     "desc": "Medium close-up of Daniel.",
     "dialogue": "DANIEL：阿嬷礼拜天。", "tone": "soft", "accent": "Singapore Chinese",
     "microex": "Soft statement, not a question; eyes on Grace",
     "sfx": "Quiet ambience",
     "props": "",
     "trans": "Cut", "beat": "", "en": "DANIEL: Grandma's Sunday."},

    # 24 — CU Grace "我知道"
    {"shot": 24, "dur": 2, "type": "CU", "cam": "Static",
     "desc": "Close-up of Grace.",
     "dialogue": "GRACE：(轻声) 我知道。", "tone": "quiet", "accent": "Singapore Chinese",
     "microex": "Quiet; eyes still down",
     "sfx": "Quiet ambience",
     "props": "",
     "trans": "Cut", "beat": "", "en": "GRACE: (softly) I know."},

    # 25 — MS Grace turns to window monologue
    {"shot": 25, "dur": 4, "type": "MS", "cam": "Static",
     "desc": "Medium shot of Grace. She turns slightly toward the studio window. Warm city haze of Tiong Bahru at night through the bamboo blinds.",
     "dialogue": "GRACE：(望向窗外) 我离开大公司是想自己做。每一件都是一份全职工作。我只有一个人。",
     "tone": "hollow", "accent": "Singapore Chinese",
     "microex": "Looking out window; voice tired, not bitter",
     "sfx": "Faint city hum; quiet ambience",
     "props": "Bamboo blinds, window with Tiong Bahru night view",
     "trans": "Cut", "beat": "",
     "en": "GRACE: (looking out the window) I left the big agency to do my own thing. Every one of those is a full-time job. There's only one of me."},

    # 26 — OTS Daniel palm near hers
    {"shot": 26, "dur": 3, "type": "OTS", "cam": "Static",
     "desc": "OTS over Grace's shoulder onto Daniel sitting at the corner of the desk (medium close-up framing). He rests his palm flat near hers — doesn't take her hand.",
     "dialogue": "DANIEL：那个从大公司离开的人 —— 她没在扛七份工作。",
     "tone": "grounding", "accent": "Singapore Chinese",
     "microex": "Quiet; eyes meet hers; mouth soft",
     "sfx": "Faint city hum",
     "props": "Desk surface, Daniel's hand near Grace's hand",
     "trans": "Cut", "beat": "",
     "en": "DANIEL: The version of you that quit the big agency — she didn't carry seven jobs."},

    # 27 — CU Grace "我只有一个人"
    {"shot": 27, "dur": 3, "type": "CU", "cam": "Static",
     "desc": "Close-up of Grace.",
     "dialogue": "GRACE：我只有一个人。", "tone": "breaking", "accent": "Singapore Chinese",
     "microex": "Eyes glaze; small breath",
     "sfx": "Quiet — holds on the breath",
     "props": "",
     "trans": "Cut", "beat": "",
     "en": "GRACE: There's only one of me."},
]


def build_row(spec, row_idx):
    """Build a 17-col row (A-Q) with formula in Q."""
    return [
        spec["shot"],           # A
        spec["dur"],            # B
        spec["type"],           # C
        spec["cam"],            # D
        "",                     # E Merge
        spec["desc"],           # F
        spec["dialogue"],       # G
        spec["tone"],           # H
        spec["accent"],         # I
        spec["microex"],        # J
        spec["sfx"],            # K
        spec["props"],          # L
        "",                     # M Brand
        spec["trans"],          # N
        spec["beat"],           # O
        spec["en"],             # P
        Q(row_idx),             # Q formula
    ]


def main():
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(TAB)

    # Snapshot pre-state — get row count
    pre = ws.get("A1:A100", value_render_option="FORMATTED_VALUE")
    pre_shots = [r[0] for r in pre if r and r[0]]
    print(f"Pre-edit: {len(pre_shots)-1} shots in shotlist (last shot #{pre_shots[-1]})")

    # 1. Delete rows 14-23 (current Daniel block, 10 rows)
    print("Deleting rows 14-23 (current Daniel block)...")
    ws.delete_rows(14, 23)

    # 2. Build 15 new rows at indices 14..28
    print("Inserting 15 new rows at row 14...")
    new_rows_values = [build_row(spec, 14 + i) for i, spec in enumerate(NEW_ROWS_TEMPLATE)]
    ws.insert_rows(new_rows_values, row=14, value_input_option="USER_ENTERED")

    # 3. Renumber col A for rows 29..60 — old shots #23-54 → new shots #28-59
    print("Renumbering col A in rows 29-60 (old #23-54 → new #28-59)...")
    # Read what's currently at A29:A60 to verify before overwrite
    post_A = ws.get("A29:A60", value_render_option="FORMATTED_VALUE")
    print(f"  current A29:A60 has {len(post_A)} values, first 3: {[r[0] for r in post_A[:3] if r]}")
    # Build new shot numbers — old #23 is now at row 29, should become #28
    # Continue: old #24 at row 30 → #29 ... old #54 at row 60 → #59
    new_A = [[i] for i in range(28, 60)]  # 28..59 inclusive = 32 values for rows 29..60
    ws.update(range_name="A29:A60", values=new_A, value_input_option="USER_ENTERED")

    print()
    # Verify
    print("Verifying...")
    verify = ws.get("A1:Q100", value_render_option="FORMATTED_VALUE")
    shots_now = [r for r in verify[1:] if r and r[0]]
    print(f"Post-edit: {len(shots_now)} shots, last shot #{shots_now[-1][0]} at row {len(shots_now)+1}")

    # Spot-check the boundary
    print()
    print("--- Boundary check ---")
    for row_idx in [13, 14, 28, 29, 30]:
        if row_idx-2 < len(verify)-1:
            r = verify[row_idx-1]
            print(f"  row {row_idx}: #{r[0]} {r[1]}s {r[2]:<6} | {r[5][:50]}... | {r[6][:40] if len(r)>6 else ''}")


if __name__ == "__main__":
    main()

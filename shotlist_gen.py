#!/usr/bin/env python3
"""Atomize a locked script into a DearAI v2.2 episode SOT.

This is intentionally conservative: it produces editable first-pass rows,
keeps formula columns live, and writes only text rows into bible tabs. Image
generation and BytePlus upload are handled by later pipeline stages.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import gspread

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # type: ignore
from _create_blank_sot import shotlist_q_formula, storyboard_body_formula, storyboard_prompt_formula


SHOTLIST_HEADERS_18 = [
    "Shot #", "Duration (s)", "Shot Type", "Camera Movement", "Merge Candidate",
    "Shot Description", "Dialogue/VO", "Tone of Voice", "Accent", "Microexpression",
    "SFX", "Props/Wardrobe", "Brand Integration", "Transition", "Beat",
    "English Translation", "Prompt", "Bahasa Prompt",
]

STORYBOARD_HEADERS = [
    "Set #", "Shot Range", "Storyboard Prompt", "Bahasa Prompt", "Drive Folder",
    "Status", "Iter 1 URL", "Iter 2 URL", "Error",
    "Body", "Bahasa Body", "Location", "Video Iter 1 URL", "Video Iter 2 URL",
]

CHARACTER_HEADERS = [
    "Name", "Alias", "Role / Archetype", "Age", "Gender / Pronouns",
    "Ethnicity / Heritage", "Height", "Weight / Build", "Hair", "Eyes",
    "Distinguishing features", "Wardrobe", "Signature accessory / prop",
    "Personality", "Core theme", "Speech accent", "Mood / aura",
    "First Shot #", "Notes", "Iter 1 URL (white bg)", "Iter 2 URL (white bg)",
    "Status", "Error",
]
LOCATION_HEADERS = [
    "Name", "Shot Size", "Type (INT/EXT)", "Description", "Lighting / Mood",
    "Time of Day", "First Shot #", "Notes", "Prompt", "Iter 1 URL",
    "Iter 2 URL", "Status", "Error", "Feedback", "Aliases",
]
SIMPLE_BIBLE_HEADERS = [
    "Name", "Worn By / Used By", "Description", "First Shot #", "Notes",
    "Prompt", "Iter 1 URL", "Iter 2 URL", "Status", "Error", "Feedback",
]

LOCALE_ACCENT = {
    "jakarta": "Jakarta Bahasa Indonesia with natural code-switching",
    "manila": "Manila Filipino English with natural Tagalog code-switching",
    "seoul": "Seoul Korean with natural English code-switching",
    "generic": "natural local accent",
}


def parse_sheet_id(value: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", value or "")
    return match.group(1) if match else (value or "").strip()


def split_units(text: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
    if len(blocks) >= 8:
        return blocks
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def dialogue_from(text: str) -> str:
    quotes = re.findall(r'"([^"]{2,220})"', text)
    if quotes:
        return " / ".join(quotes[:2])
    return ""


def clean_description(text: str) -> str:
    text = re.sub(r"^[A-Z0-9 ._-]{1,32}:\s*", "", text.strip())
    return re.sub(r"\s+", " ", text)


def shot_type_for(index: int, total: int) -> str:
    if index == 1:
        return "Establishing wide"
    if index == total:
        return "Cliffhanger close-up"
    return ["Medium shot", "Close-up", "Wide shot", "Tracking shot"][index % 4]


def movement_for(index: int) -> str:
    return ["Static hold", "Slow push-in", "Handheld follow", "Whip pan", "Dolly move"][index % 5]


def atomize(script_text: str, locale: str) -> list[list[str]]:
    units = split_units(script_text)
    if not units:
        raise SystemExit("Script is empty")
    accent = LOCALE_ACCENT[locale]
    rows = []
    for i, unit in enumerate(units, start=1):
        desc = clean_description(unit)
        rows.append([
            str(i), "3", shot_type_for(i, len(units)), movement_for(i), "",
            desc[:900], dialogue_from(unit), "", accent, "",
            "", "", "", "", "", "",
        ])
    return rows


def words_by_frequency(text: str) -> list[tuple[str, int]]:
    stop = {"THE", "AND", "WITH", "FROM", "THIS", "THAT", "THEY", "THEIR", "INTO", "WHEN", "WHERE"}
    counts: dict[str, int] = {}
    for token in re.findall(r"\b[A-Z][A-Z0-9'-]{2,}(?:\s+[A-Z][A-Z0-9'-]{2,})?\b", text):
        token = token.strip().upper()
        if token in stop:
            continue
        counts[token] = counts.get(token, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def first_shot_for(name: str, shots: list[list[str]]) -> str:
    pattern = re.compile(rf"\b{re.escape(name)}\b", re.I)
    for row in shots:
        if pattern.search(row[5]) or pattern.search(row[6]):
            return row[0]
    return "1"


def build_bibles(script_text: str, shots: list[list[str]], show_name: str):
    names = [n for n, c in words_by_frequency(script_text) if c >= 2][:12]
    if not names:
        names = [show_name.upper()]
    chars = []
    for name in names[:8]:
        chars.append([
            name, "", "Microdrama character", "", "", "", "", "", "", "",
            "", "Show-appropriate wardrobe", "", "Driven, emotionally readable",
            "Core conflict", "", "Grounded dramatic presence", first_shot_for(name, shots),
            "Auto-extracted from locked script; producer should refine.", "", "", "Pending", "",
        ])
    locations = [[
        "Primary Location", "wide", "INT/EXT", f"Main recurring environment for {show_name}.",
        "Natural cinematic lighting", "", "1",
        "Auto placeholder; producer should rename/refine.", "", "", "", "Pending", "", "", "",
    ]]
    props = []
    for term in [n for n, _ in words_by_frequency(script_text) if n not in names][:12]:
        props.append([term.title(), "", f"Script-mentioned object or production detail: {term}.",
                      first_shot_for(term, shots), "Auto-extracted.", "", "", "", "Pending", "", ""])
    return chars, locations, props, [], []


def formula_columns(headers: list[str]) -> tuple[str, str]:
    prompt_ix = next((i for i, h in enumerate(headers) if h.strip().lower() == "prompt"), 16)
    prompt_col = chr(ord("A") + prompt_ix)
    bahasa_col = chr(ord("A") + prompt_ix + 1)
    return prompt_col, bahasa_col


def ensure_ws(sh, title: str, rows: int, cols: int):
    try:
        ws = sh.worksheet(title)
        ws.resize(rows=max(ws.row_count, rows), cols=max(ws.col_count, cols))
        return ws
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def write_sheet(sheet_id: str, show_name: str, shots: list[list[str]], bibles, dry_run: bool) -> None:
    set_count = math.ceil(len(shots) / 5)
    if dry_run:
        print(f"DRY RUN: would write {len(shots)} shot rows and {set_count} storyboard sets to {sheet_id}")
        for row in shots[:5]:
            print(f"  shot {row[0]}: {row[5][:100]}")
        chars, locs, props, costumes, effects = bibles
        print(f"  bible rows: CHARACTERS={len(chars)} LOCATIONS={len(locs)} PROPS={len(props)} COSTUME={len(costumes)} EFFECTS={len(effects)}")
        return

    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(parse_sheet_id(sheet_id))

    shot_ws = ensure_ws(sh, "Shotlist", max(120, len(shots) + 5), 18)
    headers = shot_ws.row_values(1)
    if not headers:
        headers = SHOTLIST_HEADERS_18
        shot_ws.update(range_name="A1:R1", values=[headers], value_input_option="RAW")
    prompt_col, bahasa_col = formula_columns(headers + [""] * 20)
    shot_ws.update(range_name=f"A2:P{len(shots)+1}", values=shots, value_input_option="USER_ENTERED")
    q_values = [[shotlist_q_formula(r)] for r in range(2, len(shots) + 2)]
    r_values = [[f'=IF(A{r}="","",GOOGLETRANSLATE({prompt_col}{r},"en","id"))'] for r in range(2, len(shots) + 2)]
    sh.values_batch_update(body={"valueInputOption": "USER_ENTERED", "data": [
        {"range": f"Shotlist!{prompt_col}2:{prompt_col}{len(shots)+1}", "values": q_values},
        {"range": f"Shotlist!{bahasa_col}2:{bahasa_col}{len(shots)+1}", "values": r_values},
    ]})

    sp = ensure_ws(sh, "Storyboard Prompts", max(50, set_count + 12), 14)
    sp.update(range_name="A10:N10", values=[STORYBOARD_HEADERS], value_input_option="RAW")
    sp_rows = []
    for n in range(1, set_count + 1):
        start, end = (n - 1) * 5 + 1, min(n * 5, len(shots))
        sp_rows.append([str(n), f"{start}-{end}", storyboard_prompt_formula(),
                        f'=IF(A{10+n}="","",GOOGLETRANSLATE(C{10+n},"en","id"))',
                        "", "Pending", "", "", "", storyboard_body_formula(),
                        f'=IF(A{10+n}="","",GOOGLETRANSLATE(J{10+n},"en","id"))',
                        "", "", ""])
    sp.update(range_name=f"A11:N{10+set_count}", values=sp_rows, value_input_option="USER_ENTERED")

    chars, locs, props, costumes, effects = bibles
    ensure_ws(sh, "CHARACTERS", max(50, len(chars) + 2), 23).update(range_name=f"A1:W{len(chars)+1}", values=[CHARACTER_HEADERS] + chars, value_input_option="USER_ENTERED")
    ensure_ws(sh, "LOCATIONS", max(50, len(locs) + 5), 15).update(range_name=f"A4:O{len(locs)+4}", values=[LOCATION_HEADERS] + locs, value_input_option="USER_ENTERED")
    for title, rows in [("PROPS", props), ("COSTUME", costumes), ("EFFECTS", effects)]:
        ws = ensure_ws(sh, title, max(50, len(rows) + 6), 11)
        values = [SIMPLE_BIBLE_HEADERS] + rows if rows else [SIMPLE_BIBLE_HEADERS]
        ws.update(range_name=f"A5:K{len(values)+4}", values=values, value_input_option="USER_ENTERED")
    print(f"Done: wrote {len(shots)} shots, {set_count} sets, and text bible rows to {sh.title}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--script", required=True, help="Locked script path")
    ap.add_argument("--sheet", required=True, help="Target episode SOT sheet ID or URL")
    ap.add_argument("--name", required=True, help="Show name")
    ap.add_argument("--locale", default="generic", choices=sorted(LOCALE_ACCENT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    script_path = Path(args.script).expanduser()
    script_text = script_path.read_text(encoding="utf-8")
    shots = atomize(script_text, args.locale)
    bibles = build_bibles(script_text, shots, args.name)
    write_sheet(args.sheet, args.name, shots, bibles, args.dry_run)


if __name__ == "__main__":
    main()

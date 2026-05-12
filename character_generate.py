#!/usr/bin/env python3
"""
Generate character reference sheets via Higgsfield gpt_image_2.

Reads the CHARACTERS tab, fills the character-bible prompt with each row's
data, calls Higgsfield gpt_image_2, uploads the PNG to
the show's character-refs/ Drive folder, sets anyone-with-link sharing,
writes the URL back to the Reference Image URL column.

Idempotent: skips Status="Done" rows unless --force passed.

Usage:
    python3 character_generate.py --sheet <sheet-id-or-url>
    python3 character_generate.py --sheet <id> --character KHENSU       # one row
    python3 character_generate.py --sheet <id> --force                  # regenerate Done
    python3 character_generate.py --sheet <id> --quality medium         # low/medium/high
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time

import gspread
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from auth import get_credentials
import higgs_gen


HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

MODEL = "gpt_image_2"  # Higgsfield CLI
DEFAULT_ASPECT = "16:9"
DEFAULT_QUALITY = "high"
DEFAULT_RESOLUTION = "2k"

SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


PROMPT_TEMPLATE = """Professional cinematic character reference sheet, single landscape page, {background}, clean infographic layout with labeled sections and thin divider lines, documentary editorial portrait photography aesthetic, natural skin texture with visible pores and small natural imperfections, Kodak Portra 400 color science, no airbrushing, no beauty retouch, no game-engine rendering, no movie-poster polish. Editorial / production-bible aesthetic. Aspect ratio 16:9, ultra-high detail.
CHARACTER BIBLE (fill in):

Name: {name}
Alias: {alias}
Role / Archetype: {role}
Age: {age}
Gender / Pronouns: {gender}
Ethnicity / Heritage: {ethnicity}
Height: {height}
Weight / Build: {build}
Hair: {hair}
Eyes: {eyes}
Distinguishing features: {distinguishing}
Wardrobe: {wardrobe}
Signature accessory / prop: {prop}
Personality: {personality}
Core theme: {theme}
Speech accent: {accent}
Mood / aura: {mood}

LAYOUT — render all of these labeled panels on one page:

Top-left header block titled "CHARACTER REFERENCE SHEET" listing Name, Alias, Role, Age, Personality, Core Theme, Speech Accent.
"MAIN IDENTITY + SCALE SHEET": four full-body shots on a height grid — 1. Front, 2. 3/4 view, 3. Side, 4. Back. Identical lighting, wardrobe, and proportions across all four. Leave the height grid markings blank / unlabeled so they can be filled in later.
"COLOR PALETTE": a row of 7 swatches sampled from the wardrobe and skin tones.
"EXPRESSION PROGRESSION": 8 head-and-shoulders shots labeled Neutral, Curious, Worried, Surprised, Afraid, Sad, Determined, Relieved.
"MICRO EXPRESSIONS": 5 tight close-ups labeled Subtle Eye Tension, Slight Smirk, Lip Tension, Brow Furrow, Controlled Breath.
"HEAD DETAIL SHEET": 5 head angles labeled 3/4 Headshot, Side Headshot, Top Angle, Low Angle, Diagonal Angle.
"NEUTRAL BASELINE" + "POSTURE VARIATION": full-body shots labeled Relaxed, Tense, Confident.
"WARDROBE / ACCESSORIES DETAILS": 4 macro crops — hairstyle detail, overcoat / outerwear detail, footwear, accessories.
"PROP": an isolated product-style shot of the signature prop, with a small empty spec block beside it (Object Name, Type, Traits).
"CLOSE-UP POSE": one large hero portrait with cinematic lighting.

Maintain consistent face, build, wardrobe, and lighting across every panel. Muted, desaturated palette. Subtle film grain. Shot on medium format film, natural skin tones, raw editorial honesty over glamour."""


def parse_sheet_id(s: str) -> str:
    m = SHEETS_URL_RE.search(s)
    return m.group(1) if m else s.strip()


def slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name)[:60].strip("_")


def get_or_create_folder(drive, parent_id: str, name: str) -> str:
    safe = name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and trashed=false "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and name='{safe}'"
    )
    res = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()
    if res.get("files"):
        return res["files"][0]["id"]
    return drive.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()["id"]


def generate_image(prompt: str, aspect_ratio: str, quality: str,
                    resolution: str = DEFAULT_RESOLUTION) -> bytes:
    """Higgsfield gpt_image_2 via CLI."""
    return higgs_gen.generate(
        prompt=prompt, model=MODEL,
        aspect_ratio=aspect_ratio,
        quality=quality, resolution=resolution,
    )


def upload_and_share(drive, folder_id: str, filename: str, content: bytes) -> str:
    """Resumable upload — non-resumable BrokenPipe'd on 6-8MB
    gpt_image_2 character-sheet outputs. 1MB chunks survive transient
    network hiccups between the local box and Drive's edge."""
    # Write to a tempfile so MediaFileUpload can stream it in chunks
    # (resumable streaming from a BytesIO is unreliable across forks).
    import tempfile
    from googleapiclient.http import MediaFileUpload
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(content)
        tmp_path = tf.name
    try:
        media = MediaFileUpload(tmp_path, mimetype="image/png",
                                resumable=True, chunksize=1024 * 1024)
        request = drive.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id,webViewLink",
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        drive.permissions().create(
            fileId=response["id"],
            body={"role": "reader", "type": "anyone"},
            fields="id",
        ).execute()
        return response["webViewLink"]
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# Single-iter per char from now on. Each regen produces iter 1 (off-white bg)
# only — half the credits, half the time, and the dashboard already only shows
# Iter 1 URL prominently. To restore 2-iter mode, add the dark-bg dict back.
ITERS = [
    {"num": 1, "background": "off-white studio background (light ivory tone)", "suffix": "iter-1"},
]


def build_prompt(row: dict, *, background: str) -> str:
    return PROMPT_TEMPLATE.format(
        background=background,
        name=row.get("Name", "") or "Unnamed",
        alias=row.get("Alias", "") or "—",
        role=row.get("Role / Archetype", "") or "—",
        age=row.get("Age", "") or "—",
        gender=row.get("Gender / Pronouns", "") or "—",
        ethnicity=row.get("Ethnicity / Heritage", "") or "—",
        height=row.get("Height", "") or "—",
        build=row.get("Weight / Build", "") or "—",
        hair=row.get("Hair", "") or "—",
        eyes=row.get("Eyes", "") or "—",
        distinguishing=row.get("Distinguishing features", "") or "—",
        wardrobe=row.get("Wardrobe", "") or "—",
        prop=row.get("Signature accessory / prop", "") or "—",
        personality=row.get("Personality", "") or "—",
        theme=row.get("Core theme", "") or "—",
        accent=row.get("Speech accent", "") or "—",
        mood=row.get("Mood / aura", "") or "—",
    )


# Column letters in the 23-col CHARACTERS schema
COL_ITER1 = "T"
COL_ITER2 = "U"
COL_STATUS = "V"
COL_ERROR = "W"


def process_character(
    chars_ws,
    drive,
    sheet_row: int,
    row: dict,
    char_folder_id: str,
    image_size: str,
    quality: str,
    *,
    force: bool = False,
) -> dict:
    name = row.get("Name", "")
    status = row.get("Status", "")

    if not name:
        return {"status": "skip", "reason": "no name"}

    if status == "Done" and not force:
        print(f"\n=== {name} (row {sheet_row}) — SKIP (already Done) ===")
        return {"status": "skip", "reason": "already Done"}

    print(f"\n=== {name} (row {sheet_row}) ===")
    chars_ws.update(range_name=f"{COL_STATUS}{sheet_row}", values=[["Generating"]])

    iter_urls = [None, None]
    err = None
    for it in ITERS:
        prompt = build_prompt(row, background=it["background"])
        print(f"  iter {it['num']} ({it['background'][:40]}...): generating...", end="", flush=True)
        t0 = time.time()
        try:
            img = generate_image(prompt, image_size, quality)
            gen_dt = time.time() - t0
            print(f" {len(img)//1024}KB in {gen_dt:.1f}s", end="", flush=True)

            fname = f"{slugify(name)}-{it['suffix']}.png"
            url = upload_and_share(drive, char_folder_id, fname, img)
            print(f" → uploaded")
            print(f"    {url}")
            iter_urls[it["num"] - 1] = url
        except Exception as e:
            err = f"iter {it['num']}: {type(e).__name__}: {e}"
            print(f"\n  FAILED: {err}")
            # Don't break — keep trying the other iter independently.
            continue

    iter1, iter2 = iter_urls[0] or "", iter_urls[1] or ""
    if iter1 and iter2:
        sheet_status, err_msg = "Done", ""
    elif iter1 or iter2:
        sheet_status, err_msg = "Done", err or ""  # partial success counts as Done
    else:
        sheet_status, err_msg = "Failed", err or "unknown error"
    chars_ws.update(
        range_name=f"{COL_ITER1}{sheet_row}:{COL_ERROR}{sheet_row}",
        values=[[iter1, iter2, sheet_status, err_msg]],
        value_input_option="USER_ENTERED",
    )
    print(f"  → row {sheet_row}: {sheet_status} (iter1={'✓' if iter1 else '✗'}, iter2={'✓' if iter2 else '✗'})")
    return {"status": "done" if sheet_status == "Done" else "fail",
            "iter1": iter1, "iter2": iter2, "error": err}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True, help="Sheet ID or URL")
    ap.add_argument("--character", help="Generate only this character (matches Name col exactly)")
    ap.add_argument("--force", action="store_true", help="Regenerate Done characters")
    ap.add_argument("--aspect", default=DEFAULT_ASPECT,
                    choices=["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
                    help=f"Higgsfield gpt_image_2 aspect ratio (default {DEFAULT_ASPECT})")
    ap.add_argument("--quality", default=DEFAULT_QUALITY,
                    choices=["low", "medium", "high"],
                    help="Higgsfield gpt_image_2 quality (default high)")
    ap.add_argument("--resolution", default=DEFAULT_RESOLUTION,
                    choices=["1k", "2k", "4k"],
                    help=f"Higgsfield gpt_image_2 resolution (default {DEFAULT_RESOLUTION})")
    args = ap.parse_args()

    higgs_gen.assert_authed()

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_id = parse_sheet_id(args.sheet)
    sh = gc.open_by_key(sheet_id)
    print(f"Sheet: {sh.title}")
    print(f"Aspect: {args.aspect}  Quality: {args.quality}  Resolution: {args.resolution}")

    # Make sure CHARACTERS tab is the v23 schema (with iter 1 + iter 2 URL columns)
    chars_ws = sh.worksheet("CHARACTERS")
    headers = chars_ws.row_values(1)
    if (
        len(headers) < 23
        or headers[0] != "Name"
        or headers[15] != "Speech accent"
        or "Iter 1" not in headers[19]
        or "Iter 2" not in headers[20]
    ):
        sys.exit(
            f"CHARACTERS tab schema mismatch (expected 23 cols with Iter 1 URL at T, Iter 2 URL at U, "
            f"got {len(headers)} cols). Run pharaoh_characters_migrate.py first."
        )

    # Get parent folder for character-refs/
    sheet_meta = drive.files().get(fileId=sheet_id, fields="parents").execute()
    parent_id = sheet_meta["parents"][0]
    char_folder_id = get_or_create_folder(drive, parent_id, "character-refs")
    print(f"character-refs/ id={char_folder_id}")

    rows = chars_ws.get_all_records()

    overall_start = time.time()
    results = []
    for i, row in enumerate(rows):
        sheet_row = i + 2
        name = row.get("Name", "")
        if args.character and name != args.character:
            continue
        result = process_character(
            chars_ws,
            drive,
            sheet_row,
            row,
            char_folder_id,
            args.aspect,
            args.quality,
            force=args.force,
        )
        results.append((name, result))

    total_dt = time.time() - overall_start
    print(f"\n\n=== SUMMARY ({total_dt:.1f}s) ===")
    counts = {"done": 0, "skip": 0, "fail": 0}
    for name, r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        line = f"  {name}: {r['status']}"
        if r.get("reason"):
            line += f" ({r['reason']})"
        print(line)
    print(
        f"\n  TOTAL: {counts.get('done', 0)} done, "
        f"{counts.get('skip', 0)} skipped, {counts.get('fail', 0)} failed"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
One-off: generate ISFET SPAWN (2) and TINY SCORPIONS (2) as scale-comparison
reference images.

Different from character_generate.py: this skips the multi-panel reference-sheet
template and uses custom single-frame prompts focused on size comparison with
a human figure. Per script: Isfet Spawn = 60ft long (6 stories), Tiny Scorpions
= 1in each (palm-scale).

Adds two new rows to CHARACTERS tab:
  row 9:  ISFET SPAWN (2)  — kaiju-scale comparison
  row 10: TINY SCORPIONS (2) — palm-scale macro comparison

Each gets 2 iterations (off-white bg + dark bg) like every other character row.
Uploads PNGs to character-refs/{slug}/ and writes URLs to T/U columns.
"""
from __future__ import annotations

import io
import os
import re
import time

# Load .env BEFORE importing fal_client (it caches FAL_KEY at import time)
from dotenv import load_dotenv
HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

import fal_client
import gspread
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"
MODEL = "openai/gpt-image-2"
IMAGE_SIZE = "landscape_16_9"
QUALITY = "high"


# === Multi-panel reference sheets WITH a SCALE REFERENCE corner panel ===
# Same multi-panel infographic look as the other character refs (KHENSU, AHMOSE, etc.)
# but one corner panel is dedicated to creature-vs-human scale.

ISFET_SCALE_PROMPT = (
    "Professional cinematic creature reference sheet, single landscape page, "
    "clean infographic layout with labeled sections and thin black divider lines, "
    "documentary editorial photography aesthetic, Kodak Portra 400 color science, "
    "no airbrushing, no game-engine rendering, no movie-poster polish. "
    "Editorial / production-bible aesthetic. Aspect ratio 16:9, ultra-high detail.\n\n"

    "Creature: ISFET SPAWN — Spawn of Apep\n"
    "Role: Monster antagonist, mythological born of chaos\n"
    "Length: 60 feet long (18 meters)\n"
    "Overall height: ~30 feet at carapace top; ~60 feet (six stories) with tail and stinger raised\n"
    "Scale anchor: TEN TIMES the height of a 6-foot human warrior — kaiju scale\n"
    "Build: Massive scorpion-like body, segmented and armored\n"
    "Eyes: Multiple compound insect eyes, alien\n"
    "Distinguishing features: Obsidian-black armored shell with jagged segmented plates "
    "and oily sheen reflecting sunlight; yellow bile drips from twitching mandibles "
    "(sizzles and smokes on contact with sand); massive pincers; ONE single segmented tail "
    "curving over the body (ONE tail only — never two, never multiple); stinger towering "
    "above the body; sand cascades off the carapace.\n"
    "Mood / aura: Apocalyptic, nightmare, the desert turned hostile\n\n"

    "LAYOUT — Multi-panel reference sheet with these sections, each clearly labeled:\n"
    "• HERO SHOT (largest panel): full body of the creature in dramatic three-quarter angle, "
    "towering over the desert at midday, dust haze, low camera angle.\n"
    "• TAIL DETAIL: close-up of the SINGLE segmented tail (ONE tail only, never multiple) "
    "curving overhead with stinger glinting.\n"
    "• PINCER DETAIL: close-up of one massive pincer mid-strike.\n"
    "• MANDIBLE DETAIL: close-up of the twitching mandibles with yellow bile dripping.\n"
    "• SHELL DETAIL: macro of the obsidian-black armored plates with oily sheen.\n"
    "• SCALE REFERENCE (corner panel — bottom-right): silhouette comparison on flat sand, "
    "no perspective tricks, both figures rendered at the same depth. A single ancient "
    "Egyptian sun-guard warrior (6 FEET TALL, linen kilt, bronze chest plate, spear) stands "
    "next to the creature. CRITICAL SIZE RATIO: the scorpion is TEN TIMES the warrior's "
    "height. Counting the curling tail and raised stinger, the creature towers approximately "
    "60 feet (six stories) above the warrior. The warrior's head should reach barely halfway "
    "up the scorpion's LOWEST LEG — knee-high to the lowest leg joint at most. He looks like "
    "a tiny toy figurine standing next to a six-story building. The scorpion fills the panel; "
    "the warrior is a small but visible silhouette. The ratio must be unmistakable at a glance: "
    "10:1 height, kaiju vs human.\n"
    "• COLOR PALETTE (thin row): 7 swatches sampled from the obsidian shell, yellow bile, "
    "desert sand, dust haze.\n\n"

    "Each panel separated by thin black lines and labeled in small caps. "
    "Subtle film grain, prestige cinematic palette, muted desaturated tones, raw editorial honesty."
)

TINY_SCORPIONS_SCALE_PROMPT = (
    "Professional cinematic creature reference sheet, single landscape page, "
    "clean infographic layout with labeled sections and thin black divider lines, "
    "documentary editorial macro photography aesthetic, Kodak Portra 400 color science, "
    "no airbrushing, no game-engine rendering. Editorial / production-bible aesthetic. "
    "Aspect ratio 16:9, ultra-high detail.\n\n"

    "Creature: TINY SCORPIONS — Swarm of Apep\n"
    "Role: Swarm spawn (released from the Isfet Spawn's broken shell)\n"
    "Size: Approximately 1 inch / 2.5 cm per individual — palm-scale\n"
    "Build: Insect-small, glistening like wet obsidian shards, hive-mind swarm of hundreds\n"
    "Eyes: Multiple compound eyes per individual\n"
    "Distinguishing features: Wet-obsidian carapace, tiny stingers raised, dense fast-moving "
    "black wave; each scorpion fully articulated — segmented body, eight legs, curling tail.\n"
    "Mood / aura: Skittering nightmare horde\n\n"

    "LAYOUT — Multi-panel reference sheet with these sections, each clearly labeled:\n"
    "• HERO SHOT (largest panel): a single tiny scorpion in macro detail, isolated on sand, "
    "wet-obsidian carapace catching desert light.\n"
    "• SWARM DETAIL: dozens of the scorpions moving as a dense black wave across desert sand.\n"
    "• ANATOMY DETAIL: close-up of one individual showing legs, stinger, mandibles.\n"
    "• BIRTH DETAIL: scorpions emerging from a crack in obsidian shell (the Isfet Spawn carapace).\n"
    "• SCALE REFERENCE (corner panel — bottom-right): an open ancient-Egyptian human palm and "
    "forearm filling the frame at human scale (visible skin pores, knuckle creases, sand-dust "
    "in palm lines), with several tiny scorpions crawling across the palm. Each scorpion is "
    "visibly TINY against the human skin — coin-sized at most — to convey '1 inch each' at a "
    "glance. Macro photography, hard shadows.\n"
    "• COLOR PALETTE (thin row): 7 swatches sampled from the obsidian carapace, sand, "
    "human skin tones.\n\n"

    "Each panel separated by thin black lines and labeled in small caps. "
    "Subtle film grain, prestige cinematic palette."
)


ITERATIONS = [
    {"label": "off-white bg",
     "bg_qualifier": (
         "Set against an off-white studio background (light ivory, soft seamless paper). "
         "The scene above is rendered as a still photograph with the off-white seamless behind it. "
     )},
    {"label": "dark bg",
     "bg_qualifier": (
         "Set against a dark studio background (deep charcoal, soft seamless paper). "
         "The scene above is rendered as a still photograph with the dark seamless behind it, "
         "rim-lit subjects so they separate cleanly from the dark backdrop. "
     )},
]


CHARACTER_ROWS = [
    {
        "name": "ISFET SPAWN (2)",
        "row": 9,
        "alias": "Spawn of Apep — scale reference",
        "role": "Monster antagonist (scale-comparison ref)",
        "height": "60 feet long / 18m (six stories tall)",
        "notes": "Scale reference image: scorpion shown next to human warrior to convey kaiju proportions. Per Frame.io feedback (4/30): all 'too small' notes addressed by establishing canonical scale.",
        "prompt": ISFET_SCALE_PROMPT,
        "subfolder": "isfet-spawn-2",
    },
    {
        "name": "TINY SCORPIONS (2)",
        "row": 10,
        "alias": "Swarm of Apep — scale reference",
        "role": "Swarm spawn (scale-comparison ref)",
        "height": "1 inch each (palm-scale)",
        "notes": "Scale reference image: swarm shown across human palm/forearm to convey per-individual smallness while swarm density implies threat.",
        "prompt": TINY_SCORPIONS_SCALE_PROMPT,
        "subfolder": "tiny-scorpions-2",
    },
]


def slugify(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", s)[:60].strip("_").lower()


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
    folder = drive.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()
    # Anyone-with-link reader so embedded URLs work
    try:
        drive.permissions().create(
            fileId=folder["id"],
            body={"role": "reader", "type": "anyone"},
            fields="id",
        ).execute()
    except Exception:
        pass
    return folder["id"]


def trash_existing(drive, folder_id: str, filename: str):
    safe = filename.replace("'", "\\'")
    res = drive.files().list(
        q=f"'{folder_id}' in parents and trashed=false and name='{safe}'",
        fields="files(id)", pageSize=10,
    ).execute()
    for f in res.get("files", []):
        drive.files().update(fileId=f["id"], body={"trashed": True}).execute()


def upload_and_share(drive, folder_id: str, filename: str, content: bytes) -> str:
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="image/png", resumable=False)
    f = drive.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id,webViewLink",
    ).execute()
    drive.permissions().create(
        fileId=f["id"],
        body={"role": "reader", "type": "anyone"},
        fields="id",
    ).execute()
    return f["webViewLink"]


def generate_image(prompt: str) -> bytes:
    result = fal_client.subscribe(
        MODEL,
        arguments={
            "prompt": prompt,
            "image_size": IMAGE_SIZE,
            "quality": QUALITY,
            "num_images": 1,
            "output_format": "png",
        },
        with_logs=False,
    )
    if not result.get("images"):
        raise RuntimeError(f"No images: {result}")
    img_url = result["images"][0]["url"]
    r = requests.get(img_url, timeout=300)
    r.raise_for_status()
    return r.content


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Only regen this character name (e.g. 'ISFET SPAWN (2)')")
    ap.add_argument("--iter", type=int, choices=[1, 2], help="Only regen this iteration (1 or 2)")
    args = ap.parse_args()

    if not os.getenv("FAL_KEY"):
        raise SystemExit("FAL_KEY not loaded — check .env")

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet("CHARACTERS")
    print(f"Sheet: {sh.title}")

    # Find character-refs root via show folder
    sheet_meta = drive.files().get(fileId=SHEET_ID, fields="parents").execute()
    show_folder_id = sheet_meta["parents"][0]
    char_root = get_or_create_folder(drive, show_folder_id, "character-refs")
    print(f"  character-refs/ → {char_root}")

    for cr in CHARACTER_ROWS:
        if args.only and cr["name"] != args.only:
            continue
        row = cr["row"]
        name = cr["name"]
        print(f"\n=== {name} (row {row}) ===")

        # Write the row metadata if cell A is empty (idempotent on re-runs)
        existing_a = (ws.acell(f"A{row}").value or "").strip()
        if existing_a != name:
            # Populate the new row
            row_values = [
                name,                                           # A Name
                cr["alias"],                                    # B Alias
                cr["role"],                                     # C Role
                "N/A",                                          # D Age
                "N/A",                                          # E Gender
                "Mythological",                                 # F Ethnicity
                cr["height"],                                   # G Height
                "",                                             # H Weight/Build
                "",                                             # I Hair
                "",                                             # J Eyes
                "Scale reference image — see iter URLs",        # K Distinguishing
                "",                                             # L Wardrobe
                "",                                             # M Accessory
                "",                                             # N Personality
                "Scale anchor",                                 # O Core theme
                "",                                             # P Speech accent
                "",                                             # Q Mood
                "",                                             # R First Shot #
                cr["notes"],                                    # S Notes
                "",                                             # T Iter 1 URL
                "",                                             # U Iter 2 URL
                "Generating",                                   # V Status
                "",                                             # W Error
                "",                                             # X Feedback
            ]
            ws.update(range_name=f"A{row}:X{row}", values=[row_values])
            print(f"  populated row {row} metadata")

        # Per-character subfolder
        sub_id = get_or_create_folder(drive, char_root, cr["subfolder"])

        # Single-iter mode: regen one iter, leave the other intact in the sheet
        if args.iter is not None:
            i = args.iter
            it = ITERATIONS[i - 1]
            full_prompt = cr["prompt"] + "\n\n" + it["bg_qualifier"]
            t0 = time.time()
            print(f"  iter {i} ({it['label']}) ONLY: generating...", end="", flush=True)
            try:
                img = generate_image(full_prompt)
                fname = f"{cr['subfolder']}-iter-{i}.png"
                trash_existing(drive, sub_id, fname)
                url = upload_and_share(drive, sub_id, fname, img)
                print(f" {len(img) // 1024}KB in {time.time() - t0:.1f}s → uploaded")
                print(f"    {url}")
                # Update only the iter we regen'd; preserve other iter URL
                target_col = "T" if i == 1 else "U"
                ws.update(range_name=f"{target_col}{row}", values=[[url]],
                          value_input_option="USER_ENTERED")
                print(f"  ✓ {target_col}{row} updated")
            except Exception as e:
                print(f"\n  FAILED: {type(e).__name__}: {e}")
            continue

        # Default: regen both iters
        iter_urls = [None, None]
        err = None
        for i, it in enumerate(ITERATIONS, 1):
            full_prompt = cr["prompt"] + "\n\n" + it["bg_qualifier"]
            t0 = time.time()
            print(f"  iter {i} ({it['label']}): generating...", end="", flush=True)
            try:
                img = generate_image(full_prompt)
                fname = f"{cr['subfolder']}-iter-{i}.png"
                trash_existing(drive, sub_id, fname)
                url = upload_and_share(drive, sub_id, fname, img)
                iter_urls[i - 1] = url
                print(f" {len(img) // 1024}KB in {time.time() - t0:.1f}s → uploaded")
                print(f"    {url}")
            except Exception as e:
                err = f"iter {i}: {type(e).__name__}: {e}"
                print(f"\n  FAILED: {err}")
                break

        if all(iter_urls):
            ws.update(
                range_name=f"T{row}:W{row}",
                values=[[iter_urls[0], iter_urls[1], "Done", ""]],
                value_input_option="USER_ENTERED",
            )
            print(f"  ✓ row {row} → Done")
        else:
            ws.update(
                range_name=f"T{row}:W{row}",
                values=[[iter_urls[0] or "", iter_urls[1] or "", "Failed", err or "unknown error"]],
                value_input_option="USER_ENTERED",
            )
            print(f"  ✗ row {row} → Failed")


if __name__ == "__main__":
    main()

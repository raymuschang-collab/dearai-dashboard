#!/usr/bin/env python3
"""
Render a single storyboard via gpt-image-2 with auto-injected character + location refs.

Reads the body from Storyboard Prompts col C (source of truth), prepends storyboard
globals from B1-B4, scans the body for character names + location keywords, pulls
their iter 1 reference image URLs from CHARACTERS / LOCATIONS bibles, and calls
fal.ai gpt-image-2 with the prompt + reference image URLs.

Result lands in storyboards/set-NN/ as `manual-iter-1.png` so it doesn't clobber
the existing Reve-generated iter 1/2.

Usage:
  python3 render_set_with_refs.py --set 5
  python3 render_set_with_refs.py --set 5 --model nano-banana-2  # alt model
"""
from __future__ import annotations
import argparse
import io
import os
import re
import time

# Load .env BEFORE fal_client import
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

# Location keyword aliases — body often says "rooftop" but bible says
# "Rooftop above the Bazaar". Match by keyword presence.
LOCATION_ALIASES = {
    "rooftop": "Rooftop above the Bazaar",
    "bazaar": "Peasant Bazaar",
    "marketplace": "Peasant Bazaar",
    "pyramid": "Desert Plateau / Great Pyramid",
    "battlefield": "Pyramid Field (Battlefield)",
    "battle space": "Pyramid Field (Battlefield)",
    "pyramid field": "Pyramid Field (Battlefield)",
    "base of the pyramid": "Base of the Pyramid",
    "crater": "Impact Crater",
}


def drive_id_from_url(url: str):
    if not url:
        return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def folder_id_from_url(url: str):
    if not url:
        return None
    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def lh3_url(file_id: str, w: int = 1024) -> str:
    return f"https://lh3.googleusercontent.com/d/{file_id}=w{w}"


def detect_characters(body: str, char_rows: list) -> list:
    """Return list of (name, ref_url) for characters mentioned in body."""
    refs = []
    for r in char_rows:
        if not r or not r[0]:
            continue
        name = r[0].strip()
        if re.search(r"\b" + re.escape(name) + r"\b", body, re.IGNORECASE):
            iter1 = r[19] if len(r) > 19 else ""
            fid = drive_id_from_url(iter1)
            if fid:
                refs.append((name, lh3_url(fid)))
    return refs


def detect_locations(body: str, loc_rows: list) -> list:
    """Return list of (location_name, ref_url) for locations mentioned in body.
    Uses both exact name match and keyword aliases. Pulls 'wide' variant."""
    body_lc = body.lower()
    matched_names = set()

    # Exact name matches first
    for r in loc_rows:
        if not r or not r[0]:
            continue
        name = r[0].strip()
        if name and name.lower() in body_lc:
            matched_names.add(name)

    # Keyword alias matches (catches "rooftop" → "Rooftop above the Bazaar")
    for kw, canonical_name in LOCATION_ALIASES.items():
        if kw in body_lc:
            matched_names.add(canonical_name)

    # Pull the 'wide' iter 1 URL for each matched location
    refs = []
    for r in loc_rows:
        if not r or not r[0]:
            continue
        name = r[0].strip()
        shot_size = r[1].strip() if len(r) > 1 else ""
        if name in matched_names and shot_size == "wide":
            iter1 = r[9] if len(r) > 9 else ""
            fid = drive_id_from_url(iter1)
            if fid:
                refs.append((f"{name} (wide)", lh3_url(fid)))
    return refs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=int, required=True, help="Set # to render")
    ap.add_argument(
        "--model",
        default="nano-banana-2",
        choices=["gpt-image-2", "nano-banana-2", "openai-direct"],
        help="Provider for ref-conditioned photoreal storyboard. Default nano-banana-2 "
             "(placeholder). 'openai-direct' uses OPENAI_API_KEY for gpt-image-2 with "
             "native multi-ref. Switch when the key is wired.",
    )
    ap.add_argument(
        "--iter",
        type=int,
        choices=[3, 4],
        help="Which iter slot to write. Omit to generate BOTH iter 3 and iter 4.",
    )
    args = ap.parse_args()

    if not os.getenv("FAL_KEY"):
        raise SystemExit("FAL_KEY not loaded — check .env")

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    sh = gc.open_by_key(SHEET_ID)

    # === Read source of truth ===
    # Body comes from Storyboard Prompts col C (per-set 5-shot list).
    # Globals come from VIDEO PROMPTS B1+B2 (camera + audio/dialogue) — NOT
    # the Storyboard Prompts globals (which would force pencil/stick-figure
    # aesthetic). Manual iter is meant to be a photoreal proxy of the final
    # video, so we use the same Arri 35 globals the video gen will use.
    sb = sh.worksheet("Storyboard Prompts")
    sheet_row = 10 + args.set  # set 1 → row 11
    row_data = sb.get(f"A{sheet_row}:I{sheet_row}", value_render_option="FORMATTED_VALUE")[0]
    set_num = row_data[0]
    shot_range = row_data[1] if len(row_data) > 1 else ""
    body = row_data[2] if len(row_data) > 2 else ""
    folder_url = row_data[4] if len(row_data) > 4 else ""

    # Video globals (Video Prompts B1-B2: camera + audio/dialogue)
    vp = sh.worksheet("Video Prompts")
    vp_globals_block = vp.get("B1:B2", value_render_option="FORMATTED_VALUE")
    video_globals = "\n".join(r[0] for r in vp_globals_block if r and r[0])

    # Realism anchor — same line that's working on the character reference sheets.
    # Forces documentary editorial photography aesthetic so the model doesn't drift
    # into game-engine / movie-poster look (which gpt-image-2 + nano-banana-2 both
    # tend to default toward without this constraint).
    realism_anchor = (
        "Documentary editorial photography aesthetic, natural skin texture with visible "
        "pores and small natural imperfections, Kodak Portra 400 color science, "
        "no airbrushing, no beauty retouch, no game-engine rendering, no movie-poster polish. "
        "Subtle film grain. Muted, desaturated palette. Raw editorial honesty over glamour. "
        "Natural lighting only — practical sources, no theatrical fill."
    )

    full_prompt = video_globals + "\n" + realism_anchor + "\n\n" + body

    print(f"=== Set {set_num} — Shots {shot_range} ===")
    print(f"  Drive folder: {folder_url}")
    print(f"  Prompt length: {len(full_prompt)} chars")

    # === Auto-detect refs ===
    chars = sh.worksheet("CHARACTERS")
    char_rows = chars.get("A2:T20", value_render_option="FORMATTED_VALUE")
    char_refs = detect_characters(body, char_rows)

    locs = sh.worksheet("LOCATIONS")
    loc_rows = locs.get("A5:N30", value_render_option="FORMATTED_VALUE")
    loc_refs = detect_locations(body, loc_rows)

    all_refs = char_refs + loc_refs
    print(f"\n  Auto-detected refs ({len(all_refs)}):")
    for label, url in all_refs:
        print(f"    • {label}")
        print(f"      {url}")

    if not all_refs:
        print("  ! No refs detected — proceeding text-only")

    # === Generate one image ===
    def gen_one():
        if args.model == "openai-direct":
            # Direct OpenAI API path (when OPENAI_API_KEY is wired) — supports
            # native multi-ref via images.edit with up to 16 reference images.
            if not os.getenv("OPENAI_API_KEY"):
                raise SystemExit(
                    "OPENAI_API_KEY not set. Add to .env, then re-run with --model openai-direct."
                )
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            # OpenAI's images.edit accepts file-like image inputs; download refs first
            ref_files = []
            for label, url in all_refs:
                content = requests.get(url, timeout=120).content
                buf = io.BytesIO(content)
                buf.name = f"{re.sub(r'[^a-zA-Z0-9_]+', '_', label)}.png"
                ref_files.append(buf)
            edit_kwargs = {
                "model": "gpt-image-2",
                "prompt": full_prompt,
                "size": "1536x1024",
                "quality": "high",
            }
            if ref_files:
                edit_kwargs["image"] = ref_files
                resp = client.images.edit(**edit_kwargs)
            else:
                resp = client.images.generate(
                    model="gpt-image-2",
                    prompt=full_prompt,
                    size="1536x1024",
                    quality="high",
                )
            import base64 as _b64
            return _b64.b64decode(resp.data[0].b64_json)
        elif args.model == "gpt-image-2":
            # fal.ai gpt-image-2 (text-only — fal does not expose ref-image input
            # for this model as of writing; falls through to text-only path)
            model_id = "openai/gpt-image-2"
            api_args = {
                "prompt": full_prompt,
                "image_size": "landscape_16_9",
                "quality": "high",
                "num_images": 1,
                "output_format": "png",
            }
        else:  # nano-banana-2
            model_id = "fal-ai/nano-banana-2/edit"
            api_args = {
                "prompt": full_prompt,
                "image_urls": [u for _, u in all_refs] if all_refs else [],
                "num_images": 1,
                "output_format": "png",
            }
        result = fal_client.subscribe(model_id, arguments=api_args, with_logs=False)
        if not result.get("images"):
            raise RuntimeError(f"No images returned: {result}")
        img_url = result["images"][0]["url"]
        return requests.get(img_url, timeout=300).content

    # === Determine which iters to generate ===
    iters_to_run = [args.iter] if args.iter else [3, 4]
    iter_to_col = {3: "J", 4: "K"}
    iter_to_filename = {3: "iter-3.png", 4: "iter-4.png"}

    folder_id = folder_id_from_url(folder_url)
    if not folder_id:
        raise SystemExit(f"No Drive folder for set {set_num}: {folder_url}")

    print(f"\n  Generating iter(s): {iters_to_run} via {args.model}")

    for iter_num in iters_to_run:
        print(f"\n--- iter {iter_num} ---")
        t0 = time.time()
        img_data = gen_one()
        print(f"  done in {time.time() - t0:.1f}s · {len(img_data) // 1024}KB")

        fname = iter_to_filename[iter_num]
        # Trash existing same-name file
        res = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false and name='{fname}'",
            fields="files(id)", pageSize=10,
        ).execute()
        for f in res.get("files", []):
            drive.files().update(fileId=f["id"], body={"trashed": True}).execute()

        media = MediaIoBaseUpload(io.BytesIO(img_data), mimetype="image/png", resumable=False)
        uploaded = drive.files().create(
            body={"name": fname, "parents": [folder_id]},
            media_body=media,
            fields="id,webViewLink",
        ).execute()
        drive.permissions().create(
            fileId=uploaded["id"],
            body={"role": "reader", "type": "anyone"},
            fields="id",
        ).execute()
        print(f"  ✓ uploaded {fname} → {uploaded['webViewLink']}")

        # Write the URL to the matching iter column (J = iter 3, K = iter 4)
        col = iter_to_col[iter_num]
        sb.update(
            range_name=f"{col}{sheet_row}",
            values=[[uploaded["webViewLink"]]],
            value_input_option="USER_ENTERED",
        )
        print(f"  ✓ wrote URL to Storyboard Prompts!{col}{sheet_row}")


if __name__ == "__main__":
    main()

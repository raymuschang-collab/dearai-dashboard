#!/usr/bin/env python3
"""Fire 2 variants of set 1 in parallel — both with prestige-drama teal/orange
color grade prompted inline (NOT via Video Prompts globals — those are cleared).

Gen A: text-described chars + LOCATION asset ref only
Gen B: 100% text — chars AND location described, ZERO asset refs

Both: 480p · 15s · 9:16 · Seedance 2.0 Pro · same storyboard pencil ref.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone

import gspread
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]
SHEET_ID = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"

# Asset codes
CAFE_ASSET = "asset-20260514140552-f6q88"  # Tiong Bahru Café — image

# Storyboard pencil ref for set 1 (SP!G11 → lh3 URL)
STORYBOARD_REF_LH3 = "https://lh3.googleusercontent.com/d/1ajjyFE5IwQrdxJAIeXjqjC3PzeKrUqS7=w2048"

# Visual mode preamble (back in, as in-prompt text now)
VISUAL_MODE = (
    "PRESTIGE DRAMA COLOR GRADE — teal-and-orange cinematic register. "
    "Cool cyan-teal in the shadows, warm amber-orange in the highlights "
    "and skin tones. Complementary color push, high contrast. "
    "Fincher / Industry HBO / Mr Robot tonal register — cold-warm tension. "
    "Documentary editorial photography aesthetic preserved beneath the "
    "grade — real-camera lensing on Arri Alexa, real photo realism, NOT "
    "a game-engine render, NOT CGI."
)

# Text descriptions — derived from actual character video frames (ffmpeg + visual review)
GRACE_TEXT = (
    "GRACE — a Singaporean Chinese woman in her late 20s. Slim athletic "
    "build, fair lightly-tanned skin with natural texture. Oval face with "
    "defined cheekbones. Dark almond-shaped eyes, naturally arched "
    "eyebrows. Small distinguishing mole on the lower left cheek near the "
    "jawline. Shoulder-length wavy hair worn loose — brunette with subtle "
    "ash highlights, face-framing layers with body and movement. Soft "
    "natural makeup, rosy lip balm, a small silver stud earring. "
    "Wardrobe in this scene: an oversized dusty-blue chambray shirt "
    "jacket worn open and slouchy over a cream/oatmeal fitted cropped "
    "tank top. A worn brown leather messenger-bag strap across one "
    "shoulder. Warm, easy demeanor — looks tired but still gives a "
    "natural soft smile."
)

CARMEN_TEXT = (
    "CARMEN — a Singaporean Chinese woman in her early 30s. Slim "
    "feminine build, fair clear skin with a natural healthy glow. Oval "
    "face with high cheekbones. Monolid-leaning almond eyes, sharply "
    "defined dark eyebrows. Sharp jet-black blunt bob with a center part "
    "— hair cropped clean at the chin/jawline, no layers, sleek. Subtle "
    "natural makeup — a touch of contour, light warm-tan lip balm, "
    "minimal eye makeup. Wardrobe in this scene: a cream/off-white "
    "structured chore jacket (workwear cut, button-up front with chest "
    "pocket) worn over a fitted black scoop-neck top. Composed, "
    "intelligent demeanor — half smile, the look of someone who has "
    "been where you are and is paying attention."
)

CAFE_TEXT = (
    "LOCATION — Tiong Bahru Café in modern-day Singapore. Modern "
    "minimalist independent café on the ground floor of a preserved "
    "low-rise Tiong Bahru shophouse. Large window on the left side "
    "flooding the space with soft golden daylight. Brass pendant lights "
    "hanging over small wooden two-seater tables. A wooden bookshelf "
    "against the back wall filled with paperback novels and design "
    "books. Terrazzo floor in muted grey and cream aggregate. White "
    "ceramic flat-white cups and saucers. Espresso machine visible "
    "at the counter. Clean Scandinavian-meets-Singapore aesthetic. "
    "A waiter in soft-focus apron passes behind in the background. "
    "Documentary editorial photography aesthetic — real-camera lensing, "
    "real photo realism."
)


def load_body() -> str:
    """Pull Shotlist!Q for shots 1-5."""
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    shot_ws = sh.worksheet("Shotlist")
    q_vals = shot_ws.get("Q2:Q6", value_render_option="FORMATTED_VALUE")
    return "\n\n".join(r[0] for r in q_vals if r and r[0])


def build_prompt(variant: str, body: str) -> str:
    """variant = 'A' or 'B'."""
    parts = [
        "Shot with Arri Alexa, 35mm film, shallow depth of field.",
        VISUAL_MODE,
        "Follow the storyboard reference for composition, framing, and blocking on every shot.",
        "",
        "CHARACTERS (text descriptions only — no face refs attached, generate "
        "from prompt alone):",
        "",
        GRACE_TEXT,
        "",
        CARMEN_TEXT,
        "",
    ]
    if variant == "A":
        parts.extend([
            "LOCATION — see attached reference image (Tiong Bahru Café). "
            "Use that image as the background environment for all shots.",
            "",
        ])
    else:  # B
        parts.extend([
            CAFE_TEXT,
            "",
        ])
    parts.extend([
        "No music in this scene — only café ambient (cups on saucers, "
        "espresso machine hiss, low chatter, a waiter's footsteps passing).",
        "",
        "Dialogue: Singaporean English with light Singlish and "
        "Mandarin Chinese — voice both characters with Singaporean Mandarin "
        "accents (light Singlish lilt for Grace; sharper, more controlled "
        "delivery for Carmen).",
        "",
        "Documentary editorial photography aesthetic, natural skin texture, "
        "Kodak Portra 400 color science overlaid with the teal-and-orange "
        "grade, no airbrushing, no game-engine rendering. Subtle film "
        "grain. Natural lighting only (window light + practicals).",
        "",
        "VERTICAL 9:16 drama format. The video should follow these shots "
        "in sequence:",
        "",
        body,
    ])
    return "\n".join(parts)


def submit(prompt: str, variant: str) -> str:
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": STORYBOARD_REF_LH3},
         "role": "reference_image"},
    ]
    if variant == "A":
        content.append({
            "type": "image_url",
            "image_url": {"url": f"asset://{CAFE_ASSET}"},
            "role": "reference_image",
        })
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content,
        "ratio": "9:16",
        "duration": 15,
        "resolution": "480p",
        "watermark": False,
    }
    r = requests.post(
        f"{ARK_BASE}/contents/generations/tasks",
        headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"variant {variant} submit failed: {r.status_code} {r.text[:500]}")
    resp = r.json()
    return resp.get("id") or resp.get("task_id") or resp.get("data", {}).get("id")


def poll(task_id: str, variant: str, max_wait: int = 1800) -> dict:
    start = time.time()
    last = None
    while time.time() - start < max_wait:
        r = requests.get(
            f"{ARK_BASE}/contents/generations/tasks/{task_id}",
            headers={"Authorization": f"Bearer {ARK_KEY}"},
            timeout=30,
        )
        if r.status_code != 200:
            time.sleep(30); continue
        resp = r.json()
        status = resp.get("status")
        if status != last:
            print(f"  [{variant} {int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status in ("succeeded", "completed", "success"):
            return resp
        if status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"{variant} terminal failure: {json.dumps(resp)[:500]}")
        time.sleep(30)
    raise RuntimeError(f"{variant} 30-min cap exceeded")


def extract_video_url(resp: dict) -> str | None:
    content = resp.get("content", {})
    if isinstance(content, dict):
        v = content.get("video_url")
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("url")
    text = json.dumps(resp)
    m = re.search(r'https://[^\s"\']*\.mp4[^\s"\']*', text)
    return m.group(0) if m else None


def upload_and_save(variant: str, video_url: str) -> dict:
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    def get_or_create(parent, name):
        safe = name.replace("'", "\\'")
        q = f"'{parent}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='{safe}'"
        res = drive.files().list(q=q, fields="files(id)").execute()
        if res.get("files"):
            return res["files"][0]["id"]
        f = drive.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]},
            fields="id",
        ).execute()
        drive.permissions().create(
            fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id",
        ).execute()
        return f["id"]

    videos = get_or_create(SHOW_FOLDER, "videos")
    set_folder = get_or_create(videos, "set-01")

    r = requests.get(video_url, timeout=600)
    r.raise_for_status()
    data = r.content

    # Local save
    local_dir = Path("/Users/raymuschang/Desktop/Claude Ad — Why I Almost Quit Generated Videos")
    local_dir.mkdir(parents=True, exist_ok=True)
    local = local_dir / f"set-01-textchars-{variant}-480p-15s.mp4"
    local.write_bytes(data)

    fname = f"video-set-01-textchars-{variant}-480p-15s.mp4"
    # Trash existing same-name
    res = drive.files().list(
        q=f"'{set_folder}' in parents and trashed=false and name='{fname}'",
        fields="files(id)").execute()
    for f in res.get("files", []):
        drive.files().delete(fileId=f["id"]).execute()
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": fname, "parents": [set_folder]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(
        fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id",
    ).execute()
    return {"variant": variant, "drive_view": f["webViewLink"], "local": str(local)}


def fire_one(variant: str, body: str) -> dict:
    prompt = build_prompt(variant, body)
    print(f"\n=== Variant {variant} prompt ({len(prompt)} chars) ===")
    print(f"  First 300: {prompt[:300]}")
    print(f"  ... (truncated) ...")
    t0 = time.time()
    try:
        task_id = submit(prompt, variant)
        print(f"  ▶ {variant}: task_id={task_id}", flush=True)
        result = poll(task_id, variant)
        video_url = extract_video_url(result)
        print(f"  ✓ {variant}: gen done in {time.time()-t0:.1f}s", flush=True)
        up = upload_and_save(variant, video_url)
        print(f"  ✓ {variant}: uploaded → {up['drive_view']}", flush=True)
        return {"variant": variant, "task_id": task_id, **up, "elapsed": round(time.time()-t0, 1)}
    except Exception as e:
        print(f"  ✗ {variant}: {type(e).__name__}: {e}", flush=True)
        return {"variant": variant, "error": f"{type(e).__name__}: {e}"}


def main():
    body = load_body()
    print(f"Loaded Shotlist!Q body for shots 1-5 ({len(body)} chars)\n")
    print(f"=== Firing 2 variants of set 1 in parallel ===")

    results = {}
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(fire_one, v, body) for v in ("A", "B")]
        for fut in as_completed(futures):
            r = fut.result()
            results[r["variant"]] = r

    print(f"\n=== SUMMARY ===")
    for v in ("A", "B"):
        r = results.get(v, {})
        if r.get("error"):
            print(f"  ✗ {v}: {r['error']}")
        else:
            print(f"  ✓ {v}: {r.get('drive_view')}  ({r.get('elapsed', '—')}s)")
    Path("/tmp/set1_textchars_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""SODA brief remake V2 — fal gpt-image-2 (high quality).
Pipeline:
  1) Generate 3 prep refs in parallel via fal-ai/gpt-image-2 (text-to-image, high):
     - Asian Gen-Z GIRL skater portrait
     - Craft soda bottle product photo
     - 1:1 motion-graphic tile sample
  2) Feed all 4 refs (original brief + 3 prep refs) into fal-ai/gpt-image-2/edit
     at quality=high to regenerate the brief mockup with the refs slotted in.
"""
import os, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ[k.strip()] = v.strip()

FAL_KEY = os.environ["FAL_KEY"]
T2I = "https://fal.run/fal-ai/gpt-image-2"
EDIT = "https://fal.run/fal-ai/gpt-image-2/edit"

BRIEF_URL = "https://d2ol7oe51mr4n9.cloudfront.net/user_38fTUkZCEoy7snOZxzu2iK3h3h2/34281dcc-2cf5-4311-93c6-63483b31ecaa.png"

OUT_DIR = Path("/Users/raymuschang/Downloads/SODA Launch Spot")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# === Prep ref prompts (3 standalone gens) ===
PREP_GENS = [
    ("character", "square_hd",
     "Photographic portrait, square 1:1, of a 22-year-old Asian (East-Asian / Southeast-Asian) Gen-Z GIRL skater. Sun-kissed tan skin, light-hearted casual expression with a small confident smile, beanie or cap on her head, baggy graphic tee, daylight portrait on a rooftop background slightly out of focus. Documentary editorial photography aesthetic, natural skin texture with visible pores, Kodak Portra 400 color science, no airbrushing, no beauty retouch. Subtle film grain. Real photographic still, NOT illustration. NO text, NO captions."),

    ("bottle", "square_hd",
     "Product photography, square 1:1, of a single sleek modern craft-soda glass bottle on a clean white seamless background. Bright red and yellow label wraps the bottle, condensation droplets bead up on the glass, sun-glints highlight on the rim. Studio-lit with soft shadows. Slightly desaturated commercial product photography style — Kodak Portra 400 color science, no AI gloss. The bottle is mid-frame, centered, shown three-quarter angle. NO text on the label, just bright red and yellow color blocks. NO captions, NO watermarks."),

    ("mograph", "square_hd",
     "1:1 square motion-graphic tile preview, bold sans-serif white text on a deep navy background (#14143E), reading 'CRACKED OPEN. SUN OUT. SODA IN.' arranged in three stacked lines, each line a different brand-color underline accent (red, blue, yellow). Underneath in smaller white text: 'Eighteen flavours, zero compromise.' Tight clean modern type design, like a still frame from a brand commercial title card. Vector-clean look. NO photography, NO illustration of objects — pure type-and-color graphic."),
]


# === Edit-image prompt for the final brief regen ===
EDIT_PROMPT = """Remake this creative-brief mockup design (reference image #1) with the SAME dark navy background, SAME 3-column layout (left: visual references, middle: shot sequence, right: audio & on-screen text), SAME cyan + yellow + white typography, and SAME "The brief." title — but slot in the following changes using the additional reference images provided:

1) CHARACTER section (left column, middle): change the text to read "Asian Gen-Z GIRL skater, 22, sun-kissed, light-hearted". Place the headshot/profile thumbnail from REFERENCE IMAGE #2 (the female skater portrait) in the small character thumbnail slot. The character must be a GIRL — female, not male.

2) PRODUCT IMAGES section (left column, top): replace the 3 pink-silhouette bottle placeholders with thumbnails based on REFERENCE IMAGE #3 (the craft soda bottle product photo) — show 3 distinct angles of that exact bottle: front-facing, side profile, three-quarter angle. Real product-photography thumbnails, not placeholder icons.

3) GRAPHICS section (middle column, bottom): replace the empty motion-graphics-style text box with the actual square mograph tile from REFERENCE IMAGE #4 — show it as a small 1:1 thumbnail tile inside the GRAPHICS section.

4) Keep EVERY OTHER element identical to reference image #1: same SHOT 1-4 descriptions in the middle column, same "SODA — LAUNCH SPOT" project name, same "17 MAY 2026" date, same audio section, same "Cracked open. Sun out. SODA in. Eighteen flavours, zero compromise." voiceover, same TONE OF VOICE / MALE-FEMALE / WHEN DOES VOICEOVER START sections, same color palette swatches at the bottom-left (red, blue, white, yellow with hex codes), same FEMALE checkbox ticked.

The result must read like the same brief design — UI design style is identical, dark navy #14143E background, cyan accents, typography hierarchy — just with the placeholders replaced by real-photo thumbnails based on the additional reference images and the character text gendered FEMALE."""


def fire_t2i(label, image_size, prompt):
    """Fire one text-to-image gen via fal-ai/gpt-image-2. Returns the resulting image URL."""
    body = {"prompt": prompt, "image_size": image_size, "quality": "high", "num_images": 1}
    print(f"  ◦ T2I {label} ({image_size}) — submitting...", flush=True)
    t0 = time.time()
    r = requests.post(T2I, headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}, json=body, timeout=300)
    print(f"    [{label} {int(time.time()-t0)}s] HTTP {r.status_code}", flush=True)
    if r.status_code != 200:
        print(f"    ✗ {label}: {r.text[:300]}"); return None
    js = r.json()
    images = js.get("images") or []
    if not images:
        print(f"    ✗ {label}: no images in response: {json.dumps(js)[:300]}"); return None
    url = images[0]["url"]
    # Save locally for archive
    img_bytes = requests.get(url, timeout=120).content
    out_path = OUT_DIR / f"prep_{label}.png"
    out_path.write_bytes(img_bytes)
    print(f"    ✓ {label} → {out_path.name} ({out_path.stat().st_size/1024:.1f} KB)  ·  url={url[:80]}...", flush=True)
    return url


def fire_edit(brief_url, character_url, bottle_url, mograph_url):
    """Fire the final brief regen with all 4 refs."""
    body = {
        "prompt": EDIT_PROMPT,
        "image_urls": [brief_url, character_url, bottle_url, mograph_url],
        "image_size": "landscape_16_9",   # closest enum to brief's 3:2
        "quality": "high",
        "num_images": 1,
    }
    print(f"\n=== firing brief REGEN via fal-ai/gpt-image-2/edit (quality=high) ===")
    t0 = time.time()
    r = requests.post(EDIT, headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}, json=body, timeout=420)
    print(f"  [{int(time.time()-t0)}s] HTTP {r.status_code}", flush=True)
    if r.status_code != 200:
        print(f"  ✗ body: {r.text[:500]}"); return None
    js = r.json()
    images = js.get("images") or []
    if not images:
        print(f"  ✗ no images: {json.dumps(js)[:400]}"); return None
    img_bytes = requests.get(images[0]["url"], timeout=180).content
    out_path = OUT_DIR / "soda_brief_asian_GIRL_skater_gpt2_high_v2.png"
    out_path.write_bytes(img_bytes)
    print(f"  ✓ saved → {out_path.name} ({out_path.stat().st_size/1024:.1f} KB)")
    return out_path


def main():
    t0 = time.time()
    print("=== STEP 1: fire 3 prep refs in parallel via fal-ai/gpt-image-2 ===\n")
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {label: ex.submit(fire_t2i, label, size, prompt) for label, size, prompt in PREP_GENS}
        urls = {label: f.result() for label, f in futs.items()}

    missing = [k for k, v in urls.items() if not v]
    if missing:
        print(f"\n✗ prep failed for: {missing}; aborting")
        return

    print(f"\n=== STEP 2: fire brief regen with 4 refs ===")
    out = fire_edit(BRIEF_URL, urls["character"], urls["bottle"], urls["mograph"])
    if out:
        print(f"\n=== DONE · total wall: {time.time()-t0:.1f}s ===\nFinal: {out}")


if __name__ == "__main__":
    main()

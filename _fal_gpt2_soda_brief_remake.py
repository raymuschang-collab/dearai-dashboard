#!/usr/bin/env python3
"""Remake the SODA Launch Spot brief mockup via fal gpt-image-1/edit-image.
Reference: the original brief JPEG (hosted at Higgsfield CDN).
Changes: Asian skater character + Asian profile photo + real soda bottle thumbnails + 1:1 mograph tile."""
import os, json, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

FAL_KEY = os.environ["FAL_KEY"]
ENDPOINT = "https://fal.run/fal-ai/gpt-image-1/edit-image"

BRIEF_URL = "https://d2ol7oe51mr4n9.cloudfront.net/user_38fTUkZCEoy7snOZxzu2iK3h3h2/34281dcc-2cf5-4311-93c6-63483b31ecaa.png"

OUT_DIR = Path("/Users/raymuschang/Downloads/SODA Launch Spot")
OUT_DIR.mkdir(parents=True, exist_ok=True)


PROMPT = """Remake this exact creative-brief mockup design with the SAME dark navy background, SAME 3-column layout (left: visual references, middle: shot sequence, right: audio & on-screen text), SAME cyan + yellow + white typography, and SAME "The brief." title — but with these specific content changes:

1) PRODUCT IMAGES section (left column, top): replace the 3 pink-silhouette bottle placeholders with 3 REAL photographic thumbnails of an actual craft-soda glass bottle product, shot from 3 different angles — front-facing on white, side profile, and three-quarter angle. The bottle should be a sleek modern craft-soda glass bottle with a bright red and yellow label, condensation droplets, real product photography. NOT placeholder icons — these must look like actual product photos.

2) CHARACTER section (left column, middle): change the text to read "Asian Gen-Z skater, 22, sun-kissed, light-hearted". ADD a small square photographic headshot/profile thumbnail next to or above the text — an actual photo of a 22-year-old East-Asian or Southeast-Asian young man, sun-kissed tan skin, light-hearted casual expression, slight smile, beanie or cap, streetwear vibe, daylight portrait. Documentary photo style, not illustration.

3) GRAPHICS section (middle column, bottom): replace the empty motion-graphics-style text-only box with an ACTUAL 1:1 SQUARE THUMBNAIL TILE of the motion graphic sample — bold sans-serif white text on a deep navy background reading "CRACKED OPEN. SUN OUT. SODA IN." with brand-color accent rectangles (red, blue, yellow) bordering the text. Square aspect ratio, like a still frame from the actual motion graphic.

4) Keep EVERY OTHER element identical: same SHOT 1-4 descriptions in the middle column, same "SODA — LAUNCH SPOT" project name, same "17 MAY 2026" date, same audio section, same "Cracked open. Sun out. SODA in. Eighteen flavours, zero compromise." voiceover, same TONE OF VOICE / MALE-FEMALE / WHEN DOES VOICEOVER START sections, same color palette swatches at the bottom-left (red, blue, white, yellow with hex codes).

The result should look like the same brief design, just with the placeholders replaced by real-photo thumbnails and the character switched to Asian. UI design style is identical. Same dark navy #14143E background. Same cyan accents. Same typography hierarchy. Documentary editorial photography for any real photos shown (Kodak Portra 400 look, natural skin texture, no airbrushing)."""


def main():
    body = {
        "prompt": PROMPT,
        "image_urls": [BRIEF_URL],
        "image_size": "1536x1024",
        "quality": "high",
        "num_images": 1,
        "output_format": "png",
    }
    print("◦ submitting fal gpt-image-1/edit-image (5-min cap)...", flush=True)
    t0 = time.time()
    r = requests.post(ENDPOINT,
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
        json=body, timeout=420)
    print(f"  [{int(time.time()-t0)}s] HTTP {r.status_code}", flush=True)
    if r.status_code != 200:
        print(f"  ✗ body: {r.text[:500]}"); return
    data = r.json()
    images = data.get("images") or []
    if not images:
        print(f"  ✗ no images: {json.dumps(data)[:400]}"); return
    img_bytes = requests.get(images[0]["url"], timeout=120).content
    out_path = OUT_DIR / "soda_brief_asian_skater_v1.png"
    out_path.write_bytes(img_bytes)
    print(f"  ✓ saved → {out_path.name} ({out_path.stat().st_size/1024:.1f} KB)")
    print(f"  path: {out_path}")


if __name__ == "__main__":
    main()

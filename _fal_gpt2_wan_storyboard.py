#!/usr/bin/env python3
"""fal.ai gpt-image-2 /edit-image — Wan Test 7-panel storyboard page (16:9).
Uses Image1 (man) + Image2 (woman) as multi-reference inputs.
2 iterations, sequential."""
import os, json, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

FAL_KEY = os.environ["FAL_KEY"]
# Use OpenAI's gpt-image-1 (the actual underlying "chatgpt2" image-gen model on fal).
# The "/edit-image" sync endpoint accepts multi-image refs.
ENDPOINT_SYNC = "https://fal.run/fal-ai/gpt-image-1/edit-image"

# Public CDN URLs of the face refs (uploaded earlier in session to Higgsfield's CDN)
IMG1_URL = "https://d2ol7oe51mr4n9.cloudfront.net/user_38fTUkZCEoy7snOZxzu2iK3h3h2/74c45acb-5ce0-462e-a1f9-d113e950caf0.png"  # Image1: man
IMG2_URL = "https://d2ol7oe51mr4n9.cloudfront.net/user_38fTUkZCEoy7snOZxzu2iK3h3h2/e160b80c-0161-4096-9dd6-19b9f86fe5aa.png"  # Image2: woman

OUT_DIR = Path("/Users/raymuschang/Downloads/Wan Test/chatgpt_outputs")
OUT_DIR.mkdir(exist_ok=True)

PROMPT = """A 16:9 photographic STORYBOARD PAGE — 7 panels arranged in a clean 4-column-by-2-row grid on dark gunmetal-gray background, thin white borders separating each panel, small "01"-"07" panel number badges in the top-left of each panel. The 8th cell (bottom-right) contains a white-text title block reading "WAN TEST · 7-SHOT PARK SEQUENCE".

Panel 01 (WIDE SHOT): The man from the first reference image (beard, dark hair, cream mandarin-collar shirt) stands facing the woman from the second reference image (bob haircut, cream blazer-shirt over black top), mid-conversation, both full-body in frame, under the sprawling shade of a massive raintree (Samanea saman). Harsh dappled tropical sunlight breaks through the canopy.

Panel 02 (WIDE SHOT slightly tighter): same two characters, camera has pushed in slightly, conversation continues.

Panel 03 (CLOSE-UP, OTS): tight on the face of the man from the first reference image; back of the woman's bob hair softly out of focus in the foreground.

Panel 04 (MID-SHOT, OTS): the face of the woman from the second reference image in sharp focus; back of the man's head and shoulder softly out of focus in the foreground.

Panel 05 (CLOSE-UP, LOW ANGLE): tight on the face of the woman from the second reference image, camera positioned low looking up, raintree branches sprawling overhead with sun streaming through; her expression sullen.

Panel 06 (WIDE SHOT, surveillance POV through foliage): an Asian man wearing a bright yellow knit beanie and a black jacket holds black binoculars to his eyes in the foreground right of the panel, watching the distant man and woman who are visible small in frame under the raintree.

Panel 07 (CLOSE-UP): the same Asian man in yellow beanie holds binoculars up to his eyes pointed at the camera, beanie filling the top of the panel.

Style: every panel is photoreal documentary editorial photography, Kodak Portra 400 color science, natural skin texture with visible pores, no illustration. The man's face throughout must match the first reference image. The woman's face throughout must match the second reference image. The yellow-beanie man is a NEW character introduced only in panels 06 and 07."""


def fire(iter_num: int):
    out_path = OUT_DIR / f"wan_storyboard_page_v{iter_num}_chatgpt2_16x9.png"
    if out_path.exists() and out_path.stat().st_size > 100_000:
        print(f"  • v{iter_num} exists, skipping"); return out_path

    body = {
        "prompt": PROMPT,
        "image_urls": [IMG1_URL, IMG2_URL],
        "image_size": "1536x1024",   # 16:9 horizontal (fal gpt-image-1 only accepts auto/1024x1024/1536x1024/1024x1536)
        "quality": "high",
        "num_images": 1,
        "output_format": "png",
    }
    print(f"  ◦ v{iter_num} — submitting sync (5-min cap)...", flush=True)
    t0 = time.time()
    r = requests.post(ENDPOINT_SYNC,
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
        json=body, timeout=420)
    print(f"    [v{iter_num} {int(time.time()-t0)}s] HTTP {r.status_code}", flush=True)
    if r.status_code != 200:
        print(f"  ✗ v{iter_num} body: {r.text[:400]}"); return None
    data = r.json()
    images = data.get("images") or []
    if not images:
        print(f"  ✗ v{iter_num} no images in response: {json.dumps(data)[:400]}"); return None
    img_url = images[0].get("url")
    img_bytes = requests.get(img_url, timeout=120).content
    out_path.write_bytes(img_bytes)
    print(f"  ✓ v{iter_num} → {out_path.name} ({out_path.stat().st_size/1024:.1f} KB)", flush=True)
    return out_path


def main():
    t0 = time.time()
    for i in (1, 2):
        fire(i)
        time.sleep(3)
    print(f"\nwall: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Re-fire the WAN 7-panel 16:9 storyboard page on BOTH:
  - Reve remix (using <img>0</img> + <img>1</img> tokens)
  - fal.ai gpt-image-1/edit-image (natural-language ref descriptions)
With a hard Portra-400 / documentary-editorial / natural-skin-and-hair anchor.
One iteration each."""
import os, json, base64, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

REVE_KEY = os.environ["REVE_API_KEY"]
FAL_KEY  = os.environ["FAL_KEY"]
REVE_URL = "https://api.reve.com/v1/image/remix"
FAL_URL  = "https://fal.run/fal-ai/gpt-image-1/edit-image"

IMG1_PATH = Path("/tmp/wan_refs/Image1_man.jpeg")
IMG2_PATH = Path("/tmp/wan_refs/Image2_woman.jpeg")
IMG1_URL  = "https://d2ol7oe51mr4n9.cloudfront.net/user_38fTUkZCEoy7snOZxzu2iK3h3h2/74c45acb-5ce0-462e-a1f9-d113e950caf0.png"
IMG2_URL  = "https://d2ol7oe51mr4n9.cloudfront.net/user_38fTUkZCEoy7snOZxzu2iK3h3h2/e160b80c-0161-4096-9dd6-19b9f86fe5aa.png"

REVE_OUT = Path("/Users/raymuschang/Downloads/Wan Test/reve_outputs/wan_storyboard_portra_16x9.png")
FAL_OUT  = Path("/Users/raymuschang/Downloads/Wan Test/chatgpt_outputs/wan_storyboard_portra_16x9.png")
REVE_OUT.parent.mkdir(exist_ok=True)
FAL_OUT.parent.mkdir(exist_ok=True)


# === REVE PROMPT (with <img>X</img> tokens, kept tight to dodge the prompt-length limit) ===
REVE_PROMPT = """A 16:9 STORYBOARD PAGE — 7 photographic panels in a 4-col by 2-row grid on dark gunmetal background, thin white borders, "01"-"07" numbered badges top-left of each panel. 8th cell: title block "WAN TEST · 7-SHOT PARK SEQUENCE".

LOOK (every panel): shot on Kodak Portra 400 35mm film. Visible film grain, warm midtones, slightly desaturated greens, lifted shadows. Documentary editorial style (Wim Wenders / Alec Soth) — NOT advertising, NOT AI-glossy. Natural skin texture with visible pores and slight oil sheen from tropical heat. Natural hair with flyaway strands, NOT perfectly styled. Practical sunlight only — NO theatrical fill, NO ring-light. Subtle vignetting. Real-camera depth of field. NO airbrushing. NO beauty retouch.

Panel 01 (WIDE): man from <img>0</img> facing woman from <img>1</img>, mid-conversation under a massive raintree, harsh dappled tropical sunlight, both full body, slight sweat sheen on foreheads.
Panel 02 (WIDE tighter): same scene, camera pushed in, hair moving in breeze.
Panel 03 (CU, OTS): tight on face of <img>0</img>, pore-level skin detail visible, back of <img>1</img>'s bob softly blurred in foreground.
Panel 04 (MS, OTS): face of <img>1</img> sharp, flyaway hair visible at her temple, back of <img>0</img>'s head blurred in foreground.
Panel 05 (CU low angle): tight on face of <img>1</img>, raintree branches above, sun through leaves, sullen expression, visible skin pores and faint shadow under eye.
Panel 06 (WIDE surveillance POV through foliage): Asian man in yellow knit beanie + black jacket holds binoculars in foreground right; <img>0</img> + <img>1</img> small in the distant background under raintree.
Panel 07 (CU): same yellow-beanie man holds binoculars to eyes pointed at camera, visible knit texture of the beanie.

Man's face matches <img>0</img>. Woman's face matches <img>1</img>. Yellow-beanie man is a new character (panels 06-07 only). Every panel is a real photographic still — NO illustration."""


# === FAL gpt-image-1 PROMPT (natural language, no <img> tokens) ===
FAL_PROMPT = """A 16:9 photographic storyboard page — 7 panels in a 4-column by 2-row grid on a dark gunmetal-gray background, thin white borders separating each panel, small "01"-"07" panel-number badges in the top-left corner of each panel. The 8th cell (bottom-right) is a title block reading "WAN TEST · 7-SHOT PARK SEQUENCE".

EVERY panel must obey this look: shot on actual 35mm Kodak Portra 400 film. Visible film grain throughout. Warm midtones, slightly desaturated greens, lifted shadows, characteristic Portra skin tones (peachy, never plastic). Documentary editorial photography style — think Wim Wenders, Alec Soth, Sally Mann — NOT advertising, NOT fashion, NOT AI-glossy. Natural skin texture with visible pores, faint micro-wrinkles around the eyes, slight oil and sweat sheen from tropical heat, occasional blemish — NO airbrushing, NO beauty retouch. Natural hair with flyaway strands, slight humidity frizz, NOT perfectly styled, NOT glossy AI hair. Practical natural sunlight only — NO theatrical fill, NO ring-light, NO AI rim-light. Subtle vignetting. Real-camera depth of field with imperfect bokeh.

Panel 01 (WIDE SHOT): the man from the first reference image (beard, dark hair, cream mandarin-collar shirt) stands facing the woman from the second reference image (bob haircut, cream blazer-shirt over black top), mid-conversation, both full body, under the sprawling shade of a massive raintree. Harsh dappled tropical sunlight breaks through the canopy. Slight sweat sheen on their foreheads from the heat.

Panel 02 (WIDE SHOT slightly tighter): same two characters in the same setting, camera has nudged closer, hair moving slightly in a humid breeze, conversation continues.

Panel 03 (CLOSE-UP, OTS into the man): tight on the face of the man from the first reference image with pore-level skin detail visible; the back of the woman's bob hair from the second reference image is softly out of focus in the foreground.

Panel 04 (MID-SHOT, OTS into the woman): the woman from the second reference image in sharp focus, flyaway hair visible at her temple; the back of the man's head and shoulder softly out of focus in the foreground.

Panel 05 (CLOSE-UP, LOW ANGLE): tight on the face of the woman from the second reference image, camera positioned low looking up, raintree branches sprawling overhead with sun streaming through leaves, sullen expression, visible skin pores and a faint shadow under her eye.

Panel 06 (WIDE SHOT, surveillance POV through dense foliage): an Asian man wearing a bright yellow knit beanie and a black jacket holds black binoculars to his eyes in the foreground right of the panel, watching the distant man and woman who appear small in the background under the raintree.

Panel 07 (CLOSE-UP): the same Asian man in yellow beanie holds binoculars up to his eyes pointed at the camera, beanie filling the top of the panel, visible knit texture of the beanie.

The man's face throughout must match the first reference image. The woman's face throughout must match the second reference image. The yellow-beanie man is a new character introduced only in panels 06 and 07. Every panel is a real photographic still — NO illustration, NO digital painting, NO 3D render."""


def fire_reve():
    img1_b64 = base64.b64encode(IMG1_PATH.read_bytes()).decode()
    img2_b64 = base64.b64encode(IMG2_PATH.read_bytes()).decode()
    body = {"prompt": REVE_PROMPT, "reference_images": [img1_b64, img2_b64], "aspect_ratio": "16:9", "version": "latest"}
    for attempt in range(5):
        print(f"  ◦ reve — attempt {attempt+1}", flush=True)
        r = requests.post(REVE_URL,
            headers={"Authorization": f"Bearer {REVE_KEY}", "Accept": "application/json", "Content-Type": "application/json"},
            json=body, timeout=300)
        if r.status_code == 200:
            data = r.json()
            if "image" in data:
                REVE_OUT.write_bytes(base64.b64decode(data["image"]))
                print(f"  ✓ reve → {REVE_OUT.name} ({REVE_OUT.stat().st_size/1024:.1f} KB)", flush=True)
                return REVE_OUT
            print(f"  ✗ reve missing image: {json.dumps(data)[:200]}"); return None
        if r.status_code == 429:
            wait = 10 + attempt * 5
            print(f"    429, sleeping {wait}s...", flush=True); time.sleep(wait); continue
        print(f"  ✗ reve HTTP {r.status_code}: {r.text[:300]}"); return None


def fire_fal():
    body = {
        "prompt": FAL_PROMPT,
        "image_urls": [IMG1_URL, IMG2_URL],
        "image_size": "1536x1024",
        "quality": "high",
        "num_images": 1,
        "output_format": "png",
    }
    print(f"  ◦ fal gpt-image-1 — submitting sync (5-min cap)...", flush=True)
    t0 = time.time()
    r = requests.post(FAL_URL,
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
        json=body, timeout=420)
    print(f"    [fal {int(time.time()-t0)}s] HTTP {r.status_code}", flush=True)
    if r.status_code != 200:
        print(f"  ✗ fal body: {r.text[:400]}"); return None
    data = r.json()
    images = data.get("images") or []
    if not images:
        print(f"  ✗ fal no images: {json.dumps(data)[:400]}"); return None
    img_bytes = requests.get(images[0]["url"], timeout=120).content
    FAL_OUT.write_bytes(img_bytes)
    print(f"  ✓ fal → {FAL_OUT.name} ({FAL_OUT.stat().st_size/1024:.1f} KB)", flush=True)
    return FAL_OUT


def main():
    t0 = time.time()
    print("\n=== firing REVE remix + fal gpt-image-1 in parallel ===\n")
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(fire_reve)
        f2 = ex.submit(fire_fal)
        f1.result(); f2.result()
    print(f"\nwall: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()

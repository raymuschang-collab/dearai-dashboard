#!/usr/bin/env python3
"""Reve — Wan Test shots 4, 5, 6, 7 × 2 iterations each (8 gens total).
Sequential with pacing to avoid the 429 rate limit.

Shots 4-6 use /v1/image/remix with Image1+Image2 face refs.
Shot 7 uses /v1/image/create (text-only) — surveillance man is a new character.
"""
import os, json, base64, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

REVE_KEY = os.environ["REVE_API_KEY"]
REMIX_URL  = "https://api.reve.com/v1/image/remix"
CREATE_URL = "https://api.reve.com/v1/image/create"

IMG1 = Path("/tmp/wan_refs/Image1_man.jpeg")
IMG2 = Path("/tmp/wan_refs/Image2_woman.jpeg")
OUT_DIR = Path("/Users/raymuschang/Downloads/Wan Test/reve_outputs")
OUT_DIR.mkdir(exist_ok=True)

PACE_SECONDS = 5  # pause between API calls to dodge 429

# Each entry: (label, endpoint, body)
img1_b64 = base64.b64encode(IMG1.read_bytes()).decode()
img2_b64 = base64.b64encode(IMG2.read_bytes()).decode()

SHOTS = [
    ("shot4_MS_OTS_him", "remix",
     "Mid-shot OTS photograph, 9:16 vertical. Over the shoulder of the woman from <img>1</img> — her back-of-head and right shoulder soft-focus in the right foreground. Beyond her, in sharp focus, the man from <img>0</img> stands mid-conversation. He gestures with one hand, brow slightly furrowed, mouth speaking mid-word. Same setting as the establishing wide: under the dense shade of a massive raintree (Samanea saman) with sprawling lateral branches overhead, harsh tropical midday sunlight breaking through the canopy in dappled patches — HIGH CONTRAST, deep shadow, blown-out highlights on the foliage behind him. Documentary editorial photography aesthetic, natural skin texture with visible pores, Kodak Portra 400 color science, no airbrushing. The man's face must match <img>0</img> exactly (beard, dark hair, cream mandarin-collar shirt). The woman's hair and shoulder match <img>1</img>."),

    ("shot5_low_angle_sullen", "remix",
     "Mid-shot from low angle, 9:16 vertical. The woman from <img>1</img> stands looking off-frame, her expression sullen — jaw set, eyes downcast, mouth pressed into a thin line. Camera positioned low looking up at her; the raintree (Samanea saman) canopy fills the upper half of frame with branches sprawling overhead. Harsh tropical midday sunlight backlights her face, creating high contrast — face partially in shadow, halo of bright leaves behind her. Same setting and lighting as preceding shots. Documentary editorial photography aesthetic, natural skin texture with visible pores, Kodak Portra 400 color science, no airbrushing. The woman's face must match <img>1</img> exactly (bob haircut, cream blazer-shirt over black top). No other characters in frame."),

    ("shot6_surveillance_OTS_far", "remix",
     "Wide shot photograph, 9:16 vertical. Photograph from inside dense tropical foliage — leaves and branches in the foreground partially obscuring the lens, creating a 'shooting through the bushes' framing. In the right foreground, much closer to camera, an Asian man wearing a bright yellow knit beanie and a black jacket holds a pair of black binoculars up to his eyes, his back partly turned to camera, watching something across the park. In the far background, distant under a massive raintree (Samanea saman), the man from <img>0</img> (cream mandarin-collar shirt) and the woman from <img>1</img> (cream blazer over black top) stand talking, small in frame, unaware they are being watched. Harsh tropical midday sunlight filters through the foliage — deep contrast, dappled patches of light. Documentary editorial photography aesthetic, Kodak Portra 400 color science. The two distant figures should be RECOGNIZABLE as the people in <img>0</img> and <img>1</img> but they are SMALL in frame, photographed from far away."),

    ("shot7_surveillance_CU_binoculars", "create",
     "Close-up photograph, 9:16 vertical. Asian man wearing a bright yellow knit beanie and a black jacket holds a pair of black binoculars up to his eyes, looking straight at the camera through them. The binoculars dominate the center of the frame, covering most of his face except the lower jaw and the beanie. Behind him: dense tropical raintree foliage, dappled harsh sunlight, slightly out of focus. He is mid-30s, short dark hair visible at the sides of the beanie, clean-shaven or with light stubble. Tense, watchful expression visible in the set of his jaw. Documentary editorial photography aesthetic, natural skin texture, Kodak Portra 400 color science, no airbrushing. Tight CU framing, the man and binoculars filling the frame."),
]


def fire_one(label: str, endpoint: str, prompt: str, iter_num: int):
    out_path = OUT_DIR / f"{label}_v{iter_num}.png"
    if out_path.exists() and out_path.stat().st_size > 100_000:
        print(f"  • {label} v{iter_num} already on disk, skipping")
        return out_path

    if endpoint == "remix":
        url = REMIX_URL
        body = {"prompt": prompt, "reference_images": [img1_b64, img2_b64], "aspect_ratio": "9:16", "version": "latest"}
    else:
        url = CREATE_URL
        body = {"prompt": prompt, "aspect_ratio": "9:16"}

    for attempt in range(5):
        print(f"  ◦ {label} v{iter_num} ({endpoint}) — attempt {attempt+1}", flush=True)
        r = requests.post(url,
            headers={"Authorization": f"Bearer {REVE_KEY}", "Accept": "application/json", "Content-Type": "application/json"},
            json=body, timeout=300)
        if r.status_code == 200:
            data = r.json()
            if "image" in data:
                out_path.write_bytes(base64.b64decode(data["image"]))
                print(f"  ✓ {label} v{iter_num} → {out_path.name} ({out_path.stat().st_size/1024:.1f} KB)", flush=True)
                return out_path
            print(f"  ✗ {label} v{iter_num}: missing 'image' field — {json.dumps(data)[:200]}")
            return None
        if r.status_code == 429:
            wait = 10 + attempt * 5
            print(f"    429 rate limited, sleeping {wait}s...", flush=True)
            time.sleep(wait); continue
        print(f"  ✗ {label} v{iter_num}: HTTP {r.status_code} — {r.text[:300]}")
        return None
    return None


def main():
    t0 = time.time()
    print(f"firing {len(SHOTS)*2} gens sequentially (pacing={PACE_SECONDS}s)...\n")

    landed = []
    for label, endpoint, prompt in SHOTS:
        for iter_num in (1, 2):
            p = fire_one(label, endpoint, prompt, iter_num)
            if p: landed.append(p)
            time.sleep(PACE_SECONDS)

    print(f"\n=== DONE · {len(landed)}/{len(SHOTS)*2} landed · wall: {time.time()-t0:.1f}s ===")
    for p in landed:
        print(f"  {p}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reve remix — Wan Test 7-shot storyboard PAGE.
Single 16:9 image, 7 panels in a 4-col × 2-row grid (8th cell = title),
using Image1 (man) + Image2 (woman) as multi-reference inputs.
2 iterations · sequential with pacing."""
import os, json, base64, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

REVE_KEY = os.environ["REVE_API_KEY"]
REMIX_URL = "https://api.reve.com/v1/image/remix"

IMG1 = Path("/tmp/wan_refs/Image1_man.jpeg")
IMG2 = Path("/tmp/wan_refs/Image2_woman.jpeg")
OUT_DIR = Path("/Users/raymuschang/Downloads/Wan Test/reve_outputs")
OUT_DIR.mkdir(exist_ok=True)

PROMPT = """A 16:9 STORYBOARD PAGE — 7 photographic panels in a 4-column-by-2-row grid on dark gunmetal background, thin white borders, small "01"-"07" numbered badges in each panel's top-left corner. 8th cell contains a title block "WAN TEST · 7-SHOT PARK SEQUENCE".

Panel 01 (WIDE SHOT): man from <img>0</img> facing woman from <img>1</img> mid-conversation under a massive raintree, harsh dappled tropical sunlight, both full body in frame.
Panel 02 (WIDE SHOT slightly tighter): same scene, same two characters, conversation continues.
Panel 03 (CU, OTS): tight on face of <img>0</img>, back of <img>1</img>'s bob hair softly blurred in foreground.
Panel 04 (MS, OTS): face of <img>1</img> in sharp focus, back of <img>0</img>'s head and shoulder blurred in foreground.
Panel 05 (CU, LOW ANGLE): tight on face of <img>1</img>, raintree branches sprawling above, sun streaming through, her expression sullen.
Panel 06 (WIDE SHOT, surveillance POV through foliage): Asian man in yellow knit beanie + black jacket holds binoculars in the foreground right, watching the distant <img>0</img> + <img>1</img> who are small in frame under the raintree.
Panel 07 (CU): the same Asian man in yellow beanie holds binoculars up to his eyes, pointed at camera, beanie filling the top of frame.

Style: every panel is a photoreal documentary still, Kodak Portra 400 color science, natural skin texture, no illustration. Man's face matches <img>0</img>. Woman's face matches <img>1</img>. The yellow-beanie man is a new character (only in panels 06 and 07)."""


def fire(iter_num: int):
    out_path = OUT_DIR / f"wan_storyboard_page_v{iter_num}_16x9.png"
    if out_path.exists() and out_path.stat().st_size > 100_000:
        print(f"• v{iter_num} exists, skipping"); return out_path
    img1_b64 = base64.b64encode(IMG1.read_bytes()).decode()
    img2_b64 = base64.b64encode(IMG2.read_bytes()).decode()
    body = {"prompt": PROMPT, "reference_images": [img1_b64, img2_b64], "aspect_ratio": "16:9", "version": "latest"}
    for attempt in range(5):
        print(f"  ◦ v{iter_num} — attempt {attempt+1}", flush=True)
        r = requests.post(REMIX_URL,
            headers={"Authorization": f"Bearer {REVE_KEY}", "Accept": "application/json", "Content-Type": "application/json"},
            json=body, timeout=300)
        if r.status_code == 200:
            data = r.json()
            if "image" in data:
                out_path.write_bytes(base64.b64decode(data["image"]))
                print(f"  ✓ v{iter_num} → {out_path.name} ({out_path.stat().st_size/1024:.1f} KB)", flush=True)
                return out_path
            print(f"  ✗ v{iter_num}: missing 'image' — {json.dumps(data)[:200]}"); return None
        if r.status_code == 429:
            wait = 10 + attempt * 5
            print(f"    429, sleeping {wait}s...", flush=True)
            time.sleep(wait); continue
        print(f"  ✗ v{iter_num}: HTTP {r.status_code} — {r.text[:200]}"); return None
    return None


def main():
    t0 = time.time()
    for i in (1, 2):
        fire(i)
        time.sleep(6)
    print(f"\nwall: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()

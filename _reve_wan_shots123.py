#!/usr/bin/env python3
"""Reve remix — Wan Test shots 1, 2, 3. 6 gens total (3 shots × 2 iterations).
Uses Image1 (man, mandarin-collar shirt, beard) + Image2 (woman, bob, cream blazer)
as multi-reference inputs via Reve's /v1/image/remix endpoint with <img>0</img>
+ <img>1</img> token-style prompt references."""
import os, sys, json, base64, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests

HERE = Path(__file__).parent
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

REVE_KEY = os.environ["REVE_API_KEY"]
REVE_URL = "https://api.reve.com/v1/image/remix"

IMG1 = Path("/tmp/wan_refs/Image1_man.jpeg")
IMG2 = Path("/tmp/wan_refs/Image2_woman.jpeg")
OUT_DIR = Path("/Users/raymuschang/Downloads/Wan Test/reve_outputs")
OUT_DIR.mkdir(exist_ok=True)

SHOTS = [
    ("shot1_WS", "Wide shot photograph, 9:16 vertical. The man in <img>0</img> stands facing the woman in <img>1</img>, mid-conversation, full body in frame. They are under the dense shade of a massive raintree (Samanea saman) with sprawling lateral branches overhead. Harsh tropical midday sunlight breaks through the canopy in dappled patches — HIGH CONTRAST, deep shadow on their bodies, blown-out highlights on the foliage and ground behind them. Documentary editorial photography aesthetic, natural skin texture with visible pores, Kodak Portra 400 color science, no airbrushing, no game-engine rendering. The man's face must match <img>0</img> exactly (beard, dark hair, cream mandarin-collar shirt). The woman's face must match <img>1</img> exactly (bob haircut, cream blazer-shirt over black top). No text, no captions."),
    ("shot2_MS_OTS_listening", "Mid-shot OTS photograph, 9:16 vertical. Over the shoulder of the man from <img>0</img> — his back-of-head and right shoulder soft-focus in the left foreground. Beyond him, in sharp focus, the woman from <img>1</img> stands listening attentively. Gaze direct on his face, mouth closed, focused expression. Background: shaded raintree canopy with dappled light filtering through. Same harsh-light high-contrast lighting as the establishing wide. Documentary editorial photography aesthetic, natural skin texture, Kodak Portra 400 color science. The woman's face must match <img>1</img> exactly. The man's hair and shoulder match <img>0</img>."),
    ("shot3_CU_OTS_listening", "Close-up OTS photograph, 9:16 vertical. The back of the man's head and right shoulder from <img>0</img> is heavily blurred in the foreground, occupying the right third of the frame. The woman from <img>1</img> fills the rest of the frame in tight close-up. She listens intently — mouth closed, eyes focused on his face just off-frame, micro-expression of concentration. Soft dappled raintree light from above; shallow depth of field. Documentary editorial photography aesthetic, natural skin texture with visible pores, Kodak Portra 400 color science. The woman's face must match <img>1</img> exactly."),
]


def fire_one(label: str, prompt: str, iter_num: int, img1_b64: str, img2_b64: str):
    body = {
        "prompt": prompt,
        "reference_images": [img1_b64, img2_b64],
        "aspect_ratio": "9:16",
        "version": "latest",
    }
    print(f"  ◦ firing {label} iter {iter_num}...", flush=True)
    r = requests.post(
        REVE_URL,
        headers={
            "Authorization": f"Bearer {REVE_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=300,
    )
    if r.status_code != 200:
        print(f"  ✗ {label} iter {iter_num}: HTTP {r.status_code} — {r.text[:300]}")
        return None
    data = r.json()
    if "image" not in data:
        print(f"  ✗ {label} iter {iter_num}: response missing 'image' — {json.dumps(data)[:300]}")
        return None
    img_bytes = base64.b64decode(data["image"])
    out_path = OUT_DIR / f"{label}_v{iter_num}.png"
    out_path.write_bytes(img_bytes)
    print(f"  ✓ {label} iter {iter_num} → {out_path.name} ({len(img_bytes)/1024:.1f} KB)", flush=True)
    return out_path


def main():
    t0 = time.time()
    img1_b64 = base64.b64encode(IMG1.read_bytes()).decode()
    img2_b64 = base64.b64encode(IMG2.read_bytes()).decode()
    print(f"refs loaded · Image1={len(img1_b64)/1024:.0f}KB b64 · Image2={len(img2_b64)/1024:.0f}KB b64\n")

    jobs = []
    for label, prompt in SHOTS:
        for iter_num in (1, 2):
            jobs.append((label, prompt, iter_num))

    print(f"firing {len(jobs)} gens in parallel...\n")
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(fire_one, label, prompt, n, img1_b64, img2_b64) for label, prompt, n in jobs]
        results = [f.result() for f in futs]

    landed = [r for r in results if r]
    print(f"\n=== DONE · {len(landed)}/{len(jobs)} landed · wall: {time.time()-t0:.1f}s ===")
    for p in landed:
        print(f"  {p}")


if __name__ == "__main__":
    main()

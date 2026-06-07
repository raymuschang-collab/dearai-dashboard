#!/usr/bin/env python3
"""Retry the 3 iter-1 gens that 429'd in the parallel burst — sequentially with pacing."""
import os, json, base64, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

REVE_KEY = os.environ["REVE_API_KEY"]
REVE_URL = "https://api.reve.com/v1/image/remix"

IMG1 = Path("/tmp/wan_refs/Image1_man.jpeg")
IMG2 = Path("/tmp/wan_refs/Image2_woman.jpeg")
OUT_DIR = Path("/Users/raymuschang/Downloads/Wan Test/reve_outputs")

# Same prompts, only iter 1 of each (the failed ones)
RETRIES = [
    ("shot1_WS", "Wide shot photograph, 9:16 vertical. The man in <img>0</img> stands facing the woman in <img>1</img>, mid-conversation, full body in frame. They are under the dense shade of a massive raintree (Samanea saman) with sprawling lateral branches overhead. Harsh tropical midday sunlight breaks through the canopy in dappled patches — HIGH CONTRAST, deep shadow on their bodies, blown-out highlights on the foliage and ground behind them. Documentary editorial photography aesthetic, natural skin texture with visible pores, Kodak Portra 400 color science, no airbrushing, no game-engine rendering. The man's face must match <img>0</img> exactly (beard, dark hair, cream mandarin-collar shirt). The woman's face must match <img>1</img> exactly (bob haircut, cream blazer-shirt over black top). No text, no captions."),
    ("shot2_MS_OTS_listening", "Mid-shot OTS photograph, 9:16 vertical. Over the shoulder of the man from <img>0</img> — his back-of-head and right shoulder soft-focus in the left foreground. Beyond him, in sharp focus, the woman from <img>1</img> stands listening attentively. Gaze direct on his face, mouth closed, focused expression. Background: shaded raintree canopy with dappled light filtering through. Same harsh-light high-contrast lighting as the establishing wide. Documentary editorial photography aesthetic, natural skin texture, Kodak Portra 400 color science. The woman's face must match <img>1</img> exactly. The man's hair and shoulder match <img>0</img>."),
    ("shot3_CU_OTS_listening", "Close-up OTS photograph, 9:16 vertical. The back of the man's head and right shoulder from <img>0</img> is heavily blurred in the foreground, occupying the right third of the frame. The woman from <img>1</img> fills the rest of the frame in tight close-up. She listens intently — mouth closed, eyes focused on his face just off-frame, micro-expression of concentration. Soft dappled raintree light from above; shallow depth of field. Documentary editorial photography aesthetic, natural skin texture with visible pores, Kodak Portra 400 color science. The woman's face must match <img>1</img> exactly."),
]

img1_b64 = base64.b64encode(IMG1.read_bytes()).decode()
img2_b64 = base64.b64encode(IMG2.read_bytes()).decode()

for label, prompt in RETRIES:
    out_path = OUT_DIR / f"{label}_v1.png"
    if out_path.exists():
        print(f"  • {label} v1 already exists, skipping")
        continue
    print(f"  ◦ firing {label} v1...", flush=True)
    body = {"prompt": prompt, "reference_images": [img1_b64, img2_b64], "aspect_ratio": "9:16", "version": "latest"}
    # retry-with-backoff up to 5 times
    for attempt in range(5):
        r = requests.post(REVE_URL,
            headers={"Authorization": f"Bearer {REVE_KEY}", "Accept": "application/json", "Content-Type": "application/json"},
            json=body, timeout=300)
        if r.status_code == 200:
            data = r.json()
            if "image" in data:
                out_path.write_bytes(base64.b64decode(data["image"]))
                print(f"  ✓ {label} v1 → {out_path.name} ({out_path.stat().st_size/1024:.1f} KB)", flush=True)
                break
            else:
                print(f"  ✗ {label} v1 missing image field"); break
        elif r.status_code == 429:
            wait = 8 + attempt * 4
            print(f"    429 rate limited, sleeping {wait}s (attempt {attempt+1}/5)...", flush=True)
            time.sleep(wait)
        else:
            print(f"  ✗ {label} v1 HTTP {r.status_code}: {r.text[:200]}"); break
    else:
        print(f"  ✗ {label} v1 gave up after 5 retries")
    # pacing between successful calls to avoid hitting limit again
    time.sleep(5)

print("\ndone")

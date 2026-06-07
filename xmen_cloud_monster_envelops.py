#!/usr/bin/env python3
"""X-Men climb — cloud monster sends tendrils that envelop him.

5 shots in 13s (3+3+2+2+3): wide hero with tendrils descending, MS envelop,
ECU hair drying/weathering, ECU skin parched, ECU face holding determination.

480p / 16:9 / 13s / 3 iters. No music, SFX only.

Refs (4):
  - Reference video #1 = THE MAN          asset-20260531201701-cmnc6
  - Reference image #2 = LARGE DEMON      asset-20260531211754-2mv9d
  - Reference image #3 = UPPER FACADE     asset-20260531211815-5zvb7
  - Reference image #4 = CLIMB LOCATION   asset-20260531211826-thmjn
"""
import os
import sys
import time
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path("/Users/raymuschang/Documents/Shotlist Workflows")
load_dotenv(HERE / ".env")

ARK_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
MODEL = "dreamina-seedance-2-0-260128"
OUT_DIR = Path("/Users/raymuschang/Documents/X-men/Generated Videos/Seq02f_Cloud_Monster_Envelops")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAN          = "asset-20260531201701-cmnc6"
LARGE_DEMON  = "asset-20260531211754-2mv9d"
LOC_BLK2     = "asset-20260531211815-5zvb7"
LOC_IAR      = "asset-20260531211826-thmjn"

PROMPT = """Shot on ARRI ALEXA LF. Night. Heavy rain on a Ho Chi Minh City-style Southeast Asian street. Big sweeping Hollywood camera work, cinematic scale. Cool blue-grey midtones with warm sodium streetlight glints, prestige drama grade. NO music. Diegetic SFX only — torrential rain, distant rolling thunder within the cloud-monster, smoky hissing whoosh as the tendrils descend, wind, his ragged controlled breathing.

Reference identities:
- Reference video #1 = THE MAN — anchor his face and physicality. Soaked white tank top, exhausted but unbroken, climbing methodically.
- Reference image #2 = LARGE DEMON — anchor the monster's design (smoke-and-shadow). Now manifested as a massive cloud-form in the night sky above the building, with two huge BLUE glowing eyes.
- Reference image #3 = UPPER FACADE — composition for the building and climb.
- Reference image #4 = CLIMB LOCATION — rain-soaked HCMC facade composition.

HORIZONTAL 16:9 cinematic widescreen. Five shots cut together over 13 seconds, paced 3 + 3 + 2 + 2 + 3. Stylized supernatural-elements effect — the storm wicks moisture from him as a metaphor. NOT graphic body horror.

SHOT 1 — WS, Low Angle, ~3 seconds.
Hero low-angle composition: THE MAN climbs the rain-soaked towering facade in the FOREGROUND. High up in the night sky above the building: the massive CLOUD-FORM MONSTER with two huge BLUE GLOWING EYES dominates the upper frame. The monster's cloud body visibly EXTRUDES — long curling TENDRILS of smoke and cloud uncoil from its mass and descend toward him, snaking down the facade. Lightning flickers within the cloud-monster. Diegetic SFX: torrential rain, thunder rolling within the cloud, smoky whoosh of tendrils descending.

SHOT 2 — MS, Static, ~3 seconds.
The smoke-cloud tendrils REACH him and ENVELOP him on the facade — wrapping around his shoulders, swirling around his head and arms, billowing across his back. He keeps climbing through it, never stopping. The smoke is dense, swirling, alive but stylized — atmospheric, not violent. Diegetic SFX: smoky hiss, rain, his exhale.

SHOT 3 — ECU on his HAIR, ~2 seconds.
Extreme close-up: his soaked hair as the smoke wicks moisture out of it. Where it was plastered wet to his skull, strands now go DRY and brittle and windswept — fine wisps lifting in the smoky air, color drained to ash-grey at the tips. A subtle, stylized weathering effect — like a desert wind on damp hair. Diegetic SFX: dry rustle, faint crackling.

SHOT 4 — ECU on his SKIN, ~2 seconds.
Extreme close-up: the skin of his cheekbone and temple. Moisture leeches away — surface goes from rain-wet to parched and weathered, faint cracking texture forming like dry clay. Subtle, stylized — like a desert wind on damp earth. Diegetic SFX: dry whisper, distant thunder.

SHOT 5 — ECU on his FACE, ~3 seconds.
Extreme close-up holding on his face — hair now dry and windswept, skin parched and weathered, lips cracking. But his EYES are STILL THERE — steady, locked upward, burning with determination through the deterioration. Microexpressions of unbroken will:
- A slow controlled blink.
- Nostrils flare gently.
- Jaw locks against the toll the storm is taking.
- The faintest defiant exhale through cracked lips.
- A tiny, almost imperceptible upward lift of the chin — he is NOT broken.
- Eyes never leave the next ledge above.
Diegetic SFX: his controlled breath, distant thunder, rain continuing in the background.
"""

CONTENT = [
    {"type": "text", "text": PROMPT},
    {"type": "video_url", "video_url": {"url": f"asset://{MAN}"},          "role": "reference_video"},
    {"type": "image_url", "image_url": {"url": f"asset://{LARGE_DEMON}"},  "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{LOC_BLK2}"},     "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{LOC_IAR}"},      "role": "reference_image"},
]

BODY = {
    "model": MODEL,
    "content": CONTENT,
    "ratio": "16:9",
    "duration": 13,
    "resolution": "480p",
    "watermark": False,
}


def submit() -> str:
    r = requests.post(f"{ARK_BASE}/contents/generations/tasks",
                      headers={"Authorization": f"Bearer {ARK_KEY}",
                               "Content-Type": "application/json"},
                      json=BODY, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"submit {r.status_code}: {r.text[:400]}")
    return r.json()["id"]


fired = []
for it in (1, 2, 3):
    print(f"\n→ submitting Cloud_Monster_Envelops iter {it}")
    tid = submit()
    print(f"   task id: {tid}")
    fired.append({"iter": it, "task_id": tid, "status": "queued",
                  "video_url": None, "local": None})

remaining = {j["task_id"]: j for j in fired}
start = time.time()
while remaining:
    time.sleep(15)
    elapsed = int(time.time() - start)
    for tid in list(remaining.keys()):
        j = remaining[tid]
        try:
            r = requests.get(f"{ARK_BASE}/contents/generations/tasks/{tid}",
                             headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=60)
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            print(f"   [{elapsed}s] iter{j['iter']} poll err: {e}")
            continue
        status = d.get("status")
        if status != j["status"]:
            print(f"   [{elapsed}s] iter{j['iter']}: {j['status']} -> {status}")
            j["status"] = status
        if status == "succeeded":
            j["video_url"] = (d.get("content") or {}).get("video_url")
            print(f"       url: {j['video_url']}")
            del remaining[tid]
        elif status in ("failed", "expired", "cancelled"):
            j["error"] = d.get("error")
            print(f"       payload: {json.dumps(d.get('error'))[:300]}")
            del remaining[tid]

for j in fired:
    if j["status"] == "succeeded" and j["video_url"]:
        out = OUT_DIR / f"Seq02f_Cloud_Monster_Envelops_480p_16x9_13s_iter{j['iter']}.mp4"
        print(f"\n↓ iter{j['iter']} → {out.name}")
        with requests.get(j["video_url"], stream=True, timeout=300) as rd:
            rd.raise_for_status()
            with open(out, "wb") as f:
                for chunk in rd.iter_content(1 << 20):
                    f.write(chunk)
        j["local"] = str(out)
    else:
        print(f"\n✗ iter{j['iter']} failed: {j.get('error')}")

(OUT_DIR / "manifest.json").write_text(json.dumps(fired, indent=2, default=str))
print("\nDONE.")
for j in fired:
    print(f"  iter{j['iter']}  {j['status']:10}  {j.get('local','')}")

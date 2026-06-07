#!/usr/bin/env python3
"""X-Men cloud-monster rain-hisses-on-skin — v2 (no cracking).

Same scene structure as Seq02f but with two specific tweaks per user notes:
  1. NO skin cracking. Just discolouration + dryness.
  2. NO smoke tendrils descending. The rain itself FROM the cloud-monster
     hits him and HISSES on contact with his skin, brief steam plumes.

5 shots in 13s (3+3+2+2+3). 480p / 16:9 / 3 iters. No music, SFX only.

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
OUT_DIR = Path("/Users/raymuschang/Documents/X-men/Generated Videos/Seq02h_Cloud_Rain_Hiss")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAN          = "asset-20260531201701-cmnc6"
LARGE_DEMON  = "asset-20260531211754-2mv9d"
LOC_BLK2     = "asset-20260531211815-5zvb7"
LOC_IAR      = "asset-20260531211826-thmjn"

PROMPT = """Shot on ARRI ALEXA LF. Night. Heavy rain on a Ho Chi Minh City-style Southeast Asian street. Big sweeping Hollywood camera work, cinematic scale. Cool blue-grey midtones with warm sodium streetlight glints, prestige drama grade. NO music. Diegetic SFX only — torrential rain hammering stone, distant rolling thunder within the cloud-monster, wind, his ragged controlled breathing, soft steady HISSING sound as the rain meets his skin.

Reference identities:
- Reference video #1 = THE MAN — anchor his face and physicality. Soaked white tank top, exhausted but unbroken, climbing methodically.
- Reference image #2 = LARGE DEMON — anchor the monster's design (smoke-and-shadow). REPURPOSED as a massive storm-cloud form in the sky above the building, with two huge BLUE glowing eyes.
- Reference image #3 = UPPER FACADE — composition for the building and climb.
- Reference image #4 = CLIMB LOCATION — rain-soaked HCMC facade composition.

HORIZONTAL 16:9 cinematic widescreen. Five shots cut together over 13 seconds, paced 3 + 3 + 2 + 2 + 3. Stylized supernatural effect — the storm-monster's rain itself weathers him as a metaphor. NOT body horror. NO cracking of skin. NO graphic damage.

SHOT 1 — WS, Low Angle, ~3 seconds.
Hero low-angle composition: THE MAN climbs the rain-soaked towering facade in the FOREGROUND. High in the night sky above the building, the massive CLOUD-FORM MONSTER with two huge BLUE GLOWING EYES dominates the upper frame, roiling and shifting. Heavy torrential rain pours down from the cloud-monster's body. Lightning flickers within the cloud. Diegetic SFX: torrential rain, thunder rolling within the cloud.

SHOT 2 — MS, Static, ~3 seconds.
Sheets of rain from the cloud-monster pour directly onto him as he climbs. Each raindrop HISSES on contact with his skin — small plumes of fine steam rise briefly from his shoulders, neck, arms, where the rain lands. The rain itself is what touches him — NO smoke tendrils, NO smoke envelopment. He keeps climbing through the hissing rain, never stopping. Diegetic SFX: a soft continuous hissing layer over the rain, his exhale.

SHOT 3 — ECU on his HAIR, ~2 seconds.
Extreme close-up: his soaked hair as the supernatural rain wicks moisture out of it. Strands go DRY and brittle and windswept — fine wisps lifting in the air, color drained to ash-grey at the tips. A subtle stylized weathering effect. Diegetic SFX: dry rustle, faint steam hiss.

SHOT 4 — ECU on his SKIN, ~2 seconds.
Extreme close-up: the skin of his cheekbone and temple. Subtle DISCOLOURATION only — surface tone shifts to a sun-parched ashen / pale-grey hue. Slight DRYNESS. Faint steam wisps lifting off the surface where rain has landed. The skin remains SMOOTH — NO cracking, NO splitting, NO clay texture, NO wounds. Just stylized discolouration and dryness, like a desert wind on damp skin. Diegetic SFX: a soft skin-hiss, distant thunder.

SHOT 5 — ECU on his FACE, ~3 seconds.
Extreme close-up holding on his face — hair dry and windswept, skin smoothly discoloured and dry, lips dry but NOT cracked. His EYES are STILL THERE — steady, locked upward, burning with determination through the weathering. Microexpressions of unbroken will:
- A slow controlled blink.
- Nostrils flare gently.
- Jaw locks against the toll the storm is taking.
- The faintest defiant exhale through dry lips.
- A tiny upward lift of the chin — he is NOT broken.
- Eyes never leave the next ledge above.
Diegetic SFX: his controlled breath, the hissing of rain on skin layered with distant thunder, rain continuing in the background.
"""

CONTENT = [
    {"type": "text", "text": PROMPT},
    {"type": "video_url", "video_url": {"url": f"asset://{MAN}"},          "role": "reference_video"},
    {"type": "image_url", "image_url": {"url": f"asset://{LARGE_DEMON}"},  "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{LOC_BLK2}"},     "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{LOC_IAR}"},      "role": "reference_image"},
]

BODY = {
    "model": MODEL, "content": CONTENT,
    "ratio": "16:9", "duration": 13, "resolution": "480p", "watermark": False,
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
    print(f"\n→ submitting Cloud_Rain_Hiss iter {it}")
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
        out = OUT_DIR / f"Seq02h_Cloud_Rain_Hiss_480p_16x9_13s_iter{j['iter']}.mp4"
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

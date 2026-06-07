#!/usr/bin/env python3
"""X-Men cloud-monster lunge → burst into rain droplets → hisses on skin.

Faster kinetic version per client note: monster lunges down, bursts into a
billion water droplets, camera dollies back aggressively as the rain (=
dispersed monster) falls on the climber and hisses on his skin.

5 shots / 13s / 3 iters / 480p / 16:9. No music, SFX only.
NO skin cracking — just discolouration + dryness.

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

HERE = Path("/Users/raymuschang/Desktop/Shotlist Workflows")
load_dotenv(HERE / ".env")

ARK_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
MODEL = "dreamina-seedance-2-0-260128"
OUT_DIR = Path("/Users/raymuschang/Desktop/X-men/Generated Videos/Seq02i_Cloud_Lunge_Disperse")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAN          = "asset-20260531201701-cmnc6"
LARGE_DEMON  = "asset-20260531211754-2mv9d"
LOC_BLK2     = "asset-20260531211815-5zvb7"
LOC_IAR      = "asset-20260531211826-thmjn"

PROMPT = """Shot on ARRI ALEXA LF. Night. Heavy rain on a Ho Chi Minh City-style Southeast Asian street. Big sweeping Hollywood camera work, cinematic scale. Cool blue-grey midtones with warm sodium streetlight glints, prestige drama grade. NO music. Diegetic SFX only — torrential rain hammering stone, distant rolling thunder, his ragged controlled breathing. Stylized supernatural metaphor, NOT violent.

Reference identities:
- Reference video #1 = THE MAN — anchor his face and physicality. Soaked white tank top, exhausted but unbroken, climbing methodically.
- Reference image #2 = LARGE DEMON — anchor the monster's design (smoke-and-shadow). Now manifested as a MASSIVE cloud-form in the sky above the building with two huge BLUE glowing eyes.
- Reference image #3 = UPPER FACADE — composition for the building and climb.
- Reference image #4 = CLIMB LOCATION — rain-soaked HCMC facade composition.

HORIZONTAL 16:9 cinematic widescreen. FAST KINETIC SEQUENCE. Five shots cut together over 13 seconds, paced 2 + 2 + 3 + 3 + 3. NO skin cracking — just discolouration and dryness. NO graphic violence — the monster disperses BEFORE contact.

SHOT 1 — WS, Low Angle, ~2 seconds.
Hero low-angle composition: THE MAN climbs the rain-soaked towering facade in the FOREGROUND. High in the night sky above the building, the massive CLOUD-FORM MONSTER with two huge BLUE GLOWING EYES dominates the upper frame, roiling and shifting. Brief setup of the threat. Diegetic SFX: rain, thunder rolling within the cloud.

SHOT 2 — WS, Aggressive Tracking Plunge, ~2 seconds.
The cloud-monster LUNGES DOWN from the sky toward him — fast, predatory diving motion — its BLUE eyes burning brighter as it descends, tendrils of cloud trailing behind it like a comet tail. Camera tracks it diving down the facade. Diegetic SFX: rising whoosh, thunder cracking, wind howling.

SHOT 3 — ECU into Aggressive Dolly Back, ~3 seconds.
Extreme close-up on the monster's BLUE GLOWING EYES mid-lunge — just before contact with him — then the monster BURSTS, scattering into a billion shimmering rain droplets. The dense cloud form EXPLODES into water. Camera DOLLIES BACK AGGRESSIVELY (fast hard pullback) as the dispersing droplets fly outward in all directions and begin to fall toward him. Diegetic SFX: percussive BOOM of dispersion, water rushing outward.

SHOT 4 — MS, Static, ~3 seconds.
The rain — which IS the dispersed monster — cascades down directly onto him as he climbs. Each droplet HISSES on contact with his skin — small plumes of fine steam rise from his shoulders, neck, arms where the rain lands. He keeps climbing through the hissing rain, never stopping. Diegetic SFX: a layered continuous hissing, rain, his exhale.

SHOT 5 — ECU on his face, ~3 seconds.
Extreme close-up on his face. His hair has gone DRY and WINDSWEPT — strands ash-grey at the tips lifting in the air. His skin shows subtle DISCOLOURATION (sun-parched ashen tone) and DRYNESS, faint steam wisps lifting from the surface. SKIN REMAINS SMOOTH — NO cracking, NO clay texture, NO splits. Lips dry but NOT cracked. His EYES are STILL THERE — steady, locked upward, burning with unbroken determination. Microexpressions: slow controlled blink, nostrils flare gently, jaw locks against the toll, the faintest defiant exhale through dry lips, tiny upward lift of the chin — he is NOT broken. Diegetic SFX: hiss on skin, his controlled breath, distant thunder.
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
    print(f"\n→ submitting Cloud_Lunge_Disperse iter {it}")
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
        out = OUT_DIR / f"Seq02i_Cloud_Lunge_Disperse_480p_16x9_13s_iter{j['iter']}.mp4"
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

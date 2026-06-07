#!/usr/bin/env python3
"""X-Men climb — cloud-form monster above building rains down on the man.

Single sustained low-angle 12s shot. Same building, same man, same large demon
relocated to the sky as a storm cloud with blue glowing eyes. Monster IS the
rain cloud — torrents fall from its body onto him as he climbs.

720p / 16:9 / 12s / 2 iters. No music, SFX only.

Refs (4 — under all caps):
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
OUT_DIR = Path("/Users/raymuschang/Documents/X-men/Generated Videos/Seq02e_Cloud_Monster_Climb")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAN          = "asset-20260531201701-cmnc6"
LARGE_DEMON  = "asset-20260531211754-2mv9d"
LOC_BLK2     = "asset-20260531211815-5zvb7"
LOC_IAR      = "asset-20260531211826-thmjn"

PROMPT = """Shot on ARRI ALEXA LF. Night. Heavy rain on a Ho Chi Minh City-style Southeast Asian street. Big sweeping Hollywood camera work, cinematic scale. Cool blue-grey midtones with warm sodium streetlight glints, prestige drama grade. NO music. Diegetic SFX only — torrential rain hammering stone, distant rolling thunder, wind, his ragged breathing, occasional low grunt of effort.

Reference identities:
- Reference video #1 = THE MAN — anchor his face and physicality. Soaked white tank top, exhausted but determined, climbing methodically.
- Reference image #2 = LARGE DEMON — anchor the monster's design (smoke-and-shadow form, glowing eyes). THIS TIME the monster is REPURPOSED as a massive cloud form in the night sky above the building.
- Reference image #3 = UPPER FACADE — composition for the building and climb.
- Reference image #4 = CLIMB LOCATION — rain-soaked HCMC facade composition.

HORIZONTAL 16:9 cinematic widescreen. SINGLE SUSTAINED LOW-ANGLE SHOT for the full 12 seconds.

WS, Low Angle, Static with a slow gentle rise, ~12 seconds.
Hero low-angle composition: THE MAN climbs the rain-soaked towering facade in a soaked white tank top, dominant in the FOREGROUND of the frame, lit from below by warm sodium streetlight. He moves steadily upward — exhausted but determined, hand over hand, never stopping.

HIGH UP in the dark night sky ABOVE the building: a MASSIVE CLOUD-FORM of the smoke-and-shadow MONSTER — the same large demon design, now coalesced from billowing storm clouds, shifting and roiling, DOMINATING the upper half of the frame. TWO HUGE BLUE GLOWING EYES burn through the cloud mass, gazing down at him. Tendrils of cloud trail off the form like smoky limbs.

The rain does NOT simply fall from the sky — it falls from the MONSTER ITSELF. Torrents of rain pour down out of the cloud-monster's body directly onto him, sheeting over the facade. Lightning flickers WITHIN the cloud-monster's form, illuminating its glowing blue eyes from inside.

He keeps climbing — methodical hand-over-hand grip, water cascading down his back and shoulders, hair plastered to his face, eyes locked upward on the next ledge. He does NOT look at the monster. He just keeps going.

The camera holds low and slowly rises with him over the 12 seconds, keeping the cloud-monster above in the upper frame and the man as the foreground anchor throughout.

Stylized natural-elements imagery, no graphic violence. The monster is an atmospheric presence — a storm metaphor."""

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
    "duration": 12,
    "resolution": "720p",
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
for it in (1, 2):
    print(f"\n→ submitting Cloud_Monster_Climb iter {it}")
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
        out = OUT_DIR / f"Seq02e_Cloud_Monster_Climb_720p_16x9_12s_iter{j['iter']}.mp4"
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

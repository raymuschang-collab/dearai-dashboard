#!/usr/bin/env python3
"""X-Men finale — rooftop victory, operatic cloud-monster dispersal, azure-sky reveal.

Hero shot. He makes it. He punches the sky. The cloud-monster detonates with
an operatic "oomph," shatters into mist, and parts to reveal a vibrant azure
sky and warm golden first light. His hair and skin are restored.

4 shots / 12s / 2 iters / 720p / 16:9. No music, SFX only.

Refs (3):
  - Reference video #1 = THE MAN          asset-20260531201701-cmnc6
  - Reference image #2 = LARGE DEMON      asset-20260531211754-2mv9d  (for cloud dispersal)
  - Reference image #3 = UPPER FACADE     asset-20260531211815-5zvb7
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
OUT_DIR = Path("/Users/raymuschang/Desktop/X-men/Generated Videos/Seq02j_Rooftop_Victory")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAN         = "asset-20260531201701-cmnc6"
LARGE_DEMON = "asset-20260531211754-2mv9d"
LOC_BLK2    = "asset-20260531211815-5zvb7"

PROMPT = """Shot on ARRI ALEXA LF. Pre-dawn breaking. The night storm is ENDING. Big sweeping Hollywood camera work, cinematic epic scale. The grade SHIFTS across the sequence: starts cool blue-grey storm → opens into warm golden first light and vibrant azure sky. Prestige drama. NO music. Diegetic SFX only — wind dying, his exhale, a deep operatic low-frequency "OOMPH" reverb as the cloud detonates, distant city ambience returning.

Reference identities:
- Reference video #1 = THE MAN — anchor his face and physicality. He has just reached the rooftop. Soaked white tank top. Exhausted but triumphant.
- Reference image #2 = LARGE DEMON — anchor the storm-cloud monster (smoke-and-shadow, blue glowing eyes) — for the dispersal/detonation moment.
- Reference image #3 = UPPER FACADE — composition for the building and the rooftop edge.

HORIZONTAL 16:9 cinematic widescreen. Four shots cut together over 12 seconds, paced 3 + 3 + 4 + 2.

SHOT 1 — MS, Slow Crane Up + Back, ~3 seconds.
THE MAN's hand grips the rooftop parapet edge. He hauls himself up over it with the last of his strength — torso emerging, then his legs. He stands slowly on the rooftop, chest heaving, soaked white tank top, exhausted but alive. The vast rain-slicked HCMC cityscape spreads behind and below him. The storm clouds above still roil — the cloud-monster's BLUE GLOWING EYES burn faintly in the sky. Diegetic SFX: wind, his ragged exhale, distant rain tapering.

SHOT 2 — WS, Hero Low Angle, ~3 seconds.
LOW-ANGLE hero composition: the man stands tall on the rooftop edge, framed against the still-stormy sky. He throws his head back, draws in a huge inhale, and PUNCHES his fist UPWARD into the sky — a single explosive victorious punch toward the cloud-monster overhead. Body language full of catharsis and defiance. Diegetic SFX: a wordless primal triumphant SHOUT, his fist cutting the air.

SHOT 3 — WS High Wide, ~4 seconds. THE OPERATIC DISPERSAL.
The frame widens, looking UP past him into the sky. At the exact impact of his punch, the massive cloud-form MONSTER DETONATES with a deep operatic "OOMPH." A radial burst of light explodes outward from the cloud-monster's core; the blue glowing eyes flare brilliant WHITE for an instant then SHATTER outward; the roiling cloud body bursts apart into a dramatic radial scattering of mist and droplets, expanding outward in slow-motion grandeur. As it disperses, the dense storm clouds PART to reveal VIBRANT AZURE SKY behind — brilliant, impossible blue. Warm golden first-light POURS through the parting clouds. The whole frame transforms from cool blue-grey to warm gold and azure. Diegetic SFX: a deep low-frequency operatic OOMPH / boom, then sustained airy whoosh of dispersing mist, then the dawn silence, distant birds beginning.

SHOT 4 — CU, Static, ~2 seconds.
Tight on the man's face, now bathed in warm golden light from the azure sky. His HAIR is FULL and VIBRANT — soft, dark, alive, lifting gently in the breeze, completely restored. His SKIN is HEALTHY — warm honey tone restored, smooth, glowing, NO discolouration, NO dryness. Eyes lifted, gaze steady on the open sky. A small triumphant private smile at the corner of his mouth — quiet, earned. Diegetic SFX: a soft inhale through his nose, the wind, distant city waking up.
"""

CONTENT = [
    {"type": "text", "text": PROMPT},
    {"type": "video_url", "video_url": {"url": f"asset://{MAN}"},          "role": "reference_video"},
    {"type": "image_url", "image_url": {"url": f"asset://{LARGE_DEMON}"},  "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{LOC_BLK2}"},     "role": "reference_image"},
]

BODY = {
    "model": MODEL, "content": CONTENT,
    "ratio": "16:9", "duration": 12, "resolution": "720p", "watermark": False,
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
    print(f"\n→ submitting Rooftop_Victory iter {it}")
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
        out = OUT_DIR / f"Seq02j_Rooftop_Victory_720p_16x9_12s_iter{j['iter']}.mp4"
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

#!/usr/bin/env python3
"""X-Men climb POV — Vietnamese lover watches from the crowd.

720p / 16:9 / 12s / 2 iters. No music, SFX only.

Refs (4 total — under 6-cap, under 3-video-cap):
  - Reference video #1 = THE MAN              asset-20260531201701-cmnc6
  - Reference video #2 = THE VIETNAMESE WOMAN asset-20260604135923-lmkrg
  - Reference image #3 = CLIMB LOCATION (IAR) asset-20260531211826-thmjn
  - Reference image #4 = UPPER FACADE (BLK2)  asset-20260531211815-5zvb7
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
OUT_DIR = Path("/Users/raymuschang/Documents/X-men/Generated Videos/Seq02c_VN_Lover_Watches")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAN          = "asset-20260531201701-cmnc6"
VN_WOMAN     = "asset-20260604135923-lmkrg"
LOC_IAR      = "asset-20260531211826-thmjn"
LOC_BLK2     = "asset-20260531211815-5zvb7"

PROMPT = """Shot on ARRI ALEXA LF. Night. Heavy rain on a Ho Chi Minh City-style Southeast Asian street. Big sweeping Hollywood camera work, cinematic scale. Cool blue-grey midtones with warm sodium streetlight glints, prestige drama grade. Diegetic SFX only — rain, wind, distant Vietnamese crowd murmur, city ambience, wet umbrellas. NO music.

Reference identities:
- Reference video #1 = THE MAN — anchor his face. He climbs the rain-slicked building facade, a small figure high up.
- Reference video #2 = THE VIETNAMESE WOMAN — anchor her exact face. She stands in the crowd of onlookers below.
- Reference image #3 = CLIMB LOCATION — rain-soaked facade with crowd at base, Vietnamese HCMC street.
- Reference image #4 = UPPER FACADE — composition for the climbing-figure shot.

HORIZONTAL 16:9 cinematic widescreen. Four shots cut together over 12 seconds:

SHOT 1 — WS, Crane Up, ~3 seconds.
Establish a sea of onlookers on a rain-slicked HCMC street at night — hundreds of umbrellas tilted, NECKS CRANED UPWARD, all looking straight UP. Rain falls heavy. THE WOMAN stands in the crowd — recognisably her face from the reference — also looking up. Diegetic SFX: rain, wet pavement, Vietnamese crowd gasps and murmurs.

SHOT 2 — WS, Low Angle Tilt Up, ~3 seconds.
The crowd's worm's-eye POV up the towering rain-slicked facade. Fat raindrops streak the lens. THE MAN is a small figure high up, climbing methodically — feet planted on the wall, never dangling. Lightning flicker in the distance. Diegetic SFX: wind, rain on stone.

SHOT 3 — MS, Static, ~3 seconds.
Hold on THE WOMAN in the crowd. Around her, other onlookers' faces show alarm and worry — hands to mouths, gasps. SHE DOES NOT. Detailed microexpressions of quiet confidence:
- Eyes lifted, steady, unblinking gaze locked on him, pupils still — not darting in panic.
- Brow smooth — no furrow between brows; the gentlest lift of recognition, not fear.
- Mouth soft, lips slightly parted, the faintest knowing half-smile at the corners.
- Jaw loose, cheeks relaxed — not clenched.
- A slow controlled exhale through parted lips, fogging slightly in the cold rain.
- Chin lifted, shoulders open, back straight — posture of belief.
- A barely perceptible tiny nod — silent "you've got this".
- Hands relaxed at her sides, not gripping or clutching, not pressed to her face.
- Eyes glisten — but with pride, not tears.
- Rain runs down her cheeks unchecked; she doesn't wipe it away.

SHOT 4 — CU push-in to ECU, ~3 seconds.
Slow push from MCU to ECU on her face. Hold the confident gaze. A small private smile blooms at the corner of her mouth — the smile of someone who already knew he would make it. Streetlight catches a single raindrop on her lash. Diegetic SFX: rain swelling, distant crowd gasp rising, then the faintest soft exhale from her — a smile becoming breath.
"""

CONTENT = [
    {"type": "text", "text": PROMPT},
    {"type": "video_url", "video_url": {"url": f"asset://{MAN}"},      "role": "reference_video"},
    {"type": "video_url", "video_url": {"url": f"asset://{VN_WOMAN}"}, "role": "reference_video"},
    {"type": "image_url", "image_url": {"url": f"asset://{LOC_IAR}"},  "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{LOC_BLK2}"}, "role": "reference_image"},
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


# Fire 2 iters
fired = []
for it in (1, 2):
    print(f"\n→ submitting VN_lover_watches iter {it}")
    tid = submit()
    print(f"   task id: {tid}")
    fired.append({"iter": it, "task_id": tid, "status": "queued",
                  "video_url": None, "local": None})

# Poll
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

# Download
for j in fired:
    if j["status"] == "succeeded" and j["video_url"]:
        out = OUT_DIR / f"Seq02c_VN_Lover_Watches_720p_16x9_12s_iter{j['iter']}.mp4"
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

#!/usr/bin/env python3
"""X-Men climb — solo exhaustion + mustering-strength beat.

720p / 16:9 / 12s / 2 iters. No music, no dialogue, SFX only.
NO monster — clean climb focused on physical exhaustion + willpower.

Shots paced 2 + 2 + 2 + 6 (the mustering-strength beat is the long held shot).

Refs (3 — under all caps):
  - Reference video #1 = THE MAN          asset-20260531201701-cmnc6
  - Reference image #2 = CLIMB LOCATION    asset-20260531211826-thmjn
  - Reference image #3 = UPPER FACADE      asset-20260531211815-5zvb7
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
OUT_DIR = Path("/Users/raymuschang/Documents/X-men/Generated Videos/Seq02d_Climb_Exhaustion_Solo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAN      = "asset-20260531201701-cmnc6"
LOC_IAR  = "asset-20260531211826-thmjn"
LOC_BLK2 = "asset-20260531211815-5zvb7"

PROMPT = """Shot on ARRI ALEXA LF. Night. Heavy rain on a Ho Chi Minh City-style Southeast Asian street. Big sweeping Hollywood camera work, cinematic scale. Cool blue-grey midtones with warm sodium streetlight glints, prestige drama grade. NO monster, no demon — clean climbing scene focused entirely on his physical exhaustion and willpower. Diegetic SFX only — rain on stone, wind, his ragged breathing, fingers scraping wet stone. NO music. NO dialogue.

Reference identities:
- Reference video #1 = THE MAN — anchor his face and physicality. White tank top soaked through, muscles strained, body drained.
- Reference image #2 = CLIMB LOCATION — rain-soaked towering facade on an HCMC street.
- Reference image #3 = UPPER FACADE — composition for the higher-up beats.

HORIZONTAL 16:9 cinematic widescreen. Four shots cut together over 12 seconds, paced 2 + 2 + 2 + 6 — the final shot is the long held mustering-strength beat.

SHOT 1 — WS, Slow Crane Up, ~2 seconds.
Establishing wide: THE MAN climbs high on the rain-soaked towering facade in a soaked white tank top, dwarfed against the vast wet wall. Every movement laboured, body language drained. Diegetic SFX: rain roar, wind.

SHOT 2 — CU, Static, ~2 seconds.
Front close-up on his face pressed to the wet stone. Eyes squeezed shut. Brow furrowed deeply. Mouth open in a soundless gasp. Rain runs down his cheeks. Chest heaves visibly. Diegetic SFX: ragged exhale, rain on stone.

SHOT 3 — CU, Side Profile, ~2 seconds.
Side angle on his jaw and temple. Water drips from his chin and lashes. Vein at his temple throbs. Jaw slack with fatigue. He grits down — jaw begins to clench. Diegetic SFX: deep inhale, rain.

SHOT 4 — CU, Static, ~6 seconds. The mustering-strength beat — HELD LONG.
Tight on his right hand and forearm reaching slowly upward toward the next ledge. The hand TREMBLES in mid-air, fingers quivering. A long held PAUSE — he can't quite reach it yet. His other hand grips the lower hold, knuckles white. Detailed microexpressions of overcoming exhaustion:
- Lips move soundlessly — a private self-talk, "come on".
- Eyes squeezed shut tighter for one beat — gathering everything.
- A long controlled inhale through his nose, chest expanding.
- Jaw locks; nostrils flare; eyes flash open hard with determination.
- The trembling hand steadies — for one frame, perfectly still.
- Then he reaches — fingers extending the last inch with deliberate force.
- His fingertips brush the upper ledge — and SEIZE it with a white-knuckled grip, rainwater squeezing out from under his palm.
Diegetic SFX: rain swelling, his breath catching, then a low primal grunt of effort, then the wet slap of his hand locking onto the ledge.
"""

CONTENT = [
    {"type": "text", "text": PROMPT},
    {"type": "video_url", "video_url": {"url": f"asset://{MAN}"},      "role": "reference_video"},
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


fired = []
for it in (1, 2):
    print(f"\n→ submitting Climb_Exhaustion_Solo iter {it}")
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
        out = OUT_DIR / f"Seq02d_Climb_Exhaustion_Solo_720p_16x9_12s_iter{j['iter']}.mp4"
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

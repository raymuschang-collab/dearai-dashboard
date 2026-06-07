#!/usr/bin/env python3
"""X-Men gym support scene — woman brings water bottle to break-taking man.

720p / 16:9 / 12s / 2 iters. No music, SFX only.

Refs (3 — under all caps):
  - Reference video #1 = THE MAN              asset-20260531201701-cmnc6
  - Reference video #2 = THE VIETNAMESE WOMAN asset-20260604135923-lmkrg
  - Reference image #3 = INDUSTRIAL GYM       asset-20260531211804-w5zzk
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
OUT_DIR = Path("/Users/raymuschang/Documents/X-men/Generated Videos/Seq01b_Gym_Support")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAN      = "asset-20260531201701-cmnc6"
VN_WOMAN = "asset-20260604135923-lmkrg"
GYM_BLK  = "asset-20260531211804-w5zzk"

PROMPT = """Action-cam handheld, dark grey tee. Harsh daylight, pushed grain, Kodak Portra 800 grain, slightly over-exposed and desaturated. INDUSTRIAL gym interior — exposed concrete walls, raw steel beams, weights racks and bars, dim natural light spilling through tall dusty windows. Warm muted desaturated palette. NO music. Diegetic SFX only — bar creak, heavy breathing, footsteps on concrete, ambient gym hum, soft cap unscrew.

Reference identities:
- Reference video #1 = THE MAN — anchor his face and physicality. He is mid-workout, sweaty, dark grey tee, focused.
- Reference video #2 = THE VIETNAMESE WOMAN — anchor her exact face. She comes into the gym to support him.
- Reference image #3 = INDUSTRIAL GYM BLOCKING — composition, depth, mood.

HORIZONTAL 16:9 cinematic widescreen. Four shots cut together over 12 seconds. NO DIALOGUE — the scene is entirely wordless, communicated through body language and microexpressions.

SHOT 1 — WS, Handheld, ~3 seconds.
THE MAN takes a break — sits on a weight bench in the industrial gym, head down, elbows on knees, sweaty, chest heaving. Body language exhausted but not defeated. SFX: bar creak in the distance, his heavy controlled breathing, ambient gym hum.

SHOT 2 — MS, Handheld tracking, ~3 seconds.
THE VIETNAMESE WOMAN walks across the gym floor toward him, calm and purposeful, holding an unopened water bottle in both hands. She is not in workout gear — casual, supportive presence. SFX: footsteps on concrete, distant weight clink, soft ambient hum.

SHOT 3 — MCU, Handheld, ~3 seconds.
She stops in front of him, offering the bottle with both hands. Warm supportive smile — soft eyes, slight head tilt, gentle "you got this" energy. Microexpressions: eyes meet his with quiet pride; corners of mouth lift in a small private smile; brow gently raised in encouragement, not pity. He looks up at her, eyes lifting from the floor. SFX: ambient hum, her soft footstep settling.

SHOT 4 — MCU, Handheld, ~3 seconds.
He takes the bottle, fingers brushing hers for a beat. A tired grateful smile spreads slowly across his face — first the eyes softening, then the corners of his mouth lifting. He looks up at her, holds her gaze. A quiet held beat between them — wordless understanding, full of trust. He gives the slightest nod of thanks. SFX: bottle cap soft creak, his exhale, ambient gym hum.
"""

CONTENT = [
    {"type": "text", "text": PROMPT},
    {"type": "video_url", "video_url": {"url": f"asset://{MAN}"},      "role": "reference_video"},
    {"type": "video_url", "video_url": {"url": f"asset://{VN_WOMAN}"}, "role": "reference_video"},
    {"type": "image_url", "image_url": {"url": f"asset://{GYM_BLK}"},  "role": "reference_image"},
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
    print(f"\n→ submitting Gym_Support iter {it}")
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
        out = OUT_DIR / f"Seq01b_Gym_Support_720p_16x9_12s_iter{j['iter']}.mp4"
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

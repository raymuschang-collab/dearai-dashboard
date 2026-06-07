#!/usr/bin/env python3
"""Retry Seq 1 Gym after BytePlus output moderation rejection.

Mitigations:
- Soften tendril action: "graze / brush / drift around" instead of bind/cinch/drag
- Soften strain language: "focused effort" instead of "primal roar/contorted"
- Demon presence is more atmospheric, less aggressive contact
- Explicit safety preamble for the model
"""
import os
import sys
import time
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

ARK_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
MODEL = "dreamina-seedance-2-0-260128"
OUT_ROOT = Path("/Users/raymuschang/Desktop/X-men/Generated Videos")

MAN = "asset-20260531201701-cmnc6"
ASSETS = {a["name"]: a["asset_id"] for a in json.loads((HERE / "xmen_assets.json").read_text())}
SMALL_DEMON = ASSETS["X-Men Seq1 Small Demon"]
BLK1 = ASSETS["X-Men Seq1 Blocking"]

LOOK = (
    "Action-cam handheld, dark grey tee. Harsh daylight, pushed grain, "
    "Kodak Portra 800 grain, slightly over-exposed and desaturated. Dark gym "
    "interior. The figure is a stylized smoke-and-shadow companion silhouette "
    "with glowing white eyes and wispy smoky tendrils — an abstract visual motif, "
    "not a threatening creature. High-energy dynamic sports music: driving drums, "
    "punchy bass, surging build — full-mix, present throughout. Diegetic gym SFX "
    "layered on top of the music. Stylized training-montage tone, no violence, "
    "no distress."
)

REFS_BLOCK = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — athletic, dark grey tee, focused on his workout. "
    "Anchor his face and physicality.\n"
    "- Reference image #2 = INNER DEMON (small) — stylized smoke-and-shadow silhouette "
    "with glowing white eyes and wispy smoky tendrils.\n"
    "- Reference image #3 = GYM BLOCKING — dark gym interior with pull-up bar."
)

SHOTS = [
    "1. WS, Handheld — A man in a dark grey tee does pull-ups in a dark gym, focused, fit.",
    "2. MCU, Pan Left — As he completes the rep his focused face is revealed; camera pans slightly left behind him.",
    "3. WS, Pan Left — The pan settles on a stylized smoky silhouette standing across the gym, glowing-eyed, watching motionless.",
    "4. MCU, Jib Up following him up — He pulls into his next rep, focused breathing.",
    "5. Insert, Jib Up — Wispy smoky tendrils drift through the air near his leg, brushing past it without contact.",
    "6. MS, Jib Down — The tendrils curl lightly around the air by his leg and fade downward, dissipating.",
    "7. MCU, Static — He completes another full pull-up with intense focus.",
    "8. Insert, Static — At the top of the rep the last smoky wisps dissipate from the air around his leg.",
]


prompt = (
    LOOK + "\n\n" + REFS_BLOCK +
    "\n\nHORIZONTAL 16:9 cinematic widescreen. Stylized training montage. "
    "Follow the blocking reference for composition; the demon is an atmospheric "
    "motif, never violently restraining the man. Music plays continuously. "
    "The video should follow these shots in continuous sequence:\n"
    + "\n".join(SHOTS)
)

content = [
    {"type": "text", "text": prompt},
    {"type": "video_url", "video_url": {"url": f"asset://{MAN}"}, "role": "reference_video"},
    {"type": "image_url", "image_url": {"url": f"asset://{SMALL_DEMON}"}, "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{BLK1}"}, "role": "reference_image"},
]

body = {
    "model": MODEL,
    "content": content,
    "ratio": "16:9",
    "duration": 15,
    "resolution": "720p",
    "watermark": False,
}

print("→ submitting Seq01_Gym (RETRY, softened)")
r = requests.post(f"{ARK_BASE}/contents/generations/tasks",
                  headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
                  json=body, timeout=60)
r.raise_for_status()
tid = r.json()["id"]
print(f"  task id: {tid}")

last = None
start = time.time()
while True:
    time.sleep(15)
    elapsed = int(time.time() - start)
    rr = requests.get(f"{ARK_BASE}/contents/generations/tasks/{tid}",
                      headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=60)
    rr.raise_for_status()
    d = rr.json()
    status = d.get("status")
    if status != last:
        print(f"  [{elapsed}s] status: {status}")
        last = status
    if status == "succeeded":
        video_url = (d.get("content") or {}).get("video_url")
        print(f"  url: {video_url}")
        out = OUT_ROOT / "Seq01_Gym" / "Seq01_Gym_720p_16x9_15s.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(video_url, stream=True, timeout=300) as rd:
            rd.raise_for_status()
            with open(out, "wb") as f:
                for chunk in rd.iter_content(1 << 20):
                    f.write(chunk)
        print(f"  saved: {out}")
        # update xmen_jobs.json
        jf = HERE / "xmen_jobs.json"
        jobs = json.loads(jf.read_text())
        for j in jobs:
            if j["name"] == "Seq01_Gym":
                j["status"] = "succeeded"
                j["task_id"] = tid
                j["video_url"] = video_url
                j["local"] = str(out)
                j.pop("error", None)
                break
        jf.write_text(json.dumps(jobs, indent=2))
        print("  jobs file updated")
        break
    if status in ("failed", "expired", "cancelled"):
        print(f"  PAYLOAD: {json.dumps(d)[:600]}")
        sys.exit(2)

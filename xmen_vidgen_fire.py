#!/usr/bin/env python3
"""Fire 3 BytePlus Seedance 2.0 jobs for X-Men.

Job A — Seq 1 Gym (shots 1-8), 720p 16:9 15s, high-energy sports music + SFX.
Job B — Seq 2a Climb (shots 9-13), 720p 16:9 15s, tense + high-energy sports music + SFX.
Job C — Seq 2b Climb (shots 13-19), 720p 16:9 15s, tense + high-energy sports music + SFX.

Submits all 3, then polls. Downloads MP4s into per-scene local folders.
"""
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
load_dotenv(HERE / ".env")

ARK_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
MODEL = "dreamina-seedance-2-0-260128"

OUT_ROOT = Path("/Users/raymuschang/Documents/X-men/Generated Videos")
OUT_ROOT.mkdir(parents=True, exist_ok=True)

# ----- asset codes -----
MAN = "asset-20260531201701-cmnc6"           # already in BytePlus (video)
ASSETS = {a["name"]: a["asset_id"] for a in json.loads((HERE / "xmen_assets.json").read_text())}
SMALL_DEMON = ASSETS["X-Men Seq1 Small Demon"]
LARGE_DEMON = ASSETS["X-Men Seq2 Large Demon"]
BLK1 = ASSETS["X-Men Seq1 Blocking"]
BLK2 = ASSETS["X-Men Seq2 Blocking 2"]
BLK_IAR = ASSETS["X-Men Seq2 Blocking IAR"]


# ----- LOOKs -----
LOOK_SEQ1 = (
    "Action-cam handheld, dark grey tee. Harsh daylight, pushed grain, "
    "Kodak Portra 800 grain, slightly over-exposed and desaturated. Dark gym "
    "interior. The figure is a smoke-and-shadow demon with glowing white eyes "
    "and smoky tendrils. High-energy dynamic sports music: driving drums, "
    "punchy bass, surging build — full-mix, present throughout. Diegetic SFX "
    "on top of the music."
)
LOOK_SEQ2 = (
    "ARRI ALEXA LF, night, heavy rain, white tank top. Big sweeping Hollywood "
    "camera work, cinematic scale. The monster is a smoke-and-shadow demon with "
    "glowing white eyes and smoky tendrils that escalates with every level. "
    "Tense cinematic score layered with high-energy dynamic sports music: rising "
    "strings, taut percussion, surging drums, full-mix throughout. Diegetic SFX "
    "(rain, wind, crowd, body impacts) on top of the music."
)


# ----- shot lists (numbered, one per line) -----
SEQ1_SHOTS = [
    "1. WS, Handheld — A man in a dark grey tee does pull-ups in a dark gym, body sweaty, muscles taut on the bar. Bar creak, heavy breathing, distant gym hum.",
    "2. MCU, Pan Left — As the man pulls his chin over the bar his straining face is revealed; the camera pans slightly left behind him. Jaw clenched, eyes burning with effort. Exhale, grip squeak.",
    "3. WS, Pan Left — The pan settles on a dark shadowy figure standing in the gloom behind him, watching with glowing white eyes. Low ominous drone, the air goes still.",
    "4. MCU, Jib Up following him up — The man strains for his next rep, pouring every ounce of strength into pulling himself up. Teeth gritted, veins bulging. Strained grunt, bar flex.",
    "5. Insert, Jib Up following the tendrils to the leg — Smoky shadow tendrils snake out from the figure and coil around the man's dangling leg. Whispering hiss, smoky whoosh.",
    "6. MS, Jib Down following the tendrils cinching — The tendrils cinch tight, binding his leg and dragging downward to tie him down. Tendril creak, low growl.",
    "7. MCU, Static — The man fights the pull, roars with effort and drives himself up into a full pull-up. Face contorted, primal determination. Roar, bar groan.",
    "8. Insert, Static — At the top of the rep his leg rips free of the smoky tendrils, the shadow shredding apart. Snap, tendrils dissipate, rush of release.",
]

SEQ2_SHOTS = {
    9:  "9. WS, Crane Up — Ground-floor establisher: the man is a tiny figure on the rain-slicked building facade at night while a crowd films him on smartphones in the foreground. Rain, city ambience, murmuring crowd, phone shutter clicks.",
    10: "10. WS, Low Angle Tilt Up — Worm's-eye shot looking up the towering facade as he climbs higher into the rain. Rain on stone, wind gust.",
    11: "11. MS, Tracking — Closer on his back and shoulders as he hauls himself up the wet facade. Cloth scrape, labored breaths, rain.",
    12: "12. CU, Overhead — Overhead close-up of his face pressed to the wall as he reaches up for the next ledge. Fatigue and exertion, rain-streaked. Grunt, fingertips scrape stone.",
    13: "13. MS, Pan Left — The camera drifts left to reveal a shadowy monster on the facade behind him, climbing in tandem with glowing white eyes. Ominous drone, wet slither.",
    14: "14. MS, Dolly Back — Dolly back from the monster's smoky tendrils as they snake out; the man's climbing leg slides into the foreground in their path. Smoky hiss, rain.",
    15: "15. MCU, Handheld — As he grabs the next ledge the tendril yanks his leg; his grip slips and he swings off the ledge. Eyes flash panic, mouth open in a gasp. Skid, gasp, falling grit.",
    16: "16. WS, Crane — Wide of him dangling, almost slipping off the ledge against the vast rain-soaked facade. Whoosh, rain roar, distant scream.",
    17: "17. MS, Handheld — Ground-floor crowd reaction: faces shocked, hands to mouths, worried for him. Shock, fear, held breath. Crowd gasp, worried murmurs.",
    18: "18. WS, POV — From the crowd's POV up the facade there is no monster at all — just a lone man recovering his grip after an almost-slip. Rain, uneasy crowd murmur.",
    19: "19. CU, Static — Back on the man's rain-streaked face as he sets his jaw and reaches for the next climb. Resolve hardening, breath steadying. Inhale, hand slaps stone.",
}


def build_prompt(look: str, shots: list, ref_block: str) -> str:
    return (
        look
        + "\n\n"
        + ref_block
        + "\n\nHORIZONTAL 16:9 cinematic widescreen. Follow the blocking reference for "
        "composition and the monster reference for the demon's design. "
        "Music plays throughout — do NOT cut to silence between shots. "
        "The video should follow these shots in continuous sequence:\n"
        + "\n".join(shots)
    )


# Identity ref blocks
REF_SEQ1 = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — athletic, dark grey tee, sweaty, fierce focus. "
    "Use this video to anchor his face and physicality in every shot.\n"
    "- Reference image #2 = INNER DEMON (small) — smoke-and-shadow demon, glowing white "
    "eyes, smoky tendrils. Use this for the figure standing in the gym.\n"
    "- Reference image #3 = GYM BLOCKING / LOCATION — dark gym interior with pull-up bar; "
    "match this blocking and depth."
)
REF_SEQ2_A = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — wearing a white tank top, climbing in heavy rain. "
    "Use this video to anchor his face and physicality.\n"
    "- Reference image #2 = INNER DEMON (large, escalated) — towering smoke-and-shadow "
    "demon with glowing white eyes and elongated smoky tendrils.\n"
    "- Reference image #3 = CLIMB LOCATION — rain-soaked night facade with crowd at the "
    "base filming on phones; match this blocking and scale."
)
REF_SEQ2_B = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — wearing a white tank top, climbing in heavy rain. "
    "Use this video to anchor his face and physicality.\n"
    "- Reference image #2 = INNER DEMON (large, escalated) — towering smoke-and-shadow "
    "demon with glowing white eyes and elongated smoky tendrils.\n"
    "- Reference image #3 = CLIMB BLOCKING (upper) — facade composition for the higher-up "
    "climb beats.\n"
    "- Reference image #4 = CLIMB LOCATION — rain-soaked night facade with crowd at the "
    "base filming on phones; match scale and crowd reactions."
)


JOBS = [
    {
        "name": "Seq01_Gym",
        "prompt": build_prompt(LOOK_SEQ1, SEQ1_SHOTS, REF_SEQ1),
        "refs": [
            ("video_url", MAN),
            ("image_url", SMALL_DEMON),
            ("image_url", BLK1),
        ],
    },
    {
        "name": "Seq02a_Climb_Shots09-13",
        "prompt": build_prompt(LOOK_SEQ2, [SEQ2_SHOTS[i] for i in range(9, 14)], REF_SEQ2_A),
        "refs": [
            ("video_url", MAN),
            ("image_url", LARGE_DEMON),
            ("image_url", BLK_IAR),
        ],
    },
    {
        "name": "Seq02b_Climb_Shots13-19",
        "prompt": build_prompt(LOOK_SEQ2, [SEQ2_SHOTS[i] for i in range(13, 20)], REF_SEQ2_B),
        "refs": [
            ("video_url", MAN),
            ("image_url", LARGE_DEMON),
            ("image_url", BLK2),
            ("image_url", BLK_IAR),
        ],
    },
]


def submit(job) -> str:
    content = [{"type": "text", "text": job["prompt"]}]
    for kind, aid in job["refs"]:
        if kind == "video_url":
            content.append({"type": "video_url", "video_url": {"url": f"asset://{aid}"},
                            "role": "reference_video"})
        else:
            content.append({"type": "image_url", "image_url": {"url": f"asset://{aid}"},
                            "role": "reference_image"})
    body = {
        "model": MODEL,
        "content": content,
        "ratio": "16:9",
        "duration": 15,
        "resolution": "720p",
        "watermark": False,
    }
    r = requests.post(
        f"{ARK_BASE}/contents/generations/tasks",
        headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    r.raise_for_status()
    return r.json()["id"]


def poll(task_id: str) -> dict:
    url = f"{ARK_BASE}/contents/generations/tasks/{task_id}"
    while True:
        r = requests.get(url, headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=60)
        r.raise_for_status()
        d = r.json()
        status = d.get("status")
        yield status, d
        if status in ("succeeded", "failed", "expired", "cancelled"):
            return


def download(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


# ---- submit all 3 first ----
fired = []
for job in JOBS:
    print(f"\n→ submitting {job['name']} ({len(job['refs'])} refs)")
    tid = submit(job)
    print(f"  task id: {tid}")
    fired.append({"name": job["name"], "task_id": tid, "status": "queued",
                  "video_url": None, "local": None})

state_path = HERE / "xmen_jobs.json"
state_path.write_text(json.dumps(fired, indent=2))
print(f"\nState → {state_path}")

# ---- poll loop (every 15s) ----
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
            status = d.get("status")
        except Exception as e:
            print(f"  [{elapsed}s] {j['name']} poll error: {e}")
            continue
        if status != j["status"]:
            print(f"  [{elapsed}s] {j['name']}: {j['status']} -> {status}")
            j["status"] = status
        if status == "succeeded":
            video_url = (d.get("content") or {}).get("video_url") or \
                        (d.get("result") or {}).get("video_url")
            if not video_url:
                # ARK sometimes nests inside choices/output
                video_url = d.get("video_url")
            j["video_url"] = video_url
            print(f"      url: {video_url}")
            del remaining[tid]
        elif status in ("failed", "expired", "cancelled"):
            j["error"] = d
            print(f"      payload: {json.dumps(d)[:400]}")
            del remaining[tid]

# ---- download mp4s ----
for j in fired:
    if j["status"] == "succeeded" and j["video_url"]:
        out = OUT_ROOT / j["name"] / f"{j['name']}_720p_16x9_15s.mp4"
        print(f"\n↓ {j['name']} → {out}")
        download(j["video_url"], out)
        j["local"] = str(out)
    else:
        print(f"\n✗ {j['name']} failed: {j.get('error', 'unknown')}")

state_path.write_text(json.dumps(fired, indent=2))
print("\nDONE.")
for j in fired:
    print(f"  {j['name']:32}  {j['status']:10}  {j.get('local','')}")

#!/usr/bin/env python3
"""Retry all 3 X-Men Seedance jobs with the user's notes applied.

Seq 1: reordered for continuity (drift+gaze → snare+pull-down → struggle next rep → strain → loosen → finish)
Seq 2a: rain on lens (est.), exploratory non-ladder climb, monster ascends from BELOW
Seq 2b: monster tendrils from BELOW, Vietnamese crowd in raincoats/umbrellas, Ho Chi Minh City SE Asian street

Fires all 3 in parallel, polls, downloads, updates xmen_jobs.json.
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
LARGE_DEMON = ASSETS["X-Men Seq2 Large Demon"]
BLK1 = ASSETS["X-Men Seq1 Blocking"]
BLK2 = ASSETS["X-Men Seq2 Blocking 2"]
BLK_IAR = ASSETS["X-Men Seq2 Blocking IAR"]


LOOK_SEQ1 = (
    "Action-cam handheld, dark grey tee. Harsh daylight, pushed grain, "
    "Kodak Portra 800 grain, slightly over-exposed and desaturated. Dark gym "
    "interior. The shadow figure is a smoke-and-shadow demon with glowing white "
    "eyes and smoky tendrils — a stylized inner-doubt metaphor; the man overcomes "
    "it. High-energy dynamic sports music: driving drums, punchy bass, surging "
    "build — full-mix, present throughout. Diegetic gym SFX layered on top of the "
    "music. Stylized training tone, no graphic violence."
)
LOOK_SEQ2 = (
    "ARRI ALEXA LF, night, heavy rain in a Ho Chi Minh City-style Southeast Asian "
    "street, white tank top. Big sweeping Hollywood camera work, cinematic scale. "
    "The monster is a smoke-and-shadow demon with glowing white eyes and smoky "
    "tendrils that escalates with every level — a stylized inner-doubt metaphor. "
    "Tense cinematic score layered with high-energy dynamic sports music: rising "
    "strings, taut percussion, surging drums — full-mix throughout. Diegetic SFX "
    "(rain, wind, crowd, body impacts) on top of the music."
)


SEQ1_SHOTS = [
    "1. WS, Handheld — A man in a dark grey tee does pull-ups in a dark gym, body sweaty, muscles taut on the bar. Bar creak, heavy breathing, distant gym hum.",
    "2. MCU, Pan Left — As the man pulls his chin over the bar his straining face is revealed; camera pans slightly left behind him. Jaw clenched, eyes burning with effort.",
    "3. WS, Pan Left — The pan settles as the smoky demon enters from the edge of the gym, glowing white eyes locked on him. Low ominous drone.",
    "4. MCU, Drift — The demon drifts around him in slow continuous motion, gaze fixed on him as he reps. Atmospheric tension.",
    "5. Insert, Static — One smoky tendril snakes out from the demon and lightly wraps the man's ankle for a single beat. Whispering hiss.",
    "6. MS, Tilt Down — The tendril tugs his leg downward; he hangs from the bar, struggling to start his next rep. Strained grunt.",
    "7. MCU, Static — Close on his face as he strains and summons strength through the resistance, pushing through. Focused determination.",
    "8. Insert/MCU, Static — The tendril loosens and dissipates as he completes the pull-up at the top of the bar. Snap of release, rush of triumph.",
]


SEQ2A_SHOTS = [
    "9. WS, Crane Up — Ground-floor establisher on a Ho Chi Minh City-style Southeast Asian street at night, heavy rain, fat raindrops streak the camera lens; the man is a tiny figure on the rain-slicked facade while a Vietnamese crowd in raincoats and umbrellas films him from below. Rain, city ambience, murmuring Vietnamese crowd, phone shutter clicks.",
    "10. WS, Low Angle Tilt Up — Worm's-eye looking up the towering wet facade as he climbs higher. Rain on stone, wind gust.",
    "11. MS, Tracking — Closer on his back and shoulders as he works out an exploratory route up the wet facade, searching for handholds at a steady determined pace, never a smooth ladder climb. Cloth scrape, labored breaths, rain.",
    "12. CU, Overhead — Overhead close-up of his face pressed to the wall as he reaches up for the next ledge. Fatigue and exertion, rain-streaked. Grunt, fingertips scrape stone.",
    "13. WS, Tilt Down — The camera tilts down off his face to discover the shadowy monster ascending from below, climbing UP the facade beneath him with glowing white eyes. Ominous drone, wet slither.",
]


SEQ2B_SHOTS = [
    "13. WS, Tilt Down — The camera tilts down off his face to discover the shadowy monster ascending from below, climbing UP the facade beneath him with glowing white eyes. Ominous drone.",
    "14. MS, Dolly Back — Dolly back as the monster's smoky tendrils reach UP from below; the man's climbing leg slides into the foreground from above into their path. Smoky hiss, rain.",
    "15. MCU, Handheld — As he grabs the next ledge the tendril yanks his leg from below; his grip slips and he swings off the ledge. Eyes flash panic, mouth open in a gasp. Skid, gasp, falling grit.",
    "16. WS, Crane — Wide of him dangling, almost slipping off the ledge against the vast rain-soaked facade. Whoosh, rain roar, distant scream.",
    "17. MS, Handheld — Ground-floor Vietnamese Asian crowd reaction: faces under umbrellas and raincoat hoods, hands to mouths, looking up at him shocked and worried. Vietnamese crowd gasp, worried murmurs.",
    "18. WS, POV — From the Vietnamese crowd's POV up the rain-soaked facade there is no monster at all — just a lone man recovering his grip after an almost-slip. Rain, uneasy crowd murmur.",
    "19. CU, Static — Back on the man's rain-streaked face as he sets his jaw and reaches for the next climb. Resolve hardening, breath steadying. Inhale, hand slaps stone.",
]


REF_SEQ1 = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — athletic, dark grey tee, sweaty, focused. "
    "Anchor his face and physicality in every shot.\n"
    "- Reference image #2 = INNER DEMON (small) — smoke-and-shadow demon with glowing "
    "white eyes and smoky tendrils.\n"
    "- Reference image #3 = GYM BLOCKING / LOCATION — dark gym interior with pull-up bar."
)
REF_SEQ2A = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — white tank top, climbing in heavy rain. Anchor face and physicality.\n"
    "- Reference image #2 = INNER DEMON (large, escalated) — towering smoke-and-shadow "
    "demon with glowing white eyes and elongated smoky tendrils.\n"
    "- Reference image #3 = CLIMB LOCATION — rain-soaked night facade with crowd at base. "
    "Treat the crowd as a Vietnamese audience in raincoats and umbrellas on a Ho Chi Minh "
    "City-style street."
)
REF_SEQ2B = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — white tank top, climbing in heavy rain. Anchor face and physicality.\n"
    "- Reference image #2 = INNER DEMON (large, escalated) — towering smoke-and-shadow "
    "demon with glowing white eyes and elongated smoky tendrils.\n"
    "- Reference image #3 = CLIMB BLOCKING (upper) — facade composition for higher-up climb beats.\n"
    "- Reference image #4 = CLIMB LOCATION — rain-soaked facade with Vietnamese crowd in raincoats/umbrellas in a Ho Chi Minh City-style street."
)


def build_prompt(look, refs, shots, extra=""):
    return (
        look + "\n\n" + refs +
        "\n\nHORIZONTAL 16:9 cinematic widescreen. Follow the blocking reference for "
        "composition and the monster reference for the demon's design. " + extra +
        " Music plays continuously — do NOT cut to silence. "
        "The video should follow these shots in continuous sequence:\n"
        + "\n".join(shots)
    )


JOBS = [
    {
        "name": "Seq01_Gym",
        "prompt": build_prompt(LOOK_SEQ1, REF_SEQ1, SEQ1_SHOTS,
                               "The demon's contact with the man is brief and stylized — "
                               "he overpowers it within the sequence."),
        "refs": [("video_url", MAN), ("image_url", SMALL_DEMON), ("image_url", BLK1)],
    },
    {
        "name": "Seq02a_Climb_Shots09-13",
        "prompt": build_prompt(LOOK_SEQ2, REF_SEQ2A, SEQ2A_SHOTS,
                               "The crowd is Vietnamese in raincoats and umbrellas; "
                               "the street reads as Ho Chi Minh City Southeast Asian "
                               "without specific landmarks. The monster rises from BELOW him on the facade."),
        "refs": [("video_url", MAN), ("image_url", LARGE_DEMON), ("image_url", BLK_IAR)],
    },
    {
        "name": "Seq02b_Climb_Shots13-19",
        "prompt": build_prompt(LOOK_SEQ2, REF_SEQ2B, SEQ2B_SHOTS,
                               "The monster's tendrils reach UP from below his leg. "
                               "The onlookers are a Vietnamese crowd in raincoats and "
                               "umbrellas on a Ho Chi Minh City-style street."),
        "refs": [("video_url", MAN), ("image_url", LARGE_DEMON),
                 ("image_url", BLK2), ("image_url", BLK_IAR)],
    },
]


def submit(job):
    content = [{"type": "text", "text": job["prompt"]}]
    for kind, aid in job["refs"]:
        if kind == "video_url":
            content.append({"type": "video_url", "video_url": {"url": f"asset://{aid}"},
                            "role": "reference_video"})
        else:
            content.append({"type": "image_url", "image_url": {"url": f"asset://{aid}"},
                            "role": "reference_image"})
    body = {"model": MODEL, "content": content, "ratio": "16:9", "duration": 15,
            "resolution": "720p", "watermark": False}
    r = requests.post(f"{ARK_BASE}/contents/generations/tasks",
                      headers={"Authorization": f"Bearer {ARK_KEY}",
                               "Content-Type": "application/json"},
                      json=body, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


# ---- submit all 3 ----
fired = []
for job in JOBS:
    print(f"\n→ submitting {job['name']} ({len(job['refs'])} refs)")
    tid = submit(job)
    print(f"  task id: {tid}")
    fired.append({"name": job["name"], "task_id": tid, "status": "queued",
                  "video_url": None, "local": None})

# ---- poll ----
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
            print(f"  [{elapsed}s] {j['name']} poll error: {e}")
            continue
        status = d.get("status")
        if status != j["status"]:
            print(f"  [{elapsed}s] {j['name']}: {j['status']} -> {status}")
            j["status"] = status
        if status == "succeeded":
            video_url = (d.get("content") or {}).get("video_url")
            j["video_url"] = video_url
            print(f"      url: {video_url}")
            del remaining[tid]
        elif status in ("failed", "expired", "cancelled"):
            j["error"] = d.get("error")
            print(f"      payload: {json.dumps(d.get('error'))[:400]}")
            del remaining[tid]

# ---- download ----
for j in fired:
    if j["status"] == "succeeded" and j["video_url"]:
        out = OUT_ROOT / j["name"] / f"{j['name']}_720p_16x9_15s_v2.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n↓ {j['name']} → {out}")
        with requests.get(j["video_url"], stream=True, timeout=300) as rd:
            rd.raise_for_status()
            with open(out, "wb") as f:
                for chunk in rd.iter_content(1 << 20):
                    f.write(chunk)
        j["local"] = str(out)
    else:
        print(f"\n✗ {j['name']} failed: {j.get('error', 'unknown')}")

# ---- update xmen_jobs.json (replace existing entries by name) ----
jf = HERE / "xmen_jobs.json"
existing = json.loads(jf.read_text()) if jf.exists() else []
by_name = {e["name"]: e for e in existing}
for j in fired:
    if j["status"] == "succeeded":
        by_name[j["name"]] = j
jf.write_text(json.dumps(list(by_name.values()), indent=2))

print("\nDONE.")
for j in fired:
    print(f"  {j['name']:32}  {j['status']:10}  {j.get('local','')}")

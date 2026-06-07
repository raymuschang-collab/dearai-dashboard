#!/usr/bin/env python3
"""X-Men v3: 3 sequences × 2 iterations = 6 Seedance jobs.

v3 directions applied:
  Seq 1: tendrils start UNBOUND, slither in and visibly WRAP+BIND ankles;
         he struggles; demon RISES SLOWLY into frame behind him; he strains
         and succeeds.
  Seq 2a: monster FLIES into frame from off-screen below the man
          (NOT emerging from ground / appearing in place).
  Seq 2b: camera PANS UP from monster on lower facade to man climbing above
          with feet PLANTED ON THE WALL (never dangling); monster's
          tendrils reach up and VISIBLY WRAP his legs; Vietnamese crowd
          looks UP with necks craned; POV shot looks UP.

All 720p / 16:9 / 15s, music + SFX baked into prompt.
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
OUT_ROOT = Path("/Users/raymuschang/Documents/X-men/Generated Videos")

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
    "build — full-mix, present throughout. Diegetic gym SFX layered on top. "
    "Stylized training tone, no graphic violence."
)
LOOK_SEQ2 = (
    "ARRI ALEXA LF, night, heavy rain on a Ho Chi Minh City-style Southeast Asian "
    "street, white tank top. Big sweeping Hollywood camera work, cinematic scale. "
    "The monster is a smoke-and-shadow demon with glowing white eyes and smoky "
    "tendrils — a stylized inner-doubt metaphor that escalates with every level. "
    "Tense cinematic score layered with high-energy dynamic sports music: rising "
    "strings, taut percussion, surging drums — full-mix throughout. Diegetic SFX "
    "(rain, wind, Vietnamese crowd, body impacts) on top of the music."
)

# ---------- SEQ 1 v3: visible wrap+bind, then demon rises slowly behind ----------
SEQ1_SHOTS = [
    "1. WS, Handheld — A man in a dark grey tee does pull-ups in a dark gym, body sweaty, muscles taut on the bar. Bar creak, heavy breathing.",
    "2. MCU, Pan Left — As he pulls his chin over the bar his straining face is revealed; camera pans slightly left behind him. Jaw clenched.",
    "3. Insert, Static — From below the bar, smoky tendrils slither IN and VISIBLY WRAP around his ankles, binding them. The shot must BEGIN with his ankles UNBOUND and END with the tendrils coiled tight. Whispering hiss.",
    "4. MS, Static — He hangs from the bar, his bound ankles tugged downward; he struggles to start his next rep. Strained grunt.",
    "5. WS, Slow Tilt Up — BEHIND him, the smoky demon rises SLOWLY into frame from a low position, glowing white eyes locked on him. The demon was NOT in frame before — it materialises slowly. Low ominous drone.",
    "6. MCU, Static — Close on his face as he strains and summons strength through the resistance. Focused effort.",
    "7. MS, Static — He begins to pull himself up against the binding, muscles locked, willpower fighting through. Bar groan.",
    "8. Insert, Static — He completes the pull-up at the top of the bar; the smoky tendrils loosen and dissipate from his ankles. Snap, rush of triumph.",
]

# ---------- SEQ 2a v3: monster FLIES into frame from off-screen below ----------
SEQ2A_SHOTS = [
    "9. WS, Crane Up — Ground-floor establisher on a Ho Chi Minh City-style Southeast Asian street at night, heavy rain, fat raindrops streak the camera lens; the man is a tiny figure on the rain-slicked facade while a Vietnamese crowd in raincoats and umbrellas, necks craned UPWARD, films him from below. Rain, Vietnamese crowd murmur, phone clicks.",
    "10. WS, Low Angle Tilt Up — Worm's-eye looking UP the towering wet facade as he climbs higher. Rain on stone.",
    "11. MS, Tracking — Closer on his back and shoulders as he works out an EXPLORATORY ROUTE up the wet facade, searching for handholds at a steady determined pace; methodical, NEVER a smooth ladder climb. Cloth scrape, labored breaths, rain.",
    "12. CU, Overhead — Overhead close-up of his face pressed to the wall as he reaches up for the next ledge. Fatigue and exertion, rain-streaked.",
    "13. MS, Static — The shadowy monster FLIES INTO frame from off-screen BELOW the man, materialising mid-air against the rain-slicked facade beneath him with glowing white eyes. The monster MUST enter the frame mid-shot — it is NOT in frame at the start, NOT emerging from the ground, NOT appearing in place. Ominous drone, wet slither.",
]

# ---------- SEQ 2b v3: pan UP reveal (feet on wall), tendrils VISIBLY WRAP, crowd looks UP ----------
SEQ2B_SHOTS = [
    "13. MS, Slow Tilt/Pan UP — The camera tilts and pans UP the wet facade from the lower section, where the shadowy monster lurks at the lower part of the building with glowing white eyes, RISING up the facade to reveal the man climbing above with his FEET FIRMLY PLANTED ON THE WALL (never dangling in mid-air). Ominous drone.",
    "14. MS, Dolly Back — The monster's smoky tendrils reach UP from below and VISIBLY WRAP and coil around the man's climbing legs. The shot BEGINS with the legs free and ENDS with the tendrils coiled tight. His feet remain in contact with the wall. Smoky hiss, rain.",
    "15. MCU, Handheld — As he grabs the next ledge the tendril yanks his leg from below; his grip slips and he swings off the ledge. Eyes flash panic. Skid, gasp.",
    "16. WS, Crane — Wide of him dangling, almost slipping off the ledge against the vast rain-soaked facade. Whoosh, rain roar.",
    "17. MS, Handheld — Ground-floor Vietnamese Asian crowd reaction: faces under umbrellas and raincoat hoods, NECKS CRANED UPWARD, looking straight UP the facade — hands to mouths, shocked and worried. They are NOT looking at eye level. Vietnamese crowd gasp.",
    "18. WS, POV — From the Vietnamese crowd's POV looking UP at the rain-soaked facade — necks craned upward — there is no monster, just a lone man recovering his grip after an almost-slip; his feet planted on the wall. Rain, uneasy crowd murmur.",
    "19. CU, Static — Back on the man's rain-streaked face as he sets his jaw and reaches for the next climb. Resolve hardening. Inhale, hand slaps stone.",
]

REF_SEQ1 = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — athletic, dark grey tee, sweaty, focused. Anchor face and physicality.\n"
    "- Reference image #2 = INNER DEMON (small) — smoke-and-shadow demon, glowing white eyes, smoky tendrils.\n"
    "- Reference image #3 = GYM BLOCKING — dark gym interior with pull-up bar."
)
REF_SEQ2A = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — white tank top, climbing in heavy rain. Anchor face and physicality.\n"
    "- Reference image #2 = INNER DEMON (large) — towering smoke-and-shadow demon, glowing white eyes, smoky tendrils.\n"
    "- Reference image #3 = CLIMB LOCATION — rain-soaked night facade in a Vietnamese Ho Chi Minh City-style street with a crowd at the base."
)
REF_SEQ2B = (
    "Reference identities:\n"
    "- Reference video #1 = THE MAN — white tank top, climbing in heavy rain. Anchor face and physicality.\n"
    "- Reference image #2 = INNER DEMON (large) — towering smoke-and-shadow demon, glowing white eyes, smoky tendrils.\n"
    "- Reference image #3 = CLIMB BLOCKING (upper) — facade composition for higher-up climb beats.\n"
    "- Reference image #4 = CLIMB LOCATION — rain-soaked facade with Vietnamese crowd in raincoats/umbrellas in a Ho Chi Minh City-style street."
)


def build(look, refs, shots, extra=""):
    return (
        look + "\n\n" + refs +
        "\n\nHORIZONTAL 16:9 cinematic widescreen. Follow the blocking reference for "
        "composition and the monster reference for the demon's design. " + extra +
        " Music plays continuously — do NOT cut to silence. "
        "The video should follow these shots in continuous sequence:\n"
        + "\n".join(shots)
    )


SEQS = [
    {
        "name": "Seq01_Gym",
        "prompt": build(LOOK_SEQ1, REF_SEQ1, SEQ1_SHOTS,
                        "Key continuity: the tendrils begin OFF him and wrap his ankles "
                        "on-screen; the demon BEHIND him rises slowly into frame from a "
                        "low offscreen position. He overpowers it by the end."),
        "refs": [("video_url", MAN), ("image_url", SMALL_DEMON), ("image_url", BLK1)],
    },
    {
        "name": "Seq02a_Climb_Shots09-13",
        "prompt": build(LOOK_SEQ2, REF_SEQ2A, SEQ2A_SHOTS,
                        "Key continuity: the monster FLIES INTO frame from off-screen "
                        "BELOW the man — not from the ground, not in place. The crowd "
                        "is Vietnamese in raincoats/umbrellas looking UP."),
        "refs": [("video_url", MAN), ("image_url", LARGE_DEMON), ("image_url", BLK_IAR)],
    },
    {
        "name": "Seq02b_Climb_Shots13-19",
        "prompt": build(LOOK_SEQ2, REF_SEQ2B, SEQ2B_SHOTS,
                        "Key continuity: camera PANS UP from the monster at the lower "
                        "facade to the man above — his feet stay on the wall throughout. "
                        "The tendrils VISIBLY WRAP his legs. The Vietnamese crowd looks "
                        "straight UP with necks craned, not at eye level."),
        "refs": [("video_url", MAN), ("image_url", LARGE_DEMON),
                 ("image_url", BLK2), ("image_url", BLK_IAR)],
    },
]


def submit(prompt, refs):
    content = [{"type": "text", "text": prompt}]
    for kind, aid in refs:
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


# ---- submit 3 seqs × 2 iters = 6 ----
fired = []
for seq in SEQS:
    for it in (1, 2):
        print(f"\n→ submitting {seq['name']} iter {it} ({len(seq['refs'])} refs)")
        tid = submit(seq["prompt"], seq["refs"])
        print(f"  task id: {tid}")
        fired.append({"name": seq["name"], "iter": it, "task_id": tid,
                      "status": "queued", "video_url": None, "local": None})

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
            print(f"  [{elapsed}s] {j['name']} iter{j['iter']} poll error: {e}")
            continue
        status = d.get("status")
        if status != j["status"]:
            print(f"  [{elapsed}s] {j['name']} iter{j['iter']}: {j['status']} -> {status}")
            j["status"] = status
        if status == "succeeded":
            j["video_url"] = (d.get("content") or {}).get("video_url")
            print(f"      url: {j['video_url']}")
            del remaining[tid]
        elif status in ("failed", "expired", "cancelled"):
            j["error"] = d.get("error")
            print(f"      payload: {json.dumps(d.get('error'))[:300]}")
            del remaining[tid]

# ---- download ----
for j in fired:
    if j["status"] == "succeeded" and j["video_url"]:
        out = OUT_ROOT / j["name"] / f"{j['name']}_720p_16x9_15s_v3_iter{j['iter']}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"\n↓ {j['name']} iter{j['iter']} → {out}")
        with requests.get(j["video_url"], stream=True, timeout=300) as rd:
            rd.raise_for_status()
            with open(out, "wb") as f:
                for chunk in rd.iter_content(1 << 20):
                    f.write(chunk)
        j["local"] = str(out)
    else:
        print(f"\n✗ {j['name']} iter{j['iter']} failed: {j.get('error')}")

print("\nDONE.")
for j in fired:
    print(f"  {j['name']:32}  iter{j['iter']}  {j['status']:10}  {j.get('local','')}")

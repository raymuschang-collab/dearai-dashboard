#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 08 REPLAY2 v2 (NO BEARD FIX).
720p · 16:9 · 5s · Fires V1 + V2 in parallel.

FIXES vs the original replay2 fire:
- Removed every "beard" / "scholar's cap" text descriptor for MINISTER (caused
  model to render bearded minister even though source ref is clean-shaven).
- Added canonical MINISTER source video as 2nd video ref so model has fresh
  identity input alongside the keyframe (which is from a prior bearded gen).
- Bumped to 720p from 480p.
- Duration dropped from 15s → 5s to roughly match the vertical strip's 3.08s
  (5s is Seedance's minimum; smaller values rejected).

Refs (2 videos + 2 images + 1 audio):
  - image: SHOT8 MINISTER 12s KEYFRAME (scene anchor — composition + framing)
  - image: PALACE COLLAGE (location anchor — palette + lighting)
  - video: SHOT7 MINISTER VERTICAL STRIP 3s (acting + lip-sync driver)
  - video: MINISTER 4.4s (canonical identity — clean-shaven baseline)
  - audio: SHOT7 DIALOGUE (voice + content)
"""
import json, os, re, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]

OUT_DIR = Path("/Users/raymuschang/Documents/Channel 8 Underwater — Landed Outputs")
OUT_DIR.mkdir(exist_ok=True)

KEYFRAME_REF      = "asset://asset-20260518110610-rqh9m"   # 12s keyframe (composition)
COLLAGE_REF       = "asset://asset-20260518092632-np5gm"   # PALACE COLLAGE (location)
VERT_STRIP_REF    = "asset://asset-20260518110621-lsxn4"   # vertical strip (acting + lip-sync)
MINISTER_REF      = "asset://asset-20260517201250-rhxdq"   # canonical MINISTER 4.4s (identity)
SHOT7_AUDIO_REF   = "asset://asset-20260518102541-4tjvf"   # SHOT7 DIALOGUE mp3


GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
"""

REF_GUIDE = """Reference inputs:
- Reference image #1 (SCENE ANCHOR — composition + framing) = a keyframe from a prior take of this very scene. Use it for camera angle, blocking, character placement, costumes, set dressing, light direction, and palette. Match its composition 80–100%.
- Reference image #2 (LOCATION ANCHOR) = the underwater palace collage. Locks the throne hall geometry, columns with coral and kelp, motionless footsoldiers in armor along the perimeter, refracting underwater light, bubble density.
- Reference video #3 (ACTING + DIALOGUE DRIVER) = a vertical strip of the live minister speaking. Drives the MINISTER's:
  * Performance — head turns, hand gestures, body language, micro-expressions
  * Dialogue lip-sync — frame-for-frame mouth movements
  * Timing — every beat hits at the same timestamp
- Reference video #4 (MINISTER CANONICAL IDENTITY) = the authoritative MINISTER character reference. The minister's face, complexion, hairline, and overall appearance in the final shot must come from THIS reference. Do not introduce facial hair, beards, or features not present in this canonical reference. Wardrobe (hanfu robes, court attire) is also taken from this reference.
- Reference audio #5 = SHOT 07 dialogue mp3. Reinforces voice timbre, cadence, and dialogue content.
"""

SHOT_PROMPT = """Shot 08 — minister giving a formal court greeting in the underwater palace.

The composition and visual setting come from the SCENE ANCHOR image: the MINISTER stands at center-frame mid-greeting, the EMPEROR is seated on the throne in foreground silhouette, PRINCESS and ELDER are kneeling alongside, motionless footsoldiers in armor stand behind. The underwater palette (refracting light, wave caustics on faces and clothing, bubbles drifting, hanfu robes catching the current) is locked.

The MINISTER's identity — face, complexion, hairline — comes from the canonical MINISTER reference video (#4). Render him faithfully to that reference. Do not add facial hair.

The MINISTER's performance — gestures (cupped fists greeting, slight bow, head raised to speak), lip-sync, dialogue timing — comes from the vertical strip live performance reference (#3). Bind that performance to the minister character.

The audio reinforces the dialogue content and voice timbre.

Environmental directives:
- Wave caustics rippling across the minister's face and the emperor's silhouette
- Slow bubble streams drifting up through the frame
- Hanfu robes catching the underwater current (slow billowing motion)
- Motionless footsoldiers in armor behind the subjects (no movement, facing forward)
- Muffled underwater pressure rumble + bubble SFX under the spoken dialogue
- All four characters (emperor, minister, princess, elder) visible per the scene anchor framing"""


def submit(content_block):
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content_block,
        "ratio": "16:9",
        "duration": 5,
        "resolution": "720p",
        "watermark": False,
    }
    r = requests.post(
        f"{ARK_BASE}/contents/generations/tasks",
        headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"submit failed: {r.status_code} {r.text[:500]}")
    return r.json().get("id") or r.json().get("task_id")


def extract_url(resp):
    c = resp.get("content", {})
    if isinstance(c, dict):
        v = c.get("video_url")
        if isinstance(v, str): return v
        if isinstance(v, dict): return v.get("url")
    m = re.search(r'https://[^\s"\']*\.mp4[^\s"\']*', json.dumps(resp))
    return m.group(0) if m else ""


def fire_one(version: int, content):
    print(f"\n  ◦ V{version} submitting...")
    tid = submit(content)
    print(f"    ✓ V{version} task_id: {tid}")
    start = time.time(); last = None
    while True:
        r = requests.get(f"{ARK_BASE}/contents/generations/tasks/{tid}",
                          headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=30)
        resp = r.json(); status = resp.get("status")
        if status != last:
            print(f"    [V{version} {int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status in ("succeeded", "completed", "success"):
            break
        if status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"V{version} failure: {json.dumps(resp)[:500]}")
        time.sleep(20)
    video_url = extract_url(resp)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / f"shot_08_minister_NOBEARD_v{version}_720p_5s.mp4"
    out_path.write_bytes(data)
    print(f"    ✓ V{version} saved: {out_path.name}")
    return out_path


def main():
    t0 = time.time()

    refs = [
        ("image", KEYFRAME_REF,    "12s KEYFRAME (composition anchor)"),
        ("image", COLLAGE_REF,     "PALACE COLLAGE (location anchor)"),
        ("video", VERT_STRIP_REF,  "SHOT7 VERTICAL STRIP 3s (acting + dialogue driver)"),
        ("video", MINISTER_REF,    "MINISTER canonical 4.4s (identity — clean-shaven)"),
        ("audio", SHOT7_AUDIO_REF, "SHOT7 DIALOGUE"),
    ]

    prompt = GLOBALS + "\n" + REF_GUIDE + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  2 videos (7.48s) + 2 images + 1 audio ✓")
    for kind, url, label in refs:
        print(f"  {kind:<6} → {url}  ({label})")

    content = [{"type": "text", "text": prompt}]
    for kind, url, _ in refs:
        if kind == "video":
            content.append({"type": "video_url", "video_url": {"url": url}, "role": "reference_video"})
        elif kind == "image":
            content.append({"type": "image_url", "image_url": {"url": url}, "role": "reference_image"})
        elif kind == "audio":
            content.append({"type": "audio_url", "audio_url": {"url": url}, "role": "reference_audio"})

    print(f"\n=== Firing V1 + V2 in parallel (720p · 5s · 16:9 · NO BEARD) ===")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(fire_one, v, content) for v in (1, 2)]
        for f in futs:
            try: f.result()
            except Exception as e: print(f"  ✗ {e}")

    print(f"\n=== ALL DONE  ·  wall: {time.time()-t0:.1f}s ===")


if __name__ == "__main__":
    main()

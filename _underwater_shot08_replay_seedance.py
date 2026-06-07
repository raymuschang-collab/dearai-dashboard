#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 08 REPLAY: live-plate-driven reskin.
15s · 480p · 16:9. Fires V1 + V2 in parallel.

Approach: use the live-action plate as a video reference to drive acting,
dialogue lip-sync, timing, and duration. The first-frame of v5 anchors
the underwater visual style.

Refs (1 image + 1 video + 1 audio):
  - image: SHOT8 V5 FIRSTFRAME — scene/style anchor (underwater palace, characters in costume)
  - video: SHOT8 LIVE PLATE 5.6s — drives acting performance, blocking, gestures, dialogue timing
  - audio: SHOT8 DIALOGUE — reinforces lip-sync content
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

OUT_DIR = Path("/Users/raymuschang/Desktop/Channel 8 Underwater — Landed Outputs")
OUT_DIR.mkdir(exist_ok=True)

# Refs
FIRSTFRAME_REF = "asset://asset-20260518110031-m6hg6"   # SHOT8 V5 firstframe (scene anchor)
LIVE_PLATE_REF = "asset://asset-20260518110044-t78gk"   # shot 08.mp4 live action plate
SHOT8_AUDIO    = "asset://asset-20260518092222-2b9td"   # SHOT8 DIALOGUE mp3


GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
"""

REF_GUIDE = """Reference inputs:
- Reference image #1 (scene/style anchor) = the FIRST FRAME of the target shot in the underwater palace. Use it to lock the visual style, location, costumes, lighting, color palette, and character identities. The throne, columns, kelp/coral, soldiers in armor, refracting underwater light, and character placement seen in this still must all be preserved in the generated video.
- Reference video #2 (performance/timing driver) = the LIVE-ACTION PLATE of this scene. Use this video to drive:
  * Acting performance — gestures, head turns, body language, expressions
  * Dialogue lip-sync — match every mouth movement frame-for-frame to the speaker in this video
  * Timing and pacing — every beat in the generated video should hit at the same timestamp as the live plate
  * Duration — the action in the generated video should mirror the duration of the live plate's action (~5.6s of plate content, with bubbles/SFX continuing in the remaining time)
  * Camera framing and movement — match the live plate's framing
- Reference audio #3 (dialogue) = SHOT8 dialogue mp3. Reinforces the lip-sync content and provides the voice timbre/cadence for the spoken line.
"""

SHOT_PROMPT = """Shot 08 REPLAY — reskin the live-action plate into the underwater palace setting.

The composition, acting, dialogue, blocking, and timing of every character in the generated video must match the live-action reference video frame-for-frame. The visual style — underwater palace, hanfu costumes, lit by refracting water caustics, with bubbles drifting through the frame and motionless footsoldiers in armor standing behind the principal subjects — comes from the first-frame scene reference image.

Translate the live plate into this underwater setting:
- Every actor's performance (gestures, head movements, expressions, dialogue) must reproduce exactly what the live plate shows
- Every actor's wardrobe transforms from contemporary clothing into the hanfu robes shown in the scene reference (emperor in imperial gold/dark hanfu, princess in court hanfu, elder in white-bearded scholar's robes, minister in red and gold court robes)
- The flat-lit indoor location of the live plate transforms into the underwater throne hall — ambient refracting light, wave caustics rippling across all surfaces and faces, columns wrapped in coral and kelp, schools of fish drifting in the background, bubble streams drifting up through frame
- Motionless footsoldiers in armor stand behind the principal subjects throughout
- The dialogue (lip-synced to the audio reference) carries in muffled underwater fashion with bubble streams and pressure rumble underneath

Camera, framing, blocking, performance, dialogue, and timing all driven by the live plate. Setting, costumes, lighting, color palette, and SFX driven by the underwater scene reference."""


def submit(content_block):
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content_block,
        "ratio": "16:9",
        "duration": 15,
        "resolution": "480p",
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
    out_path = OUT_DIR / f"shot_08_replay_v{version}_480p_15s.mp4"
    out_path.write_bytes(data)
    print(f"    ✓ V{version} saved: {out_path.name}")
    return out_path


def main():
    t0 = time.time()

    refs = [
        ("image", FIRSTFRAME_REF, "SHOT8 V5 FIRSTFRAME (scene anchor)"),
        ("video", LIVE_PLATE_REF, "LIVE PLATE 5.6s (acting + timing driver)"),
        ("audio", SHOT8_AUDIO,    "SHOT8 DIALOGUE"),
    ]

    prompt = GLOBALS + "\n" + REF_GUIDE + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  1 video (5.6s) + 1 image + 1 audio ✓")
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

    print(f"\n=== Firing V1 + V2 in parallel (480p · 15s) ===")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(fire_one, v, content) for v in (1, 2)]
        for f in futs:
            try: f.result()
            except Exception as e: print(f"  ✗ {e}")

    print(f"\n=== ALL DONE  ·  wall: {time.time()-t0:.1f}s ===")


if __name__ == "__main__":
    main()

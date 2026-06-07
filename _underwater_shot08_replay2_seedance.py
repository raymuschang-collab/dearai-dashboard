#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 08 REPLAY2: 12s-keyframe-driven minister greeting.
15s · 480p · 16:9. Fires V1 + V2 in parallel.

Approach: lock the scene composition from the 12s keyframe (mid-greeting moment
from the previous fire), then drive the minister's acting + dialogue lip-sync
from the shot 07 vertical strip (live performance reference).

Refs (1 video + 2 images + 1 audio):
  - image: SHOT8 MINISTER 12s KEYFRAME (NEW scene anchor — locks composition + character identities + costumes)
  - image: UNDERWATER PALACE COLLAGE (location anchor — lighting + palette + setting)
  - video: SHOT7 MINISTER VERTICAL STRIP 3s (drives minister's acting, gesture, lip-sync, dialogue timing)
  - audio: SHOT7 DIALOGUE (reinforces voice timbre + dialogue content)
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

KEYFRAME_REF      = "asset://asset-20260518110610-rqh9m"   # 12s keyframe (scene + identity anchor)
COLLAGE_REF       = "asset://asset-20260518092632-np5gm"   # PALACE COLLAGE (location)
VERT_STRIP_REF    = "asset://asset-20260518110621-lsxn4"   # vertical strip (acting + dialogue driver)
SHOT7_AUDIO_REF   = "asset://asset-20260518102541-4tjvf"   # SHOT7 DIALOGUE mp3


GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
"""

REF_GUIDE = """Reference inputs:
- Reference image #1 (SCENE ANCHOR) = a keyframe extracted at the 12s mark from a prior fire of this very scene. Lock the composition, framing, character placement, costumes, and character identities (EMPEROR seated on the throne, MINISTER giving the formal greeting in red and gold hanfu with scholar's cap, ELDER kneeling/standing alongside in white-bearded scholar robes, PRINCESS in court hanfu — all visible in this still). Match this still 80–100%.
- Reference image #2 (LOCATION ANCHOR) = the underwater palace collage. Locks the broader location language — throne hall geometry, columns with coral and kelp, motionless footsoldiers in armor along the perimeter, refracting underwater light, color palette, bubble density, depth-of-field.
- Reference video #3 (ACTING + DIALOGUE DRIVER) = a vertical strip of the live minister speaking. Use this video to drive the minister's:
  * Acting performance — head turns, hand gestures, body language, micro-expressions
  * Dialogue lip-sync — match every mouth movement frame-for-frame to the speaker in this video
  * Dialogue content + timing — what is being said, and the pacing of each beat
  * Speaker identity in the resulting frame should be the MINISTER as seen in the scene anchor (red and gold hanfu, scholar's cap, beard), with the live-strip's performance bound to him.
- Reference audio #4 = SHOT 07 dialogue mp3. Reinforces the voice timbre, cadence, and content of the minister's formal greeting.
"""

SHOT_PROMPT = """Shot 08 REPLAY2 — 12s-keyframe-driven minister greeting in the underwater palace.

The composition and visual style come from the SCENE ANCHOR image (12s keyframe) — that is what the final shot should look like. The minister stands at center-frame, mid-greeting, with the emperor seated on the throne in the foreground/silhouette and the princess + elder kneeling alongside. Footsoldiers in armor are motionless behind. The underwater palette is locked.

The minister's performance (gesture, head pose, lip movement, dialogue) is driven by the SHOT 07 VERTICAL STRIP reference video — translate his acting and lip-sync from that live performance onto the MINISTER character as seen in the scene anchor. He is delivering a formal court greeting (cupped fists, slight bow, head raised to speak) — match the cadence and lip movements of the live performance frame-for-frame.

The audio reference reinforces the dialogue content and voice. Lip-sync should match the audio.

Environmental directives:
- Wave caustics rippling across the minister's face and the emperor's silhouette
- Bubble streams drifting up through the frame
- Hanfu robes catching the underwater current (slow billowing motion)
- Motionless footsoldiers behind all subjects
- Muffled underwater pressure rumble + bubble SFX underneath the spoken dialogue
- All four characters (emperor, minister, princess, elder) visible per the scene anchor's framing"""


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
    out_path = OUT_DIR / f"shot_08_replay2_keyframe_v{version}_480p_15s.mp4"
    out_path.write_bytes(data)
    print(f"    ✓ V{version} saved: {out_path.name}")
    return out_path


def main():
    t0 = time.time()

    refs = [
        ("image", KEYFRAME_REF,    "12s KEYFRAME (scene anchor)"),
        ("image", COLLAGE_REF,     "PALACE COLLAGE (location anchor)"),
        ("video", VERT_STRIP_REF,  "SHOT7 VERTICAL STRIP 3s (acting + dialogue driver)"),
        ("audio", SHOT7_AUDIO_REF, "SHOT7 DIALOGUE"),
    ]

    prompt = GLOBALS + "\n" + REF_GUIDE + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  1 video (3s) + 2 images + 1 audio ✓")
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

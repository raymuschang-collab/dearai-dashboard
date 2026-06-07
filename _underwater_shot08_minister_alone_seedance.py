#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 08 MINISTER ALONE (4-shot single-character sequence).
720p · 16:9 · 15s · Fires V1 + V2 in parallel.

4 shots, all minister alone in frame, delivering his formal greeting to the
emperor (off-frame):
  Shot A · CU front 3/4 low angle (4s)
  Shot B · MS clean (4s) — cupped greeting gesture
  Shot C · CU profile (3s)
  Shot D · MS slight high angle (4s)

Refs (1 video + 1 image + 1 audio — minimal, no competing identity signals):
  - image: PALACE COLLAGE (location anchor)
  - video: MINISTER canonical 4.4s (identity — clean-shaven)
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

OUT_DIR = Path("/Users/raymuschang/Desktop/Channel 8 Underwater — Landed Outputs")
OUT_DIR.mkdir(exist_ok=True)

COLLAGE_REF       = "asset://asset-20260518092632-np5gm"   # PALACE COLLAGE (image)
MINISTER_REF      = "asset://asset-20260517201250-rhxdq"   # MINISTER canonical 4.4s
SHOT7_AUDIO_REF   = "asset://asset-20260518102541-4tjvf"   # SHOT7 DIALOGUE mp3


GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
"""

REF_GUIDE = """Reference inputs:
- Reference image #1 (LOCATION ANCHOR) = the underwater palace collage. Locks throne hall geometry, columns with coral and kelp, motionless footsoldiers in armor in the background, refracting underwater light, color palette, bubble density.
- Reference video #2 (MINISTER CANONICAL IDENTITY) = the authoritative MINISTER reference. The minister's face, complexion, hairline, wardrobe (hanfu robes) all come from THIS reference. Do not introduce facial hair, beards, or features not present here.
- Reference audio #3 = SHOT 07 dialogue mp3. Voice timbre, cadence, and content of the formal greeting line.
"""

SHOT_PROMPT = """Shot 08 — MINISTER alone, 4-shot single-character sequence delivering his formal greeting to the EMPEROR (who is OFF-FRAME). All four shots show the MINISTER alone in frame. Static cuts between shots. 15s total.

Shot A (CU, 4s, front 3/4 angle from below — slight low angle, as if from the EMPEROR's seated POV looking up at him): Tight close-up on the MINISTER's face. He raises his head from a bowed position and begins to speak the formal greeting. Eyes respectful, jaw set. Wave caustics ripple across his face; bubble streams drift past in the background. Hanfu collar visible at the bottom of frame. No other characters in shot.

Shot B (MS, 4s, slightly to the side — clean MS framing, no OTS): The MINISTER from waist up, alone in frame, facing the EMPEROR (off-frame to the right). Hands brought up into the formal court greeting gesture — fists cupped, pressed together in front of his chest, slight bow. He raises his head and continues delivering the greeting. Hanfu robes billowing gently in the underwater current. Motionless footsoldiers visible deep in the background, blurred. Bubbles drift upward.

Shot C (CU, 3s, profile or quarter-profile from his right side): Profile close-up of the MINISTER's face mid-dialogue. The greeting continues. Underwater light streams diagonally across his cheek; caustics ripple. Mouth movements clearly visible (lip-syncing to the audio reference). Bubbles drift past.

Shot D (MS, 4s, slight high angle from behind the EMPEROR's silhouette — but EMPEROR is OFF-FRAME, so the angle just suggests his presence): The MINISTER from a slight high angle, alone in frame, finishing the greeting. Hands still in the cupped formal gesture, head respectfully lowered then raised one last time. Robes catching the underwater current. Footsoldiers in armor visible in the deep background, motionless. Bubble streams drifting up. End on him holding the position.

The MINISTER's identity (face, hairline, complexion) must come from Reference video #2 — do NOT render facial hair or features beyond what is in that canonical reference. His voice and dialogue lip-sync should match the Reference audio #3.

Environmental: wave caustics, bubble streams, slow billowing robes throughout. Underwater pressure rumble + bubble SFX bedded under the spoken greeting."""


def submit(content_block):
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content_block,
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
    out_path = OUT_DIR / f"shot_08_minister_alone_v{version}_720p_15s.mp4"
    out_path.write_bytes(data)
    print(f"    ✓ V{version} saved: {out_path.name}")
    return out_path


def main():
    t0 = time.time()

    refs = [
        ("image", COLLAGE_REF,     "PALACE COLLAGE (location anchor)"),
        ("video", MINISTER_REF,    "MINISTER canonical 4.4s (identity)"),
        ("audio", SHOT7_AUDIO_REF, "SHOT7 DIALOGUE"),
    ]

    prompt = GLOBALS + "\n" + REF_GUIDE + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  1 video (4.4s) + 1 image + 1 audio ✓")
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

    print(f"\n=== Firing V1 + V2 in parallel (720p · 15s · 16:9) ===")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(fire_one, v, content) for v in (1, 2)]
        for f in futs:
            try: f.result()
            except Exception as e: print(f"  ✗ {e}")

    print(f"\n=== ALL DONE  ·  wall: {time.time()-t0:.1f}s ===")


if __name__ == "__main__":
    main()

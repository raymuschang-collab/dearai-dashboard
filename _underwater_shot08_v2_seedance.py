#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 08 V2 Seedance vidgen.
15s · 720p · 16:9 · Multi-shot OTS montage with location COLLAGE as anchor.

Refs (5 total: 3 video + 2 image + 1 audio; respects 3-video cap):
  - image: UNDERWATER PALACE COLLAGE (location anchor)
  - video: EMPEROR 3s (1.49x FF) — speaker
  - video: PRINCESS 3s (1.42x FF) — listener
  - video: ELDER 3s (1.49x FF) — listener
  - image: MINISTER STILL (4th character — still since 3-video cap)
  - audio: SHOT8 DIALOGUE (mp3, ~5.6s)

Video budget: 3 + 3 + 3 = 9s ✓
"""
import io, json, os, re, sys, time
from pathlib import Path

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

SHOT_DIR = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 08")
OUT_DIR = SHOT_DIR / "seedance outputs"
OUT_DIR.mkdir(exist_ok=True)

# Refs
COLLAGE_REF     = "asset://asset-20260518092632-np5gm"   # UNDERWATER PALACE COLLAGE (image)
EMPEROR_3S_REF  = "asset://asset-20260518092150-rkvfg"   # EMPEROR 3s
PRINCESS_3S_REF = "asset://asset-20260518092201-bxlnw"   # PRINCESS 3s
ELDER_3S_REF    = "asset://asset-20260518092211-8cz4x"   # ELDER 3s
MINISTER_IMG    = "asset://asset-20260518092642-kppqq"   # MINISTER STILL (image)
SHOT8_AUDIO_REF = "asset://asset-20260518092222-2b9td"   # SHOT8 DIALOGUE mp3

GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
Staging note: Soldiers standing behind the characters and in front of the throne at ALL times.
"""

REF_GUIDE = """Reference identities:
- Reference image #1 = UNDERWATER PALACE COLLAGE — composition/location anchor for throne hall, columns, soldiers, lighting, color palette.
- Reference video #2 = EMPEROR — the speaker, seated on the throne addressing his subjects.
- Reference video #3 = PRINCESS — kneeling subject, female, attentive listener.
- Reference video #4 = ELDER — kneeling subject, old wise man with beard, attentive listener.
- Reference image #5 = MINISTER — kneeling subject (4th figure), same hanfu robes as seen in shot 07.
- Reference audio #6 = EMPEROR voice/tone — use this voice timbre and cadence for the emperor's dialogue.
"""

SHOT_PROMPT = """8, 15s, multi-shot OTS montage (WS → MS → overhead → CU), Static cuts —

Shot A (WS, 4s, OTS from behind PRINCESS, ELDER, MINISTER kneeling in a row): Wide shot of the underwater throne hall, framing matching the COLLAGE location reference. In the foreground (silhouetted, soft-focus), three figures kneel in a row with backs to camera — PRINCESS on the left, ELDER in the middle, MINISTER on the right. Beyond them, on a raised dais, the EMPEROR sits on the underwater throne and addresses his subjects with regal authority. Footsoldiers in armor stand at attention behind the throne and along the columns. Bubbles drift up through the frame; light shafts pierce the water from above.

Shot B (MS, 3s, OTS from behind the throne looking out at the four kneeling subjects): Over the EMPEROR's shoulder, we see PRINCESS, ELDER, and MINISTER kneeling in a row, heads bowed, listening attentively. Their hanfu robes billow gently in the underwater current. The PRINCESS lifts her gaze for a beat — eyes respectful. The ELDER nods slowly. The MINISTER holds his head bowed.

Shot C (Overhead high-jib MS looking straight down, 4s): God's-eye view straight down on the scene — the EMPEROR seated centered on the throne at the top of the frame, the THREE subjects (PRINCESS, ELDER, MINISTER) kneeling in a horizontal row beneath him. Soldiers ring the perimeter. Schools of fish drift through the upper portion of the frame. Bubbles spiral up past camera.

Shot D (CU, 4s, OTS over the kneeling subjects looking up at EMPEROR): Tight close-up of the EMPEROR speaking — jaw set, voice carrying gravitas. EMPEROR: (Singapore Chinese accent) speaks to his subjects — see attached audio reference for tone, cadence, and content. His face is lit by refracting underwater light, wave caustics rippling across his features. Bubble streams; muffled water-pressure rumble; the faint clink of soldier armor in the background."""


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


def poll(task_id, max_wait=1800):
    start = time.time(); last = None
    while time.time() - start < max_wait:
        r = requests.get(f"{ARK_BASE}/contents/generations/tasks/{task_id}",
                          headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=30)
        if r.status_code != 200:
            time.sleep(30); continue
        resp = r.json(); status = resp.get("status")
        if status != last:
            print(f"    [{int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status in ("succeeded", "completed", "success"):
            return resp
        if status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"failure: {json.dumps(resp)[:500]}")
        time.sleep(30)
    raise RuntimeError("30-min cap exceeded")


def extract_url(resp):
    c = resp.get("content", {})
    if isinstance(c, dict):
        v = c.get("video_url")
        if isinstance(v, str): return v
        if isinstance(v, dict): return v.get("url")
    m = re.search(r'https://[^\s"\']*\.mp4[^\s"\']*', json.dumps(resp))
    return m.group(0) if m else ""


def main():
    t0 = time.time()

    # Order: image (location) → 3 videos (speakers/listeners) → image (4th char) → audio
    refs = [
        ("image", COLLAGE_REF,     "PALACE COLLAGE (loc anchor)"),
        ("video", EMPEROR_3S_REF,  "EMPEROR 3s"),
        ("video", PRINCESS_3S_REF, "PRINCESS 3s"),
        ("video", ELDER_3S_REF,    "ELDER 3s"),
        ("image", MINISTER_IMG,    "MINISTER still"),
        ("audio", SHOT8_AUDIO_REF, "SHOT8 DIALOGUE"),
    ]

    prompt = GLOBALS + "\n\n" + REF_GUIDE + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  video budget: 9s (3 videos) + 2 images + 1 audio ✓")
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

    print(f"\n  ◦ submitting shot 08 V2 (15s · 720p · 16:9)...")
    tid = submit(content)
    print(f"    ✓ task_id: {tid}")
    result = poll(tid)
    video_url = extract_url(result)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / "shot_08_underwater_v5_collage_4char_720p_15s.mp4"
    out_path.write_bytes(data)
    print(f"\n=== DONE  ·  wall: {time.time()-t0:.1f}s ===")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

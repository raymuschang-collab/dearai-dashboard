#!/usr/bin/env python3
"""Channel 8 Underwater — Freeform: EMPEROR addressing 2 subjects (no audible dialogue).
15s · 720p · 16:9 · MS + CU montage.

Refs (3 video + 1 image, within 3-video cap):
  - image: UNDERWATER PALACE COLLAGE (location anchor)
  - video: EMPEROR 3s
  - video: PRINCESS 3s
  - video: ELDER 3s
  No audio ref (dialogue inaudible by design — only SFX).
"""
import json, os, re, sys, time
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

OUT_DIR = Path("/Users/raymuschang/Documents/Channel 8 Underwater — Landed Outputs")
OUT_DIR.mkdir(exist_ok=True)

COLLAGE_REF     = "asset://asset-20260518092632-np5gm"   # UNDERWATER PALACE COLLAGE (image)
EMPEROR_3S_REF  = "asset://asset-20260518092150-rkvfg"
PRINCESS_3S_REF = "asset://asset-20260518092201-bxlnw"
ELDER_3S_REF    = "asset://asset-20260518092211-8cz4x"

GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds. Dialogue muffled/inaudible in this shot — speech is drowned by underwater pressure rumble and bubbles.
Accents: Singapore Chinese accent (n/a here — no audible dialogue).
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
Production directives (locked across this show):
- Max 3 characters per shot (hard API cap on video refs).
- ENVIRONMENT INTEGRATION: characters must be fully inhabiting the underwater palace — robes catch the underwater current, hair floats slightly, light caustics ripple across faces and clothing. They are NOT floating heads composited onto a background; they are physically present in the water.
- ACTOR INTEGRATION for all mid-shots and close-ups: the character's body, robes, and surrounding water/light interact realistically. Visible bubbles drift near them, columns/throne behind them, water reflections on their skin.
- Staging note: Footsoldiers in armor stand BEHIND the two seated/standing subjects (princess + elder), motionless at attention, facing forward. Their helmets, spears, and armor catch the light. They do NOT move.
"""

REF_GUIDE = """Reference identities:
- Reference image #1 = UNDERWATER PALACE COLLAGE — location anchor: throne hall, columns, soldiers, lighting, color palette. Composition framing should echo this collage's panels.
- Reference video #2 = EMPEROR — central figure, seated on the throne, speaking to his subjects with regal authority.
- Reference video #3 = PRINCESS — younger female subject, standing/kneeling, listening attentively.
- Reference video #4 = ELDER — older male subject with beard, standing/kneeling, listening attentively.
"""

SHOT_PROMPT = """Freeform, 15s, MS + CU montage of EMPEROR addressing 2 subjects (PRINCESS + ELDER) in the underwater throne hall. Static cuts —

Shot A (MS, 4s, dolly-in slow on the EMPEROR): The EMPEROR sits on the underwater throne, speaking with measured authority. We see his mouth moving but the dialogue is INAUDIBLE — only muffled water-pressure rumble and bubble streams reach the camera. Footsoldiers in armor stand motionless behind him on either side of the throne, facing forward, spears upright. Wave caustics ripple across his face and robes. Bubbles drift up through the frame.

Shot B (CU, 3s, profile of PRINCESS listening): Tight close-up on the PRINCESS's face — eyes downcast in respect, attentive, jaw soft. Her hanfu collar billows gently in the current. Light caustics ripple across her cheek. A footsoldier's silhouette is visible behind her right shoulder, motionless at attention. Bubbles drift past her face.

Shot C (MS, 4s, two-shot of PRINCESS + ELDER from a low angle looking up): Both subjects stand/kneel side by side facing the throne (off-frame). The PRINCESS on the left, the ELDER on the right. Behind them: a row of motionless footsoldiers standing at attention, helmets and armor catching refracting light, spears vertical. The ELDER nods slowly; the PRINCESS keeps her eyes lowered. Their robes shift gently in the underwater current. Schools of fish drift through the deep background.

Shot D (CU, 4s, on ELDER reacting): Tight close-up on the ELDER's face — old, beard floating slightly in the water, eyes attentive and respectful. A subtle reaction crosses his features as the EMPEROR (off-frame) speaks — perhaps a tightening of the jaw, or a slow blink. Light caustics ripple across his weathered skin. A motionless soldier silhouette behind his left shoulder. Bubble streams drift past.

Audio bed across all 4 shots: muffled water-pressure rumble, slow bubble streams, distant kelp swaying, the faint clink of armor on the motionless soldiers. NO audible speech."""


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

    refs = [
        ("image", COLLAGE_REF,     "PALACE COLLAGE (loc anchor)"),
        ("video", EMPEROR_3S_REF,  "EMPEROR 3s"),
        ("video", PRINCESS_3S_REF, "PRINCESS 3s"),
        ("video", ELDER_3S_REF,    "ELDER 3s"),
    ]

    prompt = GLOBALS + "\n" + REF_GUIDE + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  video budget: 9s (3 chars) + 1 image, no audio ✓")
    for kind, url, label in refs:
        print(f"  {kind:<6} → {url}  ({label})")

    content = [{"type": "text", "text": prompt}]
    for kind, url, _ in refs:
        if kind == "video":
            content.append({"type": "video_url", "video_url": {"url": url}, "role": "reference_video"})
        elif kind == "image":
            content.append({"type": "image_url", "image_url": {"url": url}, "role": "reference_image"})

    print(f"\n  ◦ submitting EMPEROR + 2 subjects (15s · 720p · 16:9)...")
    tid = submit(content)
    print(f"    ✓ task_id: {tid}")
    result = poll(tid)
    video_url = extract_url(result)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / "emperor_2subjects_v1_720p_15s.mp4"
    out_path.write_bytes(data)
    print(f"\n=== DONE  ·  wall: {time.time()-t0:.1f}s ===")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

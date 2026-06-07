#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 08 mutation v2: MINISTER formal greeting (re-fire).
15s · 720p · 16:9. Fires V1 + V2 in parallel.

Replicates the v5 working pattern: COLLAGE + 3 char videos + 1 char still + audio.

Shot A (~7s): Side OTS from behind/over the soldiers' shoulders — emperor's subjects
              (PRINCESS, ELDER, MINISTER) seen in a row, kneeling/standing.
Shot B (~8s): MINISTER speaks to EMPEROR — formal greeting with gesture. Audio drives
              lip-sync + voice timbre.

All 4 characters present (3 video + 1 image):
  - image: UNDERWATER PALACE COLLAGE (location + composition anchor)
  - video: EMPEROR 3s (1.49x FF)
  - video: MINISTER 4.4s (original)
  - video: ELDER 3s (1.49x FF)
  - image: PRINCESS STILL (kept as image since 3-video cap is hard)
  - audio: SHOT7 DIALOGUE
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
COLLAGE_REF       = "asset://asset-20260518092632-np5gm"   # PALACE COLLAGE image
EMPEROR_3S_REF    = "asset://asset-20260518092150-rkvfg"
MINISTER_REF      = "asset://asset-20260517201250-rhxdq"   # 4.4s original
ELDER_3S_REF      = "asset://asset-20260518092211-8cz4x"
PRINCESS_STILL    = "asset://asset-20260518104612-tl6xc"   # PRINCESS STILL image (uploaded today)
SHOT7_AUDIO_REF   = "asset://asset-20260518102541-4tjvf"   # SHOT7 DIALOGUE (uploaded earlier today)


GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
Production directives (locked across this show):
- Max 3 characters per shot (hard API cap on video refs).
- ENVIRONMENT INTEGRATION: characters must be fully inhabiting the underwater palace — robes catch the underwater current, hair floats slightly, light caustics ripple across faces and clothing. NOT floating heads on a background.
- ACTOR INTEGRATION for all mid-shots and close-ups: bodies, robes, water, light interact realistically. Visible bubbles drift near them, columns/throne behind them, water reflections on skin.
- Composition: framing should echo the palace collage reference image 80–100% — same camera angles, same depth relationships, same staging of soldiers behind subjects.
- Staging note: Footsoldiers in armor stand BEHIND the subjects, motionless at attention, facing forward.
"""

REF_GUIDE = """Reference identities — ALL FOUR CHARACTERS MUST APPEAR IN THE FRAME:
- Reference image #1 = UNDERWATER PALACE COLLAGE — location + composition anchor. Throne hall, columns, kelp, soldiers, lighting, palette.
- Reference video #2 = EMPEROR — seated on the underwater throne, dignified, receives the formal greeting. Wears imperial gold + dark hanfu robes.
- Reference video #3 = MINISTER — middle-aged court official, beard, scholar's cap, red and gold hanfu robes (same wardrobe as shot 07). He is the speaker giving the formal greeting.
- Reference video #4 = ELDER — older male council member with white beard and hanfu robes, kneeling/standing alongside princess and minister. Listening attentively.
- Reference image #5 = PRINCESS — younger female, hanfu robes, hair styled in court fashion. Kneeling/standing alongside elder and minister. Listening attentively. (She is the 4th character — though provided as a still image due to API ref caps, she MUST be present and visible in the frame.)
- Reference audio #6 = MINISTER's voice — use this voice timbre, cadence, and content for the minister's formal greeting line.
"""

SHOT_PROMPT = """Shot 08 mutation v2, 15s, 2-shot static cut — ALL FOUR CHARACTERS (EMPEROR, PRINCESS, ELDER, MINISTER) appear in this sequence.

Shot A (side OTS from behind/over the soldiers' shoulders, ~7s): Camera positioned BEHIND a row of motionless footsoldiers in armor (silhouetted, soft-focus foreground occupying the bottom third and right side of frame — helmets, spears, shoulder plates visible). Beyond them, side-angle view down the row of the EMPEROR's three subjects — PRINCESS on the left (younger female in hanfu, head bowed respectfully), ELDER in the middle (old man with white beard, hands clasped), MINISTER on the right (middle-aged court official in red and gold robes, beard, scholar's cap) — kneeling/standing in a row, waiting. Their hanfu robes shift gently in the underwater current; light caustics ripple across their faces and clothing. The MINISTER stands and bows his head slightly, preparing to speak. The EMPEROR is visible in the deep mid-ground on the throne, watching. Bubbles drift up through the frame. Underwater ambient — slow bubbles, deep pressure rumble, faint armor clink.

Shot B (MS, ~8s, OTS from over the EMPEROR's shoulder onto the MINISTER): Over the EMPEROR's right shoulder (soft-focus foreground — back of head and crown silhouette, throne edge, gold trim), we see the MINISTER in full mid-shot, with the PRINCESS visible kneeling/standing just behind the minister to his left and the ELDER kneeling/standing to his right (all three subjects in the frame, the minister centered as the speaker). The MINISTER raises his head, brings his hands together in a formal court greeting gesture (fists cupped in front of his chest, slight bow), and speaks his greeting to the EMPEROR. MINISTER: (Singapore Chinese accent) speaks the formal greeting — see attached audio reference for voice timbre, cadence, and content (lip-sync to the audio). His robes billow gently; bubbles drift past; wave caustics ripple across his features and the EMPEROR's silhouetted shoulder. PRINCESS and ELDER stand/kneel attentively behind him, heads bowed. A row of motionless footsoldiers stands at attention deep in the background. The MINISTER's gesture and head position match the moment of his greeting; expression respectful but composed."""


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
        time.sleep(30)
    video_url = extract_url(resp)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / f"shot_08_minister_greeting_v{version}_4char_720p_15s.mp4"
    out_path.write_bytes(data)
    print(f"    ✓ V{version} saved: {out_path.name}")
    return out_path


def main():
    t0 = time.time()

    refs = [
        ("image", COLLAGE_REF,    "PALACE COLLAGE"),
        ("video", EMPEROR_3S_REF, "EMPEROR 3s"),
        ("video", MINISTER_REF,   "MINISTER 4.4s"),
        ("video", ELDER_3S_REF,   "ELDER 3s"),
        ("image", PRINCESS_STILL, "PRINCESS STILL"),
        ("audio", SHOT7_AUDIO_REF,"SHOT7 DIALOGUE"),
    ]

    prompt = GLOBALS + "\n" + REF_GUIDE + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  3 videos (10.4s) + 2 images + audio ✓")
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

    print(f"\n=== Firing V1 + V2 in parallel ===")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(fire_one, v, content) for v in (1, 2)]
        for f in futs:
            try: f.result()
            except Exception as e: print(f"  ✗ {e}")

    print(f"\n=== ALL DONE  ·  wall: {time.time()-t0:.1f}s ===")


if __name__ == "__main__":
    main()

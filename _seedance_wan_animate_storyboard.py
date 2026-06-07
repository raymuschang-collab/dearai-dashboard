#!/usr/bin/env python3
"""Wan Test 7-shot park sequence — animate the storyboard via Seedance 2.0.
@carmen + @daniel · 480p · 9:16 · 15s · Singapore English accent.

Refs (2 video + 1 image, well under all caps):
  - image: WAN SHOTLIST 7-SHOT COLLAGE (storyboard composition anchor)
  - video: DANIEL 5s (canonical identity)
  - video: CARMEN 5s (canonical identity)
"""
import json, os, re, sys, time
from pathlib import Path

import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]

OUT_DIR = Path("/Users/raymuschang/Downloads/Wan Test/seedance_outputs")
OUT_DIR.mkdir(exist_ok=True)

COLLAGE_REF  = "asset://asset-20260520135439-pv5j8"   # WAN SHOTLIST 7-SHOT COLLAGE
DANIEL_REF   = "asset://asset-20260516223044-dggtl"   # DANIEL 5s
CARMEN_REF   = "asset://asset-20260516170559-dvf29"   # CARMEN 5s


GLOBALS = """Setting: A public park in Singapore at golden hour, under the sprawling shade of a massive raintree (Samanea saman).
Look: Realistic documentary cinema realism — NO game / CGI / cartoon look. Practical light only.
No music — SFX only: park ambient (wind in leaves, distant traffic, birds), dialogue, the SFX cues called out in the storyboard (shutter click + zipper + leather creak in shot 6).
Accents: SINGAPORE ENGLISH accent on ALL dialogue (both Daniel and Carmen). Casual Singaporean cadence.
Camera: Shot with Arri 35. Harsh dappled tropical sunlight breaking through the canopy in patches — HIGH CONTRAST, deep shadow on the subjects' bodies, blown-out highlights on the foliage behind them. Wave-light caustics on faces.
"""

REF_GUIDE = """Reference inputs:
- Reference image #1 (STORYBOARD COMPOSITION ANCHOR) = a 7-panel storyboard collage of this exact scene. The collage shows the camera framing, blocking, and order for all 7 shots. Use it as the spine — the video must execute these 7 cuts in sequence, matching the framing of each panel.
- Reference video #2 (DANIEL identity) = the male lead. Bearded, dark hair, cream mandarin-collar shirt. Face must match this reference exactly throughout.
- Reference video #3 (CARMEN identity) = the female lead. Bob haircut, cream blazer-shirt over black top. Face must match this reference exactly throughout.
"""

SHOT_PROMPT = """7-shot single-scene park sequence, 15s total, static cuts between shots. All 7 shots are in the same physical location (under the raintree at golden hour) except shots 6 and 7 which cut to the surveillance man hidden in nearby foliage.

DIALOGUE — all in SINGAPORE ENGLISH accent (casual Singaporean cadence, NOT American or British):

SHOT 1 (WS · 4s · 2-shot under raintree, harsh light): DANIEL and CARMEN stand facing each other in full body.
  DANIEL: "I shouldn't be here."
  CARMEN: "Then why did you come?"

SHOT 2 (WS · 2s · slow push-in): same framing tightening slightly.
  DANIEL: "You'll read it in the news tomorrow."

SHOT 3 (CU · 3s · OTS into DANIEL — Carmen's hair soft-focus in foreground): tight on DANIEL's face.
  DANIEL: "Forty-eight hours. He signs Friday."

SHOT 4 (MS · 3s · OTS into CARMEN — Daniel's shoulder soft-focus in foreground): she holds the silence.
  CARMEN: "Friday."
  (she lets the silence run for a beat — no further dialogue this shot)

SHOT 5 (CU · 4s · low angle on CARMEN, sun through raintree canopy backlighting her): power shift moment.
  CARMEN: "I already know."
  CARMEN: "And so does the KPK."

SHOT 6 (WS · 3s · POV from inside foliage, looking through leaves): An Asian man (NEW CHARACTER — wearing a bright yellow knit beanie and black jacket) is in the right foreground, much closer to camera, with binoculars to his eyes watching DANIEL and CARMEN who are now distant under the raintree. He LOWERS the binoculars by half. NO DIALOGUE.
  SFX: shutter click, zipper of a camera bag, leather strap creak.

SHOT 7 (CU · 3s · binoculars-to-camera, the surveillance man): Tight CU on the same yellow-beanie Asian man, binoculars held up to his eyes pointed at camera. He lowers them by half, locks eyes with the camera, speaks low into an earpiece.
  SURVEILLANCE MAN (low, into earpiece, Singapore English accent): "Pak. They're both here. And she knows."

Performance: DANIEL plays the entire scene with controlled urgency — he's risking everything to be here. CARMEN starts guarded and pivots in shot 5 to quiet authority (she has the upper hand). The surveillance man is watchful, professional, expressionless until the final line.

Environmental: golden-hour dappled sunlight through the raintree, gentle warm breeze moving the leaves, cicadas in the background, distant park ambient (no music)."""


def submit(content_block):
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content_block,
        "ratio": "9:16",
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


def poll(task_id, max_wait=1800):
    start = time.time(); last = None
    while time.time() - start < max_wait:
        r = requests.get(f"{ARK_BASE}/contents/generations/tasks/{task_id}",
                          headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=30)
        if r.status_code != 200:
            time.sleep(20); continue
        resp = r.json(); status = resp.get("status")
        if status != last:
            print(f"    [{int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status in ("succeeded","completed","success"): return resp
        if status in ("failed","expired","cancelled"):
            raise RuntimeError(f"failure: {json.dumps(resp)[:500]}")
        time.sleep(20)
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
        ("image", COLLAGE_REF, "WAN SHOTLIST 7-SHOT COLLAGE"),
        ("video", DANIEL_REF,  "DANIEL 5s"),
        ("video", CARMEN_REF,  "CARMEN 5s"),
    ]
    prompt = GLOBALS + "\n" + REF_GUIDE + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  2 videos (10s) + 1 image (storyboard) ✓")
    for k, u, l in refs:
        print(f"  {k:<6} → {u}  ({l})")

    content = [{"type": "text", "text": prompt}]
    for k, u, _ in refs:
        if k == "video": content.append({"type":"video_url","video_url":{"url":u},"role":"reference_video"})
        elif k == "image": content.append({"type":"image_url","image_url":{"url":u},"role":"reference_image"})

    print(f"\n  ◦ submitting (480p · 9:16 · 15s · Singapore English)...")
    tid = submit(content)
    print(f"    ✓ task_id: {tid}")
    result = poll(tid)
    video_url = extract_url(result)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / f"wan_animated_storyboard_v1_480p_15s.mp4"
    out_path.write_bytes(data)
    print(f"\n=== DONE · wall: {time.time()-t0:.1f}s ===")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Wan Test V2 — counter wooden delivery from V1.
Same scene · 480p · 9:16 · 15s · Singapore English · adds:
  - Performance-notes COLLAGE as scene anchor (annotations baked into the image)
  - PERFORMANCE NOTES text block in prompt (breath, micro-expression, body language, pacing per shot)
Fires V2a + V2b in parallel.
"""
import json, os, re, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

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

PERF_COLLAGE_REF = "asset://asset-20260520143547-7fmj9"   # PERF-NOTES collage
DANIEL_REF       = "asset://asset-20260516223044-dggtl"
CARMEN_REF       = "asset://asset-20260516170559-dvf29"


GLOBALS = """Setting: A public park in Singapore at golden hour, under the sprawling shade of a massive raintree (Samanea saman).
Look: Realistic documentary cinema realism — NO game / CGI / cartoon look. Practical light only.
No music — SFX only: park ambient (wind in leaves, distant traffic, birds), dialogue, the SFX cues called out in the storyboard.
Accents: SINGAPORE ENGLISH accent on ALL dialogue. Casual Singaporean cadence — slightly faster than American, slightly more clipped, no over-enunciation.
Camera: Shot with Arri 35. Harsh dappled tropical sunlight breaking through the canopy in patches — HIGH CONTRAST, deep shadow on bodies, blown-out highlights on the foliage. Wave-light caustics on faces.
"""

REF_GUIDE = """Reference inputs:
- Reference image #1 (STORYBOARD + PERFORMANCE NOTES) = a 7-panel storyboard with per-panel performance directives written underneath each panel. Execute the 7 cuts in panel order AND follow the performance notes on each panel exactly.
- Reference video #2 (DANIEL identity) = bearded, dark hair, cream mandarin-collar shirt. Face must match this reference exactly.
- Reference video #3 (CARMEN identity) = bob haircut, cream blazer-shirt over black top. Face must match this reference exactly.
"""

PERFORMANCE_NOTES = """PERFORMANCE NOTES — counter wooden / mechanical delivery. EVERY actor must show:
- BREATH: visible inhale before key lines, exhale on emotional beats. Throat works on swallows.
- MICRO-EXPRESSION: eye flickers, jaw tightens, brow furrows, blink rhythm changes.
- BODY LANGUAGE: weight shifts between feet; fingers curl/uncurl; small fidgets (NOT theatrical gestures).
- PACING: pauses INSIDE lines as well as between them; some words come faster than others; lines can trail off.
- EYE CONTACT RHYTHM: break and return — never staring without flickering.

PER-SHOT DIRECTION:

Shot 01 (WS, 4s):
- DANIEL: half-beat of silence BEFORE "I shouldn't be here." His eyes find hers AFTER he speaks, not before. Subtle swallow visible at his throat.
- CARMEN: arms loosely folded across her chest, weight on one foot. "Then why did you come?" — clipped, doesn't blink.

Shot 02 (WS slow push, 2s):
- DANIEL: holds eye contact, but his fingers at his side curl into a loose fist on "tomorrow". Audible exhale at end of line.

Shot 03 (CU OTS into Daniel, 3s):
- DANIEL: throat-swallow visible BEFORE he speaks. Eyes flick down to her mouth, then back up to her eyes BETWEEN "Forty-eight hours" and "He signs Friday". The 2nd line lands FASTER than the 1st — urgency leaking.

Shot 04 (MS OTS into Carmen, 3s):
- CARMEN: one beat of stillness BEFORE "Friday." Said flat, low, no emphasis. Then HOLDS the silence — chin lifts almost imperceptibly. Eyes dead-level on him, NO BLINK.

Shot 05 (CU low angle on Carmen, 4s):
- CARMEN: utterly still. Does NOT smile. Does NOT lean in. "I already know." — single beat. "And so does the KPK." — same flat register, no rise on KPK. The danger is in the calm. ONE hard blink at the end.

Shot 06 (WS surveillance POV through foliage, 3s):
- YELLOW-BEANIE MAN: lowers the binoculars BY HALF, not all the way. Head does not move. ONLY the hands.

Shot 07 (CU yellow-beanie man with binoculars to camera, 3s):
- YELLOW-BEANIE MAN: eyes FLAT behind the binoculars. Lowers them slightly to reveal mouth only. "Pak. They're both here." — clipped, professional, no inflection. Beat. "And she knows." — same register, but a FRACTIONAL eyebrow lift on "knows" — the ONLY emotion in the entire shot.

OVERALL RULE: no theatrical gestures. No smiles. No tears. No raised eyebrows except where explicitly specified. All emotion is SUB-SURFACE — eye flickers, breath, throat, fingers. This is a noir conversation, not a soap opera. Breath drives the pacing.
"""

SHOT_PROMPT = """7-shot single-scene park sequence, 15s total, static cuts. Same physical location (under the raintree at golden hour) for shots 1-5; shots 6-7 cut to the surveillance man hidden in foliage.

DIALOGUE — ALL in SINGAPORE ENGLISH accent (casual Singaporean cadence, NOT American or British):

Shot 01 (4s · WS):
  DANIEL: "I shouldn't be here."
  CARMEN: "Then why did you come?"

Shot 02 (2s · WS push):
  DANIEL: "You'll read it in the news tomorrow."

Shot 03 (3s · CU OTS):
  DANIEL: "Forty-eight hours. He signs Friday."

Shot 04 (3s · MS OTS):
  CARMEN: "Friday."
  (silence runs)

Shot 05 (4s · CU low angle):
  CARMEN: "I already know."
  CARMEN: "And so does the KPK."

Shot 06 (3s · WS POV through foliage):
  (no dialogue)
  SFX: shutter click, zipper of camera bag, leather strap creak.

Shot 07 (3s · CU surveillance man, Singapore English):
  SURVEILLANCE MAN (low, into earpiece): "Pak. They're both here."
  (beat)
  SURVEILLANCE MAN: "And she knows.\""""


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


def extract_url(resp):
    c = resp.get("content", {})
    if isinstance(c, dict):
        v = c.get("video_url")
        if isinstance(v, str): return v
        if isinstance(v, dict): return v.get("url")
    m = re.search(r'https://[^\s"\']*\.mp4[^\s"\']*', json.dumps(resp))
    return m.group(0) if m else ""


def fire_one(label: str, content):
    print(f"\n  ◦ {label} submitting...")
    tid = submit(content)
    print(f"    ✓ {label} task_id: {tid}")
    start = time.time(); last = None
    while True:
        r = requests.get(f"{ARK_BASE}/contents/generations/tasks/{tid}",
                          headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=30)
        resp = r.json(); status = resp.get("status")
        if status != last:
            print(f"    [{label} {int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status in ("succeeded","completed","success"): break
        if status in ("failed","expired","cancelled"):
            raise RuntimeError(f"{label} failure: {json.dumps(resp)[:500]}")
        time.sleep(20)
    video_url = extract_url(resp)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / f"wan_animated_storyboard_{label}_480p_15s.mp4"
    out_path.write_bytes(data)
    print(f"    ✓ {label} saved: {out_path.name}")
    return out_path


def main():
    t0 = time.time()
    refs = [
        ("image", PERF_COLLAGE_REF, "WAN PERF NOTES COLLAGE (storyboard + acting cues)"),
        ("video", DANIEL_REF,       "DANIEL 5s"),
        ("video", CARMEN_REF,       "CARMEN 5s"),
    ]
    prompt = GLOBALS + "\n" + REF_GUIDE + "\n" + PERFORMANCE_NOTES + "\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  2 videos (10s) + 1 image (perf-notes anchor) ✓")
    for k, u, l in refs:
        print(f"  {k:<6} → {u}  ({l})")

    content = [{"type": "text", "text": prompt}]
    for k, u, _ in refs:
        if k == "video": content.append({"type":"video_url","video_url":{"url":u},"role":"reference_video"})
        elif k == "image": content.append({"type":"image_url","image_url":{"url":u},"role":"reference_image"})

    print(f"\n=== Firing V2a + V2b in parallel (480p · 9:16 · 15s · Singapore English · perf-tuned) ===")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(fire_one, lab, content) for lab in ("v2a", "v2b")]
        for f in futs:
            try: f.result()
            except Exception as e: print(f"  ✗ {e}")

    print(f"\n=== ALL DONE · wall: {time.time()-t0:.1f}s ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""SODA — Launch Spot · ONE-TAKE FIZZ FLOOD variant.
Single continuous shot: Asian Gen-Z girl drinks → scene rapidly floods with
fizz bubbles → camera tilts up to sky → tagline appears.
480p · 9:16 · 15s · California English female VO."""
import json, os, re, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]

OUT_DIR = Path("/Users/raymuschang/Downloads/SODA Launch Spot/seedance_outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)


PROMPT = """SODA — Launch Spot · ONE-TAKE FIZZ FLOOD · 15s · 9:16 vertical · brand commercial · LA rooftop, California, golden hour.

★ THIS IS A SINGLE CONTINUOUS TAKE — NO CUTS, NO SHOT CHANGES. One camera move from start to finish.

CHARACTER: a 22-year-old Asian (East-Asian / Southeast-Asian) Gen-Z girl skater, sun-kissed tan, light-hearted, casual rooftop streetwear (graphic crop tee, baggy cargo pants, beanie or cap). Real natural-skin documentary edge — visible pores, natural skin texture, NO airbrushing. Kodak Portra 400 color science.

LOOK: bright primaries (signature red, sunny yellow) accents over a deep navy sky. Crisp daylight, harsh sun glints, real-camera shallow depth of field. Documentary-editorial photography aesthetic with a polished commercial finish.

MUSIC: upbeat indie pop, drum-led, 120 BPM, sunny tone. Music carries from frame 1 through frame end. A drum-build into the fizz explosion at the midpoint, then the final beat lands as the tagline appears.

VOICEOVER: female, CALIFORNIA ENGLISH accent (warm, sun-warmed, confident, playful). The exact VO line, timed across the take: "Cracked open." (as she drinks, 0:02) — "Sun out." (as the camera begins tilting up to sky) — "SODA in." (as the tagline lands) — "Eighteen flavours, zero compromise." (closing line over the final sky frame).

CONTINUOUS TAKE — SINGLE CAMERA MOVE, START TO FINISH (15 seconds):

(0:00–0:02) Open on a clean medium-close framing of the Asian skater girl on the rooftop, golden-hour light on her face, holding a SODA glass bottle in her right hand. She raises the bottle to her lips with a small confident smile. Camera handheld, slight push-in.

(0:02–0:05) She takes a long, satisfying swig of the soda. We see condensation on the bottle, her throat working as she drinks. SFX: glass bottle to lips, swallow, faint carbonation hiss. VO: "Cracked open."

(0:05–0:08) THE INSTANT she lowers the bottle, the entire scene RAPIDLY floods with fizz bubbles — a sudden eruption of carbonation bubbles bursts from the bottle's mouth and from the air around her. The bubbles MULTIPLY exponentially, filling the rooftop air, swirling around her, climbing higher. Her hair lifts slightly in the bubble updraft. She looks up, eyes catching the light. The bubbles are physically real (water-physics) and catch the golden sunlight — each one a tiny lens. Music drum-fills under the eruption.

(0:08–0:12) Camera begins a smooth TILT UP from her face — following the bubbles as they rise — past the rooftop edge, past the skyline, up into the open California sky. The bubbles rise with the camera, growing more sparse the higher we go. Sky transitions from golden-edge horizon to deep clear blue at the top of frame. VO: "Sun out."

(0:12–0:15) At the top of the tilt, the camera holds on a clean sky with the last few bubbles drifting up and fading. The BRAND TAGLINE animates in — bold sans-serif white text appearing in three quick beats on the blue sky: "CRACKED OPEN. // SUN OUT. // SODA IN." Each line lands with a music stab. Then directly underneath in smaller text: "Eighteen flavours, zero compromise." VO finishes the line as the text settles. Final music beat lands.

KEY DIRECTIVES:
- ONE TAKE: this is a single continuous camera move (handheld + tilt up). NO cuts. NO transitions. NO black frames between beats.
- The fizz-flood beat is the WOW moment — bubbles physically realistic, water-physics, light-catching, en masse. Think a champagne pop crossed with an underwater shot, but in mid-air.
- The tilt up from face to sky should feel weightless, like the camera is being carried by the rising bubbles.
- The tagline animation is part of the take — text appears IN the sky, not as a post-overlay cut-in.
- Asian girl character (not American Caucasian). Real skin texture, no AI-glossy beauty look.
- Female California English VO — confident, playful, sun-warmed, never breathless or corporate."""


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
    print(f"Prompt length: {len(PROMPT)} chars  ·  text-only · ONE-TAKE\n")

    content = [{"type": "text", "text": PROMPT}]
    print(f"  ◦ submitting SODA ONE-TAKE FIZZ FLOOD (480p · 9:16 · 15s)...")
    tid = submit(content)
    print(f"    ✓ task_id: {tid}")

    result = poll(tid)
    video_url = extract_url(result)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / "soda_one_take_fizz_flood_v1_480p_9x16_15s.mp4"
    out_path.write_bytes(data)
    print(f"\n=== DONE · wall: {time.time()-t0:.1f}s ===")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

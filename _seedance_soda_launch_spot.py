#!/usr/bin/env python3
"""SODA — Launch Spot (Seedance 2.0)
Text-only fire from creative brief (no character refs supplied).
480p · 9:16 · 15s · California English VO (female · confident, playful, sun-warmed)."""
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


PROMPT = """SODA — Launch Spot · 15s · 9:16 vertical · brand commercial · LA rooftop, California, golden hour.

CHARACTER: a 22-year-old Gen-Z skater, sun-kissed tan, light-hearted, casual rooftop streetwear (graphic tee, board shorts or cargo pants, beanie or cap optional). Female VO, but the on-screen action can include both the skater drinking and product-only inserts. Naturally lit, real-skin documentary edge.

LOOK: bright primaries (signature red #FFE98B accent, electric blue #41DABF7 accent, sunlit white, sunny yellow #FFE99E pop) over a deep navy #14143E sky in the background. Crisp daylight, harsh sun glints, real-camera shallow depth of field. Documentary-editorial photography aesthetic with a polished commercial finish — NOT advertising-glossy, NOT AI-painted.

MUSIC: upbeat indie pop, drum-led, 120 BPM, sunny tone. Music is the bed under the VO; carries from frame 1 through frame end. NO score-style theatrics — keep it driving and warm.

VOICEOVER: female, CALIFORNIA ENGLISH accent (warm, sun-warmed, confident, playful — never breathless, never corporate). Starts at 0:02 (after the first sip in Shot 1 lands). Total VO is exactly: "Cracked open. Sun out. SODA in. Eighteen flavours, zero compromise." (24 words max — these are the words.)

SHOT 1 (0:00–0:04 · macro close-up): Tight macro on a SODA glass bottle sitting on a rooftop ledge. Condensation droplets bead up and slide slowly down the bottle's curved side. Late-afternoon California sun glints on the rim of the bottle. Subtle wind. NO dialogue. SFX: drum-led indie pop kicks in soft; faint distant traffic.

SHOT 2 (0:04–0:07 · hand grab + product moment): A sun-kissed hand reaches into a cooler full of ice and pulls out the SODA bottle. Smooth twist of the cap — POP — a sharp tssss of carbonation hisses out and a faint mist of fizz puffs from the bottle's mouth. Wider frame so we see ice, water, sunlight. VO BEGINS over the SFX: "Cracked open."

SHOT 3 (0:07–0:11 · POV swig → freeze-frame splash): First-person POV. The Gen-Z skater raises the bottle to camera, takes a long swig — bottle hits the lens for a fraction of a second — fizz splatters across the lens in a freeze-frame burst. The action FREEZES mid-splatter for a beat with droplets suspended in mid-air. VO over the freeze: "Sun out. SODA in."

SHOT 4 (0:11–0:15 · table slam + tagline payoff): Action resumes — the bottle slams down onto a wooden rooftop table next to a worn skateboard, condensation rings forming. Camera pushes in slightly. Bold sans-serif TAGLINE animates in over the bottle: "CRACKED OPEN. SUN OUT. SODA IN." VO lands the close: "Eighteen flavours, zero compromise." Music swells then drops to a quick stab on the final beat.

TONE: confident, playful, sun-warmed. No characters smiling at camera in a fake-ad way — the skater's energy is genuine, slightly off-hand, like a friend handing you a cold one. Soda is the hero; the skater is the lifestyle wrap.

CAMERA: shot with a real cine camera (Arri 35-style sensor) — handheld for shots 1, 2, 4 (gentle handheld, not shaky); shot 3 is first-person POV. Shallow depth of field on the macros. Subtle film grain throughout. Color palette stays in the brand zone — red, blue, white, yellow accents against deep navy."""


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
    print(f"Prompt length: {len(PROMPT)} chars  ·  text-only (no character refs supplied)\n")

    content = [{"type": "text", "text": PROMPT}]
    print(f"  ◦ submitting SODA Launch Spot (480p · 9:16 · 15s · California English)...")
    tid = submit(content)
    print(f"    ✓ task_id: {tid}")

    result = poll(tid)
    video_url = extract_url(result)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / "soda_launch_spot_v1_480p_9x16_15s.mp4"
    out_path.write_bytes(data)
    print(f"\n=== DONE · wall: {time.time()-t0:.1f}s ===")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

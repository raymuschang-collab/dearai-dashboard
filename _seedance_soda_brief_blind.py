#!/usr/bin/env python3
"""Seedance 2 — execute the SODA brief V2 with refs only, no extra direction.
The brief mockup itself contains: shot sequence, character ref, product ref,
mograph tile, VO text, music style, tone, color palette, setting. Let the model
read it all from the image.
"""
import json, os, re, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]

OUT_DIR = Path("/Users/raymuschang/Downloads/SODA Launch Spot/seedance_outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BRIEF_REF = "asset://asset-20260520185036-rb48t"   # SODA BRIEF V2 GIRL

# Bare-minimum prompt — the brief image carries all the spec
PROMPT = "Execute this creative-brief storyboard exactly as documented in the reference image. Follow the shot sequence, character, product, motion graphics tile, voiceover, audio, tone, color palette, and setting shown in the brief."


def submit(content):
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content,
        "ratio": "9:16",
        "duration": 15,
        "resolution": "480p",
        "watermark": False,
    }
    r = requests.post(f"{ARK_BASE}/contents/generations/tasks",
        headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
        json=body, timeout=60)
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
            print(f"    [{int(time.time()-start)}s] {status}", flush=True); last = status
        if status in ("succeeded","completed","success"): return resp
        if status in ("failed","expired","cancelled"):
            raise RuntimeError(f"failure: {json.dumps(resp)[:500]}")
        time.sleep(20)
    raise RuntimeError("timed out")


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
    content = [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": BRIEF_REF}, "role": "reference_image"},
    ]
    print(f"Prompt length: {len(PROMPT)} chars  ·  1 image ref (full brief)  ·  no character/audio refs\n")
    print("  ◦ submitting (480p · 9:16 · 15s) ...")
    tid = submit(content)
    print(f"    ✓ task_id: {tid}")
    result = poll(tid)
    video_url = extract_url(result)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / "soda_brief_blind_v1_480p_9x16_15s.mp4"
    out_path.write_bytes(data)
    print(f"\n=== DONE · wall: {time.time()-t0:.1f}s ===")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

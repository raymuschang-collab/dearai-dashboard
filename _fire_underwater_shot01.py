#!/usr/bin/env python3
"""Fire underwater Channel 8 shot 01 — 2× gens at 480p/8s.
Blocking ref: shot 01 mp4 (7.72s). Look ref: throne-emperor reskin still."""
import io, json, os, re, sys, time, argparse
from pathlib import Path
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]
SHOT_FOLDER = "/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 01"

PROMPT = """Reference video shows the original take — follow the acting, dialogue, blocking, camera movement 100% from this reference. Match performance, framing, timing, and camera motion exactly.

Reference image shows the look and feel target — this scene is set underwater, in an underwater palace. The emperor wears flowing yellow and white robes, sits on a gilded golden throne with carved dragon coils. The setting is illuminated by aqueous teal-blue light filtering down from above, golden carved pillars wrapped in dragon motifs, schools of fish swimming through the frame, coral and underwater flora in the background. Faint bubbles, soft caustic light patterns, suspended-in-water hair and fabric motion.

The character is the same actor/blocking as the reference video — replace the production environment with the underwater palace look.

Documentary editorial cinematography. Arri Alexa, 35mm film, shallow depth of field. Natural light only (filtered underwater)."""

REFS = [
    {"type": "video", "url": "asset://asset-20260517234523-xt8v6", "label": "BLOCKING (shot 01 mp4)"},
    {"type": "image", "url": "asset://asset-20260517234513-wjlmj", "label": "LOOK (underwater throne)"},
]


def submit():
    content = [{"type": "text", "text": PROMPT}]
    for r in REFS:
        if r["type"] == "video":
            content.append({"type": "video_url", "video_url": {"url": r["url"]}, "role": "reference_video"})
        else:
            content.append({"type": "image_url", "image_url": {"url": r["url"]}, "role": "reference_image"})
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content,
        "ratio": "16:9",
        "duration": 8,
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
            time.sleep(30); continue
        resp = r.json(); status = resp.get("status")
        if status != last:
            print(f"  [{int(time.time()-start)}s] {status}", flush=True)
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
    return m.group(0) if m else None


def fire(variant):
    t0 = time.time()
    print(f"=== Underwater shot 01 v{variant} ===")
    print(f"  refs: {len(REFS)} · 16:9 · 8s · 480p")
    for r in REFS:
        print(f"    {r['label']:<26} → {r['url']}")
    task_id = submit()
    print(f"  task_id: {task_id}\n  polling...")
    result = poll(task_id)
    video_url = extract_url(result)
    data = requests.get(video_url, timeout=600).content
    out = Path(SHOT_FOLDER) / f"shot_01_underwater_v{variant}.mp4"
    out.write_bytes(data)
    print(f"  ✓ saved: {out}")
    print(f"  wall: {time.time()-t0:.1f}s")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", type=int, default=1)
    args = ap.parse_args()
    fire(args.variant)

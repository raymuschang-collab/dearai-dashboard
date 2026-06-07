#!/usr/bin/env python3
"""Generic fire script for underwater Channel 8 reskin shots."""
import io, json, os, re, sys, time, argparse
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

BASE_PROMPT = """Reference video shows the original take — follow the acting, dialogue, blocking, camera movement 100% from this reference. Match performance, framing, timing, and camera motion exactly.

Reference image shows the look and feel target — this scene is set underwater, in an underwater palace. Aqueous teal-blue light filtering down from above, golden carved pillars wrapped in dragon motifs, schools of fish swimming through the frame, jellyfish, coral and underwater flora in the background. Faint bubbles, soft caustic light patterns, suspended-in-water hair and fabric motion. {extra}

The characters are the same actors/blocking as the reference video — replace the production environment with the underwater palace look.

Documentary editorial cinematography. Arri Alexa, 35mm film, shallow depth of field. Natural light only (filtered underwater)."""


def fire(shot, variant, video_ref, image_ref, duration, out_path, extra=""):
    prompt = BASE_PROMPT.format(extra=extra)
    content = [
        {"type": "text", "text": prompt},
        {"type": "video_url", "video_url": {"url": f"asset://{video_ref}"}, "role": "reference_video"},
        {"type": "image_url", "image_url": {"url": f"asset://{image_ref}"}, "role": "reference_image"},
    ]
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content,
        "ratio": "16:9",
        "duration": duration,
        "resolution": "480p",
        "watermark": False,
    }
    t0 = time.time()
    print(f"=== shot {shot} v{variant} · {duration}s ·  refs: video={video_ref} image={image_ref}")
    r = requests.post(
        f"{ARK_BASE}/contents/generations/tasks",
        headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"submit failed: {r.status_code} {r.text[:500]}")
    task_id = r.json().get("id") or r.json().get("task_id")
    print(f"  task: {task_id}")

    # Poll
    start = time.time(); last = None
    while time.time() - start < 1800:
        rr = requests.get(f"{ARK_BASE}/contents/generations/tasks/{task_id}",
                          headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=30)
        if rr.status_code != 200:
            time.sleep(30); continue
        resp = rr.json(); status = resp.get("status")
        if status != last:
            print(f"  [{int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status in ("succeeded", "completed", "success"):
            c = resp.get("content", {}) or {}
            v = c.get("video_url")
            video_url = v if isinstance(v, str) else (v.get("url") if isinstance(v, dict) else None)
            if not video_url:
                m = re.search(r'https://[^\s"\']*\.mp4[^\s"\']*', json.dumps(resp))
                video_url = m.group(0) if m else None
            data = requests.get(video_url, timeout=600).content
            Path(out_path).write_bytes(data)
            print(f"  ✓ saved: {out_path}")
            print(f"  wall: {time.time()-t0:.1f}s")
            return
        if status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"failure: {json.dumps(resp)[:500]}")
        time.sleep(30)
    raise RuntimeError("30-min cap exceeded")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--variant", type=int, required=True)
    ap.add_argument("--video", required=True, help="video ref asset code (no asset:// prefix)")
    ap.add_argument("--image", required=True, help="image ref asset code")
    ap.add_argument("--duration", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--extra", default="")
    args = ap.parse_args()
    fire(args.shot, args.variant, args.video, args.image, args.duration, args.out, args.extra)

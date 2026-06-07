#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from kling_api import poll_task, extract_video_url

EP = "/v1/videos/omni-video"
OUT = Path("/Users/raymuschang/Desktop/Channel 8 Underwater — Landed Outputs")
OUT.mkdir(parents=True, exist_ok=True)
tasks = json.loads((HERE / ".kling_omni_julia_tasks.json").read_text())

jobs = [
    ("shotA_submarine_corridor_9x16", tasks["shotA"]["data"]["task_id"]),
    ("shotB_hydroponic_side_16x9",    tasks["shotB"]["data"]["task_id"]),
]

for name, tid in jobs:
    print(f"[{name}] polling {tid} …", flush=True)
    try:
        data = poll_task(EP, tid, max_wait=1800)
        url = extract_video_url(data)
        if not url:
            print(f"[{name}] FAILED / no url. raw: {json.dumps(data)[:600]}", flush=True)
            continue
        dest = OUT / f"julia_newtsuit_{name}_o1_pro_5s.mp4"
        dest.write_bytes(requests.get(url, timeout=120).content)
        print(f"[{name}] DONE → {dest}  ({dest.stat().st_size/1e6:.1f} MB)", flush=True)
    except Exception as e:
        print(f"[{name}] ERROR: {e}", flush=True)

print("ALL DONE", flush=True)

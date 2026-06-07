#!/usr/bin/env python3
"""Kling omni-video V2V — remove boom mike from shot 08 1080p underwater gen.

Source: shot_08_underwater_v1_1080p.mp4
Output: shot_08_underwater_v1_1080p_nomic.mp4 (same folder)
"""
import json, os, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from kling_api import omni_video, get_task

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SRC = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 08/seedance outputs/shot_08_underwater_v1_1080p.mp4")
OUT = SRC.parent / "shot_08_underwater_v1_1080p_nomic.mp4"

PROMPT = (
    "Transform <<<video_1>>>. Remove the boom microphone that appears in the frame. "
    "Preserve EVERYTHING else exactly as in the source video: every character, performance, "
    "facial expression, costume, prop, blocking, framing, camera movement, edit timing, and dialogue. "
    "Keep the underwater palace setting completely intact — aqueous teal-blue caustic light, "
    "golden carved dragon-coiled pillars, schools of fish swimming through frame, jellyfish, coral, "
    "underwater flora, faint bubbles, suspended-in-water hair and fabric motion. "
    "Documentary editorial cinematography style, Arri Alexa 35mm look, shallow depth of field, "
    "filtered natural underwater light. The ONLY change is: the boom mic is gone — replace its area "
    "with the underwater ceiling architecture or filtered water above, whichever is contextually correct."
)


def main():
    if not SRC.exists():
        sys.exit(f"missing: {SRC}")

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling V2V Test Inputs' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    parent_id = drive.files().list(q=q, fields="files(id)", pageSize=1).execute()["files"][0]["id"]

    print(f"=== uploading source ===\n  {SRC.name} ({SRC.stat().st_size/1024/1024:.1f}MB)")
    media = MediaFileUpload(str(SRC), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": f"kling_nomic_input_{SRC.name}", "parents": [parent_id]},
        media_body=media, fields="id",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    video_url = f"https://drive.google.com/uc?export=download&id={f['id']}"
    print(f"  → {video_url}")

    # Fire V2V
    print(f"\n=== firing omni-video V2V ===\n  model=kling-video-o1, mode=std, refer_type=base")
    for attempt in range(4):
        r = omni_video(
            prompt=PROMPT,
            video_urls=[video_url],
            refer_type="base",
            keep_original_sound=False,
            model="kling-video-o1",
            mode="std",
            duration=5,
        )
        code = r.get("code")
        if code == 0:
            task_id = (r.get("data") or {}).get("task_id")
            print(f"  ✓ task: {task_id}")
            break
        if code == 1303:
            wait = 60 * (attempt + 1)
            print(f"  ⏰ parallel task limit hit, sleeping {wait}s (attempt {attempt+1}/4)")
            time.sleep(wait)
            continue
        sys.exit(f"submit failed: {json.dumps(r)[:500]}")
    else:
        sys.exit("4 retries exhausted on parallel-task-limit")

    # Poll
    print(f"\n=== polling ===")
    start = time.time()
    last = None
    while time.time() - start < 1800:
        resp = get_task("omni-video", task_id)
        data = resp.get("data") or {}
        status = data.get("task_status")
        if status != last:
            print(f"  [{int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status == "succeed":
            videos = (data.get("task_result") or {}).get("videos") or []
            url = videos[0].get("url") if videos else None
            if not url:
                sys.exit(f"succeed but no video url: {json.dumps(resp)[:500]}")
            break
        if status == "failed":
            sys.exit(f"task failed: {json.dumps(resp)[:500]}")
        time.sleep(15)
    else:
        sys.exit("poll timeout")

    print(f"\n  downloading → {OUT}")
    OUT.write_bytes(requests.get(url, timeout=600).content)
    print(f"  ✓ final: {OUT}  ({OUT.stat().st_size/1024/1024:.1f}MB)")
    print(f"\nTotal wall: {time.time()-start:.1f}s")


if __name__ == "__main__":
    main()

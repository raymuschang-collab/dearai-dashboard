#!/usr/bin/env python3
"""Kling motion-control v3 — same trimmed-from-3s shot 01 + NEW pose ref.

New pose: 'Oriental Patterns Style.png' (the high-fidelity underwater-palace reskin
of the endframe — yellow imperial robes, dragon pillars, fish, throne).
"""
import json, os, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from kling_api import motion_control, get_task

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SHOT_FOLDER = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 01")
NEW_POSE_PNG = SHOT_FOLDER / "first and last frames/Oriental Patterns Style.png"
OUTPUT_DIR = SHOT_FOLDER / "kling mocap"

# Reuse the already-uploaded trimmed driving video from v2 — saves a Drive upload + an ffmpeg pass
TRIMMED_VIDEO_URL = "https://drive.google.com/uc?export=download&id=1Il7HcZFSAtmOygFpQzVm-5xppZWPfdym"

PROMPT = ("underwater scene. small fish swimming. bubbles coming out of the man's mouth "
          "when he talks. waves form when his body moves.")


def upload_image(drive, parent_id: str, local_path: Path) -> str:
    print(f"  uploading {local_path.name} ({local_path.stat().st_size/1024/1024:.1f}MB)...")
    media = MediaFileUpload(str(local_path), mimetype="image/png", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": f"kling_mc_v3_{local_path.name}", "parents": [parent_id]},
        media_body=media, fields="id",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    url = f"https://lh3.googleusercontent.com/d/{f['id']}=w2048"
    print(f"    → {url}")
    return url


def main():
    if not NEW_POSE_PNG.exists():
        sys.exit(f"missing: {NEW_POSE_PNG}")

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling Motion-Control Test' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    parent_id = drive.files().list(q=q, fields="files(id)", pageSize=1).execute()["files"][0]["id"]
    print(f"folder: {parent_id}")

    image_url = upload_image(drive, parent_id, NEW_POSE_PNG)

    print(f"\n=== firing motion-control ===")
    print(f"  model=kling-v3, mode=std, character_orientation=video")
    print(f"  image: {image_url}")
    print(f"  video: {TRIMMED_VIDEO_URL}")
    for attempt in range(4):
        r = motion_control(
            image_url=image_url,
            video_url=TRIMMED_VIDEO_URL,
            prompt=PROMPT,
            model="kling-v3",
            character_orientation="video",
            keep_original_sound=False,
            mode="std",
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

    (HERE / ".kling_mc_shot01_v3.json").write_text(json.dumps({"task_id": task_id, "image_url": image_url}, indent=2))

    print(f"\n=== polling ===")
    start = time.time()
    last = None
    while time.time() - start < 1800:
        resp = get_task("motion-control", task_id)
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

    out = OUTPUT_DIR / "kling_mocap_v3.mp4"
    print(f"\n  downloading → {out}")
    out.write_bytes(requests.get(url, timeout=600).content)
    print(f"  ✓ final: {out}  ({out.stat().st_size/1024/1024:.1f}MB)")
    print(f"\nTotal wall: {time.time()-start:.1f}s")


if __name__ == "__main__":
    main()

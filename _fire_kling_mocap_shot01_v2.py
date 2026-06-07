#!/usr/bin/env python3
"""Kling motion-control v2 — shot 01 trimmed from 3s + restyled endframe.

Inputs:
- driving video : shot 01.mp4 trimmed to start at 3.0s (≈4.72s long)
- pose image    : shot 1.png (AI-restyled endframe, 1376×768)
Settings: kling-v3, mode=std, character_orientation=video (richer motion lock,
max 30s — fits the 4.72s clip).

Output → shot 01/kling mocap/kling_mocap_v2.mp4  (no reverse — we kept the
source's natural direction this time).
"""
import json, os, subprocess, sys, time
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
SOURCE_MP4 = SHOT_FOLDER / "shot 01.mp4"
RESTYLED_PNG = SHOT_FOLDER / "first and last frames/shot 1.png"
OUTPUT_DIR = SHOT_FOLDER / "kling mocap"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TRIMMED_MP4 = OUTPUT_DIR / "_shot01_from3s.mp4"   # intermediate, kept for re-use

PROMPT = ("underwater scene. small fish swimming. bubbles coming out of the man's mouth "
          "when he talks. waves form when his body moves.")


def upload_to_drive(drive, parent_id: str, local_path: Path, mime: str) -> str:
    print(f"  uploading {local_path.name} ({local_path.stat().st_size/1024/1024:.1f}MB)...")
    media = MediaFileUpload(str(local_path), mimetype=mime, resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": f"kling_mc_v2_{local_path.name}", "parents": [parent_id]},
        media_body=media, fields="id",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    if mime.startswith("image/"):
        url = f"https://lh3.googleusercontent.com/d/{fid}=w2048"
    else:
        url = f"https://drive.google.com/uc?export=download&id={fid}"
    print(f"    → {url}")
    return url


def main():
    if not SOURCE_MP4.exists(): sys.exit(f"missing: {SOURCE_MP4}")
    if not RESTYLED_PNG.exists(): sys.exit(f"missing: {RESTYLED_PNG}")

    # 1. ffmpeg trim — start at 3.0s, keep everything after
    print(f"=== trimming source ===")
    print(f"  in  : {SOURCE_MP4}")
    print(f"  out : {TRIMMED_MP4}")
    cmd = [
        "ffmpeg", "-y", "-ss", "3.0", "-i", str(SOURCE_MP4),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        str(TRIMMED_MP4),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"ffmpeg trim failed:\n{res.stderr[-500:]}")
    # Get trimmed duration
    dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(TRIMMED_MP4)]
    dur = subprocess.run(dur_cmd, capture_output=True, text=True).stdout.strip()
    print(f"  ✓ trimmed: {dur}s, {TRIMMED_MP4.stat().st_size/1024/1024:.1f}MB")

    # 2. Drive uploads
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling Motion-Control Test' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    found = drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    parent_id = found[0]["id"]
    print(f"\n=== uploading ===\nfolder: {parent_id}")
    video_url = upload_to_drive(drive, parent_id, TRIMMED_MP4, "video/mp4")
    image_url = upload_to_drive(drive, parent_id, RESTYLED_PNG, "image/png")

    # 3. Fire motion-control (video orientation this round)
    print(f"\n=== firing motion-control ===")
    print(f"  model=kling-v3, mode=std, character_orientation=video")
    for attempt in range(4):
        r = motion_control(
            image_url=image_url,
            video_url=video_url,
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
    (HERE / ".kling_mc_shot01_v2.json").write_text(json.dumps({"task_id": task_id}, indent=2))

    # 4. Poll
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

    # 5. Download (no reverse — source already plays in natural direction this run)
    out = OUTPUT_DIR / "kling_mocap_v2.mp4"
    print(f"\n  downloading → {out}")
    out.write_bytes(requests.get(url, timeout=600).content)
    print(f"  ✓ final: {out}  ({out.stat().st_size/1024/1024:.1f}MB)")
    print(f"\nTotal wall: {time.time()-start:.1f}s")


if __name__ == "__main__":
    main()

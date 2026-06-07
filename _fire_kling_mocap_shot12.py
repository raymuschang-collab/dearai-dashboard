#!/usr/bin/env python3
"""Kling motion-control — shot 12 underwater test.

driving video: shot 12.mp4 (1920x1080, 2.8s, 2.4MB)
pose image   : shot12_firstframe.png (1376x768)
settings     : kling-v3, mode=std, character_orientation=video

If 2.8s is rejected as too short (≥3s typical), loop-extend with ffmpeg.

Output → shot 12/kling mocap/kling_mocap_v1.mp4
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

SHOT = Path("/Users/raymuschang/Documents/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 12")
DRIVING_MP4 = SHOT / "shot 12.mp4"
POSE_PNG = SHOT / "first and last frames/shot12_firstframe.png"
OUTPUT_DIR = SHOT / "kling mocap"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = ("underwater scene. small fish swimming. bubbles coming out of the man's mouth "
          "when he talks. waves form when his body moves.")


def maybe_extend_to_3s(src: Path) -> Path:
    """If source < 3.0s, boomerang it (forward + reversed) to 2x duration.

    Why boomerang and NOT stream_loop: a plain loop creates a hard cut at the
    seam where frame N jumps back to frame 0. Kling's character-detection rejects
    that as 'invalid character / first frame'. The forward+reversed palindrome is
    seamless — frame N matches frame N as it reverses, so the seam is invisible.
    """
    dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(src)]
    dur = float(subprocess.run(dur_cmd, capture_output=True, text=True).stdout.strip())
    if dur >= 3.0:
        return src
    print(f"  source is {dur}s (< 3s) — boomeranging (forward + reversed)")
    out = OUTPUT_DIR / "_shot12_boomerang.mp4"
    cmd = ["ffmpeg", "-y", "-i", str(src),
           "-filter_complex", "[0:v]split=2[fwd][tmp];[tmp]reverse[rev];[fwd][rev]concat=n=2:v=1[v]",
           "-map", "[v]", "-an",
           "-c:v", "libx264", "-preset", "fast", "-crf", "20",
           str(out)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    print(f"  ✓ boomeranged → {out}")
    return out


def upload(drive, parent_id: str, local_path: Path, mime: str) -> str:
    print(f"  uploading {local_path.name} ({local_path.stat().st_size/1024/1024:.1f}MB)...")
    media = MediaFileUpload(str(local_path), mimetype=mime, resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": f"kling_mc_shot12_{local_path.name}", "parents": [parent_id]},
        media_body=media, fields="id",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    url = (f"https://lh3.googleusercontent.com/d/{fid}=w2048" if mime.startswith("image/")
           else f"https://drive.google.com/uc?export=download&id={fid}")
    print(f"    → {url}")
    return url


def main():
    if not DRIVING_MP4.exists(): sys.exit(f"missing: {DRIVING_MP4}")
    if not POSE_PNG.exists():    sys.exit(f"missing: {POSE_PNG}")

    src_video = maybe_extend_to_3s(DRIVING_MP4)

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling Motion-Control Test' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    parent_id = drive.files().list(q=q, fields="files(id)", pageSize=1).execute()["files"][0]["id"]
    print(f"folder: {parent_id}\n=== uploading ===")
    video_url = upload(drive, parent_id, src_video, "video/mp4")
    image_url = upload(drive, parent_id, POSE_PNG, "image/png")

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
    (HERE / ".kling_mc_shot12.json").write_text(json.dumps({"task_id": task_id}, indent=2))

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

    out = OUTPUT_DIR / "kling_mocap_v1.mp4"
    print(f"\n  downloading → {out}")
    out.write_bytes(requests.get(url, timeout=600).content)
    print(f"  ✓ final: {out}  ({out.stat().st_size/1024/1024:.1f}MB)")
    print(f"\nTotal wall: {time.time()-start:.1f}s")


if __name__ == "__main__":
    main()

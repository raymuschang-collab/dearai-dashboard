#!/usr/bin/env python3
"""Kling i2v multi-shot — underwater hall scene + minister element.

scene image  : shot 07/first and last frames/shot 7.png
minister elem: 311017617324500 (trained from minister.mp4)

4-beat multi_shot:
  1) 4s wide hold of scene
  2) 2s punch-in CU on minister (foreground right)
  3) 2s tighter CU on minister
  4) 2s eyes-only insert on minister
Total: 10s. mode=pro. element_list attached (first-time attempt on i2v).
"""
import json, os, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from kling_api import _request, get_task

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCENE_PNG = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 07/first and last frames/shot 7.png")
OUTPUT_DIR = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 07/kling i2v multishot")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MINISTER_ELEMENT = 311017617324500

MULTI_PROMPT = [
    {"index": 1, "duration": "4",
     "prompt": ("Hold on the wide underwater palace hall scene. Slow drift of bubbles and small fish through frame. "
                "Gentle suspended motion of fabric and hair. No camera movement, just the world breathing. <<<object_1>>> "
                "stands on the foreground right.")},
    {"index": 2, "duration": "2",
     "prompt": ("Punch into a close-up of <<<object_1>>> on the foreground right. He stands tall, the covered dish still "
                "visible on his left side. Subtle facial expression — a flicker of awareness. Bubbles drift up past him.")},
    {"index": 3, "duration": "2",
     "prompt": ("Tighter close-up of <<<object_1>>>'s face. Eyes-only insert. A microexpression of concern. The dish with "
                "lid still visible on his left. Underwater caustic light dances across his features.")},
    {"index": 4, "duration": "2",
     "prompt": ("Pull back slightly from <<<object_1>>>'s close-up. He turns his head subtly. The covered dish remains on "
                "his left. Soft suspended motion in his hair and robes.")},
]


def upload_image(drive, parent_id, local_path):
    print(f"  uploading {local_path.name} ({local_path.stat().st_size/1024/1024:.1f}MB)...")
    media = MediaFileUpload(str(local_path), mimetype="image/png", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": f"kling_i2v_multishot_{local_path.name}", "parents": [parent_id]},
        media_body=media, fields="id",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    url = f"https://lh3.googleusercontent.com/d/{f['id']}=w2048"
    print(f"    → {url}")
    return url


def main():
    if not SCENE_PNG.exists():
        sys.exit(f"missing: {SCENE_PNG}")

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling V2V Test Inputs' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    parent_id = drive.files().list(q=q, fields="files(id)", pageSize=1).execute()["files"][0]["id"]
    print(f"folder: {parent_id}\n=== uploading ===")
    image_url = upload_image(drive, parent_id, SCENE_PNG)

    body = {
        "model_name": "kling-v3",
        "image": image_url,
        "multi_shot": "true",
        "shot_type": "customize",
        "multi_prompt": MULTI_PROMPT,
        "duration": "10",
        "mode": "pro",
        "sound": "off",
        "aspect_ratio": "16:9",
        "element_list": [{"element_id": str(MINISTER_ELEMENT)}],
        "negative_prompt": "",
    }
    print(f"\n=== firing kling-v3 image2video multi_shot ===")
    print(f"  body: image=<scene>, multi_shot=true, 4 beats, element_list=[{MINISTER_ELEMENT}]")
    for attempt in range(4):
        r = _request("POST", "/v1/videos/image2video", body)
        code = r.get("code")
        if code == 0:
            task_id = (r.get("data") or {}).get("task_id")
            print(f"  ✓ task: {task_id}")
            break
        if code == 1303:
            wait = 60 * (attempt + 1)
            print(f"  ⏰ parallel task limit, sleeping {wait}s")
            time.sleep(wait)
            continue
        sys.exit(f"submit failed: {json.dumps(r)[:500]}")
    else:
        sys.exit("4 retries exhausted")
    (HERE / ".kling_i2v_multishot_shot07.json").write_text(json.dumps({"task_id": task_id}, indent=2))

    print(f"\n=== polling ===")
    start = time.time()
    last = None
    while time.time() - start < 1800:
        resp = get_task("image2video", task_id)
        data = resp.get("data") or {}
        status = data.get("task_status")
        if status != last:
            print(f"  [{int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status == "succeed":
            videos = (data.get("task_result") or {}).get("videos") or []
            url = videos[0].get("url") if videos else None
            if not url:
                sys.exit(f"succeed but no url: {json.dumps(resp)[:500]}")
            break
        if status == "failed":
            sys.exit(f"task failed: {json.dumps(resp)[:500]}")
        time.sleep(15)
    else:
        sys.exit("poll timeout")

    out = OUTPUT_DIR / "kling_i2v_multishot_v1.mp4"
    print(f"\n  downloading → {out}")
    out.write_bytes(requests.get(url, timeout=600).content)
    print(f"  ✓ final: {out}  ({out.stat().st_size/1024/1024:.1f}MB)")
    print(f"\nTotal wall: {time.time()-start:.1f}s")


if __name__ == "__main__":
    main()

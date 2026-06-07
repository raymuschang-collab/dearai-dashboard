#!/usr/bin/env python3
"""Kling motion-control with video elements — shots 07 + 09.

For each shot:
  driving video : shot_NN_minister_red_vertical.mp4
  pose image    : pose_v2_minister_4s.png (shared, 1080x1920, cropped from multishot v2 at 4s)
  element       : freshly-trained video element from the SAME red_vertical mp4

settings: kling-v3, mode=std, character_orientation=video, elements attached
"""
import json, os, sys, time, concurrent.futures
from pathlib import Path
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
env = Path(HERE / ".env")
for line in env.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

from kling_api import motion_control, get_task, create_element_video_refer, get_element
from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SPLITS = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits")
POSE = SPLITS / "shot 07/first and last frames/pose_v2_minister_4s.png"
PROMPT = ("underwater scene. small fish swimming. bubbles coming out of the man's mouth "
          "when he talks. waves form when his body moves.")

JOBS = [
    {"shot": "07", "mp4": SPLITS / "shot 07/shot_07_minister_red_vertical.mp4",
     "elem_name": "minister_shot07_red", "elem_desc": "Channel 8 minister shot 07 vertical"},
    {"shot": "09", "mp4": SPLITS / "shot 09/shot_09_minister_red_vertical.mp4",
     "elem_name": "minister_shot09_red", "elem_desc": "Channel 8 minister shot 09 vertical"},
]


def upload(drive, parent_id, local, mime):
    media = MediaFileUpload(str(local), mimetype=mime, resumable=True, chunksize=1024*1024)
    f = drive.files().create(body={"name": f"kling_e_{local.name}", "parents": [parent_id]},
                              media_body=media, fields="id").execute()
    drive.permissions().create(fileId=f["id"], body={"role":"reader","type":"anyone"}, fields="id").execute()
    fid = f["id"]
    return (f"https://lh3.googleusercontent.com/d/{fid}=w2048" if mime.startswith("image/")
            else f"https://drive.google.com/uc?export=download&id={fid}")


def train_element(name, desc, video_url):
    r = create_element_video_refer(element_name=name, element_description=desc, video_url=video_url)
    if r.get("code") != 0:
        raise RuntimeError(f"create failed: {r}")
    tid = r["data"]["task_id"]
    start = time.time()
    while time.time() - start < 180:
        pr = get_element(tid)
        d = pr.get("data") or {}
        s = d.get("task_status")
        if s in ("succeed","succeeded"):
            elems = (d.get("task_result") or {}).get("elements") or []
            return elems[0]["element_id"]
        if s in ("failed","expired"):
            raise RuntimeError(f"train failed: {pr}")
        time.sleep(5)
    raise RuntimeError("train timeout")


def fire_mocap(image_url, video_url, element_id, out_path):
    for attempt in range(6):
        r = motion_control(image_url=image_url, video_url=video_url, prompt=PROMPT,
                           model="kling-v3", character_orientation="video",
                           keep_original_sound=False, mode="std",
                           elements=[str(element_id)])
        code = r.get("code")
        if code == 0:
            task_id = (r.get("data") or {}).get("task_id")
            break
        if code == 1303:
            wait = 60 * (attempt + 1)
            print(f"  ⏰ {out_path.name}: parallel cap, sleeping {wait}s", flush=True)
            time.sleep(wait); continue
        raise RuntimeError(f"submit failed: {r}")
    else:
        raise RuntimeError("parallel retries exhausted")
    print(f"  ✓ {out_path.name}: task {task_id}", flush=True)

    start = time.time(); last = None
    while time.time() - start < 1800:
        rr = get_task("motion-control", task_id)
        d = rr.get("data") or {}
        s = d.get("task_status")
        if s != last:
            print(f"    [{int(time.time()-start)}s] {out_path.name}: {s}", flush=True); last = s
        if s == "succeed":
            url = ((d.get("task_result") or {}).get("videos") or [{}])[0].get("url")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(requests.get(url, timeout=600).content)
            print(f"    ✓ {out_path}  ({out_path.stat().st_size/1024/1024:.1f}MB)", flush=True)
            return
        if s == "failed":
            msg = d.get("task_status_msg") or "unknown"
            raise RuntimeError(f"{out_path.name}: task failed: {msg}")
        time.sleep(15)
    raise RuntimeError(f"{out_path.name}: poll timeout")


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling Motion-Control Test' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    parent = drive.files().list(q=q, fields="files(id)", pageSize=1).execute()["files"][0]["id"]

    # Uploads
    print("=== uploading pose ===")
    pose_url = upload(drive, parent, POSE, "image/png")
    print(f"  pose: {pose_url}")

    for j in JOBS:
        print(f"=== uploading driving for shot {j['shot']} ===")
        j["video_url"] = upload(drive, parent, j["mp4"], "video/mp4")
        print(f"  → {j['video_url']}")

    # Train elements in parallel
    print("\n=== training elements (parallel) ===")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(train_element, j["elem_name"], j["elem_desc"], j["video_url"]): j for j in JOBS}
        for fut in concurrent.futures.as_completed(futures):
            j = futures[fut]
            j["element_id"] = fut.result()
            print(f"  ✓ shot {j['shot']}: element_id = {j['element_id']}")

    # Save element manifest
    elems_path = HERE / ".kling_elements.json"
    existing = json.loads(elems_path.read_text()) if elems_path.exists() else {}
    for j in JOBS:
        existing[j["elem_name"]] = j["element_id"]
    elems_path.write_text(json.dumps(existing, indent=2))
    print(f"  saved manifest: {elems_path}")

    # Fire mocaps in parallel
    print("\n=== firing motion-controls (parallel) ===")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futures = []
        for j in JOBS:
            out = SPLITS / f"shot {j['shot']}/kling mocap/kling_mocap_v1_with_element.mp4"
            futures.append(ex.submit(fire_mocap, pose_url, j["video_url"], j["element_id"], out))
        for fut in concurrent.futures.as_completed(futures):
            fut.result()


if __name__ == "__main__":
    main()

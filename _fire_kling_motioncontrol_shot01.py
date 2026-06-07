#!/usr/bin/env python3
"""Kling motion-control test on shot 01 — underwater reskin.

Inputs:
- driving video : shot_01_reversed.mp4 (reversed for camera-down → easier on the model)
- pose image    : Shot 1_EndFrame.png
- element       : video_refer from shot_01_reversed.mp4 (optional — may fail)

Output: reverse the gen so the camera plays back jibbing UP (= original direction).
"""
import json, os, subprocess, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from kling_api import motion_control, get_task, create_element_video_refer, get_element

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SHOT_FOLDER = Path("/Users/raymuschang/Documents/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 01")
REVERSED_MP4 = SHOT_FOLDER / "shot_01_reversed.mp4"
ENDFRAME_PNG = SHOT_FOLDER / "first and last frames/Shot 1_EndFrame.png"
OUTPUT_DIR = SHOT_FOLDER / "kling mocap"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = ("underwater scene. small fish swimming. bubbles coming out of the man's mouth "
          "when he talks. waves form when his body moves.")


def upload_to_drive(drive, parent_id: str, local_path: Path, mime: str) -> str:
    print(f"  uploading {local_path.name} ({local_path.stat().st_size/1024/1024:.1f}MB)...")
    media = MediaFileUpload(str(local_path), mimetype=mime, resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": f"kling_mc_input_{local_path.name}", "parents": [parent_id]},
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
    if not REVERSED_MP4.exists():
        sys.exit(f"missing: {REVERSED_MP4}")
    if not ENDFRAME_PNG.exists():
        sys.exit(f"missing: {ENDFRAME_PNG}")

    # 1. Drive folder
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling Motion-Control Test' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    found = drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    if found:
        parent_id = found[0]["id"]
    else:
        folder = drive.files().create(
            body={"name": "Kling Motion-Control Test", "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        parent_id = folder["id"]
        drive.permissions().create(fileId=parent_id, body={"role": "reader", "type": "anyone"}, fields="id").execute()
    print(f"folder: {parent_id}")

    # 2. Upload inputs
    video_url = upload_to_drive(drive, parent_id, REVERSED_MP4, "video/mp4")
    image_url = upload_to_drive(drive, parent_id, ENDFRAME_PNG, "image/png")

    # 3. Attempt element creation (best-effort, non-blocking)
    element_ids = []
    print("\n=== trying to create video-refer element ===")
    try:
        r = create_element_video_refer(
            element_name="shot01_actor",
            element_description="Male actor from Channel 8 underwater test, shot 01 (reversed)",
            video_url=video_url,
        )
        print(f"  element create response: {json.dumps(r)[:300]}")
        if r.get("code") == 0:
            data = r.get("data") or {}
            elem_task_id = data.get("task_id") or data.get("element_id")
            if elem_task_id:
                # Poll briefly (up to 3 min) for element to be ready
                print(f"  element task_id: {elem_task_id} — polling up to 3 min...")
                el_start = time.time()
                while time.time() - el_start < 180:
                    er = get_element(elem_task_id)
                    edata = er.get("data") or {}
                    estatus = edata.get("task_status") or edata.get("status")
                    print(f"    [{int(time.time()-el_start)}s] element status={estatus}")
                    if estatus in ("succeed", "ready", "succeeded"):
                        # The element_id is usually the task_id itself or in task_result
                        eid = (edata.get("task_result") or {}).get("element_id") or elem_task_id
                        element_ids = [eid]
                        print(f"  ✓ element ready: {eid}")
                        break
                    if estatus in ("failed", "expired"):
                        print(f"  ✗ element training failed — proceeding without")
                        break
                    time.sleep(15)
                else:
                    print(f"  ⏰ element still training after 3min — proceeding without")
        else:
            print(f"  ✗ element create rejected: {r.get('message')} — proceeding without")
    except Exception as e:
        print(f"  ✗ element create exception: {e} — proceeding without")

    # 4. Fire motion-control
    print(f"\n=== firing motion-control ===")
    print(f"  model=kling-v3, mode=std, character_orientation=image, elements={element_ids or 'none'}")
    r = motion_control(
        image_url=image_url,
        video_url=video_url,
        prompt=PROMPT,
        model="kling-v3",
        character_orientation="image",
        keep_original_sound=False,
        mode="std",
        elements=element_ids or None,
    )
    code = r.get("code")
    if code != 0:
        sys.exit(f"motion-control submit failed: {json.dumps(r)[:500]}")
    task_id = (r.get("data") or {}).get("task_id")
    print(f"  ✓ task: {task_id}")
    (HERE / ".kling_mc_shot01.json").write_text(json.dumps({"task_id": task_id, "elements": element_ids}, indent=2))

    # 5. Poll
    print(f"\n=== polling ===")
    start = time.time()
    while time.time() - start < 1800:
        resp = get_task("motion-control", task_id)
        data = resp.get("data") or {}
        status = data.get("task_status")
        print(f"  [{int(time.time()-start)}s] {status}", flush=True)
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

    # 6. Download (reversed-motion output) + reverse to play forward
    raw_out = OUTPUT_DIR / "kling_motioncontrol_underwater_reversed_motion.mp4"
    print(f"\n  downloading raw output → {raw_out}")
    raw_out.write_bytes(requests.get(url, timeout=600).content)

    final_out = OUTPUT_DIR / "kling_motioncontrol_underwater.mp4"
    print(f"  reversing → {final_out}")
    cmd = [
        "ffmpeg", "-y", "-i", str(raw_out),
        "-vf", "reverse",
        "-af", "areverse",
        "-preset", "fast",
        str(final_out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        # Try without audio reverse (in case no audio track)
        cmd2 = ["ffmpeg", "-y", "-i", str(raw_out), "-vf", "reverse", "-an", "-preset", "fast", str(final_out)]
        res2 = subprocess.run(cmd2, capture_output=True, text=True)
        if res2.returncode != 0:
            print(f"  ✗ ffmpeg reverse failed: {res.stderr[-300:]}")
            sys.exit(1)
    size_mb = final_out.stat().st_size / 1024 / 1024
    print(f"  ✓ final: {final_out}  ({size_mb:.1f}MB)")
    print(f"\nTotal wall: {time.time()-start:.1f}s")


if __name__ == "__main__":
    main()

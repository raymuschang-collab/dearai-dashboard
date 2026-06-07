#!/usr/bin/env python3
"""Upload 2 refs for shot 08 replay2 (12s-keyframe-driven minister greeting):
  - shot08_minister_v2_12s_keyframe.jpg (NEW scene anchor — minister mid-greeting)
  - shot_07_minister_red_vertical.mp4 (acting + dialogue driver, vertical strip)
"""
import os, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials
import byteplus_asset_v2 as bp
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

GROUP_ID = "group-20260505195134-wqx2b"

REFS = [
    (Path("/Users/raymuschang/Downloads/channel8_refs/shot08_replay2/shot08_minister_v2_12s_keyframe.jpg"),
     "image/jpeg", "SHOT8 MINISTER 12s KEYFRAME (scene anchor)", "Image"),
    (Path("/Users/raymuschang/Documents/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 07/shot_07_minister_red_vertical.mp4"),
     "video/mp4", "SHOT7 MINISTER VERTICAL STRIP 3s (acting + dialogue driver)", "Video"),
]


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    folder_name = "Channel 8 Test Shoot — Character Refs"
    res = drive.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)").execute()
    parent = res["files"][0]["id"]

    results = []
    for local, mime, label, kind in REFS:
        print(f"\n=== {label} ===")
        media = MediaFileUpload(str(local), mimetype=mime, resumable=True, chunksize=1024*1024)
        f = drive.files().create(
            body={"name": local.name, "parents": [parent]},
            media_body=media, fields="id",
        ).execute()
        drive.permissions().create(fileId=f["id"], body={"role":"reader","type":"anyone"}, fields="id").execute()
        fid = f["id"]
        if kind == "Image":
            url = f"https://lh3.googleusercontent.com/d/{fid}=w2048"
        else:
            url = f"https://drive.google.com/uc?export=download&id={fid}"
        aid = bp.create_asset(GROUP_ID, url, kind, name=label)
        bp.poll_asset(aid, timeout=300)
        print(f"  ✓ {aid}")
        results.append((label, aid))

    print("\n=== ASSET CODES ===")
    for label, aid in results:
        print(f'  {label:65} asset://{aid}')


if __name__ == "__main__":
    main()

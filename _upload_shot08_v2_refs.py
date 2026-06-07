#!/usr/bin/env python3
"""Upload 2 image assets for shot 08 V2:
  - Underwater Palace Collage.png (location image ref)
  - MINISTER_still.jpg (4th character as still since 3-video cap limits us)
"""
import os, sys, re as _re
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
    (Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/location-refs/Underwater Palace Collage.png"),
     "image/png", "UNDERWATER PALACE COLLAGE"),
    (Path("/Users/raymuschang/Downloads/channel8_refs/shot08_v2/MINISTER_still.jpg"),
     "image/jpeg", "MINISTER STILL"),
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
    for local, mime, label in REFS:
        print(f"\n=== {label} ===")
        media = MediaFileUpload(str(local), mimetype=mime, resumable=True, chunksize=1024*1024)
        f = drive.files().create(
            body={"name": local.name, "parents": [parent]},
            media_body=media, fields="id,webViewLink",
        ).execute()
        drive.permissions().create(fileId=f["id"], body={"role":"reader","type":"anyone"}, fields="id").execute()
        fid = f["id"]
        # Images use lh3 binary URL (BytePlus rejects /view)
        lh3 = f"https://lh3.googleusercontent.com/d/{fid}=w2048"
        aid = bp.create_asset(GROUP_ID, lh3, "Image", name=label)
        bp.poll_asset(aid, timeout=300)
        print(f"  ✓ {aid}")
        results.append((label, aid))

    print("\n=== ASSET CODES ===")
    for label, aid in results:
        print(f'  {label:30} asset://{aid}')


if __name__ == "__main__":
    main()

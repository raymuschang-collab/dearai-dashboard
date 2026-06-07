#!/usr/bin/env python3
"""Upload Underwater Palace Montage (15s, 1920×1080) as a Location asset on BytePlus.
For the Channel 8 underwater reskin test."""
import os, sys
from datetime import datetime, timezone
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
LOCAL = "/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/location-refs/Underwater Palace Montage.mp4"
ASSET_NAME = "UNDERWATER PALACE (montage)"


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    # Reuse the Channel 8 Drive folder we created earlier
    folder_name = "Channel 8 Test Shoot — Character Refs"
    res = drive.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)", pageSize=5,
    ).execute()
    parent = res["files"][0]["id"] if res.get("files") else None
    if not parent:
        sys.exit("Could not find Channel 8 folder")
    print(f"Reusing folder: {parent}")

    # Drive upload
    print("=== Step 1: Drive upload ===")
    media = MediaFileUpload(LOCAL, mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": "Underwater_Palace_Montage_15s.mp4", "parents": [parent]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    drive_view = f["webViewLink"]
    download_url = f"https://drive.google.com/uc?export=download&id={fid}"
    print(f"  drive_view: {drive_view}")

    # BytePlus
    print("\n=== Step 2: BytePlus CreateAsset ===")
    aid = bp.create_asset(GROUP_ID, download_url, "Video", name=ASSET_NAME)
    print(f"  asset_id: {aid}, polling...")
    bp.poll_asset(aid, timeout=300)
    print(f"  ✓ active")

    print(f"\n=== DONE ===")
    print(f"Name:       {ASSET_NAME}")
    print(f"Asset code: {aid}")
    print(f"Duration:   15s · 1920×1080")
    print(f"Use in prompts as: asset://{aid}")


if __name__ == "__main__":
    main()

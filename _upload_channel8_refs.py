#!/usr/bin/env python3
"""Upload Channel 8 Test Shoot 4 character refs to Drive + BytePlus."""
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

REFS = [
    ("EMPEROR",  "/Users/raymuschang/Downloads/channel8_refs/EMPEROR_5s.mp4"),
    ("ELDER",    "/Users/raymuschang/Downloads/channel8_refs/ELDER_5s.mp4"),
    ("MINISTER", "/Users/raymuschang/Downloads/channel8_refs/MINISTER_5s.mp4"),
    ("PRINCESS", "/Users/raymuschang/Downloads/channel8_refs/PRINCESS_5s.mp4"),
]


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    # Create dedicated folder at Drive root for Channel 8 test shoot refs
    folder_name = "Channel 8 Test Shoot — Character Refs"
    q = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()
    if res.get("files"):
        folder_id = res["files"][0]["id"]
        print(f"Reusing folder: {folder_id}")
    else:
        f = drive.files().create(
            body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        folder_id = f["id"]
        drive.permissions().create(fileId=folder_id, body={"role": "reader", "type": "anyone"}, fields="id").execute()
        print(f"Created folder: {folder_id}")

    results = []
    for name, local in REFS:
        print(f"\n=== {name} ===")

        # Drive upload
        media = MediaFileUpload(local, mimetype="video/mp4", resumable=True, chunksize=1024*1024)
        f = drive.files().create(
            body={"name": f"{name}_5s.mp4", "parents": [folder_id]},
            media_body=media, fields="id,webViewLink",
        ).execute()
        drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
        fid = f["id"]
        drive_view = f["webViewLink"]
        download_url = f"https://drive.google.com/uc?export=download&id={fid}"
        print(f"  drive: {drive_view}")

        # BytePlus
        aid = bp.create_asset(GROUP_ID, download_url, "Video", name=name)
        bp.poll_asset(aid, timeout=300)
        print(f"  asset_id: {aid}")
        results.append((name, aid, drive_view))

    print(f"\n=== DONE ===")
    print(f"Drive folder: https://drive.google.com/drive/folders/{folder_id}\n")
    for name, aid, drive_view in results:
        print(f"  {name:<10} → asset://{aid}")


if __name__ == "__main__":
    main()

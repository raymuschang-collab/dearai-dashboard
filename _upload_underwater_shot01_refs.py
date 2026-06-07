#!/usr/bin/env python3
"""Upload shot 01 reskin refs (image + blocking video) to BytePlus."""
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


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    # Reuse the Channel 8 Test Shoot Drive folder
    q = "name='Channel 8 Test Shoot — Character Refs' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()
    parent = res["files"][0]["id"] if res.get("files") else None
    if not parent:
        # fallback: create folder
        f = drive.files().create(
            body={"name": "Channel 8 Underwater Refs", "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        parent = f["id"]
        drive.permissions().create(fileId=parent, body={"role": "reader", "type": "anyone"}, fields="id").execute()

    refs = [
        ("shot01_throne_look", "/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 01/shot 1.png", "Image"),
        ("shot01_blocking_ref", "/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 01/shot 01.mp4", "Video"),
    ]

    results = []
    for name, local, atype in refs:
        print(f"\n=== {name} ({atype}) ===")
        mime = "image/png" if atype == "Image" else "video/mp4"
        media = MediaFileUpload(local, mimetype=mime, resumable=True, chunksize=1024*1024)
        f = drive.files().create(
            body={"name": Path(local).name, "parents": [parent]},
            media_body=media, fields="id,webViewLink",
        ).execute()
        drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
        fid = f["id"]
        if atype == "Image":
            byteplus_url = f"https://lh3.googleusercontent.com/d/{fid}=w2048"
        else:
            byteplus_url = f"https://drive.google.com/uc?export=download&id={fid}"
        print(f"  drive: {f['webViewLink']}")

        aid = bp.create_asset(GROUP_ID, byteplus_url, atype, name=name)
        bp.poll_asset(aid, timeout=300)
        print(f"  asset_id: {aid}")
        results.append((name, aid))

    print(f"\n=== DONE ===")
    for name, aid in results:
        print(f"  {name:<22} → asset://{aid}")


if __name__ == "__main__":
    main()

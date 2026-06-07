#!/usr/bin/env python3
"""Upload shot 02 + shot 03 underwater refs to BytePlus."""
import os, sys, json
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
BASE = "/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits"


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    q = "name='Channel 8 Test Shoot — Character Refs' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()
    parent = res["files"][0]["id"]

    refs = [
        ("shot02_look_v1_no_soldiers", f"{BASE}/shot 02/shot 2b.png", "Image"),
        ("shot02_look_v2_with_soldiers", f"{BASE}/shot 02/shot 2a.png", "Image"),
        ("shot02_blocking_ref", f"{BASE}/shot 02/shot 02.mp4", "Video"),
        ("shot03_look_throne_kneeling", f"{BASE}/shot 03/shot 3.png", "Image"),
        ("shot03_blocking_ref", f"{BASE}/shot 03/shot 03.mp4", "Video"),
    ]

    results = {}
    for name, local, atype in refs:
        print(f"=== {name} ({atype}) ===")
        mime = "image/png" if atype == "Image" else "video/mp4"
        media = MediaFileUpload(local, mimetype=mime, resumable=True, chunksize=1024*1024)
        f = drive.files().create(
            body={"name": Path(local).name + f"::{name}", "parents": [parent]},
            media_body=media, fields="id,webViewLink",
        ).execute()
        drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
        fid = f["id"]
        url = (f"https://lh3.googleusercontent.com/d/{fid}=w2048" if atype == "Image"
               else f"https://drive.google.com/uc?export=download&id={fid}")
        aid = bp.create_asset(GROUP_ID, url, atype, name=name)
        bp.poll_asset(aid, timeout=300)
        print(f"  asset: {aid}")
        results[name] = aid

    print("\n=== ASSET CODES ===")
    print(json.dumps(results, indent=2))
    Path(HERE / ".underwater_shot02_03_codes.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

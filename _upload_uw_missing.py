#!/usr/bin/env python3
"""Re-upload missing underwater refs (shots 04, 06, 07, 08 + shot 14 audio-stripped)."""
import os, sys, json
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
BASE = "/Users/raymuschang/Documents/Video Editing/clients/Channel 8 Test Shoot/cuts/splits"


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Channel 8 Test Shoot — Character Refs' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    parent = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()["files"][0]["id"]

    refs = [
        ("shot04_blocking_v2", f"{BASE}/shot 04/shot 04.mp4", "Video"),
        ("shot04_first_reskin_v2", f"{BASE}/shot 04/shot4_firstframe.png", "Image"),
        ("shot04_end_reskin_v2", f"{BASE}/shot 04/shot4 end frame.png", "Image"),
        ("shot06_blocking_v2", f"{BASE}/shot 06/shot 06.mp4", "Video"),
        ("shot06_look_6b_v2", f"{BASE}/shot 06/shot 6b.png", "Image"),
        ("shot07_blocking_v2", f"{BASE}/shot 07/shot 07.mp4", "Video"),
        ("shot07_look_v2", f"{BASE}/shot 07/shot 7.png", "Image"),
        ("shot08_blocking_v2", f"{BASE}/shot 08/shot 08.mp4", "Video"),
        ("shot08_look_v2", f"{BASE}/shot 08/shot8_endframe.png", "Image"),
        # Shot 14 with audio stripped
        ("shot14_blocking_v2_noaudio", "/tmp/shot14_noaudio.mp4", "Video"),
        ("shot14_look_v2", f"{BASE}/shot 14/shot 14 firstframe.png", "Image"),
    ]

    # Existing codes from earlier partial run
    results = {
        "shot09_blocking": "asset-20260518000056-75kzn",
        "shot09_look":     "asset-20260518000106-nbcsg",
        "shot10_blocking": "asset-20260518000116-54gbw",
        "shot10_look":     "asset-20260518000126-wvb8d",
        "shot12_blocking": "asset-20260518000137-d8zn6",
        "shot12_look":     "asset-20260518000147-jsmrz",
    }

    for name, local, atype in refs:
        if not Path(local).exists():
            print(f"⚠ MISSING: {local}")
            continue
        print(f"  {name} ({atype})")
        mime = "image/png" if atype == "Image" else "video/mp4"
        media = MediaFileUpload(local, mimetype=mime, resumable=True, chunksize=1024*1024)
        f = drive.files().create(
            body={"name": f"{name}::{Path(local).name}", "parents": [parent]},
            media_body=media, fields="id,webViewLink",
        ).execute()
        drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
        fid = f["id"]
        url = (f"https://lh3.googleusercontent.com/d/{fid}=w2048" if atype == "Image"
               else f"https://drive.google.com/uc?export=download&id={fid}")
        aid = bp.create_asset(GROUP_ID, url, atype, name=name)
        bp.poll_asset(aid, timeout=300)
        # Strip the _v2 suffix when writing to results
        key = name.replace("_v2_noaudio", "").replace("_v2", "")
        results[key] = aid
        print(f"    → {aid}")

    out = Path(HERE / ".uw_remaining_codes.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"\n=== ALL CODES ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

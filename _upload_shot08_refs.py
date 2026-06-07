#!/usr/bin/env python3
"""Upload 4 fast-forwarded video refs (PALACE 3s, EMPEROR 3s, PRINCESS 3s, ELDER 3s)
+ shot 8 audio mp3 to Drive + BytePlus. Prints asset_ids for use in shot 08 fire script.
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

FF_DIR = Path("/Users/raymuschang/Downloads/channel8_refs/3s_ff")
SHOT8_DIR = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 08")

REFS = [
    ("video/mp4",  FF_DIR / "PALACE_3s.mp4",        "UNDERWATER PALACE 3s (5x FF)",      "Video"),
    ("video/mp4",  FF_DIR / "EMPEROR_3s.mp4",       "EMPEROR 3s (1.49x FF)",             "Video"),
    ("video/mp4",  FF_DIR / "PRINCESS_3s.mp4",      "PRINCESS 3s (1.42x FF)",            "Video"),
    ("video/mp4",  FF_DIR / "ELDER_3s.mp4",         "ELDER 3s (1.49x FF)",               "Video"),
    ("audio/mpeg", SHOT8_DIR / "Shot 8_Audio.mp3",  "SHOT8 DIALOGUE",                    "Audio"),
]


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    folder_name = "Channel 8 Test Shoot — Character Refs"
    res = drive.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)", pageSize=5,
    ).execute()
    parent = res["files"][0]["id"] if res.get("files") else None
    if not parent:
        sys.exit("Channel 8 folder not found")
    print(f"Drive parent: {parent}")

    results = []
    for mime, local, label, kind in REFS:
        print(f"\n=== {label} ===")
        media = MediaFileUpload(str(local), mimetype=mime, resumable=True, chunksize=1024*1024)
        f = drive.files().create(
            body={"name": local.name, "parents": [parent]},
            media_body=media, fields="id,webViewLink",
        ).execute()
        drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
        fid = f["id"]
        dl = f"https://drive.google.com/uc?export=download&id={fid}"
        aid = bp.create_asset(GROUP_ID, dl, kind, name=label)
        bp.poll_asset(aid, timeout=300)
        print(f"  ✓ {aid}")
        results.append((label, aid))

    print("\n\n=== ASSET CODES ===")
    for label, aid in results:
        print(f'  {label:40} asset://{aid}')


if __name__ == "__main__":
    main()

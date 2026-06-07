#!/usr/bin/env python3
"""Upload Claude.ai laptop-screen screenshot to Drive + BytePlus as an image asset."""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials
import byteplus_asset_v2 as bp
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"
SOT_SHEET = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
GROUP_ID = "group-20260505195134-wqx2b"
LOCAL_PNG = "/Users/raymuschang/Downloads/Screenshot 2026-05-16 at 10.07.28 PM.png"
ASSET_NAME = "LAPTOP SCREEN (Claude.ai)"


def get_or_create_subfolder(drive, parent, name):
    safe = name.replace("'", "\\'")
    q = f"'{parent}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='{safe}'"
    res = drive.files().list(q=q, fields="files(id)").execute()
    if res.get("files"): return res["files"][0]["id"]
    f = drive.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}, fields="id").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    return f["id"]


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SOT_SHEET)
    al = sh.worksheet("Asset Library")

    # 1. Drive upload
    print("=== Step 1: Drive upload ===")
    refs_folder = get_or_create_subfolder(drive, SHOW_FOLDER, "screen-assets")
    media = MediaFileUpload(LOCAL_PNG, mimetype="image/png", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": "claude-ai-laptop-screen.png", "parents": [refs_folder]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    drive_view = f["webViewLink"]
    lh3_url = f"https://lh3.googleusercontent.com/d/{fid}=w2048"
    print(f"  drive_view: {drive_view}")

    # 2. BytePlus CreateAsset (Image)
    print("\n=== Step 2: BytePlus CreateAsset ===")
    aid = bp.create_asset(GROUP_ID, lh3_url, "Image", name=ASSET_NAME)
    print(f"  asset_id: {aid}, polling...")
    bp.poll_asset(aid, timeout=300)
    print(f"  ✓ active")

    # 3. Asset Library writeback
    print("\n=== Step 3: Asset Library writeback ===")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_row = [
        ASSET_NAME,    # A: Bible Entry Name
        "PROPS",       # B: Bible Tab
        aid,           # C: Asset Code
        drive_view,    # D: Source URL
        "image",       # E: Asset Type
        "Uploaded",    # F: Status
        ts,            # G: Uploaded At
        "Set 6",       # H: First Used Shot
    ]
    al.append_rows([new_row], value_input_option="USER_ENTERED")
    print(f"  wrote 1 row to Asset Library")

    print(f"\n=== DONE ===")
    print(f"Name:       {ASSET_NAME}")
    print(f"Asset code: {aid}")
    print(f"Use in prompts as: asset://{aid}")


if __name__ == "__main__":
    main()

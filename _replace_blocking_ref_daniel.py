#!/usr/bin/env python3
"""Replace 'blocking references' (Daniel studio): swap 15s → 4s (3-7s segment)."""
import os, sys
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
LOCAL_MP4 = "/Users/raymuschang/Downloads/daniel_studio_blocking_3to7s.mp4"
ASSET_NAME = "blocking references"
OLD_ASSET_CODE = "asset-20260516234440-d5bdp"


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

    print("=== Step 1: Drive upload ===")
    refs_folder = get_or_create_subfolder(drive, SHOW_FOLDER, "blocking-refs")
    media = MediaFileUpload(LOCAL_MP4, mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": "daniel-studio-blocking-3to7s-4s.mp4", "parents": [refs_folder]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    drive_view = f["webViewLink"]
    download_url = f"https://drive.google.com/uc?export=download&id={fid}"
    print(f"  drive_view: {drive_view}")

    print("\n=== Step 2: BytePlus CreateAsset ===")
    aid = bp.create_asset(GROUP_ID, download_url, "Video", name=ASSET_NAME)
    print(f"  asset_id: {aid}, polling...")
    bp.poll_asset(aid, timeout=300)
    print(f"  ✓ active")

    print("\n=== Step 3: Mark old asset row as Replaced ===")
    all_rows = al.get_all_values()
    found = False
    for idx, row in enumerate(all_rows, start=1):
        if len(row) > 2 and row[2] == OLD_ASSET_CODE:
            print(f"  found old asset at row {idx}, setting Status → Replaced")
            al.update(range_name=f"F{idx}", values=[["Replaced"]], value_input_option="USER_ENTERED")
            found = True
            break
    if not found:
        print(f"  ⚠ old asset code {OLD_ASSET_CODE} not found in Asset Library")

    print("\n=== Step 4: Asset Library writeback (new row) ===")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_row = [ASSET_NAME, "LOCATIONS", aid, drive_view, "video", "Uploaded", ts, "Set 4"]
    al.append_rows([new_row], value_input_option="USER_ENTERED")
    print(f"  wrote 1 row to Asset Library")

    print(f"\n=== DONE ===")
    print(f"Name:       {ASSET_NAME}")
    print(f"Old code:   {OLD_ASSET_CODE}  → Status=Replaced")
    print(f"New code:   {aid}")
    print(f"Duration:   4s (3-7s segment — Daniel enters with tea + sets mug)")
    print(f"Use in prompts as: asset://{aid}")


if __name__ == "__main__":
    main()

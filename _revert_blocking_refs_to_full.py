#!/usr/bin/env python3
"""Revert 3 blocking references to their full-length versions."""
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

DANIEL_15S = "asset-20260516234440-d5bdp"
DANIEL_4S  = "asset-20260517001509-zdkzc"
TRANSFORMATION_4S = "asset-20260516235138-v6bcl"
TRANSFORMATION_FULL_LOCAL = "/Users/raymuschang/Desktop/Claude Ad — Why I Almost Quit Generated Videos/set-10-11-transformation-saturday-480p-15s.mp4"


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

    all_rows = al.get_all_values()

    def find_row(asset_code):
        for idx, row in enumerate(all_rows, start=1):
            if len(row) > 2 and row[2] == asset_code:
                return idx
        return None

    print("=== Step 1: Daniel — flip 15s back to Uploaded, 4s to Replaced ===")
    r15 = find_row(DANIEL_15S)
    r4 = find_row(DANIEL_4S)
    print(f"  Daniel 15s at row {r15} → Status: Uploaded")
    print(f"  Daniel 4s  at row {r4}  → Status: Replaced")
    al.batch_update([
        {"range": f"F{r15}", "values": [["Uploaded"]]},
        {"range": f"F{r4}",  "values": [["Replaced"]]},
    ], value_input_option="USER_ENTERED")

    print("\n=== Step 2: Carmen Apt — already 15s, no action needed ===")
    print("  asset-20260516234623-jq488 stays Uploaded")

    print("\n=== Step 3: Transformation — upload full 15s as new asset ===")
    refs_folder = get_or_create_subfolder(drive, SHOW_FOLDER, "blocking-refs")
    media = MediaFileUpload(TRANSFORMATION_FULL_LOCAL, mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": "transformation-saturday-blocking-15s-full.mp4", "parents": [refs_folder]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    drive_view = f["webViewLink"]
    download_url = f"https://drive.google.com/uc?export=download&id={fid}"
    print(f"  drive_view: {drive_view}")

    print("\n  BytePlus CreateAsset (Video, 15s)...")
    aid = bp.create_asset(GROUP_ID, download_url, "Video", name="blocking references (Transformation + Saturday)")
    print(f"  asset_id: {aid}, polling...")
    bp.poll_asset(aid, timeout=300)
    print(f"  ✓ active")

    # Mark old 4s as Replaced
    r_trans = find_row(TRANSFORMATION_4S)
    print(f"\n  Transformation 4s at row {r_trans} → Status: Replaced")
    al.update(range_name=f"F{r_trans}", values=[["Replaced"]], value_input_option="USER_ENTERED")

    # Add new 15s row
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_row = [
        "blocking references (Transformation + Saturday)", "LOCATIONS", aid, drive_view,
        "video", "Uploaded", ts, "Set 10/11",
    ]
    al.append_rows([new_row], value_input_option="USER_ENTERED")
    print(f"  ✓ appended 15s row to Asset Library")

    print(f"\n=== DONE — Full-length blocking refs active ===")
    print(f"  Daniel Studio       → asset://{DANIEL_15S}  (15s, 9 shots)")
    print(f"  Carmen Apartment    → asset://asset-20260516234623-jq488  (15s, 5 shots)")
    print(f"  Transformation+Sat  → asset://{aid}  (15s, 5 shots) [NEW]")


if __name__ == "__main__":
    main()

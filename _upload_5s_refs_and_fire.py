#!/usr/bin/env python3
"""Upload 4.9s-trimmed Grace/Mom/Dad refs to Drive + BytePlus, write to Asset
Library, then fire parents scene with all 3 anchored."""
import io, json, os, re, sys, time
from pathlib import Path
import requests
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402
import byteplus_asset_v2 as bp  # noqa: E402

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]
SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"
SOT_SHEET = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
GROUP_ID = "group-20260505195134-wqx2b"

REFS_TO_UPLOAD = [
    {"local": "/Users/raymuschang/Downloads/GRACE_5s.mp4", "name": "GRACE TAN_5s", "bible_name": "GRACE TAN"},
    {"local": "/Users/raymuschang/Downloads/GRACE_MOM_5s.mp4", "name": "GRACE'S MOM_5s", "bible_name": "GRACE'S MOM"},
    {"local": "/Users/raymuschang/Downloads/GRACE_DAD_5s.mp4", "name": "GRACE'S DAD_5s", "bible_name": "GRACE'S DAD"},
]


def get_or_create_subfolder(drive, parent: str, name: str) -> str:
    safe = name.replace("'", "\\'")
    q = f"'{parent}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='{safe}'"
    res = drive.files().list(q=q, fields="files(id)").execute()
    if res.get("files"): return res["files"][0]["id"]
    f = drive.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}, fields="id").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    return f["id"]


def upload_to_drive(drive, folder_id: str, local_path: str, name: str) -> dict:
    """Upload a local MP4 to Drive; return {id, drive_view, download_url}."""
    media = MediaFileUpload(local_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": name, "parents": [folder_id]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    return {
        "id": fid,
        "drive_view": f["webViewLink"],
        "download_url": f"https://drive.google.com/uc?export=download&id={fid}",
    }


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SOT_SHEET)
    al = sh.worksheet("Asset Library")

    # 1. Create the char-refs-5s subfolder
    print("=== Step 1: Drive subfolder ===")
    refs_folder = get_or_create_subfolder(drive, SHOW_FOLDER, "character-refs-5s")
    print(f"  folder_id: {refs_folder}")

    # 2. Upload each trimmed MP4 to Drive
    print("\n=== Step 2: Upload trimmed MP4s to Drive ===")
    for r in REFS_TO_UPLOAD:
        d = upload_to_drive(drive, refs_folder, r["local"], Path(r["local"]).name)
        r["drive_id"] = d["id"]
        r["drive_view"] = d["drive_view"]
        r["download_url"] = d["download_url"]
        print(f"  {r['name']:<20} → {d['drive_view']}")

    # 3. CreateAsset on BytePlus + poll until Active
    print("\n=== Step 3: BytePlus CreateAsset ===")
    for r in REFS_TO_UPLOAD:
        print(f"  uploading {r['name']}...")
        aid = bp.create_asset(GROUP_ID, r["download_url"], "Video", name=r["name"])
        r["asset_code"] = aid
        print(f"    asset_id: {aid}, polling...")
        bp.poll_asset(aid, timeout=300)
        print(f"    ✓ active")

    # 4. Append to Asset Library
    print("\n=== Step 4: Asset Library writeback ===")
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_rows = []
    for r in REFS_TO_UPLOAD:
        new_rows.append([
            r["bible_name"],     # A: Bible Entry Name (canonical, NOT _5s — vidgen matches by this)
            "CHARACTERS",        # B: Bible Tab
            r["asset_code"],     # C: Asset Code
            r["drive_view"],     # D: Source URL
            "video",             # E: Asset Type
            "Uploaded",          # F: Status
            ts,                  # G: Uploaded At
            "Set 2/3",           # H: First Used Shot
        ])
    # Append at end
    al.append_rows(new_rows, value_input_option="USER_ENTERED")
    print(f"  wrote {len(new_rows)} rows to Asset Library")

    # 5. Print summary for next-step fire
    print("\n=== Step 5: Summary ===")
    for r in REFS_TO_UPLOAD:
        print(f"  {r['name']:<20} → asset://{r['asset_code']}")

    # Save asset codes for the fire script
    out_path = HERE / ".5s_asset_codes.json"
    out_path.write_text(json.dumps({r["name"]: r["asset_code"] for r in REFS_TO_UPLOAD}, indent=2))
    print(f"\n  codes saved to {out_path}")
    print("\nReady to fire — run _fire_set2_parents_v6_all3anchored.py")


if __name__ == "__main__":
    main()

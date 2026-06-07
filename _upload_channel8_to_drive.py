#!/usr/bin/env python3
"""Mirror the entire Channel 8 Test Shoot/ folder to Drive (raymus@dearai.com)."""
import os, sys, mimetypes, time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
env = Path(HERE / ".env")
for line in env.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

LOCAL_ROOT = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot")
SKIP_NAMES = {".DS_Store"}

creds = get_credentials()
drive = build("drive", "v3", credentials=creds)


def find_or_create_folder(name: str, parent_id: str | None = None) -> str:
    q = f"name='{name.replace(chr(39), chr(92)+chr(39))}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    found = drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    if found:
        return found[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    return drive.files().create(body=body, fields="id").execute()["id"]


def upload_file(local: Path, parent_id: str) -> None:
    if local.name in SKIP_NAMES:
        return
    mime = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
    size_mb = local.stat().st_size / 1024 / 1024
    print(f"  uploading {local.relative_to(LOCAL_ROOT)} ({size_mb:.1f}MB)...", flush=True)
    media = MediaFileUpload(str(local), mimetype=mime, resumable=size_mb > 5, chunksize=4*1024*1024)
    t0 = time.time()
    for attempt in range(3):
        try:
            drive.files().create(body={"name": local.name, "parents": [parent_id]},
                                  media_body=media, fields="id").execute()
            dt = time.time() - t0
            print(f"    ✓ {dt:.1f}s ({size_mb/dt:.1f}MB/s)", flush=True)
            return
        except Exception as e:
            print(f"    ⚠ attempt {attempt+1} failed: {e!s:.150}", flush=True)
            time.sleep(5 * (attempt + 1))
    print(f"    ✗ SKIPPED after 3 attempts: {local}", flush=True)


def mirror(local_dir: Path, drive_parent_id: str) -> None:
    for entry in sorted(local_dir.iterdir()):
        if entry.name in SKIP_NAMES:
            continue
        if entry.is_dir():
            sub_id = find_or_create_folder(entry.name, drive_parent_id)
            mirror(entry, sub_id)
        else:
            upload_file(entry, drive_parent_id)


# Top-level folder in Drive root
print(f"=== creating top folder ===")
top_id = find_or_create_folder(LOCAL_ROOT.name)
print(f"  folder_id: {top_id}")
print(f"  URL: https://drive.google.com/drive/folders/{top_id}")

start = time.time()
mirror(LOCAL_ROOT, top_id)
print(f"\n✓ mirror complete in {(time.time()-start)/60:.1f}m")
print(f"\nDRIVE URL: https://drive.google.com/drive/folders/{top_id}")

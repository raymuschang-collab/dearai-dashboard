#!/usr/bin/env python3
"""Walk the Channel 8 Drive folder and emit {relative_path: file_id} JSON."""
import json, os, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
env = Path(HERE / ".env")
for line in env.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
from auth import get_credentials
from googleapiclient.discovery import build

TOP_ID = "1WVRSmcaRNljz9P83WXQw_8sTi-PM9WO0"

creds = get_credentials()
drive = build("drive", "v3", credentials=creds)


def walk(parent_id, prefix=""):
    """Yield (relative_path, file_id, mime_type)."""
    page_token = None
    while True:
        resp = drive.files().list(
            q=f"'{parent_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType)",
            pageSize=200,
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            path = f"{prefix}/{f['name']}" if prefix else f["name"]
            if f["mimeType"] == "application/vnd.google-apps.folder":
                yield from walk(f["id"], path)
            else:
                yield (path, f["id"], f["mimeType"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


result = {}
for path, fid, mime in walk(TOP_ID):
    if mime.startswith(("video/", "image/", "audio/")) or path.endswith(".mp4"):
        result[path] = fid

print(json.dumps(result, indent=2, sort_keys=True))
Path(".channel8_drive_files.json").write_text(json.dumps(result, indent=2, sort_keys=True))
print(f"\n=== {len(result)} media files indexed → .channel8_drive_files.json ===", file=sys.stderr)

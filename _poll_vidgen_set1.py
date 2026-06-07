#!/usr/bin/env python3
"""Long-poll vidgen task until done — handles BytePlus slow-queue case
(can take 10-30 min during peak). On succeeded, downloads MP4, uploads
to Drive, writes URL back to SP, saves local copy."""
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import gspread
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

TASK_ID = "cgt-20260516171903-5gwhq"
SHEET_ID = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"
SET_NUM = 1
SLOT = 1
RESOLUTION = "480p"
DURATION = 15

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]


def poll(max_wait: int = 1800):
    """30-min total cap."""
    start = time.time()
    last = None
    while time.time() - start < max_wait:
        r = requests.get(
            f"{ARK_BASE}/contents/generations/tasks/{TASK_ID}",
            headers={"Authorization": f"Bearer {ARK_KEY}"},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  [{int(time.time()-start)}s] poll HTTP {r.status_code}", flush=True)
            time.sleep(30)
            continue
        resp = r.json()
        status = resp.get("status")
        if status != last:
            print(f"  [{int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status in ("succeeded", "completed", "success"):
            return resp
        if status in ("failed", "expired", "cancelled"):
            print(f"  ✗ terminal failure: {json.dumps(resp)[:500]}")
            sys.exit(1)
        time.sleep(30)
    print(f"  ⚠ 30-min cap exceeded — task still running. Re-run script to keep polling.")
    sys.exit(2)


def get_or_create_folder(drive, parent: str, name: str) -> str:
    safe = name.replace("'", "\\'")
    q = (f"'{parent}' in parents and trashed=false "
         f"and mimeType='application/vnd.google-apps.folder' and name='{safe}'")
    res = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()
    if res.get("files"):
        return res["files"][0]["id"]
    f = drive.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]},
        fields="id",
    ).execute()
    drive.permissions().create(
        fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id",
    ).execute()
    return f["id"]


def main():
    print(f"=== Polling {TASK_ID} ===")
    result = poll()

    # Extract video URL from result
    video_url = None
    content = result.get("content", {})
    if isinstance(content, dict):
        v = content.get("video_url")
        if isinstance(v, str):
            video_url = v
        elif isinstance(v, dict):
            video_url = v.get("url")
    # Fallback patterns
    if not video_url:
        results = result.get("results") or {}
        if isinstance(results, dict):
            video_url = results.get("video_url") or results.get("url")
    if not video_url:
        # Search nested
        text = json.dumps(result)
        m = re.search(r'https://[^\s"\']*\.mp4[^\s"\']*', text)
        if m:
            video_url = m.group(0)
    if not video_url:
        print(f"  ✗ no video_url in result: {json.dumps(result)[:1500]}")
        sys.exit(1)
    print(f"  ✓ video_url: {video_url[:80]}...")

    # Download
    print(f"  Downloading...")
    r = requests.get(video_url, timeout=600)
    r.raise_for_status()
    data = r.content
    print(f"  ✓ {len(data)//1024}KB downloaded")

    # Save local
    local_dir = Path("/Users/raymuschang/Desktop/Claude Ad — Why I Almost Quit Generated Videos")
    local_dir.mkdir(parents=True, exist_ok=True)
    local_fname = f"set-{SET_NUM:02d}-iter-{SLOT}-{RESOLUTION}-{DURATION}s.mp4"
    local_path = local_dir / local_fname
    local_path.write_bytes(data)
    print(f"  ✓ local: {local_path}")

    # Upload to Drive
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    videos_folder = get_or_create_folder(drive, SHOW_FOLDER, "videos")
    set_folder = get_or_create_folder(drive, videos_folder, f"set-{SET_NUM:02d}")
    drive_fname = f"video-iteration-{SLOT}-{RESOLUTION}-{DURATION}s.mp4"
    # Trash existing same-name
    res = drive.files().list(
        q=f"'{set_folder}' in parents and trashed=false and name='{drive_fname}'",
        fields="files(id)").execute()
    for f in res.get("files", []):
        drive.files().delete(fileId=f["id"]).execute()
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": drive_fname, "parents": [set_folder]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(
        fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id",
    ).execute()
    drive_view = f["webViewLink"]
    print(f"  ✓ Drive: {drive_view}")

    # Write back to SP!M11 (slot 1 → col M)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    sp = sh.worksheet("Storyboard Prompts")
    sp.update(range_name=f"M11", values=[[drive_view]], value_input_option="USER_ENTERED")
    print(f"  ✓ SP!M11 written")

    # Expense log
    log_path = HERE / ".byteplus_expense.json"
    try:
        log = json.loads(log_path.read_text()) if log_path.exists() else {"entries": [], "cumulative_usd": 0.0}
    except Exception:
        log = {"entries": [], "cumulative_usd": 0.0}
    cost = round(0.05 * DURATION, 2)  # ~$0.05/s for 480p Pro
    log["entries"].append({
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": TASK_ID, "model": "dreamina-seedance-2-0-260128",
        "duration": DURATION, "resolution": RESOLUTION, "aspect": "9:16",
        "set": SET_NUM, "slot": SLOT, "estimated_usd": cost,
    })
    log["cumulative_usd"] = round(sum(e["estimated_usd"] for e in log["entries"]), 2)
    log_path.write_text(json.dumps(log, indent=2))

    # Remove from pending
    pending_path = HERE / ".byteplus_pending.json"
    if pending_path.exists():
        try:
            pending = json.loads(pending_path.read_text())
            pending = [p for p in pending if p.get("task_id") != TASK_ID]
            pending_path.write_text(json.dumps(pending, indent=2))
        except Exception:
            pass

    print(f"\n=== DONE ===")
    print(f"Drive: {drive_view}")
    print(f"Local: {local_path}")


if __name__ == "__main__":
    main()

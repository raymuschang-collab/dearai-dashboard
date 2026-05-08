#!/usr/bin/env python3
"""
byteplus_vidgen_resume.py — Crash-recovery for vidgen tasks.

Reads `.byteplus_pending.json` (written by byteplus_vidgen.py at submit
time) and walks each entry. For tasks BytePlus reports as `succeeded`,
runs the post-submit pipeline that the original subprocess didn't finish:
download MP4 → upload to Drive → write SP!M/N. Successfully-recovered
tasks get removed from the pending ledger.

This is the safety net for the failure mode where Render redeploys (or
gunicorn worker bounces, or OOM kills) the original byteplus_vidgen.py
subprocess between BytePlus succeed and the writeback step. Without it
the videos exist on BytePlus but never reach the sheet — the team sees
"watcher gave up" red banners on jobs that actually completed.

Usage:
    python3 byteplus_vidgen_resume.py                # resume all pending
    python3 byteplus_vidgen_resume.py --task-id <id>  # resume one
    python3 byteplus_vidgen_resume.py --dry-run       # show what would resume

Idempotent. Safe to run on a cron / from /api/vidgen-resume / manually.
"""
from __future__ import annotations

import argparse
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
from dotenv import load_dotenv
from googleapiclient.discovery import build as gbuild
from googleapiclient.http import MediaIoBaseUpload

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))
from auth import get_credentials  # type: ignore

ARK_API_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = os.getenv("BYTEPLUS_ARK_BASE",
                      "https://ark.ap-southeast.bytepluses.com/api/v3")
PENDING_LOG = HERE / ".byteplus_pending.json"

SLOT_TO_COL = {1: "M", 2: "N"}


def _load_pending() -> dict:
    if not PENDING_LOG.exists():
        return {"pending": []}
    try:
        d = json.loads(PENDING_LOG.read_text())
        if not isinstance(d, dict) or "pending" not in d:
            return {"pending": []}
        return d
    except Exception:
        return {"pending": []}


def _save_pending(data: dict):
    PENDING_LOG.write_text(json.dumps(data, indent=2))


def _drop_pending(task_id: str):
    data = _load_pending()
    before = len(data["pending"])
    data["pending"] = [e for e in data["pending"]
                        if e.get("task_id") != task_id]
    if len(data["pending"]) != before:
        _save_pending(data)


def get_byteplus_task(task_id: str) -> dict | None:
    """GET BytePlus task. Returns parsed JSON or None on error."""
    url = f"{ARK_BASE}/contents/generations/tasks/{task_id}"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {ARK_API_KEY}"},
                         timeout=30)
        if r.status_code != 200:
            print(f"    ✗ GetTask {task_id}: {r.status_code} {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"    ✗ GetTask {task_id} exception: {e}")
        return None


def get_or_create_folder(drive, parent: str, name: str) -> str:
    """Find or create a Drive folder under `parent`. Returns folder id.
    Sets anyone-with-link reader on creation so the gallery can pull
    thumbs without per-user OAuth."""
    safe = name.replace("'", "\\'")
    q = (f"'{parent}' in parents and trashed=false and name='{safe}' "
         f"and mimeType='application/vnd.google-apps.folder'")
    res = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if res:
        return res[0]["id"]
    fid = drive.files().create(
        body={"name": name,
              "mimeType": "application/vnd.google-apps.folder",
              "parents": [parent]},
        fields="id").execute()["id"]
    drive.permissions().create(fileId=fid,
        body={"role": "reader", "type": "anyone"}, fields="id").execute()
    return fid


def archive_existing_same_name(drive, set_folder: str, fname: str):
    """Move any existing file with this name into a sibling archive/
    folder, prefixed with timestamp. Same convention as byteplus_vidgen.py
    so re-runs don't clobber prior versions."""
    q = f"'{set_folder}' in parents and trashed=false and name='{fname}'"
    existing = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if not existing:
        return
    archive_id = get_or_create_folder(drive, set_folder, "archive")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for ex in existing:
        drive.files().update(fileId=ex["id"], addParents=archive_id,
                              removeParents=set_folder,
                              body={"name": f"{ts}_{fname}"}).execute()


def complete_task(entry: dict, dry_run: bool = False) -> str:
    """Run the post-submit pipeline (download → Drive → sheet) for a
    succeeded task. Returns one of:
        "done"       — sheet write succeeded, entry should be dropped
        "still_running" — task not done, leave entry alone
        "failed"     — task failed terminally, drop entry
        "error"      — recoverable error, leave entry for next run
    """
    task_id = entry["task_id"]
    set_n = entry["set"]
    slot = entry["slot"]
    sheet_id = entry["sheet"]
    duration = entry.get("duration", 15)
    resolution = entry.get("resolution", "480p")

    print(f"\n  → resuming {task_id} (set {set_n} slot {slot})…")
    task = get_byteplus_task(task_id)
    if task is None:
        return "error"

    status = task.get("status", "")
    print(f"    BytePlus status: {status}")

    if status in ("running", "pending", "queued", "submitted", "in_progress"):
        return "still_running"
    if status in ("failed", "expired", "cancelled"):
        print(f"    ✗ task terminally failed — dropping from pending")
        return "failed"
    if status not in ("succeeded", "completed", "success"):
        print(f"    ⚠ unknown status {status!r} — leaving for retry")
        return "error"

    target_col = SLOT_TO_COL[slot]
    target_row = 10 + set_n

    # Auth once for everything that follows (sheet read, sheet write,
    # Drive ops). Cached in locals; only one creds call.
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet("Storyboard Prompts")
    except Exception as e:
        print(f"    ✗ couldn't auth/open sheet: {e}")
        return "error"

    # Idempotency check — if SP!M/N already holds a Drive URL, the
    # writeback ALREADY happened (original subprocess just died before
    # remove_pending). Skip re-download to save bandwidth + avoid the
    # archive churn from re-upload.
    try:
        existing = ws.acell(f"{target_col}{target_row}",
                             value_render_option="FORMATTED_VALUE").value or ""
        if existing.strip().startswith("http"):
            print(f"    ✓ SP!{target_col}{target_row} already populated — skipping")
            return "done"
    except Exception:
        pass  # cell read failed; try the full pipeline

    video_url = (task.get("content", {}).get("video_url")
                  or task.get("video_url")
                  or task.get("data", {}).get("video_url")
                  or task.get("results", {}).get("video_url"))
    if not video_url:
        print(f"    ✗ task succeeded but no video_url found in response")
        return "error"

    if dry_run:
        print(f"    [dry-run] would download + write to SP!{target_col}{target_row}")
        return "done"

    # Download MP4 (24h expiry on BytePlus's TOS link)
    print(f"    downloading MP4…")
    try:
        mp4 = requests.get(video_url, timeout=300).content
    except Exception as e:
        print(f"    ✗ download failed: {e}")
        return "error"
    print(f"    {len(mp4)/(1024*1024):.2f} MB")

    drive = gbuild("drive", "v3", credentials=creds)

    # Resolve <show>/videos/set-NN/
    try:
        sheet_meta = drive.files().get(fileId=sheet_id, fields="parents").execute()
        show_folder = sheet_meta["parents"][0]
        videos_folder = get_or_create_folder(drive, show_folder, "videos")
        set_folder = get_or_create_folder(drive, videos_folder, f"set-{set_n:02d}")
        drive.permissions().create(fileId=set_folder,
            body={"role": "reader", "type": "anyone"}, fields="id").execute()
    except Exception as e:
        print(f"    ✗ Drive folder resolution failed: {e}")
        return "error"

    fname = f"video-iteration-{slot}-{resolution}-{duration}s.mp4"
    archive_existing_same_name(drive, set_folder, fname)

    media = MediaIoBaseUpload(io.BytesIO(mp4), mimetype="video/mp4", resumable=False)
    try:
        new_file = drive.files().create(
            body={"name": fname, "parents": [set_folder]}, media_body=media,
            fields="id,webViewLink").execute()
        drive.permissions().create(fileId=new_file["id"],
            body={"role": "reader", "type": "anyone"}, fields="id").execute()
    except Exception as e:
        print(f"    ✗ Drive upload failed: {e}")
        return "error"
    print(f"    ✓ Drive: {new_file['webViewLink']}")

    target_col = SLOT_TO_COL[slot]
    target_row = 10 + set_n
    try:
        ws.update(values=[[new_file["webViewLink"]]],
                   range_name=f"{target_col}{target_row}",
                   value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"    ✗ sheet write failed: {e}")
        return "error"
    print(f"    ✓ Storyboard Prompts!{target_col}{target_row} written")
    return "done"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", help="Resume just this task_id")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would resume without writing")
    args = ap.parse_args()

    if not ARK_API_KEY:
        sys.exit("BYTEPLUS_ARK_API_KEY not set")

    data = _load_pending()
    pending = data.get("pending", [])
    if args.task_id:
        pending = [e for e in pending if e.get("task_id") == args.task_id]
        if not pending:
            sys.exit(f"task_id {args.task_id} not in pending log")

    if not pending:
        print("No pending tasks to resume.")
        return

    print(f"Resuming {len(pending)} pending task(s)…")
    counts = {"done": 0, "still_running": 0, "failed": 0, "error": 0}
    for entry in list(pending):
        result = complete_task(entry, dry_run=args.dry_run)
        counts[result] = counts.get(result, 0) + 1
        if not args.dry_run and result in ("done", "failed"):
            _drop_pending(entry["task_id"])

    print("\n=== resume summary ===")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

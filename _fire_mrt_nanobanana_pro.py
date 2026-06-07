#!/usr/bin/env python3
"""One-off: fire fal-ai/nano-banana-pro for the MRT Train Carriage location ref.
Reads LOCATIONS!I7 (the prompt we just wrote), generates a 16:9 wide,
uploads to location-refs/MRT_Train_Carriage/, writes URL back to LOCATIONS!J7.

Standalone helper — Nanobanana PRO isn't wired into location_generate.py yet."""
from __future__ import annotations

import io
import os
import re
import sys
import time
from pathlib import Path

import fal_client
import gspread
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402

# Load FAL_KEY
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith("FAL_KEY="):
            os.environ["FAL_KEY"] = line.split("=", 1)[1].strip()
            break
assert os.getenv("FAL_KEY"), "FAL_KEY missing"

SHEET_ID = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"
ROW = 7  # LOCATIONS!7 = MRT Train Carriage


def fal_nano_banana_pro(prompt: str) -> bytes:
    """fal-ai/nano-banana-pro — premium image-gen tier from Google's nano-banana
    family. 16:9 wide, premium quality."""
    result = fal_client.subscribe(
        "fal-ai/nano-banana-pro",
        arguments={
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "num_images": 1,
        },
        with_logs=False,
    )
    if not result.get("images"):
        raise RuntimeError(f"No images returned: {result}")
    img_url = result["images"][0]["url"]
    r = requests.get(img_url, timeout=180)
    r.raise_for_status()
    return r.content


def get_or_create_folder(drive, parent_id: str, name: str) -> str:
    safe = name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and trashed=false "
        f"and mimeType='application/vnd.google-apps.folder' and name='{safe}'"
    )
    res = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()
    if res.get("files"):
        return res["files"][0]["id"]
    return drive.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()["id"]


def main():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet("LOCATIONS")

    row = ws.row_values(ROW)
    name = row[0] if row else ""
    prompt = row[8] if len(row) > 8 else ""
    if not prompt.strip():
        sys.exit(f"LOCATIONS!I{ROW} is empty — nothing to generate")
    print(f"=== {name} (row {ROW}) — fal-ai/nano-banana-pro ===")
    print(f"  prompt: {len(prompt)} chars")

    ws.update(range_name=f"L{ROW}", values=[["Generating"]])

    t0 = time.time()
    try:
        img = fal_nano_banana_pro(prompt)
        print(f"  ✓ generated {len(img)//1024}KB in {time.time()-t0:.1f}s")
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"  ✗ FAILED: {err}")
        ws.update(range_name=f"L{ROW}:M{ROW}",
                  values=[["Failed", err[:200]]],
                  value_input_option="USER_ENTERED")
        sys.exit(1)

    loc_root = get_or_create_folder(drive, SHOW_FOLDER, "location-refs")
    sub = get_or_create_folder(drive, loc_root, "MRT_Train_Carriage")

    fname = "MRT_Train_Carriage-wide-iter-1-nanobanana-pro.png"
    # Trash any existing same-name file
    res = drive.files().list(
        q=f"'{sub}' in parents and trashed=false and name='{fname}'",
        fields="files(id)",
    ).execute()
    for f in res.get("files", []):
        drive.files().update(fileId=f["id"], body={"trashed": True}).execute()

    media = MediaIoBaseUpload(io.BytesIO(img), mimetype="image/png", resumable=False)
    file = drive.files().create(
        body={"name": fname, "parents": [sub]},
        media_body=media,
        fields="id,webViewLink",
    ).execute()
    drive.permissions().create(
        fileId=file["id"],
        body={"role": "reader", "type": "anyone"},
        fields="id",
    ).execute()
    url = file["webViewLink"]
    print(f"  ✓ uploaded → {url}")

    # Write back to LOCATIONS J (Iter 1 URL), L (Status), M (Error)
    ws.update(
        range_name=f"J{ROW}:M{ROW}",
        values=[[url, "", "Done", ""]],
        value_input_option="USER_ENTERED",
    )
    print(f"\n✓ LOCATIONS!J{ROW} written")


if __name__ == "__main__":
    main()

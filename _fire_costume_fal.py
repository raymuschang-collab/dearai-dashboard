#!/usr/bin/env python3
"""One-off: fire fal-ai/flux-pro/v1.1 for two specific costume refs
(Grace's transformed outfit + pyjama bottoms), upload to Drive, write
URL back to COSTUME!G{row}.

Standalone helper — not wired into imggen_all_assets. Reads prompt from
COSTUME!F{row}, prepends an editorial-photography preamble so we don't
get game-render output (same fix we applied to LOCATIONS).
"""
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

# Load FAL_KEY from .env without dotenv (which broke earlier)
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith("FAL_KEY="):
            os.environ["FAL_KEY"] = line.split("=", 1)[1].strip()
            break
assert os.getenv("FAL_KEY"), "FAL_KEY missing"

SHEET_ID = "1mdelT9JijKv6tjTkA_xGgwCegNza2_o7_8Cms9Jxk7s"
SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"

# Locked floating-garment anchor that the production pipeline trained on.
# Garment hangs in mid-air on an invisible body, no humans, no skin, no
# face anywhere in the frame. nano-banana-2 honours this consistently;
# flux-pro biases toward inserting a model figure even with the same
# instruction, which is why the first pass drifted.
PREAMBLE = (
    "Costume reference photograph. The garment hangs in mid-air on an "
    "invisible mannequin (ghost-mannequin product photography), as if "
    "worn by a person who is fully transparent. "
    "NO humans. NO faces. NO skin. NO hands. NO model. "
    "Off-white seamless studio backdrop, soft directional lighting "
    "from a single north-facing window. Natural fabric texture, "
    "real product photography, NOT a game render. 1:1 square. "
)

TARGETS = [
    {
        "row": 7,
        "name": "Grace's transformed outfit",
        "filename": "grace_transformed_outfit.png",
    },
    {
        "row": 8,
        "name": "Grace's pyjama bottoms",
        "filename": "grace_pyjama_bottoms.png",
    },
]


def fal_nano_banana_2(prompt: str) -> bytes:
    """fal-ai/nano-banana-2 — locked model for bible costume/prop refs.

    Returns PNG bytes. The model respects 'no humans / invisible mannequin'
    framing consistently, which flux-pro doesn't."""
    result = fal_client.subscribe(
        "fal-ai/nano-banana-2",
        arguments={
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "resolution": "1K",
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
    ws = sh.worksheet("COSTUME")

    costume_folder = get_or_create_folder(drive, SHOW_FOLDER, "costume-refs")
    print(f"costume-refs/ id={costume_folder}")

    for t in TARGETS:
        row = t["row"]
        name = t["name"]
        prompt = ws.cell(row, 6).value or ""  # col F = Prompt
        if not prompt.strip():
            print(f"⚠ row {row} ({name}): no prompt — skipping")
            continue
        full = PREAMBLE + prompt
        print(f"\n=== {name} (row {row}) — fal-ai/nano-banana-2 ===")
        print(f"  prompt: {len(full)} chars")
        ws.update(range_name=f"I{row}", values=[["Generating"]])

        t0 = time.time()
        try:
            img = fal_nano_banana_2(full)
            print(f"  ✓ generated {len(img)//1024}KB in {time.time()-t0:.1f}s")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"  ✗ FAILED: {err}")
            ws.update(range_name=f"I{row}:J{row}",
                      values=[["Failed", err[:200]]],
                      value_input_option="USER_ENTERED")
            continue

        # Trash existing same-name file
        res = drive.files().list(
            q=f"'{costume_folder}' in parents and trashed=false and name='{t['filename']}'",
            fields="files(id)",
        ).execute()
        for f in res.get("files", []):
            drive.files().update(fileId=f["id"], body={"trashed": True}).execute()

        media = MediaIoBaseUpload(io.BytesIO(img), mimetype="image/png", resumable=False)
        file = drive.files().create(
            body={"name": t["filename"], "parents": [costume_folder]},
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

        # Write back to G (Iter 1 URL), I (Status), J (Error)
        ws.update(
            range_name=f"G{row}:J{row}",
            values=[[url, "", "Done", ""]],
            value_input_option="USER_ENTERED",
        )

    print("\nDone.")


if __name__ == "__main__":
    main()

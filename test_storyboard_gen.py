#!/usr/bin/env python3
"""
ONE-OFF TEST: generate 2 storyboard iterations for sets 1-3 of the canonical
reference Sheet, upload to Drive, write public URLs back to tab 2.

Validates the fal.ai nano-banana-2 → Drive upload → Sheet writeback pipeline
before scaffolding the full /storyboard-gen command.

Cost: 6 generations at ~$0.05 each = ~$0.30.

Schema impact: writes URLs to F (Iter 1) and G (Iter 2) of rows 2-4.
G is currently unused / unlabeled — that's fine for the test. The proper
schema bump (rename F → "Iter 1 URL", add G → "Iter 2 URL", H → "Error")
happens after the test passes.
"""
from __future__ import annotations

import io
import os
import sys
import time

import fal_client
import gspread
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from auth import get_credentials

load_dotenv()

SHEET_ID = "1-EPcY1YXstCfJm81MpVCpmuCdvN6O3awXWZ5H885T78"
TAB_NAME = "Storyboard Prompts"
MODEL = "fal-ai/nano-banana-2"
ASPECT_RATIO = "16:9"   # wide for 5-panel composite
RESOLUTION = "1K"       # default; storyboards are low-fi
SETS_TO_TEST = [1, 2, 3]
ITERATIONS_PER_SET = 2


def generate_image(prompt: str) -> bytes:
    """Call fal.ai nano-banana-2; return PNG bytes."""
    result = fal_client.subscribe(
        MODEL,
        arguments={
            "prompt": prompt,
            "aspect_ratio": ASPECT_RATIO,
            "resolution": RESOLUTION,
            "num_images": 1,
        },
        with_logs=False,
    )
    if not result.get("images"):
        raise RuntimeError(f"No images returned: {result}")
    img_url = result["images"][0]["url"]
    resp = requests.get(img_url, timeout=120)
    resp.raise_for_status()
    return resp.content


def upload_and_share(drive, folder_id: str, filename: str, content: bytes) -> str:
    """Upload PNG to a Drive folder, set anyone-with-link reader, return webViewLink."""
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="image/png", resumable=False)
    file = drive.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id,webViewLink",
    ).execute()
    drive.permissions().create(
        fileId=file["id"],
        body={"role": "reader", "type": "anyone"},
        fields="id",
    ).execute()
    return file["webViewLink"]


def main():
    if not os.getenv("FAL_KEY"):
        sys.exit("FAL_KEY not loaded — check .env")

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sh = gc.open_by_key(SHEET_ID)
    sb = sh.worksheet(TAB_NAME)

    # Read rows for sets 1-3 (sheet rows 2-4)
    rows = sb.get(
        f"A2:F{1 + max(SETS_TO_TEST)}",
        value_render_option="FORMATTED_VALUE",
    )

    overall_start = time.time()
    summary = []

    for i, row in enumerate(rows):
        if i + 1 not in SETS_TO_TEST:
            continue
        sheet_row = i + 2
        set_num = row[0] if len(row) > 0 else ""
        shot_range = row[1] if len(row) > 1 else ""
        prompt = row[2] if len(row) > 2 else ""
        folder_url = row[3] if len(row) > 3 else ""

        print(f"\n=== Set {set_num} — shots {shot_range} ===")
        if not prompt:
            print("  SKIP — empty prompt")
            summary.append((set_num, "skipped: empty prompt", []))
            continue
        if "/folders/" not in folder_url:
            print(f"  SKIP — bad folder URL: {folder_url!r}")
            summary.append((set_num, "skipped: bad folder url", []))
            continue
        folder_id = folder_url.split("/folders/")[1].rstrip("/")
        print(f"  prompt length: {len(prompt)} chars")
        print(f"  folder id: {folder_id}")

        # Mark as generating
        sb.update(range_name=f"E{sheet_row}", values=[["Generating"]])

        urls = []
        for it in range(1, ITERATIONS_PER_SET + 1):
            t0 = time.time()
            print(f"  iter {it}: generating...", end="", flush=True)
            try:
                img = generate_image(prompt)
                gen_dt = time.time() - t0
                print(f" {len(img)//1024}KB in {gen_dt:.1f}s", end="", flush=True)

                fname = f"set-{int(set_num):02d}-iter-{it}.png"
                url = upload_and_share(drive, folder_id, fname, img)
                up_dt = time.time() - t0 - gen_dt
                print(f" → uploaded in {up_dt:.1f}s")
                print(f"    {url}")
                urls.append(url)
            except Exception as e:
                print(f"\n    FAILED: {type(e).__name__}: {e}")
                urls.append(None)

        # Write back: status, iter1, iter2
        if all(urls):
            sb.update(
                range_name=f"E{sheet_row}:G{sheet_row}",
                values=[["Done", urls[0], urls[1]]],
                value_input_option="USER_ENTERED",
            )
            print(f"  ✓ row {sheet_row} updated: Done, F={urls[0][:40]}..., G={urls[1][:40]}...")
            summary.append((set_num, "done", urls))
        else:
            sb.update(range_name=f"E{sheet_row}", values=[["Failed"]])
            print(f"  ✗ row {sheet_row} marked Failed")
            summary.append((set_num, "failed", urls))

    total_dt = time.time() - overall_start
    print(f"\n\n=== SUMMARY ({total_dt:.1f}s total) ===")
    for set_num, status, urls in summary:
        print(f"  Set {set_num}: {status}")
        for it, u in enumerate(urls, 1):
            print(f"    iter {it}: {u or '(failed)'}")


if __name__ == "__main__":
    main()

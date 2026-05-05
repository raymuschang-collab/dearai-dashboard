#!/usr/bin/env python3
"""
Generate location reference images via fal.ai Reve text-to-image.

Reads the LOCATIONS tab — each row is one location × shot-size variant
(wide / mid). Generates 2 iterations per row using the rendered prompt from
column I (auto-assembled from globals + per-row data). Uploads PNGs to
{Show folder}/location-refs/, sets anyone-with-link sharing, writes URLs
back to columns J (Iter 1) and K (Iter 2). Status flips to Done on success.

Idempotent. Skips rows with Status="Done" unless --force is passed.

Usage:
    python3 location_generate.py --sheet <sheet-id-or-url>
    python3 location_generate.py --sheet <id> --row 6        # one specific row
    python3 location_generate.py --sheet <id> --force        # regenerate Done rows
    python3 location_generate.py --sheet <id> --aspect 21:9  # default 16:9
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import re
import sys
import time

import fal_client
import gspread
import httpx
import requests

import higgs_gen
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from auth import get_credentials


HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

# Provider routing
PROVIDER_DEFAULT = "reve-direct"  # was "fal" — switched to direct Reve API per user request
FAL_MODEL = "fal-ai/reve/text-to-image"
REVE_DIRECT_ENDPOINT = "https://api.reve.com/v1/image/create"

DEFAULT_ASPECT = "16:9"
ITERATIONS = 2

# Plan-view (overhead PHOTOREALISTIC) prompt — iter 2 of every location.
# Takes the eye-level wide (iter 1, Reve) as image reference and renders the
# SAME space from a true top-down camera angle, in the SAME photorealistic
# style as the wide. NOT a blueprint / NOT an illustration — a real overhead
# photograph.
PLAN_VIEW_PROMPT = (
    "Top-down overhead photograph of the SAME physical space shown in the "
    "reference image, viewed from a camera mounted directly above the floor "
    "and pointed straight down. Bird's-eye / plan-view angle. Maintain "
    "EXACTLY the same photorealistic style as the reference: same documentary "
    "editorial photography aesthetic, same Kodak Portra 400 color science, "
    "same subtle film grain, same muted desaturated palette, same natural "
    "practical lighting (no theatrical fill). Show the full floor plan — "
    "walls, room boundaries, major furniture and equipment (stations, shelves, "
    "doorways, sinks, counters, tables), all with full photographic texture "
    "and material fidelity (stainless steel, tile, wood, concrete) just as "
    "they appear in the reference. No people. Real photograph, not "
    "illustration. No blueprint, no line art, no labels — just a photograph "
    "of the room from above."
)

SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")

# Columns in the LOCATIONS schema (data rows start at sheet row 6)
COL_NAME = "A"
COL_SHOT_SIZE = "B"
COL_PROMPT = "I"
COL_ITER1 = "J"
COL_ITER2 = "K"
COL_STATUS = "L"
COL_ERROR = "M"


def parse_sheet_id(s: str) -> str:
    m = SHEETS_URL_RE.search(s)
    return m.group(1) if m else s.strip()


def slugify(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", s)[:60].strip("_")


def get_or_create_folder(drive, parent_id: str, name: str) -> str:
    safe = name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and trashed=false "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and name='{safe}'"
    )
    res = drive.files().list(q=q, fields="files(id)", pageSize=5).execute()
    if res.get("files"):
        return res["files"][0]["id"]
    return drive.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()["id"]


def generate_image_fal(prompt: str, aspect: str) -> bytes:
    result = fal_client.subscribe(
        FAL_MODEL,
        arguments={
            "prompt": prompt,
            "aspect_ratio": aspect,
            "num_images": 1,
            "output_format": "png",
        },
        with_logs=False,
    )
    if not result.get("images"):
        raise RuntimeError(f"No images returned: {result}")
    img_url = result["images"][0]["url"]
    resp = requests.get(img_url, timeout=180)
    resp.raise_for_status()
    return resp.content


def generate_image_reve_direct(prompt: str, aspect: str) -> bytes:
    api_key = os.getenv("REVE_API_KEY")
    if not api_key:
        raise RuntimeError("REVE_API_KEY not set in .env")
    r = httpx.post(
        REVE_DIRECT_ENDPOINT,
        json={"prompt": prompt, "aspect_ratio": aspect},
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    if "image" not in data:
        raise RuntimeError(f"Reve direct response missing 'image' field: {data}")
    return base64.b64decode(data["image"])


def generate_image(prompt: str, aspect: str, provider: str) -> bytes:
    if provider == "reve-direct":
        return generate_image_reve_direct(prompt, aspect)
    elif provider == "fal":
        return generate_image_fal(prompt, aspect)
    raise ValueError(f"Unknown provider: {provider}")


def trash_existing_with_name(drive, folder_id: str, filename: str) -> int:
    """Move any existing files with the given name in the folder to trash. Returns count trashed."""
    safe = filename.replace("'", "\\'")
    res = drive.files().list(
        q=f"'{folder_id}' in parents and trashed=false and name='{safe}'",
        fields="files(id)", pageSize=10,
    ).execute()
    n = 0
    for f in res.get("files", []):
        drive.files().update(fileId=f["id"], body={"trashed": True}).execute()
        n += 1
    return n


def upload_and_share(drive, folder_id: str, filename: str, content: bytes) -> str:
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


def process_row(ws, drive, sheet_row: int, name: str, shot_size: str, prompt: str,
                status: str, location_root_folder_id: str, aspect: str, provider: str,
                *, force: bool = False) -> dict:
    if not name:
        return {"status": "skip", "reason": "empty name"}
    if not prompt:
        return {"status": "skip", "reason": "empty prompt"}
    if status == "Done" and not force:
        print(f"\n=== {name} ({shot_size}) row {sheet_row} — SKIP (already Done) ===")
        return {"status": "skip", "reason": "already Done"}

    print(f"\n=== {name} ({shot_size}) — row {sheet_row} ===")
    print(f"  prompt: {len(prompt)} chars")
    ws.update(range_name=f"{COL_STATUS}{sheet_row}", values=[["Generating"]])

    # Per-location subfolder (matches the post-reorganization layout)
    sub_folder_id = get_or_create_folder(drive, location_root_folder_id, name)

    # Two-step pipeline:
    #   iter 1 (wide) — Reve direct on the per-row prompt
    #   iter 2 (plan view, overhead) — gpt_image_2 with iter 1 as image ref
    iter_urls = [None, None]
    err = None
    slug = slugify(name)

    # ---- iter 1: WIDE via Reve ----
    t0 = time.time()
    print(f"  iter 1 (wide, Reve): generating...", end="", flush=True)
    try:
        wide_bytes = generate_image(prompt, aspect, provider)
        print(f" {len(wide_bytes)//1024}KB in {time.time() - t0:.1f}s", end="", flush=True)
        fname = f"{slug}-{shot_size}-iter-1-wide.png"
        n_trashed = trash_existing_with_name(drive, sub_folder_id, fname)
        if n_trashed:
            print(f" [trashed {n_trashed} prior]", end="", flush=True)
        url = upload_and_share(drive, sub_folder_id, fname, wide_bytes)
        print(f" → uploaded")
        print(f"    {url}")
        iter_urls[0] = url
    except Exception as e:
        err = f"iter 1 (wide): {type(e).__name__}: {e}"
        print(f"\n  FAILED: {err}")
        wide_bytes = None

    # ---- iter 2: PLAN VIEW via gpt_image_2 with wide as ref ----
    if wide_bytes:
        t0 = time.time()
        print(f"  iter 2 (plan view, gpt_image_2): generating...", end="", flush=True)
        try:
            tmp_ref = f"/tmp/{slug}-{shot_size}-wide.png"
            with open(tmp_ref, "wb") as f:
                f.write(wide_bytes)
            plan_bytes = higgs_gen.generate(
                prompt=PLAN_VIEW_PROMPT,
                model="gpt_image_2",
                aspect_ratio="1:1",
                resolution="1k",
                image_ref_path=tmp_ref,
            )
            print(f" {len(plan_bytes)//1024}KB in {time.time() - t0:.1f}s", end="", flush=True)
            fname = f"{slug}-{shot_size}-iter-2-plan.png"
            n_trashed = trash_existing_with_name(drive, sub_folder_id, fname)
            if n_trashed:
                print(f" [trashed {n_trashed} prior]", end="", flush=True)
            url = upload_and_share(drive, sub_folder_id, fname, plan_bytes)
            print(f" → uploaded")
            print(f"    {url}")
            iter_urls[1] = url
        except Exception as e:
            err = (err or "") + f" | iter 2 (plan view): {type(e).__name__}: {e}"
            print(f"\n  FAILED iter 2 (plan view): {type(e).__name__}: {e}")
    else:
        print(f"  iter 2 (plan view): skipped (no wide ref from iter 1)")

    iter1, iter2 = iter_urls[0] or "", iter_urls[1] or ""
    if iter1 and iter2:
        sheet_status, err_msg = "Done", ""
    elif iter1 or iter2:
        sheet_status, err_msg = "Done", err or ""  # partial success
    else:
        sheet_status, err_msg = "Failed", err or "unknown error"
    ws.update(
        range_name=f"{COL_ITER1}{sheet_row}:{COL_ERROR}{sheet_row}",
        values=[[iter1, iter2, sheet_status, err_msg]],
        value_input_option="USER_ENTERED",
    )
    print(f"  → row {sheet_row}: {sheet_status} (iter1={'✓' if iter1 else '✗'}, iter2={'✓' if iter2 else '✗'})")
    return {"status": "fail", "error": err}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--row", type=int, help="Process only this sheet row (e.g. 6 = first data row)")
    ap.add_argument("--location", help="Filter to rows whose col A matches this location name")
    ap.add_argument("--force", action="store_true", help="Regenerate Done rows")
    ap.add_argument("--aspect", default=DEFAULT_ASPECT,
                    choices=["21:9", "16:9", "9:16", "3:2", "2:3", "4:3", "3:4", "1:1", "9:21"])
    ap.add_argument("--provider", default=PROVIDER_DEFAULT, choices=["reve-direct", "fal"],
                    help=f"Image gen provider (default: {PROVIDER_DEFAULT})")
    args = ap.parse_args()

    if args.provider == "reve-direct" and not os.getenv("REVE_API_KEY"):
        sys.exit("REVE_API_KEY not loaded — check .env")
    if args.provider == "fal" and not os.getenv("FAL_KEY"):
        sys.exit("FAL_KEY not loaded — check .env")

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)

    sheet_id = parse_sheet_id(args.sheet)
    sh = gc.open_by_key(sheet_id)
    print(f"Sheet: {sh.title}")
    print(f"Provider: {args.provider}  Aspect: {args.aspect}")

    ws = sh.worksheet("LOCATIONS")

    # Get show folder for location-refs/
    meta = drive.files().get(fileId=sheet_id, fields="parents").execute()
    parent_id = meta["parents"][0]
    location_folder_id = get_or_create_folder(drive, parent_id, "location-refs")
    print(f"location-refs/ id={location_folder_id}")

    # Read all data rows (sheet rows 5+; columns A:M; headers are in row 4)
    data = ws.get(f"A5:M{ws.row_count}", value_render_option="FORMATTED_VALUE")

    overall_start = time.time()
    results = []
    for i, row in enumerate(data):
        sheet_row = 5 + i
        if not row or len(row) < 1 or not row[0]:
            continue
        if args.row and sheet_row != args.row:
            continue
        name = row[0] if len(row) > 0 else ""
        if args.location and (name or "").strip().lower() != args.location.strip().lower():
            continue
        shot_size = row[1] if len(row) > 1 else ""
        prompt = row[8] if len(row) > 8 else ""
        status = row[11] if len(row) > 11 else ""

        result = process_row(
            ws, drive, sheet_row, name, shot_size, prompt, status,
            location_folder_id, args.aspect, args.provider, force=args.force,
        )
        results.append((f"{name} ({shot_size})", result))

    total_dt = time.time() - overall_start
    print(f"\n\n=== SUMMARY ({total_dt:.1f}s) ===")
    counts = {"done": 0, "skip": 0, "fail": 0}
    for label, r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        line = f"  {label}: {r['status']}"
        if r.get("reason"):
            line += f" ({r['reason']})"
        print(line)
    print(f"\n  TOTAL: {counts.get('done', 0)} done, {counts.get('skip', 0)} skipped, {counts.get('fail', 0)} failed")


if __name__ == "__main__":
    main()

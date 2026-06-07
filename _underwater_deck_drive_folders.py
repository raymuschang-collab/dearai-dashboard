#!/usr/bin/env python3
"""For the UnderwaterTestShoot_Dark.html deck:
1. Parse Slides 4 / 6 / 7 / 7b / 8 to extract their Drive IDs
2. Create 4 Drive folders (server-side copy — no moving originals; duplication OK)
3. Make each folder + each copy anyone-with-link reader
4. Print folder share URLs for use as deck buttons
"""
import os, re, sys, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

DECK = Path("/Users/raymuschang/Desktop/Sales Decks/UnderwaterTestShoot_Dark.html")


def parse_slides() -> dict:
    """Return {slide_label: [drive_id, ...]}."""
    html = DECK.read_text()
    # Split into slides via the section boundary
    sections = re.split(r'<section class="slide[^"]*">', html)
    slides = {}
    for sec in sections[1:]:  # skip preamble
        # The first child div has the label like 'Slide 04 · Methodology · 方法论'
        label_match = re.search(r'<div class="label">([^<]+)</div>', sec)
        if not label_match:
            continue
        label = label_match.group(1).strip()
        ids = re.findall(r"openLightbox\('([^']+)'\)", sec)
        if ids:
            slides[label] = list(dict.fromkeys(ids))  # preserve order, dedupe
    return slides


# Folder plan: slide_label_substring → folder_name
PLAN = {
    "Methodology": ("Underwater · 14-Shot Animatic Clips", "slide-4"),
    "Seedance 2 Test": ("Underwater · Seedance 2 Test Clips", "slide-6"),
    "Kling Test": ("Underwater · Kling Test Clips", "slide-7"),
    "Kling Omni": ("Underwater · Kling Omni Extras", "slide-7b"),
    "Recommendation": ("Underwater · Recommendation Samples", "slide-8"),
}


def get_or_create_folder(drive, name: str) -> str:
    res = drive.files().list(
        q=f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)").execute()
    if res.get("files"):
        fid = res["files"][0]["id"]
        print(f"  reusing folder: {fid}")
        return fid
    f = drive.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id").execute()
    drive.permissions().create(fileId=f["id"], body={"role":"reader","type":"anyone"}, fields="id").execute()
    print(f"  created folder: {f['id']}")
    return f["id"]


def list_folder_names(drive, folder_id):
    out = {}
    page = None
    while True:
        res = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id,name)",
            pageToken=page).execute()
        for f in res.get("files", []):
            out[f["name"]] = f["id"]
        page = res.get("nextPageToken")
        if not page: break
    return out


def copy_one(drive, src_id: str, folder_id: str, existing_names: dict):
    """Server-side copy src_id into folder_id. Idempotent."""
    try:
        meta = drive.files().get(fileId=src_id, fields="name,mimeType,size").execute()
    except HttpError as e:
        print(f"    ✗ can't read source {src_id}: {e}")
        return None
    src_name = meta["name"]
    if src_name in existing_names:
        fid = existing_names[src_name]
        return (src_id, fid, src_name, "skipped")

    try:
        copied = drive.files().copy(
            fileId=src_id,
            body={"name": src_name, "parents": [folder_id]},
            fields="id"
        ).execute()
        new_fid = copied["id"]
        # Make copy anyone-with-link reader
        try:
            drive.permissions().create(
                fileId=new_fid,
                body={"role":"reader","type":"anyone"},
                fields="id"
            ).execute()
        except HttpError:
            pass
        return (src_id, new_fid, src_name, "copied")
    except HttpError as e:
        return (src_id, None, src_name, f"err:{e}")


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    slides = parse_slides()
    print(f"Parsed {len(slides)} slides with video tiles:\n")
    for lbl, ids in slides.items():
        print(f"  {lbl}: {len(ids)} videos")

    # Match slides to plan entries
    results = {}  # slide_key → {folder_id, folder_link, copied: [...]}
    for sub, (folder_name, slide_key) in PLAN.items():
        matching_label = next((lbl for lbl in slides if sub in lbl), None)
        if not matching_label:
            print(f"\n⚠ no slide found for '{sub}', skipping")
            continue
        ids = slides[matching_label]
        print(f"\n=== {slide_key}: {folder_name} ({len(ids)} clips) ===")
        folder_id = get_or_create_folder(drive, folder_name)
        existing = list_folder_names(drive, folder_id)

        # Server-side copy (sequential — httplib2 is not thread-safe)
        copied = []
        for src in ids:
            r = copy_one(drive, src, folder_id, existing)
            if r:
                src_id, new_fid, name, status = r
                print(f"  {status:8} {name[:50]:50}  src={src_id[:14]}..  new={(new_fid or '')[:14]}", flush=True)
                copied.append({"src_id": src_id, "new_id": new_fid, "name": name, "status": status})

        folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
        results[slide_key] = {
            "folder_id": folder_id,
            "folder_link": folder_link,
            "folder_name": folder_name,
            "count": len(ids),
            "copied": copied,
        }
        print(f"  📦 {folder_link}")

    out = Path("/Users/raymuschang/Desktop/Shotlist Workflows/_underwater_deck_drive_folders.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"\n=== SUMMARY ===")
    for k, v in results.items():
        print(f"  {k:10}  {v['count']} clips  →  {v['folder_link']}")
    print(f"\nMapping saved: {out}")


if __name__ == "__main__":
    main()

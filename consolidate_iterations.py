#!/usr/bin/env python3
"""
Consolidate per-set storyboard iterations into two flat folders next to
storyboards/ in the same parent.

Layout BEFORE:
    {Show folder}/
      storyboards/
        set-01/
          set-01-iter-1.png
          set-01-iter-2.png
        set-02/
          set-02-iter-1.png
          set-02-iter-2.png
        ...

Layout AFTER (default — files are COPIED, originals preserved):
    {Show folder}/
      storyboards/
        set-01/  ... (unchanged)
        set-02/  ... (unchanged)
      storyboards-iter-1/
        set-01-iter-1.png
        set-02-iter-1.png
        ...
      storyboards-iter-2/
        set-01-iter-2.png
        set-02-iter-2.png
        ...

Idempotent. Re-runnable. Skips files that already exist in the target folder
(matched by name).

Usage:
    python3 consolidate_iterations.py --sheet <sheet-id-or-url>
    python3 consolidate_iterations.py --parent <show-folder-id>
"""
from __future__ import annotations

import argparse
import re
import sys

from googleapiclient.discovery import build

from auth import get_credentials


SHEETS_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
FOLDER_URL_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")


def parse_sheet_id(s: str) -> str:
    m = SHEETS_URL_RE.search(s)
    return m.group(1) if m else s.strip()


def parse_folder_id(s: str) -> str:
    m = FOLDER_URL_RE.search(s)
    return m.group(1) if m else s.strip()


def derive_episode_folder_name(sheet_name: str) -> str:
    """Strip common version suffixes from a sheet name to recover the episode folder name."""
    name = sheet_name
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    while True:
        new = re.sub(r"(_shotlist)?(_v\d+[._]\d+)?$", "", name, flags=re.IGNORECASE)
        if new == name:
            break
        name = new
    return name.strip() or sheet_name


def find_asset_parent_for_sheet(drive, sheet_id: str) -> tuple[str, str]:
    """Return (asset_parent_id, label) — the folder that contains storyboards/.

    Tries flat layout first (storyboards/ directly under sheet's parent), falls back
    to per-sheet layout (sheet's parent → <episode>/storyboards/).
    """
    meta = drive.files().get(fileId=sheet_id, fields="parents,name").execute()
    parents = meta.get("parents")
    if not parents:
        sys.exit(f"ERROR: sheet {sheet_id} has no parent folder")
    sheet_parent = parents[0]
    sheet_name = meta["name"]

    # Try flat layout
    res = drive.files().list(
        q=(
            f"'{sheet_parent}' in parents and trashed=false "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and name='storyboards'"
        ),
        fields="files(id)",
        pageSize=1,
    ).execute()
    if res.get("files"):
        return sheet_parent, f"flat: {sheet_name}"

    # Try per-sheet layout — look for an episode subfolder containing storyboards/
    derived = derive_episode_folder_name(sheet_name)
    safe = derived.replace("'", "\\'")
    res = drive.files().list(
        q=(
            f"'{sheet_parent}' in parents and trashed=false "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and name='{safe}'"
        ),
        fields="files(id)",
        pageSize=1,
    ).execute()
    if res.get("files"):
        sub_id = res["files"][0]["id"]
        res2 = drive.files().list(
            q=(
                f"'{sub_id}' in parents and trashed=false "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and name='storyboards'"
            ),
            fields="files(id)",
            pageSize=1,
        ).execute()
        if res2.get("files"):
            return sub_id, f"per-sheet: {sheet_name} → {derived}"

    sys.exit(f"ERROR: no 'storyboards/' folder found under {sheet_parent} or under per-sheet subfolder {derived!r}")


def find_or_create_folder(drive, parent_id: str, name: str) -> tuple[str, bool]:
    safe = name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and trashed=false "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and name='{safe}'"
    )
    res = drive.files().list(q=q, fields="files(id,name)", pageSize=10).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"], False
    body = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = drive.files().create(body=body, fields="id").execute()
    return created["id"], True


def make_public_reader(drive, file_id: str) -> None:
    """Set anyone-with-link → reader on the file or folder."""
    try:
        drive.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
            fields="id",
        ).execute()
    except Exception as e:
        # If permission already exists, that's fine
        if "already" in str(e).lower():
            return
        raise


def list_existing_files(drive, parent_id: str) -> set[str]:
    """Return set of file names already in this folder."""
    names: set[str] = set()
    page_token = None
    while True:
        res = drive.files().list(
            q=f"'{parent_id}' in parents and trashed=false",
            fields="nextPageToken, files(id,name)",
            pageSize=200,
            pageToken=page_token,
        ).execute()
        for f in res.get("files", []):
            names.add(f["name"])
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return names


def list_set_folders(drive, storyboards_id: str) -> list[dict]:
    """Return [{id, name}] for every set-NN/ folder under storyboards/."""
    res = drive.files().list(
        q=(
            f"'{storyboards_id}' in parents and trashed=false "
            f"and mimeType='application/vnd.google-apps.folder'"
        ),
        fields="files(id,name)",
        pageSize=200,
        orderBy="name",
    ).execute()
    return res.get("files", [])


def list_pngs_in_folder(drive, folder_id: str) -> list[dict]:
    """Return [{id, name}] for every PNG (or image) in the folder."""
    res = drive.files().list(
        q=(
            f"'{folder_id}' in parents and trashed=false "
            f"and (mimeType='image/png' or mimeType='image/jpeg')"
        ),
        fields="files(id,name)",
        pageSize=50,
    ).execute()
    return res.get("files", [])


def copy_file(drive, source_id: str, target_parent_id: str, new_name: str) -> str:
    body = {"name": new_name, "parents": [target_parent_id]}
    created = drive.files().copy(fileId=source_id, body=body, fields="id").execute()
    return created["id"]


def consolidate(drive, parent_folder_id: str) -> None:
    """Consolidate iter-1 and iter-2 PNGs from storyboards/set-NN/ into two flat folders."""
    # Find storyboards/ folder under the show folder
    res = drive.files().list(
        q=(
            f"'{parent_folder_id}' in parents and trashed=false "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and name='storyboards'"
        ),
        fields="files(id,name)",
        pageSize=5,
    ).execute()
    sb_folders = res.get("files", [])
    if not sb_folders:
        sys.exit(f"ERROR: no 'storyboards/' folder found under parent {parent_folder_id}")
    sb_id = sb_folders[0]["id"]
    print(f"Found storyboards/ id={sb_id}")

    # Create or reuse the two consolidation folders
    iter1_id, iter1_created = find_or_create_folder(drive, parent_folder_id, "storyboards-iter-1")
    iter2_id, iter2_created = find_or_create_folder(drive, parent_folder_id, "storyboards-iter-2")
    print(f"storyboards-iter-1/  {'CREATED' if iter1_created else 'reused'}  id={iter1_id}")
    print(f"storyboards-iter-2/  {'CREATED' if iter2_created else 'reused'}  id={iter2_id}")

    # Make consolidation folders publicly readable
    make_public_reader(drive, iter1_id)
    make_public_reader(drive, iter2_id)

    # Index existing files in target folders for idempotency
    iter1_existing = list_existing_files(drive, iter1_id)
    iter2_existing = list_existing_files(drive, iter2_id)

    # Walk every set-NN/ folder
    set_folders = list_set_folders(drive, sb_id)
    if not set_folders:
        sys.exit(f"ERROR: no set-NN/ subfolders under storyboards/")
    print(f"Found {len(set_folders)} set folders. Processing...")

    iter1_count = iter1_skip = 0
    iter2_count = iter2_skip = 0

    for sf in set_folders:
        set_name = sf["name"]
        files = list_pngs_in_folder(drive, sf["id"])
        for f in files:
            name = f["name"]
            if "iter-1" in name:
                if name in iter1_existing:
                    iter1_skip += 1
                else:
                    copy_file(drive, f["id"], iter1_id, name)
                    iter1_existing.add(name)
                    iter1_count += 1
            elif "iter-2" in name:
                if name in iter2_existing:
                    iter2_skip += 1
                else:
                    copy_file(drive, f["id"], iter2_id, name)
                    iter2_existing.add(name)
                    iter2_count += 1

    print()
    print("=== SUMMARY ===")
    print(f"  storyboards-iter-1: {iter1_count} copied, {iter1_skip} already present")
    print(f"  storyboards-iter-2: {iter2_count} copied, {iter2_skip} already present")
    print()
    print("Public folder URLs (anyone with link can view):")
    print(f"  Iter 1: https://drive.google.com/drive/folders/{iter1_id}")
    print(f"  Iter 2: https://drive.google.com/drive/folders/{iter2_id}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--sheet", help="Sheet ID or URL (we'll read its parent folder)")
    src.add_argument("--parent", help="Show folder ID (the one containing storyboards/)")
    args = ap.parse_args()

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    if args.sheet:
        sheet_id = parse_sheet_id(args.sheet)
        parent_id, label = find_asset_parent_for_sheet(drive, sheet_id)
        print(f"Resolved asset parent: {label}")
        print(f"  asset parent id: {parent_id}")
    else:
        parent_id = parse_folder_id(args.parent)
        print(f"Parent folder: {parent_id}")

    consolidate(drive, parent_id)


if __name__ == "__main__":
    main()

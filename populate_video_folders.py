#!/usr/bin/env python3
"""
Create per-set Drive folders for videos and populate Video Prompts col E.

Layout:
  {show folder}/
    storyboards/set-NN/   ← already exists
    videos/set-NN/        ← created here

Idempotent: reuses existing folders if found.
"""
from __future__ import annotations
import gspread
from googleapiclient.discovery import build
from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"


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


def folder_url(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def main():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    sh = gc.open_by_key(SHEET_ID)

    # Find show folder via the sheet's parent
    meta = drive.files().get(fileId=SHEET_ID, fields="parents,name").execute()
    show_folder_id = meta["parents"][0]
    print(f"Show folder: {meta.get('name')} ({show_folder_id})")

    # Create videos/ root
    videos_root = get_or_create_folder(drive, show_folder_id, "videos")
    print(f"  videos/ → {videos_root}")

    # Make folder public-readable so embedded URLs work without sign-in
    try:
        drive.permissions().create(
            fileId=videos_root,
            body={"role": "reader", "type": "anyone"},
            fields="id",
        ).execute()
    except Exception as e:
        print(f"    perm note: {e}")

    # Read sets from Video Prompts (or Storyboard Prompts — same set list)
    vp = sh.worksheet("Video Prompts")
    set_rows = vp.get("A7:B30", value_render_option="FORMATTED_VALUE")
    set_rows = [r for r in set_rows if r and r[0]]
    print(f"  {len(set_rows)} sets to populate")

    folder_urls = []
    for r in set_rows:
        set_num = str(r[0]).strip()
        # zero-pad: set-01, set-02, ... set-14
        try:
            sub_name = f"set-{int(set_num):02d}"
        except ValueError:
            sub_name = f"set-{set_num}"
        sub_id = get_or_create_folder(drive, videos_root, sub_name)
        # Set anyone-with-link reader
        try:
            drive.permissions().create(
                fileId=sub_id,
                body={"role": "reader", "type": "anyone"},
                fields="id",
            ).execute()
        except Exception:
            pass
        folder_urls.append([folder_url(sub_id)])
        print(f"    set {set_num} → videos/{sub_name}/")

    # Write into Video Prompts col E (Drive Folder)
    rng = f"E7:E{6 + len(folder_urls)}"
    vp.update(range_name=rng, values=folder_urls, value_input_option="USER_ENTERED")
    print(f"  ✓ Video Prompts col E populated ({len(folder_urls)} rows)")


if __name__ == "__main__":
    main()

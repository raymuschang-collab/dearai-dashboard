#!/usr/bin/env python3
"""Upload all mp4s from ~/Documents/Channel 8 Underwater — Landed Outputs/ to a
dedicated Drive folder. Print streaming URLs (uc?export=download&id=) for each
so they can be played without waiting on Drive's preview transcode.
"""
import os, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

LANDED = Path("/Users/raymuschang/Documents/Channel 8 Underwater — Landed Outputs")
FOLDER_NAME = "Channel 8 Underwater — Seedance Outputs"


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    # Find or create the Drive folder
    res = drive.files().list(
        q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,webViewLink)", pageSize=5,
    ).execute()
    if res.get("files"):
        folder_id = res["files"][0]["id"]
        folder_link = res["files"][0].get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")
        print(f"Reusing existing Drive folder: {folder_link}")
    else:
        f = drive.files().create(
            body={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            fields="id,webViewLink",
        ).execute()
        folder_id = f["id"]
        folder_link = f.get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")
        # Set folder anyone-with-link reader
        drive.permissions().create(fileId=folder_id, body={"role": "reader", "type": "anyone"}, fields="id").execute()
        print(f"Created new Drive folder: {folder_link}")

    # Get list of already-uploaded filenames in that folder (skip re-uploads)
    existing = {}
    page_token = None
    while True:
        res = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id,name)",
            pageToken=page_token,
        ).execute()
        for f in res.get("files", []):
            existing[f["name"]] = f["id"]
        page_token = res.get("nextPageToken")
        if not page_token:
            break

    # Upload each mp4 in Landed
    mp4s = sorted([p for p in LANDED.glob("*.mp4") if not p.name.startswith(".")])
    print(f"\n{len(mp4s)} mp4 files in Landed Outputs folder")

    results = []
    for local in mp4s:
        if local.name in existing:
            fid = existing[local.name]
            print(f"  • {local.name} — already on Drive, reusing id {fid}")
        else:
            print(f"  ◦ uploading {local.name} ({local.stat().st_size/1024/1024:.1f} MB)...")
            media = MediaFileUpload(str(local), mimetype="video/mp4", resumable=True, chunksize=2*1024*1024)
            f = drive.files().create(
                body={"name": local.name, "parents": [folder_id]},
                media_body=media, fields="id",
            ).execute()
            fid = f["id"]
            drive.permissions().create(fileId=fid, body={"role": "reader", "type": "anyone"}, fields="id").execute()
            print(f"    ✓ uploaded id {fid}")
        stream_url = f"https://drive.google.com/uc?export=download&id={fid}"
        view_url = f"https://drive.google.com/file/d/{fid}/view"
        results.append((local.name, fid, stream_url, view_url))

    print("\n\n========== STREAMING URLS (no transcode wait) ==========")
    for name, fid, stream, view in results:
        print(f"\n{name}")
        print(f"  STREAM (instant):     {stream}")
        print(f"  VIEW (waits for tx):  {view}")

    # Write a streamable HTML deck that points at these Drive stream URLs
    html_path = LANDED / "gallery_drive.html"
    cards = []
    for name, fid, stream, _ in results:
        cards.append(f'''
        <div class="card">
          <video src="{stream}" autoplay loop muted playsinline controls></video>
          <div class="meta">
            <div class="title">{name}</div>
            <a class="stream" href="{stream}" target="_blank">stream url ↗</a>
            <div class="fid">id: <code>{fid}</code></div>
          </div>
        </div>''')
    html = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Channel 8 Underwater — Drive Streams</title>
<style>
  :root{color-scheme:dark}*{box-sizing:border-box}
  body{margin:0;padding:24px;background:#0b0f14;color:#e7ecf3;font:14px/1.4 -apple-system,system-ui,sans-serif}
  h1{margin:0 0 8px;font-size:22px}.sub{color:#8a96a3;margin-bottom:24px;font-size:13px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:22px}
  .card{background:#131922;border:1px solid #1f2a37;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
  .card video{width:100%;height:auto;display:block;background:#000}
  .meta{padding:12px 14px}.title{font-weight:600;font-size:14px;margin-bottom:6px}
  .stream{color:#7dd3fc;font-size:12px;text-decoration:none}.stream:hover{text-decoration:underline}
  .fid{color:#5b6675;font-size:11px;margin-top:6px}code{color:#94a3b8}
</style></head><body>
<h1>Channel 8 Underwater — Drive Streams</h1>
<div class="sub">All videos load from Drive's direct-stream URL (no preview transcode wait). Anyone with link can view.</div>
<div class="grid">''' + '\n'.join(cards) + '''
</div></body></html>'''
    html_path.write_text(html)
    print(f"\n\n📦 Drive folder:  {folder_link}")
    print(f"📺 Local deck:    {html_path}")


if __name__ == "__main__":
    main()

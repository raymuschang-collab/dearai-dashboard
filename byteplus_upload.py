#!/usr/bin/env python3
"""BytePlus asset upload — single-file CLI for the team.

Upload ONE local file (image, video, or audio) to BytePlus Avatar Library
and print the asset code. Auto-handles:
  - Drive intermediate hosting (BytePlus fetches by URL — needs a public source)
  - URL format quirks (lh3 for images, uc?download for video/audio)
  - .m4a → .mp3 conversion (BytePlus rejects m4a)
  - Asset polling (waits until Status=Active)

USAGE:
  python3 byteplus_upload.py <local-file> --name "ASSET NAME"
  python3 byteplus_upload.py "/path/to/face.png"  --name "TARA face"
  python3 byteplus_upload.py "/path/to/clip.mp4"  --name "MINISTER 5s"
  python3 byteplus_upload.py "/path/to/voice.mp3" --name "TARA VO"
  python3 byteplus_upload.py "/path/to/voice.m4a" --name "TARA VO"   # auto-converts

After the run, the asset code prints to stdout. Use in vidgen prompts as:
  asset://<asset-code>

PREREQS:
  1. .env with BYTEPLUS_ARK_API_KEY and BYTEPLUS_ACCESS_KEY/BYTEPLUS_SECRET_KEY
  2. auth.py + token.json (Google Drive credentials)
  3. ffmpeg installed (only needed for m4a → mp3 conversion)
  4. GROUP_ID for the project (default below is Channel 8 / Sajangnim group)

Run from the project root (~/Documents/Shotlist Workflows).
"""
from __future__ import annotations
import argparse, os, sys, subprocess
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

# Load .env first
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from auth import get_credentials
import byteplus_asset_v2 as bp
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# === CONFIG ===
DEFAULT_GROUP_ID = "group-20260505195134-wqx2b"        # Channel 8 / Sajangnim
DEFAULT_DRIVE_FOLDER = "Channel 8 Test Shoot — Character Refs"

# Map extension → BytePlus AssetType + Drive mime + URL format
TYPE_MAP = {
    # images
    ".png":  ("Image", "image/png",  "lh3"),
    ".jpg":  ("Image", "image/jpeg", "lh3"),
    ".jpeg": ("Image", "image/jpeg", "lh3"),
    ".webp": ("Image", "image/webp", "lh3"),
    # video
    ".mp4":  ("Video", "video/mp4",          "uc_download"),
    ".mov":  ("Video", "video/quicktime",    "uc_download"),
    # audio
    ".mp3":  ("Audio", "audio/mpeg",         "uc_download"),
    ".wav":  ("Audio", "audio/wav",          "uc_download"),
    ".m4a":  ("AUDIO_M4A_NEEDS_CONVERT", None, None),   # special-cased below
}


def convert_m4a_to_mp3(src: Path) -> Path:
    """Convert m4a → mp3 via ffmpeg. BytePlus rejects m4a outright."""
    out = src.with_suffix(".mp3")
    if out.exists() and out.stat().st_size > 1024:
        print(f"  ↻ found existing converted mp3: {out.name}")
        return out
    print(f"  ◦ converting {src.name} → {out.name} via ffmpeg...")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", "192k", str(out)],
            check=True, capture_output=True,
        )
    except FileNotFoundError:
        sys.exit("ffmpeg not found — install with `brew install ffmpeg` (Mac) or `apt install ffmpeg` (Linux)")
    except subprocess.CalledProcessError as e:
        sys.exit(f"ffmpeg failed: {e.stderr.decode()[:500]}")
    if not out.exists() or out.stat().st_size < 1024:
        sys.exit("ffmpeg produced no output")
    print(f"    ✓ converted ({out.stat().st_size/1024:.1f} KB)")
    return out


def upload_to_drive(drive, parent_id: str, local: Path, mime: str) -> tuple[str, str]:
    """Resumable upload to Drive + set anyone-with-link reader.
    Returns (file_id, drive_view_link)."""
    print(f"  ◦ uploading {local.name} ({local.stat().st_size/1024/1024:.1f} MB) to Drive...")
    media = MediaFileUpload(str(local), mimetype=mime, resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": local.name, "parents": [parent_id]},
        media_body=media,
        fields="id,webViewLink",
    ).execute()
    fid = f["id"]
    # Required: anyone-with-link reader so BytePlus can fetch it
    drive.permissions().create(
        fileId=fid,
        body={"role": "reader", "type": "anyone"},
        fields="id",
    ).execute()
    print(f"    ✓ Drive id: {fid}")
    return fid, f.get("webViewLink", "")


def build_source_url(file_id: str, url_format: str) -> str:
    """Produce the right Drive URL for BytePlus to fetch from.

    - 'lh3'        → https://lh3.googleusercontent.com/d/<id>=w2048   (for images;
                     BytePlus rejects Drive /view URLs as UnsupportedImageFormat)
    - 'uc_download' → https://drive.google.com/uc?export=download&id=<id>
                     (for video + audio)
    """
    if url_format == "lh3":
        return f"https://lh3.googleusercontent.com/d/{file_id}=w2048"
    if url_format == "uc_download":
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    sys.exit(f"unknown url_format: {url_format!r}")


def find_or_create_drive_folder(drive, folder_name: str) -> str:
    res = drive.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
        pageSize=5,
    ).execute()
    if res.get("files"):
        return res["files"][0]["id"]
    print(f"  ◦ creating Drive folder '{folder_name}'...")
    f = drive.files().create(
        body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()
    return f["id"]


def main():
    ap = argparse.ArgumentParser(
        description="Upload a single asset (image/video/audio) to BytePlus and return the asset code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("file", help="Local path to the asset (PNG / JPG / MP4 / MOV / MP3 / WAV / M4A)")
    ap.add_argument("--name", required=True, help="Asset name on BytePlus (e.g. 'TARA face')")
    ap.add_argument("--group-id", default=DEFAULT_GROUP_ID,
                    help=f"BytePlus group ID (default: {DEFAULT_GROUP_ID})")
    ap.add_argument("--drive-folder", default=DEFAULT_DRIVE_FOLDER,
                    help=f"Drive folder name for the staging copy (default: '{DEFAULT_DRIVE_FOLDER}')")
    ap.add_argument("--timeout", type=int, default=300,
                    help="Polling timeout in seconds (default 300)")
    args = ap.parse_args()

    src = Path(args.file).expanduser()
    if not src.exists():
        sys.exit(f"File not found: {src}")

    ext = src.suffix.lower()
    if ext not in TYPE_MAP:
        sys.exit(f"Unsupported file extension: {ext}\nSupported: {', '.join(sorted(TYPE_MAP.keys()))}")

    # Handle m4a conversion
    if ext == ".m4a":
        print(f"⚠ BytePlus rejects .m4a — auto-converting to mp3...")
        src = convert_m4a_to_mp3(src)
        ext = ".mp3"

    asset_type, mime, url_format = TYPE_MAP[ext]
    print(f"\n=== {args.name} ===")
    print(f"  file:        {src}")
    print(f"  ext:         {ext}")
    print(f"  asset_type:  {asset_type}")
    print(f"  drive folder: {args.drive_folder}")
    print(f"  byteplus group: {args.group_id}")

    # 1. Drive
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    parent_id = find_or_create_drive_folder(drive, args.drive_folder)
    fid, view_link = upload_to_drive(drive, parent_id, src, mime)

    # 2. Build the URL BytePlus will fetch
    source_url = build_source_url(fid, url_format)
    print(f"  ◦ BytePlus source URL: {source_url}")

    # 3. Register on BytePlus
    print(f"  ◦ calling BytePlus CreateAsset (type={asset_type})...")
    aid = bp.create_asset(args.group_id, source_url, asset_type, name=args.name)
    print(f"    ✓ asset_id: {aid}")

    # 4. Poll until Active
    print(f"  ◦ polling until Status=Active (timeout {args.timeout}s)...")
    bp.poll_asset(aid, timeout=args.timeout)

    # Final summary block — easy to copy/paste
    print(f"\n=========================================================")
    print(f"  ✓ DONE — copy this into your vidgen / Seedance prompt:")
    print(f"=========================================================")
    print(f"  Name:        {args.name}")
    print(f"  Asset code:  {aid}")
    print(f"  Use as:      asset://{aid}")
    print(f"  Drive view:  {view_link}")
    print(f"=========================================================\n")


if __name__ == "__main__":
    main()

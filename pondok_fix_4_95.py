#!/usr/bin/env python3
"""Hard-trim the sped-up Pondok Indah clips to EXACTLY 4.95s, re-upload.

Pass 1 came out at 5.000s due to frame quantization. This pass:
  - Re-encodes from source with setpts + atempo AND -t 4.95 hard duration
  - Re-uploads to Drive
  - Creates new BytePlus Video assets
  - Marks the previous asset_ids as superseded in the manifest
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

sys.path.insert(0, "/Users/raymuschang/Desktop/Shotlist Workflows")
from auth import get_credentials
import byteplus_asset_v2 as bp

load_dotenv("/Users/raymuschang/Desktop/Shotlist Workflows/.env")
GROUP = os.getenv("BYTEPLUS_GROUP_ID")

SRC = Path("/Users/raymuschang/Downloads/Pondok Indah Test")
OUT_DIR = SRC / "sped_4.95s"
MF = OUT_DIR / "byteplus_uploads.json"

prev = json.loads(MF.read_text()) if MF.exists() else []
prev_by_name = {p["name"]: p for p in prev}

TARGETS = [
    {"name": "jane",   "src": SRC / "Character_introduction_montage_w…_202606021617.mp4",
     "asset_name": "Pondok Indah — Jane (4.95s)"},
    {"name": "karina", "src": SRC / "Character_introduction_montage_w…_202606021607.mp4",
     "asset_name": "Pondok Indah — Karina (4.95s)"},
]


def get_duration(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(p)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def speed_and_trim(src: Path, dst: Path, target=4.95):
    src_dur = get_duration(src)
    factor = src_dur / target
    video_setpts = 1.0 / factor
    if factor <= 2.0:
        atempo = f"atempo={factor:.6f}"
    else:
        rem = factor / 2.0
        atempo = f"atempo=2.0,atempo={rem:.6f}"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-filter_complex", f"[0:v]setpts=PTS*{video_setpts:.6f}[v];[0:a]{atempo}[a]",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{target:.3f}",                 # HARD trim to 4.95s
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


drv = build("drive", "v3", credentials=get_credentials())


def upload_drive(p: Path) -> tuple:
    media = MediaFileUpload(str(p), mimetype="video/mp4", resumable=False)
    f = drv.files().create(body={"name": p.name}, media_body=media, fields="id").execute()
    fid = f["id"]
    drv.permissions().create(fileId=fid, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/uc?export=download&id={fid}", fid


results = []
for t in TARGETS:
    print(f"\n→ {t['name']}: re-encoding with hard -t 4.95")
    dst = OUT_DIR / f"{t['name']}.mp4"
    speed_and_trim(t["src"], dst, target=4.95)
    new_dur = get_duration(dst)
    print(f"   out: {dst.name} = {new_dur:.3f}s")
    drive_url, fid = upload_drive(dst)
    print(f"   drive: {drive_url}")
    aid = bp.create_asset(GROUP, drive_url, "Video", t["asset_name"])
    print(f"   asset: {aid} (polling…)")
    info = bp.poll_asset(aid, timeout=600)
    status = info.get("Status") or info.get("status")
    print(f"   status: {status}")
    prev_aid = prev_by_name.get(t["name"], {}).get("asset_id")
    results.append({
        "name": t["name"],
        "asset_name": t["asset_name"],
        "local": str(dst),
        "duration_s": new_dur,
        "drive_id": fid,
        "drive_url": drive_url,
        "asset_id": aid,
        "status": status,
        "supersedes_asset_id": prev_aid,
    })

MF.write_text(json.dumps(results, indent=2))
print(f"\nWrote manifest: {MF}")
for r in results:
    sup = f"  (replaces {r['supersedes_asset_id']})" if r["supersedes_asset_id"] else ""
    print(f"  {r['name']:8} {r['duration_s']:.3f}s  {r['asset_id']}  {r['status']}{sup}")

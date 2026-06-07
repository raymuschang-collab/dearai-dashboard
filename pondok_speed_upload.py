#!/usr/bin/env python3
"""Speed up two Pondok Indah character intro MP4s to 4.95s each, then upload
to BytePlus as Video assets.

Source: ~/Downloads/Pondok Indah Test/Character_introduction_montage_w…_{nnnn}.mp4
        (both currently 10.00s)
Target: 4.95s  ->  speed factor 2.0202×
        ffmpeg: setpts=PTS*0.495 (video), atempo=2.0,atempo=1.0101 (audio)

Output local:
  ~/Downloads/Pondok Indah Test/sped_4.95s/jane.mp4
  ~/Downloads/Pondok Indah Test/sped_4.95s/karina.mp4

Then: upload to Drive (anyone-with-link) → BytePlus create_asset(Video) → poll.
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
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [
    {
        "src": SRC / "Character_introduction_montage_w…_202606021617.mp4",
        "name": "jane",
        "asset_name": "Pondok Indah — Jane (4.95s)",
    },
    {
        "src": SRC / "Character_introduction_montage_w…_202606021607.mp4",
        "name": "karina",
        "asset_name": "Pondok Indah — Karina (4.95s)",
    },
]


def speed_up(src: Path, dst: Path, factor: float = 2.0202):
    """factor = source_dur / target_dur. setpts uses 1/factor; audio uses atempo chain."""
    video_setpts = 1.0 / factor          # 0.495 for 2.0202
    # atempo chain: max 2.0 per filter — split into 2.0 and the remainder
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
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def get_duration(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(p)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


drv = build("drive", "v3", credentials=get_credentials())


def upload_drive(p: Path) -> str:
    media = MediaFileUpload(str(p), mimetype="video/mp4", resumable=False)
    meta = {"name": p.name}
    f = drv.files().create(body=meta, media_body=media, fields="id").execute()
    fid = f["id"]
    drv.permissions().create(fileId=fid, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/uc?export=download&id={fid}", fid


results = []
for t in TARGETS:
    if not t["src"].exists():
        print(f"MISSING: {t['src']}")
        continue
    src_dur = get_duration(t["src"])
    factor = src_dur / 4.95
    print(f"\n→ {t['name']}: source {src_dur:.3f}s, factor {factor:.4f}× → 4.95s")
    dst = OUT_DIR / f"{t['name']}.mp4"
    speed_up(t["src"], dst, factor)
    new_dur = get_duration(dst)
    print(f"   out: {dst.name} = {new_dur:.3f}s")
    drive_url, fid = upload_drive(dst)
    print(f"   drive: {drive_url}")
    aid = bp.create_asset(GROUP, drive_url, "Video", t["asset_name"])
    print(f"   asset: {aid} (polling…)")
    info = bp.poll_asset(aid, timeout=600)
    status = info.get("Status") or info.get("status")
    print(f"   status: {status}")
    results.append({
        "name": t["name"],
        "asset_name": t["asset_name"],
        "local": str(dst),
        "duration_s": new_dur,
        "drive_id": fid,
        "drive_url": drive_url,
        "asset_id": aid,
        "status": status,
    })

mf = OUT_DIR / "byteplus_uploads.json"
mf.write_text(json.dumps(results, indent=2))
print(f"\nWrote manifest: {mf}")
for r in results:
    print(f"  {r['name']:8} {r['duration_s']:.2f}s  {r['asset_id']}  {r['status']}")

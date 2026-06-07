#!/usr/bin/env python3
"""Upload 5 X-Men PNG references to Drive → register as BytePlus Image assets."""
import os
import sys
import json
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv
from PIL import Image
import tempfile

sys.path.insert(0, str(Path(__file__).parent))
from auth import get_credentials
import byteplus_asset_v2 as bp

load_dotenv(Path(__file__).parent / ".env")
GROUP = os.getenv("BYTEPLUS_GROUP_ID")
ASSETS_DIR = Path("/Users/raymuschang/Desktop/X-men/Assets")

# (local filename, BytePlus asset name)
SOURCES = [
    ("small demon.png",              "X-Men Seq1 Small Demon"),
    ("large demon.png",              "X-Men Seq2 Large Demon"),
    ("blocking 1.png",               "X-Men Seq1 Blocking"),
    ("blocking 2.png",               "X-Men Seq2 Blocking 2"),
    ("Image Adjustment Request.png", "X-Men Seq2 Blocking IAR"),
]

drv = build("drive", "v3", credentials=get_credentials())


MIN_PX = 600           # BytePlus min is 300; keep safe margin
ASPECT_LIMIT = 2.4     # BytePlus accepts 0.4–2.5; keep safe margin


def ensure_min_size(path: Path) -> Path:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    changed = False
    # 1. upscale to MIN_PX on shorter side
    if min(w, h) < MIN_PX:
        scale = MIN_PX / min(w, h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        im = im.resize((nw, nh), Image.LANCZOS)
        w, h = nw, nh
        changed = True
        print(f"  upscaled to {w}x{h}")
    # 2. pad with black if aspect > ASPECT_LIMIT
    aspect = max(w, h) / min(w, h)
    if aspect > ASPECT_LIMIT:
        if w > h:
            target_h = int(round(w / ASPECT_LIMIT)) + 1
            pad = (target_h - h) // 2
            new_im = Image.new("RGB", (w, target_h), (0, 0, 0))
            new_im.paste(im, (0, pad))
            im = new_im
            h = target_h
        else:
            target_w = int(round(h / ASPECT_LIMIT)) + 1
            pad = (target_w - w) // 2
            new_im = Image.new("RGB", (target_w, h), (0, 0, 0))
            new_im.paste(im, (pad, 0))
            im = new_im
            w = target_w
        changed = True
        print(f"  padded to {w}x{h} (aspect {w/h:.2f})")
    if not changed:
        return path
    out = Path(tempfile.gettempdir()) / f"fixed_{path.stem}_{w}x{h}.png"
    im.save(out, "PNG")
    return out


def upload_to_drive(path: Path, display_name: str) -> str:
    media = MediaFileUpload(str(path), mimetype="image/png", resumable=False)
    meta = {"name": display_name}
    f = drv.files().create(body=meta, media_body=media, fields="id").execute()
    fid = f["id"]
    drv.permissions().create(fileId=fid, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/uc?export=download&id={fid}"


results = []
for local_name, asset_name in SOURCES:
    p = ASSETS_DIR / local_name
    if not p.exists():
        print(f"MISSING: {p}")
        continue
    print(f"\n→ {local_name}")
    try:
        p_use = ensure_min_size(p)
        url = upload_to_drive(p_use, local_name)
        print(f"  drive: {url}")
        aid = bp.create_asset(GROUP, url, "Image", asset_name)
        print(f"  asset: {aid}  (polling…)")
        info = bp.poll_asset(aid, timeout=600)
        status = info.get("Status") or info.get("status")
        print(f"  status: {status}")
        results.append({"name": asset_name, "local": local_name, "drive_url": url,
                        "asset_id": aid, "status": status})
    except Exception as e:
        print(f"  FAILED: {e}")
        results.append({"name": asset_name, "local": local_name, "error": str(e)})

OUT = Path(__file__).parent / "xmen_assets.json"
OUT.write_text(json.dumps(results, indent=2))
print(f"\nWrote {OUT}")
for r in results:
    print(f"  {r['name']:40} {r['asset_id']}  {r['status']}")

#!/usr/bin/env python3
"""Pondok Indah funeral scene — Seedance 2.0 fire.

480p · 9:16 (per ANCHOR 1.png aspect) · 8s · 1 iter.
Refs:
  - ANCHOR 1.png  (location/blocking, uploaded as Image asset)
  - Tommy:        asset-20260603132552-rv5db   (image, existing)
  - Jane image:   asset-20260603154602-p8vfj   (image, existing)
  - Jane motion:  asset-20260603200635-nmbc5   (video, just uploaded)
  - Karina motion:asset-20260603200646-xr694   (video, just uploaded)
"""
import os
import sys
import time
import json
from pathlib import Path

import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

sys.path.insert(0, "/Users/raymuschang/Documents/Shotlist Workflows")
from auth import get_credentials
import byteplus_asset_v2 as bp

HERE = Path("/Users/raymuschang/Documents/Shotlist Workflows")
load_dotenv(HERE / ".env")

ARK_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
GROUP = os.getenv("BYTEPLUS_GROUP_ID")
ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
MODEL = "dreamina-seedance-2-0-260128"

ANCHOR = Path("/Users/raymuschang/Downloads/Pondok Indah Test/ANCHOR 1.png")
OUT_DIR = Path("/Users/raymuschang/Downloads/Pondok Indah Test/Generated")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOMMY      = "asset-20260603132552-rv5db"
JANE_IMG   = "asset-20260603154602-p8vfj"
JANE_VID   = "asset-20260603200635-nmbc5"
KARINA_VID = "asset-20260603200646-xr694"


# ---- 1. upload ANCHOR 1.png to Drive + create BytePlus image asset ----
drv = build("drive", "v3", credentials=get_credentials())

print("→ uploading ANCHOR 1.png to Drive")
media = MediaFileUpload(str(ANCHOR), mimetype="image/png", resumable=False)
f = drv.files().create(body={"name": ANCHOR.name}, media_body=media, fields="id").execute()
fid = f["id"]
drv.permissions().create(fileId=fid, body={"role": "reader", "type": "anyone"}).execute()
drive_url = f"https://drive.google.com/uc?export=download&id={fid}"
print(f"   drive: {drive_url}")

print("→ creating BytePlus Image asset for ANCHOR 1")
ANCHOR_ASSET = bp.create_asset(GROUP, drive_url, "Image", "Pondok Indah — ANCHOR 1 (Funeral Location)")
print(f"   asset: {ANCHOR_ASSET} (polling…)")
info = bp.poll_asset(ANCHOR_ASSET, timeout=600)
print(f"   status: {info.get('Status')}")


# ---- 2. build prompt verbatim from user's brief ----
PROMPT = """Shot with Arri Alexa, 35mm film. Documentary-style naturalistic photograph, desaturated muted color palette evoking prestige drama cinematography.

Reference identities:
- Reference image #1 = ANCHOR 1 location / blocking — funeral interior with the open coffin. Follow this for composition, blocking, depth.
- Reference image #2 = TOMMY — in the open coffin, peaceful, still (face reference).
- Reference image #3 = JANE — hunched over the coffin (face reference).
- Reference video #4 = JANE — motion / wardrobe / voice reference. She stands in front of the coffin, on the left side of the frame.
- Reference video #5 = KARINA — motion / wardrobe / voice reference. She stands to the right of the frame.

VERTICAL 9:16 prestige drama format. Continuous scene, three shots cut together:

SHOT 1 — Static ECU, ~2 seconds:
ECU on TOMMY's face in the open coffin. Peaceful. Still.
Camera TILTS UP from Tommy's coffin to JANE — hunched over the coffin edge, not standing straight, shoulders shaking, tears falling.
JANE (American English, broken whisper — to Tommy): "Why... Why... you must go..."
KARINA cuts through the crowd, stops behind Jane.
KARINA (Jakarta Bahasa, cold fury, controlled): "Pelacur macam kamu ngapain ada di sini!"

SMASH CUT →

SHOT 3 — Extreme Close-Up, ~2 seconds:
ECU on JANE's cheek. KARINA's palm connects sharply — the slap lands clean on her cheek, skin impact visible. No blood. Wedding ring catches the light as the hand pulls away.
BRIEF FREEZE FRAME — 0.5 seconds frozen at the moment of impact.

SMASH CUT →

SHOT 4 — Static CU, ~3 seconds:
Jane absorbs the slap. Slowly straightens. Jaw set. Eyes wet but steady.
JANE (American English, quiet certainty): "I am his wife."
"""

content = [
    {"type": "text", "text": PROMPT},
    {"type": "image_url", "image_url": {"url": f"asset://{ANCHOR_ASSET}"}, "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{TOMMY}"},        "role": "reference_image"},
    {"type": "image_url", "image_url": {"url": f"asset://{JANE_IMG}"},     "role": "reference_image"},
    {"type": "video_url", "video_url": {"url": f"asset://{JANE_VID}"},     "role": "reference_video"},
    {"type": "video_url", "video_url": {"url": f"asset://{KARINA_VID}"},   "role": "reference_video"},
]

body = {
    "model": MODEL,
    "content": content,
    "ratio": "9:16",
    "duration": 8,
    "resolution": "480p",
    "watermark": False,
}

print("\n→ submitting Pondok Indah funeral scene (480p / 9:16 / 8s / 1 iter)")
r = requests.post(f"{ARK_BASE}/contents/generations/tasks",
                  headers={"Authorization": f"Bearer {ARK_KEY}",
                           "Content-Type": "application/json"},
                  json=body, timeout=60)
r.raise_for_status()
tid = r.json()["id"]
print(f"   task id: {tid}")

last = None
start = time.time()
while True:
    time.sleep(15)
    elapsed = int(time.time() - start)
    rr = requests.get(f"{ARK_BASE}/contents/generations/tasks/{tid}",
                      headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=60)
    rr.raise_for_status()
    d = rr.json()
    status = d.get("status")
    if status != last:
        print(f"   [{elapsed}s] status: {status}")
        last = status
    if status == "succeeded":
        video_url = (d.get("content") or {}).get("video_url")
        print(f"   url: {video_url}")
        out = OUT_DIR / "PondokIndah_Funeral_480p_9x16_8s.mp4"
        with requests.get(video_url, stream=True, timeout=300) as rd:
            rd.raise_for_status()
            with open(out, "wb") as f:
                for chunk in rd.iter_content(1 << 20):
                    f.write(chunk)
        print(f"   saved: {out}")
        manifest = {
            "task_id": tid,
            "video_url": video_url,
            "local": str(out),
            "anchor_asset_id": ANCHOR_ASSET,
            "refs": [
                ("location/blocking", ANCHOR_ASSET, "Image"),
                ("Tommy", TOMMY, "Image"),
                ("Jane (still)", JANE_IMG, "Image"),
                ("Jane (motion)", JANE_VID, "Video"),
                ("Karina (motion)", KARINA_VID, "Video"),
            ],
        }
        (OUT_DIR / "funeral_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
        print(f"   manifest: {OUT_DIR / 'funeral_manifest.json'}")
        break
    if status in ("failed", "expired", "cancelled"):
        print(f"   PAYLOAD: {json.dumps(d)[:600]}")
        sys.exit(2)

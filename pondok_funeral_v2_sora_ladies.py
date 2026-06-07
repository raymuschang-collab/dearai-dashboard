#!/usr/bin/env python3
"""Pondok Indah funeral × 5 anchors — v2 with NEW Sora 2 lady refs.

Step 1: upload new Jane + Karina Sora 2 clips to BytePlus as Video assets.
Step 2: fire 5 Seedance jobs (1 per existing anchor asset_id from v1),
        swapping in the new lady refs (Tommy unchanged).
        480p / 9:16 / 8s / 1 iter each. Output -> Generated/v2_new_ladies/.
"""
import os
import sys
import time
import json
import re
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

DOWNLOADS = Path("/Users/raymuschang/Downloads")
OUT_DIR = Path("/Users/raymuschang/Downloads/Pondok Indah Test/Generated/v2_new_ladies")
OUT_DIR.mkdir(parents=True, exist_ok=True)

NEW_LADIES = [
    {"file": "hf_20260603_141501_9ad594f8-59fb-40e2-8d5d-d0fd78bde49b.mp4",
     "asset_name": "Pondok Indah — Jane (Sora 2, v2)"},
    {"file": "hf_20260603_141522_9fabccb8-a568-4d66-817a-d07e010feb7c.mp4",
     "asset_name": "Pondok Indah — Karina (Sora 2, v2)"},
]

# Existing anchors (already in BytePlus from previous run)
ANCHORS = [
    {"label": "ANCHOR_1",                  "asset_id": "asset-20260603220139-wfvh6"},
    {"label": "Ethereal_Transformation",   "asset_id": "asset-20260603220514-2jrkh"},
    {"label": "Funeral_Wake_Composition",  "asset_id": "asset-20260603220528-chchm"},
    {"label": "Funeral_Wake_Photography_1","asset_id": "asset-20260603220539-cqw22"},
    {"label": "Funeral_Wake_Photography",  "asset_id": "asset-20260603220551-2pgs9"},
]

TOMMY = "asset-20260603132552-rv5db"   # unchanged


PROMPT = """Shot with Arri Alexa, 35mm film. Documentary-style naturalistic photograph, desaturated muted color palette evoking prestige drama cinematography.

Reference identities:
- Reference image #1 = LOCATION / BLOCKING — funeral interior with the open coffin. Follow this for composition, blocking, depth.
- Reference video #2 = TOMMY — in the open coffin, peaceful, still. Use this video to anchor Tommy's face.
- Reference video #3 = JANE — American English speaker, hunched over the coffin edge. Use this video to anchor Jane's face and voice. She stands in front of the coffin, on the left.
- Reference video #4 = KARINA — Jakarta Bahasa speaker. Use this video to anchor Karina's face and voice. She stands to the right.

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

drv = build("drive", "v3", credentials=get_credentials())


def upload_drive(p: Path) -> tuple:
    media = MediaFileUpload(str(p), mimetype="video/mp4", resumable=True)
    f = drv.files().create(body={"name": p.name}, media_body=media, fields="id").execute()
    fid = f["id"]
    drv.permissions().create(fileId=fid, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/uc?export=download&id={fid}", fid


# ---- 1. upload new ladies ----
new_assets = []
for lady in NEW_LADIES:
    p = DOWNLOADS / lady["file"]
    print(f"\n→ uploading {p.name}")
    drive_url, fid = upload_drive(p)
    print(f"   drive: {drive_url}")
    aid = bp.create_asset(GROUP, drive_url, "Video", lady["asset_name"])
    print(f"   asset: {aid} (polling…)")
    info = bp.poll_asset(aid, timeout=900)
    status = info.get("Status")
    print(f"   status: {status}")
    new_assets.append({"name": lady["asset_name"], "asset_id": aid, "status": status,
                       "drive_id": fid})

# By upload order: index 0 = Jane, index 1 = Karina
JANE_V2 = new_assets[0]["asset_id"]
KARINA_V2 = new_assets[1]["asset_id"]
print(f"\nJANE v2 = {JANE_V2}")
print(f"KARINA v2 = {KARINA_V2}")


# ---- 2. fire 5 jobs ----
def submit_job(anchor_aid: str) -> str:
    content = [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"asset://{anchor_aid}"},
         "role": "reference_image"},
        {"type": "video_url", "video_url": {"url": f"asset://{TOMMY}"},
         "role": "reference_video"},
        {"type": "video_url", "video_url": {"url": f"asset://{JANE_V2}"},
         "role": "reference_video"},
        {"type": "video_url", "video_url": {"url": f"asset://{KARINA_V2}"},
         "role": "reference_video"},
    ]
    body = {"model": MODEL, "content": content,
            "ratio": "9:16", "duration": 8, "resolution": "480p",
            "watermark": False}
    r = requests.post(f"{ARK_BASE}/contents/generations/tasks",
                      headers={"Authorization": f"Bearer {ARK_KEY}",
                               "Content-Type": "application/json"},
                      json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"submit {r.status_code}: {r.text[:400]}")
    return r.json()["id"]


fired = []
for a in ANCHORS:
    print(f"\n→ submitting {a['label']} (anchor {a['asset_id']})")
    tid = submit_job(a["asset_id"])
    print(f"   task id: {tid}")
    fired.append({"label": a["label"], "anchor_asset_id": a["asset_id"],
                  "task_id": tid, "status": "queued",
                  "video_url": None, "local": None,
                  "jane_v2": JANE_V2, "karina_v2": KARINA_V2})

# ---- 3. poll ----
remaining = {j["task_id"]: j for j in fired}
start = time.time()
while remaining:
    time.sleep(15)
    elapsed = int(time.time() - start)
    for tid in list(remaining.keys()):
        j = remaining[tid]
        try:
            r = requests.get(f"{ARK_BASE}/contents/generations/tasks/{tid}",
                             headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=60)
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            print(f"   [{elapsed}s] {j['label']} poll err: {e}")
            continue
        status = d.get("status")
        if status != j["status"]:
            print(f"   [{elapsed}s] {j['label']}: {j['status']} -> {status}")
            j["status"] = status
        if status == "succeeded":
            j["video_url"] = (d.get("content") or {}).get("video_url")
            print(f"       url: {j['video_url']}")
            del remaining[tid]
        elif status in ("failed", "expired", "cancelled"):
            j["error"] = d.get("error")
            print(f"       payload: {json.dumps(d.get('error'))[:300]}")
            del remaining[tid]

# ---- 4. download ----
for j in fired:
    if j["status"] == "succeeded" and j["video_url"]:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", j["label"])
        out = OUT_DIR / f"PondokIndah_Funeral_{safe}_v2_480p_9x16_8s.mp4"
        print(f"\n↓ {j['label']} → {out.name}")
        with requests.get(j["video_url"], stream=True, timeout=300) as rd:
            rd.raise_for_status()
            with open(out, "wb") as f:
                for chunk in rd.iter_content(1 << 20):
                    f.write(chunk)
        j["local"] = str(out)
    else:
        print(f"\n✗ {j['label']} failed: {j.get('error')}")

(OUT_DIR / "funeral_v2_manifest.json").write_text(
    json.dumps({"new_lady_assets": new_assets, "fires": fired}, indent=2, default=str))
print("\nDONE.")
for j in fired:
    print(f"  {j['label']:28} {j['status']:10} {j.get('local','')}")

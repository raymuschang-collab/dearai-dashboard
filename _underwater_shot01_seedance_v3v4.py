#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 01 Seedance v3 + v4.
Same prompt as v1/v2 but with UNDERWATER PALACE 5s location video ref added.

Refs:
  - image: SHOT1 RESTYLED ENDFRAME (already uploaded)
  - video: EMPEROR character orbit (4.4s)
  - video: UNDERWATER PALACE 5s (to upload)
  - audio: SHOT1 DIALOGUE (already uploaded)

Video budget: 4.4 + 5 = 9.4s ✓
"""
import io, json, os, re, sys, time
from pathlib import Path

import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials
import byteplus_asset_v2 as bp

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]
GROUP_ID = "group-20260505195134-wqx2b"

SHOT_DIR = Path("/Users/raymuschang/Documents/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 01")
OUT_DIR = SHOT_DIR / "seedance outputs"
LOCATION_5S_LOCAL = Path("/Users/raymuschang/Downloads/underwater_palace_5s.mp4")

# Known refs (already on BytePlus)
EMPEROR_REF       = "asset://asset-20260517201230-7trww"   # 4.4s video character ref
AUDIO_ASSET       = "asset://asset-20260518090743-8x6g5"   # SHOT1 DIALOGUE
ENDFRAME_ASSET    = "asset://asset-20260518090753-ztgw5"   # SHOT1 RESTYLED ENDFRAME

GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
Staging note: Soldiers standing behind the characters and in front of the throne at ALL times.
"""

SHOT_PROMPT = """1, 8s, MS, Jib Down, Camera jibs down onto Grace's emperor seated on the underwater throne. An enormous golden pillar lies diagonally across him — slanting from the top-left of frame down to the bottom-right — pressing his head and right shoulder down. He struggles against its weight, neck strained, jaw set, fingers gripping the pillar as he tries to push it off. Behind him: ornate underwater palace columns, kelp and coral, soldiers standing guard in armor. Schools of fish drift through the background. Light shafts pierce the water from above. (Emperor: jaw tight; eyes desperate; veins in his neck stand out as he strains), Underwater ambient — slow bubbles, deep water-pressure SFX, the muffled groan of the pillar shifting, distant kelp swaying."""


def upload_palace_5s():
    """Upload Underwater Palace 5s to Drive + BytePlus. Returns asset_id."""
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    folder_name = "Channel 8 Test Shoot — Character Refs"
    res = drive.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
    ).execute()
    parent = res["files"][0]["id"]

    print("  ◦ uploading UNDERWATER PALACE 5s...")
    media = MediaFileUpload(str(LOCATION_5S_LOCAL), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": "Underwater_Palace_5s.mp4", "parents": [parent]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    download_url = f"https://drive.google.com/uc?export=download&id={fid}"
    aid = bp.create_asset(GROUP_ID, download_url, "Video", name="UNDERWATER PALACE 5s")
    bp.poll_asset(aid, timeout=300)
    print(f"    ✓ location asset (5s): {aid}")
    return aid


def submit(content_block):
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content_block,
        "ratio": "16:9",
        "duration": 8,
        "resolution": "720p",
        "watermark": False,
    }
    r = requests.post(
        f"{ARK_BASE}/contents/generations/tasks",
        headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"submit failed: {r.status_code} {r.text[:500]}")
    return r.json().get("id") or r.json().get("task_id")


def poll(task_id, max_wait=1800):
    start = time.time(); last = None
    while time.time() - start < max_wait:
        r = requests.get(f"{ARK_BASE}/contents/generations/tasks/{task_id}",
                          headers={"Authorization": f"Bearer {ARK_KEY}"}, timeout=30)
        if r.status_code != 200:
            time.sleep(30); continue
        resp = r.json(); status = resp.get("status")
        if status != last:
            print(f"    [{int(time.time()-start)}s] {status}", flush=True)
            last = status
        if status in ("succeeded", "completed", "success"):
            return resp
        if status in ("failed", "expired", "cancelled"):
            raise RuntimeError(f"failure: {json.dumps(resp)[:500]}")
        time.sleep(30)
    raise RuntimeError("30-min cap exceeded")


def extract_url(resp):
    c = resp.get("content", {})
    if isinstance(c, dict):
        v = c.get("video_url")
        if isinstance(v, str): return v
        if isinstance(v, dict): return v.get("url")
    m = re.search(r'https://[^\s"\']*\.mp4[^\s"\']*', json.dumps(resp))
    return m.group(0) if m else ""


def main():
    t0 = time.time()

    palace_aid = upload_palace_5s()
    palace_ref = f"asset://{palace_aid}"

    refs = [
        ("image", ENDFRAME_ASSET,  "SHOT1 RESTYLED ENDFRAME"),
        ("video", EMPEROR_REF,     "EMPEROR character orbit (4.4s)"),
        ("video", palace_ref,      "UNDERWATER PALACE 5s"),
        ("audio", AUDIO_ASSET,     "SHOT1 DIALOGUE"),
    ]

    prompt = GLOBALS + "\n\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  refs: {len(refs)} (4.4+5 = 9.4s video budget)")
    for kind, url, label in refs:
        print(f"  {kind:<6} → {url}  ({label})")

    # Build content block once, fire twice
    content = [{"type": "text", "text": prompt}]
    for kind, url, _ in refs:
        if kind == "video":
            content.append({"type": "video_url", "video_url": {"url": url}, "role": "reference_video"})
        elif kind == "image":
            content.append({"type": "image_url", "image_url": {"url": url}, "role": "reference_image"})
        elif kind == "audio":
            content.append({"type": "audio_url", "audio_url": {"url": url}, "role": "reference_audio"})

    tasks = []
    for v in (3, 4):
        print(f"\n  ◦ submitting v{v}...")
        tid = submit(content)
        print(f"    ✓ v{v} task_id: {tid}")
        tasks.append((v, tid))

    print(f"\n  Polling both (typical 4-10 min)...")
    for v, tid in tasks:
        print(f"\n  ◦ v{v} ({tid})")
        result = poll(tid)
        video_url = extract_url(result)
        if not video_url:
            print(f"    ✗ no URL")
            continue
        data = requests.get(video_url, timeout=600).content
        out_path = OUT_DIR / f"shot_01_underwater_v{v}_with_location_720p_8s.mp4"
        out_path.write_bytes(data)
        print(f"    ✓ saved: {out_path}")

    print(f"\n=== ALL DONE  ·  wall: {time.time()-t0:.1f}s ===")


if __name__ == "__main__":
    main()

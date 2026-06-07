#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 07 Seedance vidgen.
15s · 720p · 16:9 · 4-shot montage: minister + soldier approach throne with covered dish.

Refs:
  - video: MINISTER character (4.4s)
  - video: EMPEROR character (4.4s)
  - video: UNDERWATER PALACE 5s (location)
  - audio: SHOT7 DIALOGUE (mp3, ~3s)

Video budget: 4.4 + 4.4 + 5 = 13.8s ✓
Note: PRINCESS + ELDER are kneeling supporting roles, described textually only
(adding their refs would bust the 15s video budget).
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

SHOT_DIR = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 07")
AUDIO_LOCAL = SHOT_DIR / "Shot 7_Audio.mp3"
OUT_DIR = SHOT_DIR / "seedance outputs"
OUT_DIR.mkdir(exist_ok=True)

# Known refs (already on BytePlus)
EMPEROR_REF       = "asset://asset-20260517201230-7trww"   # EMPEROR 4.4s
MINISTER_REF      = "asset://asset-20260517201250-rhxdq"   # MINISTER 4.4s
PALACE_5S_REF     = "asset://asset-20260518091014-sjcnr"   # UNDERWATER PALACE 5s

GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
Staging note: Soldiers standing behind the characters and in front of the throne at ALL times.
"""

SHOT_PROMPT = """7, 15s, multi-shot montage (WS → WS → WS → overhead MS), Static cuts —

Shot A (WS, 4s, slow forward dolly): The minister and a footsoldier enter the underwater palace from the rear of the hall. Together they carry a large ceremonial dish covered with a deep red silk cloth concealing what looks like an enormous food offering. They begin the long walk down the central aisle toward the distant throne. Aisle flanked by tall ornate columns wrapped in coral and kelp. Schools of fish drift through the upper frame. Light shafts pierce the water from above.

Shot B (WS, 3s, tracking side-on as they walk): Continuing down the aisle. Their hanfu robes billow in the gentle underwater currents. The red silk on the dish ripples slightly with the water flow. Stoic footsoldiers in armor line the aisle on both sides, standing at attention.

Shot C (WS, 4s, low angle from near the throne looking back at them approaching): The throne fills the upper foreground; the EMPEROR sits on it. In the mid-ground, kneeling in a row before the throne facing the minister: the PRINCESS and the ELDER, heads slightly bowed. The minister + footsoldier approach with the covered dish. Soldiers stand guard behind the throne.

Shot D (overhead MS 2-shot, 4s, high jib angle looking down): The minister and footsoldier stop in front of the throne and lower the dish slightly. The minister raises his head and greets the emperor. MINISTER: (Singapore Chinese accent) speaks the greeting — see attached audio reference for tone and cadence. (Minister: respectful, head bowed; footsoldier: silent, eyes forward), Bubble streams; muffled water-pressure rumble; faint clink of armor; the soft groan of the dish settling."""


def upload_audio() -> str:
    """Upload SHOT7 dialogue mp3 to Drive + BytePlus. Returns asset_id."""
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    folder_name = "Channel 8 Test Shoot — Character Refs"
    res = drive.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
    ).execute()
    parent = res["files"][0]["id"]

    print("  ◦ uploading SHOT7 dialogue audio...")
    media = MediaFileUpload(str(AUDIO_LOCAL), mimetype="audio/mpeg", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": "Shot7_Audio.mp3", "parents": [parent]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    download = f"https://drive.google.com/uc?export=download&id={fid}"
    aid = bp.create_asset(GROUP_ID, download, "Audio", name="SHOT7 DIALOGUE")
    bp.poll_asset(aid, timeout=300)
    print(f"    ✓ audio asset: {aid}")
    return aid


def submit(content_block):
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content_block,
        "ratio": "16:9",
        "duration": 15,
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

    audio_aid = upload_audio()
    audio_ref = f"asset://{audio_aid}"

    refs = [
        ("video", MINISTER_REF,  "MINISTER (4.4s)"),
        ("video", EMPEROR_REF,   "EMPEROR (4.4s)"),
        ("video", PALACE_5S_REF, "UNDERWATER PALACE 5s"),
        ("audio", audio_ref,     "SHOT7 DIALOGUE"),
    ]

    prompt = GLOBALS + "\n\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars  ·  video budget: 13.8s ✓")
    for kind, url, label in refs:
        print(f"  {kind:<6} → {url}  ({label})")

    content = [{"type": "text", "text": prompt}]
    for kind, url, _ in refs:
        if kind == "video":
            content.append({"type": "video_url", "video_url": {"url": url}, "role": "reference_video"})
        elif kind == "image":
            content.append({"type": "image_url", "image_url": {"url": url}, "role": "reference_image"})
        elif kind == "audio":
            content.append({"type": "audio_url", "audio_url": {"url": url}, "role": "reference_audio"})

    print(f"\n  ◦ submitting shot 07 (15s · 720p · 16:9)...")
    tid = submit(content)
    print(f"    ✓ task_id: {tid}")
    result = poll(tid)
    video_url = extract_url(result)
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / "shot_07_underwater_v1_720p_15s.mp4"
    out_path.write_bytes(data)
    print(f"\n=== DONE  ·  wall: {time.time()-t0:.1f}s ===")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

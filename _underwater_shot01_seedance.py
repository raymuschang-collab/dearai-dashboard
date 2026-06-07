#!/usr/bin/env python3
"""Channel 8 Underwater — Shot 01 Seedance vidgen.

Step 1: Upload audio + restyled endframe to BytePlus (one-time).
Step 2: Fire 2 versions at 720p 16:9 Seedance Pro.

Project globals (locked from 2026-05-18 onward, all Channel 8 Underwater prompts):
- Setting: Underwater palace, Chinese fantasy drama
- Look: Realistic practical effects — NO game look
- No music, SFX only — underwater SFX with bubbles and water sounds
- Accents: Singapore Chinese
- Camera: Arri 35, ambient light refracting + streaming underwater, wave reflections on surfaces + characters
- Always: soldiers standing behind characters and in front of throne
- Resolution: 720p, 16:9
"""
import io, json, os, re, sys, time
from pathlib import Path

import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402
import byteplus_asset_v2 as bp  # noqa: E402

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]
GROUP_ID = "group-20260505195134-wqx2b"

SHOT_DIR = Path("/Users/raymuschang/Desktop/Video Editing/clients/Channel 8 Test Shoot/cuts/splits/shot 01")
AUDIO_LOCAL = SHOT_DIR / "Shot 1_Audio.mp3"   # BytePlus rejects .m4a; mp3 only
IMAGE_LOCAL = SHOT_DIR / "first and last frames" / "shot 1.png"
OUT_DIR = SHOT_DIR / "seedance outputs"
OUT_DIR.mkdir(exist_ok=True)

# Known refs (uploaded earlier)
EMPEROR_REF = "asset://asset-20260517201230-7trww"   # 4.4s video character ref

# ────────── GLOBALS ──────────
GLOBALS = """Setting: Underwater palace — Chinese fantasy drama.
Look: Realistic, practical-effects feel — NO game / CGI / cartoon look. Documentary cinema realism.
No music — SFX only: underwater SFX with bubbles and water sounds.
Accents: Singapore Chinese accent on all dialogue.
Camera: Shot with Arri 35. Ambient light refracting and streaming through the underwater environment. Wave reflections visible on surfaces and on characters in the water.
Staging note: Soldiers standing behind the characters and in front of the throne at ALL times.
"""

# ────────── SHOT 1 ──────────
SHOT_PROMPT = """1, 8s, MS, Jib Down, Camera jibs down onto Grace's emperor seated on the underwater throne. An enormous golden pillar lies diagonally across him — slanting from the top-left of frame down to the bottom-right — pressing his head and right shoulder down. He struggles against its weight, neck strained, jaw set, fingers gripping the pillar as he tries to push it off. Behind him: ornate underwater palace columns, kelp and coral, soldiers standing guard in armor. Schools of fish drift through the background. Light shafts pierce the water from above. (Emperor: jaw tight; eyes desperate; veins in his neck stand out as he strains), Underwater ambient — slow bubbles, deep water-pressure SFX, the muffled groan of the pillar shifting, distant kelp swaying."""


def upload_to_drive(drive, parent_id: str, local_path: Path, mime: str) -> tuple[str, str]:
    """Returns (drive_view_url, download_url)."""
    media = MediaFileUpload(str(local_path), mimetype=mime, resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": local_path.name, "parents": [parent_id]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    fid = f["id"]
    return f["webViewLink"], f"https://drive.google.com/uc?export=download&id={fid}"


def step1_upload_refs() -> tuple[str, str]:
    """Upload audio + image to Drive + BytePlus. Returns (audio_asset_id, image_asset_id)."""
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    folder_name = "Channel 8 Test Shoot — Character Refs"
    res = drive.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)", pageSize=5,
    ).execute()
    parent = res["files"][0]["id"] if res.get("files") else None
    if not parent:
        raise RuntimeError("Could not find Channel 8 folder on Drive")

    print(f"=== Step 1: Upload refs to Drive + BytePlus ===")

    # Audio
    print(f"  ◦ uploading audio: {AUDIO_LOCAL.name}")
    _, audio_download = upload_to_drive(drive, parent, AUDIO_LOCAL, "audio/mpeg")
    audio_aid = bp.create_asset(GROUP_ID, audio_download, "Audio", name="SHOT1 DIALOGUE")
    bp.poll_asset(audio_aid, timeout=300)
    print(f"    ✓ audio asset: {audio_aid}")

    # Image
    print(f"  ◦ uploading endframe: {IMAGE_LOCAL.name}")
    image_drive_view, _ = upload_to_drive(drive, parent, IMAGE_LOCAL, "image/png")
    # For images, use lh3 binary URL
    import re as _re
    m = _re.search(r"/file/d/([^/]+)/", image_drive_view)
    fid = m.group(1)
    lh3 = f"https://lh3.googleusercontent.com/d/{fid}=w2048"
    image_aid = bp.create_asset(GROUP_ID, lh3, "Image", name="SHOT1 RESTYLED ENDFRAME")
    bp.poll_asset(image_aid, timeout=300)
    print(f"    ✓ image asset: {image_aid}")

    return audio_aid, image_aid


# ────────── Seedance fire ──────────
def submit_seedance(prompt: str, refs: list[dict], duration: int = 8) -> str:
    content = [{"type": "text", "text": prompt}]
    for r in refs:
        if r["type"] == "video":
            content.append({"type": "video_url", "video_url": {"url": r["url"]}, "role": "reference_video"})
        elif r["type"] == "image":
            content.append({"type": "image_url", "image_url": {"url": r["url"]}, "role": "reference_image"})
        elif r["type"] == "audio":
            content.append({"type": "audio_url", "audio_url": {"url": r["url"]}, "role": "reference_audio"})
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content,
        "ratio": "16:9",
        "duration": duration,
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


def poll_seedance(task_id: str, max_wait: int = 1800) -> dict:
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


def extract_url(resp: dict) -> str:
    c = resp.get("content", {})
    if isinstance(c, dict):
        v = c.get("video_url")
        if isinstance(v, str): return v
        if isinstance(v, dict): return v.get("url")
    m = re.search(r'https://[^\s"\']*\.mp4[^\s"\']*', json.dumps(resp))
    return m.group(0) if m else ""


def fire_version(version: int, prompt: str, refs: list[dict], duration: int) -> tuple[str, str]:
    """Fire one version. Returns (task_id, local_path)."""
    print(f"\n=== Submitting Shot 01 v{version} (720p 16:9 · {duration}s · {len(refs)} refs) ===")
    for r in refs:
        print(f"    {r['type']:<6} → {r['url']}  ({r.get('label','')})")
    tid = submit_seedance(prompt, refs, duration)
    print(f"    task_id: {tid}")
    result = poll_seedance(tid)
    video_url = extract_url(result)
    if not video_url:
        raise RuntimeError(f"no video URL in result: {json.dumps(result)[:500]}")
    data = requests.get(video_url, timeout=600).content
    out_path = OUT_DIR / f"shot_01_underwater_v{version}_720p_{duration}s.mp4"
    out_path.write_bytes(data)
    print(f"    ✓ saved: {out_path}")
    return tid, str(out_path)


def main():
    t0 = time.time()

    # Step 1 — upload refs
    audio_aid, image_aid = step1_upload_refs()

    refs = [
        {"type": "image", "url": f"asset://{image_aid}", "label": "SHOT1 RESTYLED ENDFRAME"},
        {"type": "video", "url": EMPEROR_REF,            "label": "EMPEROR character orbit (4.4s)"},
        {"type": "audio", "url": f"asset://{audio_aid}", "label": "SHOT1 DIALOGUE"},
    ]

    prompt = GLOBALS + "\n\n" + SHOT_PROMPT
    print(f"\nPrompt length: {len(prompt)} chars")

    # Step 2 — fire 2 versions in parallel (separate threads via simple sequential submit, sequential poll)
    # Easier: fire both submissions back-to-back, then poll both.
    print(f"\n=== Step 2: Fire 2 Seedance versions in parallel ===")

    # Submit both
    tasks = []
    for v in (1, 2):
        print(f"  ◦ submitting v{v}...")
        content = [{"type": "text", "text": prompt}]
        for r in refs:
            if r["type"] == "video":
                content.append({"type": "video_url", "video_url": {"url": r["url"]}, "role": "reference_video"})
            elif r["type"] == "image":
                content.append({"type": "image_url", "image_url": {"url": r["url"]}, "role": "reference_image"})
            elif r["type"] == "audio":
                content.append({"type": "audio_url", "audio_url": {"url": r["url"]}, "role": "reference_audio"})
        body = {
            "model": "dreamina-seedance-2-0-260128",
            "content": content,
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
            print(f"    ✗ submit failed: {r.status_code} {r.text[:300]}")
            continue
        tid = r.json().get("id") or r.json().get("task_id")
        print(f"    ✓ v{v} task_id: {tid}")
        tasks.append((v, tid))

    # Poll both
    print(f"\n  Polling both versions (typical wall: 4–10 min each)...")
    for v, tid in tasks:
        print(f"\n  ◦ v{v} ({tid})")
        result = poll_seedance(tid)
        video_url = extract_url(result)
        if not video_url:
            print(f"    ✗ no video URL in result")
            continue
        data = requests.get(video_url, timeout=600).content
        out_path = OUT_DIR / f"shot_01_underwater_v{v}_720p_8s.mp4"
        out_path.write_bytes(data)
        print(f"    ✓ saved: {out_path}")

    print(f"\n=== ALL DONE  ·  wall: {time.time()-t0:.1f}s ===")
    print(f"Outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()

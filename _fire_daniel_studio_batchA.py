#!/usr/bin/env python3
"""Fire Daniel home-studio scene — batch A (5 shots, 15s).
Verbatim user prompt. Refs: Grace (5s) + Daniel v2 (7s) = 12s ✓.
No location ref — studio described textually."""
import io, json, os, re, sys, time
from pathlib import Path
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]
SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"

PROMPT = """Shot with Arri Alexa, 35mm film, shallow depth of field.
No music. Dialogue in natural Singapore Chinese accent.
Contemporary Singapore — modern-day Tiong Bahru, present day. NOT period / NOT 1950s. Real-life, real-photo realism. Documentary editorial palette: oatmeal, cream, olive, charcoal, navy, oxblood. Kodak Portra 400 color science. Natural light only.

Location: Grace's Home Studio — NIGHT. A modern Tiong Bahru walk-up flat home studio. Twin-monitor desk, monstera plants, terrazzo flooring, cream walls, bamboo blinds half-drawn, warm desk lamp. Only the desk lamp and monitor glow illuminating the space.

1, 4s, MS, Low Angle Static, Low-angle medium shot of Grace at her twin-monitor home studio desk. Twin screens glowing, late night. Only the desk lamp and monitor glow lighting the room. Cream tee, loose ponytail falling out, hunched posture. Her hands move on the keyboard., (Eyes locked on screen; jaw set), Keyboard tap; faint screen hum. From behind her, coming into focus, Daniel enters from the doorway in the background holding a cup of hot tea. Faded navy shirt, glasses catching the lamp light. He approaches quietly and sets one mug of tea on Grace's desk beside her keyboard. He doesn't speak yet., (Gentle hand placement; doesn't push), Mug set down on wood. Daniel says: "又晚?" (Soft eyes; small head tilt; Singapore Chinese accent).

2, 4s, MS, Static, Medium shot of Grace. She doesn't turn from her screens — just lays it out flat., GRACE：Henley 简报六十页,星期五要交。Garrison 礼拜二 pitch。 (Singapore Chinese accent) (Eyes still on screen; voice flat, tired), Keyboard tap; screen hum.

3, 3s, MCU, Static, Cutaway — medium close-up of Daniel listening. He doesn't interrupt. Just absorbs it., (Eyes on Grace; mouth neutral; small nod after a beat), Distant traffic; quiet ambience.

4, 2s, MCU, Static, Medium close-up of Daniel., DANIEL：你的 newsletter? (Singapore Chinese accent) (Eyebrows lift slightly), Quiet ambience.

5, 2s, CU, Static, Close-up of Grace., GRACE：晚了三个礼拜。 (Singapore Chinese accent) (Tiny exhale; jaw tightens), Quiet ambience."""

REFS = [
    {"type": "video", "url": "asset://asset-20260514120424-thhzh", "label": "GRACE"},
    {"type": "video", "url": "asset://asset-20260516170559-t767w", "label": "DANIEL"},
]


def submit():
    content = [{"type": "text", "text": PROMPT}]
    for r in REFS:
        content.append({"type": "video_url", "video_url": {"url": r["url"]}, "role": "reference_video"})
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content,
        "ratio": "9:16",
        "duration": 15,
        "resolution": "480p",
        "watermark": False,
    }
    print(f"Submitting Daniel home-studio batch A (5 shots, 15s):")
    print(f"  prompt: {len(PROMPT)} chars  ·  refs: {len(REFS)}")
    for r in REFS:
        print(f"    {r['label']:<6} → {r['url']}")
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
            print(f"  [{int(time.time()-start)}s] {status}", flush=True)
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
    return m.group(0) if m else None


def main():
    t0 = time.time()
    task_id = submit()
    print(f"\n  task_id: {task_id}\n  polling...")
    result = poll(task_id)
    video_url = extract_url(result)
    r = requests.get(video_url, timeout=600); r.raise_for_status()
    data = r.content
    local = Path("/Users/raymuschang/Desktop/Claude Ad — Why I Almost Quit Generated Videos")
    local.mkdir(parents=True, exist_ok=True)
    local_path = local / "set-04-daniel-studio-batchA-480p-15s.mp4"
    local_path.write_bytes(data)

    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    def gc(parent, name):
        safe = name.replace("'", "\\'")
        q = f"'{parent}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='{safe}'"
        res = drive.files().list(q=q, fields="files(id)").execute()
        if res.get("files"): return res["files"][0]["id"]
        f = drive.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}, fields="id").execute()
        drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
        return f["id"]
    videos = gc(SHOW_FOLDER, "videos")
    sub = gc(videos, "set-04-daniel-studio")
    fname = "daniel-studio-batchA-480p-15s.mp4"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(body={"name": fname, "parents": [sub]}, media_body=media, fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    print(f"\n=== DONE ===")
    print(f"Drive: {f['webViewLink']}")
    print(f"Local: {local_path}")
    print(f"Wall: {time.time()-t0:.1f}s")
    Path("/tmp/daniel_studio_batchA_result.json").write_text(json.dumps({
        "task_id": task_id, "drive": f["webViewLink"], "local": str(local_path),
    }, indent=2))


if __name__ == "__main__":
    main()

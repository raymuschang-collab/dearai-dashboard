#!/usr/bin/env python3
"""Fire transformation+Saturday batch v2 — montage + Daniel arrival.
~22s content into 15s output, all 4 refs anchored."""
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
No music. Dialogue in natural local accent (English by default; Singapore Chinese accent for Chinese lines).
Contemporary Singapore — modern-day Tiong Bahru, present day. NOT period / NOT 1950s. Real-life, real-photo realism. Documentary editorial palette: oatmeal, cream, olive, charcoal, navy, oxblood. Kodak Portra 400 color science. Natural light only.

Location reference: see attached home studio video reference — same desk, twin-monitor setup, monstera plants, bamboo blinds.

Lighting and time of day: morning, warm morning light through bamboo blinds, subtle volumetric light. Note: shot 1 begins in late-night warmth and progressively transitions into morning light through the dissolves.

Laptop screen reference: see attached Claude.ai chat interface image — clean minimalist UI.

1, 6s, MS, montage cutaway sequence of Grace's home studio. Same desk, same two-screen setup, monstera plants, bamboo blinds half-drawn. Grace at her screens working and she scribbles onto an iPad — calmer face now. She smooths and scrunches up her hair as she thinks and gathers willpower., (Grace: absorbed, calmer; small private movements), Apple Pencil on iPad glass; faint piano swell underneath.

2, 1.5s, OTS CU, Static, Cut to over-the-shoulder close-up of the Claude.ai chat window open on one of her monitors — the chat interface clear on screen., (no dialogue), Keyboard tap; quiet ambience.

3, 1.5s, MS, Static, Cut back to Grace as she gets back to work with a resolute expression, jaw set., (Eyes focused; jaw set; resolute), Quiet ambience; piano holds.

4, 1.5s, Insert, Static + Dissolves, Cut to the wall clock as the time changes through a sequence of soft dissolves — 9:47 PM → 10:13 PM → 6:30 AM morning., (no dialogue), Faint clock tick; piano builds gently.

5, 3s, ECU, Static, Extreme close-up of Grace's hand on the mouse — fingers relaxed, precise., (Hand confident; one slow exhale), Mouse click; piano softens.

6, 1.5s, CU, Static, Close-up of Grace's face / eye — a focused, peaceful expression — morning light catches her face now., GRACE（旁白）：一个钟。 (Singapore Chinese accent) (Focused; small smile; one slow exhale), Piano softens.

50, 3s, MS, Push In, From behind Grace as she is working. Daniel walks in from behind holding a plate of toast and walks toward her — morning light fills the studio., DANIEL：Henley 签了? (Singapore Chinese accent) (Eyebrows lift in question), Morning birds; distant traffic; piano music continues softly.

51, 2s, MS, Static, Medium shot of Grace at the desk. She looks up at Daniel, a small smile forming., GRACE：昨天。 (Singapore Chinese accent) (Small smile; eyes bright), Piano music.

52, 2s, MS, Static, Medium shot of Daniel. He sets the toast plate down on the desk near Grace's sketchbook., DANIEL：Garrison? (Singapore Chinese accent) (Small smile forming), Plate on desk; piano music."""

REFS = [
    {"type": "video", "url": "asset://asset-20260516205835-f8gnl", "label": "GRACE_5s"},
    {"type": "video", "url": "asset://asset-20260516223044-dggtl", "label": "DANIEL_5s"},
    {"type": "video", "url": "asset://asset-20260516221607-p9xs4", "label": "HOME STUDIO 2"},
    {"type": "image", "url": "asset://asset-20260516231857-dwsqg", "label": "LAPTOP SCREEN v2"},
]


def submit():
    content = [{"type": "text", "text": PROMPT}]
    for r in REFS:
        if r["type"] == "video":
            content.append({"type": "video_url", "video_url": {"url": r["url"]}, "role": "reference_video"})
        else:
            content.append({"type": "image_url", "image_url": {"url": r["url"]}, "role": "reference_image"})
    body = {
        "model": "dreamina-seedance-2-0-260128",
        "content": content,
        "ratio": "9:16",
        "duration": 15,
        "resolution": "480p",
        "watermark": False,
    }
    print(f"Submitting transformation+Saturday v2 (montage + Daniel arrival):")
    print(f"  prompt: {len(PROMPT)} chars  ·  refs: {len(REFS)}")
    for r in REFS:
        print(f"    {r['label']:<20} → {r['url']} ({r['type']})")
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
    local_path = local / "set-10-11-transformation-saturday-v2-480p-15s.mp4"
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
    sub = gc(videos, "set-10-11-transformation-saturday")
    fname = "transformation-saturday-v2-9shot-480p-15s.mp4"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(body={"name": fname, "parents": [sub]}, media_body=media, fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    print(f"\n=== DONE ===")
    print(f"Drive: {f['webViewLink']}")
    print(f"Local: {local_path}")
    print(f"Wall: {time.time()-t0:.1f}s")
    Path("/tmp/transformation_saturday_v2_result.json").write_text(json.dumps({
        "task_id": task_id, "drive": f["webViewLink"], "local": str(local_path),
    }, indent=2))


if __name__ == "__main__":
    main()

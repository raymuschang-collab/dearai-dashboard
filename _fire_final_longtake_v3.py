#!/usr/bin/env python3
"""Fire the 15s long take closer v2 — with NEW cropped laptop screen asset (Evening, Grace).
Refs: @grace + GRACE HOME STUDIO 2 (video) + Grace's Home Studio (image) + LAPTOP SCREEN v2 (image).
"""
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
No music. Dialogue in natural local accent (English by default).
Contemporary Singapore — modern-day Tiong Bahru, present day. NOT period / NOT 1950s. Real-life, real-photo realism. Documentary editorial palette: oatmeal, cream, olive, charcoal, navy, oxblood. Kodak Portra 400 color science. Natural light only.

Location references: see attached home studio video reference and home studio still image — same desk, twin-monitor setup, monstera plants, bamboo blinds, terrazzo flooring.

Laptop screen reference: see attached Claude.ai chat window image — "Evening, Grace" greeting at the top, clean minimalist interface.

Character: Grace Tan, Singaporean Chinese woman in her late 20s.

59, 15s, WS, Long Take, ONE LONG TAKE (~15 seconds). OPENS on a composite of five Graces in the same golden-hour studio. Camera then DRIFTS toward Grace 1 sketching at iPad on her desk, then PANS to Grace 2 on a sales call at the window (gesturing, smiling), then DRIFTS to Grace 3 at the kitchen counter writing her newsletter, then to Grace 4 reviewing a spreadsheet with coffee in hand, then to Grace 5 on the floor with the dog. Camera then slowly pushes toward Grace 1 at the desk. The other four Graces fade out gently one by one as the push continues. Camera ORBITS to show her MacBook screen — the Claude.ai chat interface clear on screen with greeting "Morning, Grace" at the top. Then the camera pulls back wide to the empty golden-hour studio. Title card fades in over the room — "给一个人在打拼的你 · For the ones building alone." Fade to black. AT THE SAME TIME AT START OF LONG TAKE, GRACE（旁白）：以前啊 —— 在新加坡想自己干 —— 要养七个人。现在啊 —— 一台手提电脑就够了。这里的未来 —— 感觉轻了一点。不是对那些大公司 —— 他们本来就没事。是对我们这些 —— 以前一个人要当七个人用的小家伙。我们终于可以 —— 做回一个人。 (Singapore Chinese accent) (Grace 1: small private smile; hands relaxed on keyboard), Soft piano builds through the take, then pulls to silence on the last line."""

REFS = [
    {"type": "video", "url": "asset://asset-20260514120424-thhzh", "label": "GRACE"},
    {"type": "video", "url": "asset://asset-20260516221607-p9xs4", "label": "HOME STUDIO 2"},
    {"type": "image", "url": "asset://asset-20260514140550-pv9gq", "label": "HOME STUDIO (still)"},
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
    print(f"Submitting final long take v3 (new cropped laptop screen):")
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
    local_path = local / "set-12-final-longtake-v3-drift-orbit-480p-15s.mp4"
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
    sub = gc(videos, "set-12-final-longtake")
    fname = "final-longtake-v3-drift-orbit-480p-15s.mp4"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(body={"name": fname, "parents": [sub]}, media_body=media, fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    print(f"\n=== DONE ===")
    print(f"Drive: {f['webViewLink']}")
    print(f"Local: {local_path}")
    print(f"Wall: {time.time()-t0:.1f}s")
    Path("/tmp/final_longtake_v3_result.json").write_text(json.dumps({
        "task_id": task_id, "drive": f["webViewLink"], "local": str(local_path),
    }, indent=2))


if __name__ == "__main__":
    main()

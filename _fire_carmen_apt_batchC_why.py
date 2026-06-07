#!/usr/bin/env python3
"""Fire Carmen apt batch B — revelation (2 shots, 12s exact).
Carmen white→black, Grace blue→white. Blocking ref image + apt image + Carmen + Grace."""
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

Location: Carmen's Apartment dining area (see attached apartment reference image).

Blocking and character reference: see attached blocking image — Carmen and Grace seated side-by-side at the dining table, MacBook open between them, framed photo on the cream wall.

Wardrobe: Grace (on the LEFT) wears a white blouse. Carmen (on the RIGHT) wears a black sleeveless tank.

4, 4s, MS, Static, Medium shot of Carmen and Grace side-by-side. Carmen taps lightly on her MacBook — confirming, screen still visible to Grace beside her., CARMEN：现在我们喝茶。一个 agent 还在跑 —— 整理礼拜四的客户简报。 (Singapore Chinese accent) (Small confident smile; finger taps the screen briefly; Grace leans in to look), Apartment ambient.

5, 8s, MS, Static, Medium shot of Carmen and Grace side-by-side. Carmen sits back from the laptop, hands resting on the table — she names the why-it-works, holds a beat, then lands the framing line quietly., CARMEN：我做策略的 —— 我懂系统结构。我把工作拆开,每一个 agent 负责一段。架构 —— 是我经验决定的。 ... 全部。我用它思考。 (Singapore Chinese accent) (Sits back; turns to face Grace; slow nod; eyes soften on the second line; Grace turns from screen to Carmen), Apartment ambient; piano soft."""

REFS = [
    {"type": "video", "url": "asset://asset-20260516170559-dvf29", "label": "CARMEN"},
    {"type": "video", "url": "asset://asset-20260514120424-thhzh", "label": "GRACE"},
    {"type": "image", "url": "asset://asset-20260514140556-smw7q", "label": "CARMEN APT (still)"},
    {"type": "image", "url": "asset://asset-20260517000922-8xvsm", "label": "BLOCKING REF"},
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
        "duration": 12,
        "resolution": "480p",
        "watermark": False,
    }
    print(f"Submitting Carmen apt batch C why-it-works (2 shots, 12s exact):")
    print(f"  prompt: {len(PROMPT)} chars  ·  refs: {len(REFS)}")
    for r in REFS:
        print(f"    {r['label']:<22} → {r['url']} ({r['type']})")
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
    local_path = local / "set-06-carmen-apt-batchC-why-12s-480p.mp4"
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
    sub = gc(videos, "set-06-carmen-apartment-reveal")
    fname = "carmen-apt-batchC-why-12s-480p.mp4"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(body={"name": fname, "parents": [sub]}, media_body=media, fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    print(f"\n=== DONE ===")
    print(f"Drive: {f['webViewLink']}")
    print(f"Local: {local_path}")
    print(f"Wall: {time.time()-t0:.1f}s")
    Path("/tmp/carmen_apt_batchC_result.json").write_text(json.dumps({
        "task_id": task_id, "drive": f["webViewLink"], "local": str(local_path),
    }, indent=2))


if __name__ == "__main__":
    main()

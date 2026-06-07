#!/usr/bin/env python3
"""Fire set 1 — 6 shots, NO storyboard ref, accent locked to Singapore Chinese.
Refs: old Grace + Carmen v2 + Tiong Bahru Café only."""
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
No music. ALL dialogue in natural Singapore Chinese accent.
Contemporary Singapore — modern-day Tiong Bahru, present day. NOT period / NOT 1950s. Real-life, real-photo realism. Documentary editorial palette: oatmeal, cream, olive, charcoal, navy, oxblood. Kodak Portra 400 color science. Natural light only.

Location: Tiong Bahru Café (see attached café reference image for background environment).

1, 4s, OTS, Static, OTS over Grace's shoulder onto Carmen across the small wooden café table. Two flat whites between them. Behind Carmen, a waiter in a soft-focus apron walks past the table toward the espresso counter, plates in hand. Soft golden window light from the left., CARMEN：你看起来糟透了。 (Singapore Chinese accent) (Eyes narrow; mouth flat), Café ambient: cups on saucers, espresso machine hiss, low chatter.

2, 5s, MS, Static, Medium shot of Grace seated at the café table. She looks tired — dark circles, hair out of a loose ponytail. She doesn't push back on Carmen's line; she just lays out the truth. (Editor: cut to WS of both midway through Grace's dialogue — pull the WS from shot 5's coverage or generate separately.), GRACE：我是设计师。是销售。自己当会计。自己做营销。自己处理行政。还经常忘了洗衣服。 (Singapore Chinese accent) (Eyes drop; jaw tight; small exhale), Café ambient continues; cup placed on saucer mid-line.

3, 3s, CU, Static, Close-up of Carmen. One eyebrow lifts slightly, no judgment in the expression — just the practical suggestion., CARMEN：请个人吧。 (Singapore Chinese accent) (Eyebrow lifts; mouth neutral), Café ambient.

4, 3s, CU, Static, Close-up of Grace. The corner of her mouth twitches downward. Not bitter — just done., GRACE：哪来的钱。 (Singapore Chinese accent) (Corner of mouth twitches down), Café ambient.

5, 4s, WS, Static, Wide of both at the café table. Carmen on the left, Grace on the right. Two flat whites between them. Background: the café in soft focus, pendant lights, terrazzo floor, the bookshelf at the back wall. Carmen speaks; Grace doesn't react yet., CARMEN：你七个人都累了。 (Singapore Chinese accent) (Carmen: eyes soften at the corners), Café ambient.

6, 3s, CU, Static, Close-up of Grace. A small bitter smile that doesn't reach her eyes — recognition of the truth Carmen just named., GRACE：我七个人都累了。 (Singapore Chinese accent) (Smile doesn't reach eyes; eyelids drop slightly), Café ambient."""

REFS = [
    # Old Grace, restored — face video
    {"type": "video", "url": "asset://asset-20260514120424-thhzh", "label": "GRACE"},
    # Carmen v2 — face video
    {"type": "video", "url": "asset://asset-20260516170559-dvf29", "label": "CARMEN"},
    # Tiong Bahru Café — location image
    {"type": "image", "url": "asset://asset-20260514140552-f6q88", "label": "CAFE"},
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
    print(f"Submitting set 1 — NO storyboard ref, Singapore Chinese accent:")
    print(f"  prompt: {len(PROMPT)} chars  ·  refs: {len(REFS)}")
    for r in REFS:
        print(f"    {r['label']:<6} → {r['url']} ({r['type']})")
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
    local_path = local / "set-01-noSB-sgchinese-480p-15s.mp4"
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
    sub = gc(videos, "set-01-noSB-sgchinese")
    fname = "set-01-noSB-sgchinese-480p-15s.mp4"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(body={"name": fname, "parents": [sub]}, media_body=media, fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    print(f"\n=== DONE ===")
    print(f"Drive: {f['webViewLink']}")
    print(f"Local: {local_path}")
    print(f"Wall: {time.time()-t0:.1f}s")
    Path("/tmp/set1_noSB_sgchinese_result.json").write_text(json.dumps({
        "task_id": task_id, "drive": f["webViewLink"], "local": str(local_path),
    }, indent=2))


if __name__ == "__main__":
    main()

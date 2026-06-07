#!/usr/bin/env python3
"""Fire Carmen apartment reveal scene — 6 shots (24s → 15s output).
Refs: Carmen v2 (7s) + Grace (5s) + Carmen apartment image."""
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

Wardrobe: Carmen wears a black sleeveless tank. Grace wears a blue sleeveless tank.

1, 4s, WS, Static, Wide INT of Carmen's apartment dining area — two MacBooks on the wooden dining table (closed for now), two mugs of tea, brass pendant lamp overhead, framed photograph on the cream wall, low bookshelf behind. Grace seated across from Carmen, both leaning into the conversation. Warm Sunday afternoon light through bamboo blinds., (Grace's posture: forward, attentive; Carmen: settled, calm), Apartment ambient; teacups; soft piano under.

2, 3s, MS, Static, Medium shot of Carmen across the table. She wraps both hands around her tea mug., CARMEN：我用 Claude。三种用法。 (Singapore Chinese accent) (Eyes direct; mouth neutral), Apartment ambient.

3, 3s, CU, Static, Close-up of Grace. One eyebrow lifts, lips pressed., GRACE：那个 AI。 (Singapore Chinese accent) (Eyebrow lifts; lips press), Apartment ambient.

4, 7s, MS, Static, Medium shot of Carmen. She wraps her hands around the tea mug, then names the three concrete cases in one breath — no screens shown, just her telling Grace what she did., CARMEN：Sea Group 那个案子 —— 初稿十二分钟。Hoyo 新品牌 —— 二十分钟,五个切入点,他们选了其中一个。还有 newsletter,cold pitch 邮件,LinkedIn,一个礼拜二十分钟,全部搞定。 (Singapore Chinese accent) (Eyes steady; small nod with each case; quiet confidence), Apartment ambient.

5, 3s, CU, Static, Close-up of Grace. Quiet, beginning to process the scale., GRACE：全部。 (Singapore Chinese accent) (Eyebrows draw together; mouth slightly open), Apartment ambient.

6, 4s, MS, Static, Medium shot of Carmen. She leans in slightly, voice lower — this is the actual revelation., CARMEN：这才是关键 —— 不是一个助理。是好几个 —— 同时在跑。 (Singapore Chinese accent) (Eyes widen slightly; leans in), Apartment ambient."""

REFS = [
    {"type": "video", "url": "asset://asset-20260516170559-dvf29", "label": "CARMEN"},
    {"type": "video", "url": "asset://asset-20260514120424-thhzh", "label": "GRACE"},
    {"type": "image", "url": "asset://asset-20260514140556-smw7q", "label": "CARMEN APT"},
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
    print(f"Submitting Carmen apartment reveal (6 shots, 24s → 15s output):")
    print(f"  prompt: {len(PROMPT)} chars  ·  refs: {len(REFS)}")
    for r in REFS:
        print(f"    {r['label']:<10} → {r['url']} ({r['type']})")
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
    local_path = local / "set-06-carmen-apartment-reveal-480p-15s.mp4"
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
    fname = "carmen-apartment-reveal-6shot-480p-15s.mp4"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(body={"name": fname, "parents": [sub]}, media_body=media, fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    print(f"\n=== DONE ===")
    print(f"Drive: {f['webViewLink']}")
    print(f"Local: {local_path}")
    print(f"Wall: {time.time()-t0:.1f}s")
    Path("/tmp/carmen_apartment_reveal_result.json").write_text(json.dumps({
        "task_id": task_id, "drive": f["webViewLink"], "local": str(local_path),
    }, indent=2))


if __name__ == "__main__":
    main()

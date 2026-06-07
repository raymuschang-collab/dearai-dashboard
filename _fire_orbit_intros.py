#!/usr/bin/env python3
"""Fire 5 Seedance orbit-intro gens in parallel — Grace / Daniel / Carmen / Mom / Dad.
All five characters use raymus's face video as identity-feature reference
(+ each character's own appearance ref where available).
Outputs: 5s 9:16 480p clips."""
from __future__ import annotations

import io
import json
import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials  # noqa: E402

# Load .env
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

ARK_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_API_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]
USER_FACE_ASSET = json.load(open("/tmp/user_face_asset.json"))["asset_id"]
SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"

# Character existing BytePlus video asset codes (from Asset Library)
CHAR_REFS = {
    "GRACE":  "asset-20260514120424-thhzh",
    "DANIEL": "asset-20260514120441-b2tc2",
    "CARMEN": "asset-20260514120449-5tpq8",
    # MOM + DAD: no existing refs — text-only prompt
}

PROMPTS = {
    "GRACE": (
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot, camera circling around a young attractive "
        "Singaporean Chinese woman in her late 20s. She has shoulder-length jet-black "
        "hair worn loose and flowing, fair clear skin with natural texture, expressive "
        "dark almond-shaped eyes, refined oval face, soft natural makeup, gentle warm "
        "smile. She wears a cream cotton tee, olive carpenter trousers, a delicate gold "
        "chain at her neck. She stands in a softly lit modern Tiong Bahru flat interior "
        "— cream walls, monstera plants, golden hour window light. As the camera orbits, "
        "she turns her head to follow the camera and looks toward the lens with a small "
        "soft smile, then introduces herself in Singaporean Mandarin (light Singlish "
        "lilt). Documentary editorial photography aesthetic, Kodak Portra 400 color "
        "science, real photo realism, NOT a game-engine render. "
        "Dialogue: 你好,我是 Grace。我是设计师。"
    ),
    "DANIEL": (
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot, camera circling a Singaporean Chinese man, "
        "28, lean wiry build. Thin steel-rim round glasses, fair clear skin with subtle "
        "stubble shadow, jet-black hair grown slightly past his ears parted to one side. "
        "He wears a faded navy oversized cotton shirt with sleeves rolled to the elbows. "
        "Calm, patient face — the one who waits. He stands in a softly lit modern Tiong "
        "Bahru flat interior — cream walls, evening lamp glow, kitchen counter visible. "
        "As the camera orbits, he turns his head and looks toward the lens, calm and "
        "unhurried, then introduces himself in Singaporean Mandarin. Documentary "
        "editorial photography aesthetic, real photo realism, NOT a game-engine render. "
        "Dialogue: 你好,我是 Daniel。"
    ),
    "CARMEN": (
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot, camera circling a Singaporean Chinese woman "
        "in her early 30s — sharp and elegant. Oval face with high cheekbones, "
        "intelligent dark almond eyes, jet-black hair in a clean shoulder-length blunt "
        "bob with a center part. Fitted black turtleneck under an unstructured oatmeal "
        "wool blazer, slim charcoal trousers. The composed look of someone who has been "
        "where you are. She stands in a calm Tiong Bahru café — pendant lights, wooden "
        "bookshelf, terrazzo floor, soft golden window light. As the camera orbits, she "
        "turns her head, looks toward the lens — unsmiling but warm — then introduces "
        "herself in Singaporean Mandarin. Documentary editorial photography aesthetic, "
        "real photo realism, NOT a game-engine render. "
        "Dialogue: 你好,我是 Carmen。"
    ),
    "MOM": (
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot, camera circling a Singaporean Chinese OLDER "
        "WOMAN, around 55 years old. Sturdy average build, fair skin with natural age "
        "lines around the eyes and mouth, oval face with high cheekbones. Short permed "
        "black hair with visible salt-and-pepper at the temples. Reading glasses on a "
        "thin chain around her neck. She wears a floral or solid button-up blouse in a "
        "muted color, dark trousers, a simple gold chain. She stands in a warm Singapore "
        "HDB living area — framed family photos on the cream wall, soft warm pendant "
        "light overhead, older-style furniture. As the camera orbits, she turns her head "
        "and looks toward the lens with the steady attentiveness of a mother, then "
        "introduces herself in Singaporean Mandarin. Documentary editorial photography "
        "aesthetic, real photo realism, NOT a game-engine render. AGE: 55. "
        "Dialogue: 你好,我是 Grace 的妈妈。"
    ),
    "DAD": (
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot, camera circling a Singaporean Chinese OLDER "
        "MAN, around 58 years old. Slim build, fair skin with natural age lines. Short "
        "black hair with visible gray at the temples and a slightly receding hairline. "
        "Thin-rim glasses. He wears a simple polo or button-up shirt in a muted color, "
        "dark trousers; he holds a small mug of tea in one hand. He stands in a warm "
        "Singapore HDB living area — older-style décor, framed family photos on the "
        "wall, calendar with Chinese characters. As the camera orbits, he turns his "
        "head and looks toward the lens — calm, grounded, quietly authoritative — then "
        "introduces himself in Singaporean Mandarin. Documentary editorial photography "
        "aesthetic, real photo realism, NOT a game-engine render. AGE: 58. "
        "Dialogue: 你好,我是 Grace 的爸爸。"
    ),
}


def submit_task(prompt: str, user_face_asset: str, char_asset: str | None) -> str:
    """Returns task_id."""
    content = [{"type": "text", "text": prompt}]
    # User face video — identity features
    content.append({
        "type": "video_url",
        "video_url": {"url": f"asset://{user_face_asset}"},
        "role": "reference_video",
    })
    # Character existing ref (video) — appearance hints
    if char_asset:
        content.append({
            "type": "video_url",
            "video_url": {"url": f"asset://{char_asset}"},
            "role": "reference_video",
        })

    body = {
        "model": "dreamina-seedance-2-0-260128",  # Seedance 2.0 Pro
        "content": content,
        "ratio": "9:16",
        "duration": 5,
        "resolution": "480p",
        "watermark": False,
    }
    r = requests.post(
        f"{ARK_BASE}/contents/generations/tasks",
        headers={"Authorization": f"Bearer {ARK_API_KEY}", "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"submit failed: {r.status_code} {r.text[:500]}")
    resp = r.json()
    task_id = resp.get("id") or resp.get("task_id") or resp.get("data", {}).get("id")
    if not task_id:
        raise RuntimeError(f"no task_id in response: {resp}")
    return task_id


def poll_task(task_id: str, char_name: str, max_wait: int = 600) -> dict:
    start = time.time()
    last_status = None
    while time.time() - start < max_wait:
        try:
            r = requests.get(
                f"{ARK_BASE}/contents/generations/tasks/{task_id}",
                headers={"Authorization": f"Bearer {ARK_API_KEY}"},
                timeout=30,
            )
            if r.status_code != 200:
                time.sleep(15)
                continue
            resp = r.json()
            status = resp.get("status") or resp.get("data", {}).get("status")
            if status != last_status:
                print(f"  [{char_name}: {int(time.time()-start)}s] {status}", flush=True)
                last_status = status
            if status in ("succeeded", "completed", "success"):
                return resp
            if status in ("failed", "expired", "cancelled"):
                raise RuntimeError(f"{char_name} task failed: {resp}")
        except RuntimeError:
            raise
        except Exception as e:
            print(f"  poll exception ({char_name}, non-fatal): {e}", flush=True)
        time.sleep(15)
    raise RuntimeError(f"{char_name} max wait exceeded")


def extract_video_url(resp: dict) -> str | None:
    content = resp.get("content", {})
    if isinstance(content, dict):
        url = content.get("video_url")
        if isinstance(url, str):
            return url
        if isinstance(url, dict):
            return url.get("url")
    return None


def fire_one(char: str) -> dict:
    prompt = PROMPTS[char]
    char_asset = CHAR_REFS.get(char)
    t0 = time.time()
    print(f"  ▶ {char}: submitting (char_ref={char_asset or 'TEXT-ONLY'})", flush=True)
    try:
        task_id = submit_task(prompt, USER_FACE_ASSET, char_asset)
        print(f"  ▶ {char}: task_id={task_id}", flush=True)
        result = poll_task(task_id, char)
        video_url = extract_video_url(result)
        print(f"  ✓ {char}: done in {time.time()-t0:.1f}s → {video_url[:80] if video_url else 'no url'}", flush=True)
        return {"char": char, "task_id": task_id, "video_url": video_url, "elapsed": round(time.time()-t0, 1)}
    except Exception as e:
        print(f"  ✗ {char}: FAILED — {type(e).__name__}: {e}", flush=True)
        return {"char": char, "error": f"{type(e).__name__}: {e}"}


def upload_to_drive(char: str, video_url: str) -> dict:
    """Download Seedance MP4, upload to Drive face-refs/orbit-intros/, share."""
    if not video_url:
        return {"char": char, "error": "no video url"}
    creds = get_credentials()
    drive = build('drive', 'v3', credentials=creds)
    # face-refs folder
    res = drive.files().list(
        q=f"'{SHOW_FOLDER}' in parents and trashed=false and name='face-refs'",
        fields="files(id)", pageSize=1,
    ).execute()
    face_folder = res["files"][0]["id"]
    # orbit-intros subfolder
    res = drive.files().list(
        q=f"'{face_folder}' in parents and trashed=false and name='orbit-intros'",
        fields="files(id)", pageSize=1,
    ).execute()
    if res.get("files"):
        sub = res["files"][0]["id"]
    else:
        sub = drive.files().create(
            body={"name": "orbit-intros", "mimeType": "application/vnd.google-apps.folder", "parents": [face_folder]},
            fields="id",
        ).execute()["id"]

    # Download
    r = requests.get(video_url, timeout=300)
    r.raise_for_status()
    media = MediaIoBaseUpload(io.BytesIO(r.content), mimetype="video/mp4", resumable=False)
    f = drive.files().create(
        body={"name": f"{char.lower()}_orbit_intro_5s_480p.mp4", "parents": [sub]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(
        fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id",
    ).execute()
    return {"char": char, "drive_id": f["id"], "drive_view": f["webViewLink"]}


def main():
    chars = list(PROMPTS.keys())
    print(f"=== Firing {len(chars)} Seedance Pro orbit intros in parallel ===\n")
    print(f"User face asset: {USER_FACE_ASSET}\n")

    results = {}
    with ThreadPoolExecutor(max_workers=len(chars)) as ex:
        futures = {ex.submit(fire_one, c): c for c in chars}
        for fut in as_completed(futures):
            r = fut.result()
            results[r["char"]] = r

    print("\n=== Submitted/polled — uploading to Drive ===\n")
    # Upload sequentially (Drive can choke on parallel)
    drive_results = {}
    for char, r in results.items():
        if r.get("error") or not r.get("video_url"):
            print(f"  ✗ {char} skipped (no video)")
            continue
        try:
            dr = upload_to_drive(char, r["video_url"])
            drive_results[char] = dr
            print(f"  ✓ {char}: {dr['drive_view']}")
        except Exception as e:
            print(f"  ✗ {char} drive upload failed: {e}")

    # Merge results
    final = {}
    for c in chars:
        final[c] = {**results.get(c, {}), **drive_results.get(c, {})}
    Path("/tmp/orbit_intros.json").write_text(json.dumps(final, indent=2))
    print("\n=== SUMMARY ===")
    for c, r in final.items():
        if r.get("error"):
            print(f"  ✗ {c}: {r['error']}")
        else:
            print(f"  ✓ {c}: {r.get('drive_view', '—')}  (elapsed {r.get('elapsed', '—')}s)")
    print(f"\nManifest: /tmp/orbit_intros.json")


if __name__ == "__main__":
    main()

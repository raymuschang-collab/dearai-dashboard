#!/usr/bin/env python3
"""ORBIT INTROS v2 — face-only ref + explicit feature-borrow @ ~40%.

Key change vs v1: drop the original Grace/Daniel/Carmen 5s clips entirely.
Each call gets ONLY raymus's face video as the identity reference. Prompt
explicitly instructs Seedance to use ~40% of the facial features
(bone structure / eye shape / nose / jaw / skin tone) and transform the
rest via styling — hair, age, gender expression, wardrobe.

Mom + Dad also use raymus's face but age it up to 55 / 58.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

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
ARK_API_KEY = os.environ["BYTEPLUS_ARK_API_KEY"]
USER_FACE_ASSET = json.load(open("/tmp/user_face_asset.json"))["asset_id"]
SHOW_FOLDER = "1ANRzQmVowH2qbd_-qXXg65nT0VGtTGuq"

# Shared identity-borrow preamble injected into every prompt.
IDENTITY_INSTRUCTION = (
    "IDENTITY REFERENCE — use the facial features from the supplied reference video "
    "at ~40% similarity. Pull from the reference: bone structure, cheekbones, "
    "nose shape, eye shape, jawline, skin tone, complexion. "
    "Do NOT carry over from the reference: clothing, hair style, age expression, "
    "gender expression, accessories, background. "
    "Apply the new styling described below over the borrowed facial features. "
    "The resulting character should be recognizable as a transformed version of "
    "the reference person — sharing some facial structure but clearly styled as "
    "the new character described."
)

PROMPTS = {
    "GRACE": (
        f"{IDENTITY_INSTRUCTION}\n\n"
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot. The character is a YOUNG ATTRACTIVE "
        "SINGAPOREAN CHINESE WOMAN in her late 20s. "
        "Apply over the borrowed facial features: "
        "shoulder-length jet-black hair worn loose and flowing with natural body, "
        "soft natural makeup (light mascara, nude balm lip), gentle warm "
        "expression, slim feminine neck and jawline. "
        "Wardrobe: cream cotton tee, olive carpenter trousers, a delicate gold "
        "chain at the neck. "
        "Location: softly lit modern Tiong Bahru flat interior — cream walls, "
        "monstera plants, golden hour window light. "
        "Action: as the camera orbits, she turns her head to follow the lens, "
        "gives a small soft smile, then introduces herself in Singaporean "
        "Mandarin (light Singlish lilt). "
        "Dialogue: 你好,我是 Grace。我是设计师。 "
        "Aesthetic: documentary editorial photography, Kodak Portra 400 color "
        "science, real photo realism, NOT a game-engine render, NOT CGI."
    ),
    "DANIEL": (
        f"{IDENTITY_INSTRUCTION}\n\n"
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot. The character is a SINGAPOREAN CHINESE "
        "MAN in his late 20s, lean wiry build. "
        "Apply over the borrowed facial features: "
        "thin steel-rim round glasses, jet-black hair grown slightly past the "
        "ears parted to one side, subtle stubble shadow, calm patient expression. "
        "Wardrobe: faded navy oversized cotton shirt with sleeves rolled to the "
        "elbows over a plain white tee. "
        "Location: softly lit modern Tiong Bahru flat interior — cream walls, "
        "evening lamp glow, kitchen counter visible. "
        "Action: as the camera orbits, he turns his head and looks toward the "
        "lens, calm and unhurried, then introduces himself in Singaporean "
        "Mandarin. "
        "Dialogue: 你好,我是 Daniel。 "
        "Aesthetic: documentary editorial photography, real photo realism, "
        "NOT a game-engine render."
    ),
    "CARMEN": (
        f"{IDENTITY_INSTRUCTION}\n\n"
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot. The character is a SINGAPOREAN CHINESE "
        "WOMAN in her early 30s — sharp and elegant. "
        "Apply over the borrowed facial features: "
        "jet-black hair in a clean shoulder-length BLUNT BOB with a center part, "
        "minimal makeup (warm-tan lip, light mascara), high cheekbones emphasis, "
        "composed expression — unsmiling but warm, slim feminine neck. "
        "Wardrobe: fitted black turtleneck under an unstructured oatmeal wool "
        "blazer, slim charcoal trousers. "
        "Location: calm Tiong Bahru café interior — pendant lights, wooden "
        "bookshelf, terrazzo floor, soft golden window light. "
        "Action: as the camera orbits, she turns her head, looks toward the "
        "lens — unsmiling but warm — then introduces herself in Singaporean "
        "Mandarin. "
        "Dialogue: 你好,我是 Carmen。 "
        "Aesthetic: documentary editorial photography, real photo realism, "
        "NOT a game-engine render."
    ),
    "MOM": (
        f"{IDENTITY_INSTRUCTION}\n\n"
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot. The character is a SINGAPOREAN CHINESE "
        "OLDER WOMAN, approximately 55 years old. "
        "Apply over the borrowed facial features (use the user's facial structure "
        "as a starting point, then AGE the face significantly): "
        "natural age lines around the eyes and mouth (crow's feet, smile lines), "
        "softer/heavier jawline of a 55-year-old, slightly fuller cheeks, "
        "wisdom-tinged expression, slim feminine neck. "
        "Hair: short permed black hair with visible salt-and-pepper streaks at "
        "the temples, set in a typical aunty-style perm. "
        "Wardrobe: floral or solid button-up blouse in a muted color, dark "
        "trousers, a simple gold chain, reading glasses on a thin chain around "
        "the neck. "
        "Location: warm Singapore HDB living area — framed family photos on the "
        "cream wall, soft warm pendant light overhead, older-style furniture. "
        "Action: as the camera orbits, she turns her head and looks toward the "
        "lens with the steady attentiveness of a mother, then introduces "
        "herself in Singaporean Mandarin. "
        "Dialogue: 你好,我是 Grace 的妈妈。 "
        "AGE: 55. Aesthetic: documentary editorial photography, real photo "
        "realism, NOT a game-engine render."
    ),
    "DAD": (
        f"{IDENTITY_INSTRUCTION}\n\n"
        "Shot with Arri Alexa, 35mm film, shallow depth of field. "
        "5-second slow orbit camera shot. The character is a SINGAPOREAN CHINESE "
        "OLDER MAN, approximately 58 years old. "
        "Apply over the borrowed facial features (use the user's facial structure "
        "as a starting point, then AGE the face significantly): "
        "natural age lines around the eyes and mouth, softer jawline of a "
        "58-year-old, wisdom-tinged expression, thin-rim glasses. "
        "Hair: short black hair with visible gray at the temples and a slightly "
        "receding hairline. "
        "Wardrobe: simple polo or button-up shirt in a muted color, dark "
        "trousers; holds a small mug of tea in one hand. "
        "Location: warm Singapore HDB living area — older-style décor, framed "
        "family photos on the wall, calendar with Chinese characters. "
        "Action: as the camera orbits, he turns his head and looks toward the "
        "lens — calm, grounded, quietly authoritative — then introduces himself "
        "in Singaporean Mandarin. "
        "Dialogue: 你好,我是 Grace 的爸爸。 "
        "AGE: 58. Aesthetic: documentary editorial photography, real photo "
        "realism, NOT a game-engine render."
    ),
}


def submit_task(prompt: str) -> str:
    """Single video ref — raymus's face only."""
    content = [
        {"type": "text", "text": prompt},
        {
            "type": "video_url",
            "video_url": {"url": f"asset://{USER_FACE_ASSET}"},
            "role": "reference_video",
        },
    ]
    body = {
        "model": "dreamina-seedance-2-0-260128",
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
        raise RuntimeError(f"no task_id: {resp}")
    return task_id


def poll_task(task_id: str, char: str, max_wait: int = 600) -> dict:
    start = time.time()
    last = None
    while time.time() - start < max_wait:
        try:
            r = requests.get(
                f"{ARK_BASE}/contents/generations/tasks/{task_id}",
                headers={"Authorization": f"Bearer {ARK_API_KEY}"},
                timeout=30,
            )
            if r.status_code != 200:
                time.sleep(15); continue
            resp = r.json()
            status = resp.get("status") or resp.get("data", {}).get("status")
            if status != last:
                print(f"  [{char}: {int(time.time()-start)}s] {status}", flush=True)
                last = status
            if status in ("succeeded", "completed", "success"):
                return resp
            if status in ("failed", "expired", "cancelled"):
                raise RuntimeError(f"{char} failed: {resp}")
        except RuntimeError:
            raise
        except Exception as e:
            print(f"  poll ({char}, non-fatal): {e}", flush=True)
        time.sleep(15)
    raise RuntimeError(f"{char} max wait exceeded")


def fire_one(char: str) -> dict:
    t0 = time.time()
    print(f"  ▶ {char}: submitting (face-only ref @ ~40%)", flush=True)
    try:
        task_id = submit_task(PROMPTS[char])
        print(f"  ▶ {char}: task_id={task_id}", flush=True)
        result = poll_task(task_id, char)
        content = result.get("content", {})
        url = content.get("video_url") if isinstance(content, dict) else None
        if isinstance(url, dict): url = url.get("url")
        print(f"  ✓ {char}: {time.time()-t0:.1f}s → {url[:60] if url else 'no url'}", flush=True)
        return {"char": char, "task_id": task_id, "video_url": url, "elapsed": round(time.time()-t0, 1)}
    except Exception as e:
        print(f"  ✗ {char}: {type(e).__name__}: {e}", flush=True)
        return {"char": char, "error": f"{type(e).__name__}: {e}"}


def upload_and_save_local(char: str, video_url: str) -> dict:
    creds = get_credentials()
    drive = build('drive', 'v3', credentials=creds)
    res = drive.files().list(
        q=f"'{SHOW_FOLDER}' in parents and trashed=false and name='face-refs'",
        fields="files(id)", pageSize=1,
    ).execute()
    face = res["files"][0]["id"]
    res = drive.files().list(
        q=f"'{face}' in parents and trashed=false and name='orbit-intros-v2'",
        fields="files(id)", pageSize=1,
    ).execute()
    sub = res["files"][0]["id"] if res.get("files") else drive.files().create(
        body={"name": "orbit-intros-v2", "mimeType": "application/vnd.google-apps.folder", "parents": [face]},
        fields="id",
    ).execute()["id"]

    # Download
    r = requests.get(video_url, timeout=300)
    r.raise_for_status()
    data = r.content
    # Local save
    local = Path("/Users/raymuschang/Downloads/Claude_Ad_Orbit_Intros_v2")
    local.mkdir(exist_ok=True)
    local_path = local / f"{char.lower()}_orbit_intro_v2_5s_480p.mp4"
    local_path.write_bytes(data)
    # Drive upload
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="video/mp4", resumable=False)
    f = drive.files().create(
        body={"name": f"{char.lower()}_orbit_intro_v2_5s_480p.mp4", "parents": [sub]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(
        fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id",
    ).execute()
    return {"char": char, "local": str(local_path), "drive_view": f["webViewLink"]}


def main():
    chars = list(PROMPTS.keys())
    print(f"=== Firing {len(chars)} Seedance Pro orbit intros (v2 — face-only @ ~40%) ===\n")
    print(f"User face asset: {USER_FACE_ASSET}\n")

    results = {}
    with ThreadPoolExecutor(max_workers=len(chars)) as ex:
        futures = {ex.submit(fire_one, c): c for c in chars}
        for fut in as_completed(futures):
            r = fut.result()
            results[r["char"]] = r

    print("\n=== Uploading + saving locally ===\n")
    for char, r in results.items():
        if r.get("error") or not r.get("video_url"):
            print(f"  ✗ {char} skipped")
            continue
        try:
            up = upload_and_save_local(char, r["video_url"])
            results[char].update(up)
            print(f"  ✓ {char}: local={up['local']}")
        except Exception as e:
            print(f"  ✗ {char} upload: {e}")

    Path("/tmp/orbit_intros_v2.json").write_text(json.dumps(results, indent=2))
    print(f"\nManifest: /tmp/orbit_intros_v2.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Kling OmniVideo V2V smoke test — 4 clips × 2 environment prompts = 8 gens.

Reskins the environment only, keeps faces / wardrobe / blocking / timing intact.
"""
import json, os, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from kling_api import omni_video, get_task

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SPLITS = Path("/Users/raymuschang/Documents/Video Editing/clients/Channel 8 Test Shoot/cuts/splits")

CLIPS = [
    ("shot 02", SPLITS / "shot 02/shot 02.mp4", 5),    # 6.6s → 5s
    ("shot 03", SPLITS / "shot 03/shot 03.mp4", 10),   # 9.0s → 10s
    ("shot 04", SPLITS / "shot 04/shot 04.mp4", 10),   # 11.2s → 10s
    ("shot 06", SPLITS / "shot 06/shot 06.mp4", 5),    # 3.6s → 5s
]

FOREST_PROMPT = """Transform <<<video_1>>>. Keep every character, performance, line of dialogue, costume, prop, blocking, framing, camera movement, and edit timing EXACTLY as they appear in the source video. The ONLY change is the environment: replace the original setting with a deep ancient temperate forest.

Environment detail:
- Towering moss-covered tree trunks bracketing the frame, dense ferns and undergrowth at ground level, gnarled roots, scattered mushrooms.
- Dappled golden-hour sunbeams piercing a high canopy, lighting up suspended motes of pollen and slow-drifting insects.
- Soft low-lying mist hugging the forest floor; layered atmospheric depth with backlit trees receding into haze.
- Distant rustling foliage and birdsong implied through the light and air, not new elements in frame.

Faces, costumes, hand props, hair, makeup, and skin tones are UNCHANGED from the source. Do not redress the actors. Do not change their performance.

Cinematography: Arri Alexa, anamorphic lens, shallow depth of field, naturalistic forest-green and warm-gold palette, deep shadow falloff. Documentary editorial photography aesthetic. Natural skin texture with visible pores and small natural imperfections, Kodak Portra 400 color science, subtle film grain. No game-engine rendering, no plastic/CGI sheen, no movie-poster polish. Natural light only — sunbeams through canopy as the only key."""

WAREHOUSE_PROMPT = """Transform <<<video_1>>>. Keep every character, performance, line of dialogue, costume, prop, blocking, framing, camera movement, and edit timing EXACTLY as they appear in the source video. The ONLY change is the environment: replace the original setting with a vast disused industrial warehouse.

Environment detail:
- Towering steel girders, rusted I-beams crossing overhead, exposed ductwork and conduit.
- Corrugated metal walls streaked with rust, grime, and old graffiti; exposed concrete floor marked with paint lines, oil stains, and tire tracks.
- Broken skylights letting in cold, hard shafts of daylight that catch suspended dust.
- Background dressed with stacked wooden shipping pallets, blue plastic drums, chain hoists, rolling racks, a stationary forklift in deep background.
- Air feels still and cold, faint condensation; low-key industrial ambience.

Faces, costumes, hand props, hair, makeup, and skin tones are UNCHANGED from the source. Do not redress the actors. Do not change their performance.

Cinematography: Arri Alexa, anamorphic lens, shallow depth of field, cold desaturated palette with steel-blue highlights and high-contrast shadow falloff. Documentary editorial photography aesthetic. Natural skin texture with visible pores and small natural imperfections, Kodak Portra 400 color science, subtle film grain. No game-engine rendering, no plastic/CGI sheen, no movie-poster polish. Natural light only — daylight through skylights as the only key."""

ENVIRONMENTS = [("forest", FOREST_PROMPT), ("warehouse", WAREHOUSE_PROMPT)]


def upload_to_drive(drive, parent_id: str, local_path: Path) -> str:
    """Upload an mp4 to Drive, set anyone-with-link reader, return uc?export=download URL."""
    media = MediaFileUpload(str(local_path), mimetype="video/mp4", resumable=True, chunksize=1024*1024)
    f = drive.files().create(
        body={"name": f"kling_v2v_input_{local_path.stem}.mp4", "parents": [parent_id]},
        media_body=media, fields="id",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role": "reader", "type": "anyone"}, fields="id").execute()
    return f"https://drive.google.com/uc?export=download&id={f['id']}"


def main():
    # 1. Find / create a Drive folder for the inputs
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)
    q = "name='Kling V2V Test Inputs' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    found = drive.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    if found:
        parent_id = found[0]["id"]
        print(f"using folder: {parent_id}")
    else:
        folder = drive.files().create(
            body={"name": "Kling V2V Test Inputs", "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        parent_id = folder["id"]
        drive.permissions().create(fileId=parent_id, body={"role": "reader", "type": "anyone"}, fields="id").execute()
        print(f"created folder: {parent_id}")

    # 2. Upload each clip, get URL
    clip_urls = {}
    for label, local, dur in CLIPS:
        print(f"  uploading {label} ({local.stat().st_size/1024/1024:.1f}MB)...")
        url = upload_to_drive(drive, parent_id, local)
        clip_urls[label] = url
        print(f"    → {url}")

    # 3. Fire 8 V2V calls
    jobs = []
    for label, _, dur in CLIPS:
        for env_name, env_prompt in ENVIRONMENTS:
            print(f"\n  fire: {label} × {env_name} (duration={dur})")
            r = omni_video(
                prompt=env_prompt,
                video_urls=[clip_urls[label]],
                refer_type="base",
                keep_original_sound=False,
                model="kling-video-o1",
                mode="std",
                duration=dur,
            )
            code = r.get("code")
            data = r.get("data") or {}
            tid = data.get("task_id")
            if code == 0 and tid:
                print(f"    ✓ task: {tid}")
                jobs.append({"label": label, "env": env_name, "task_id": tid, "duration": dur})
            else:
                print(f"    ✗ FAILED: code={code} msg={r.get('message')!r}")
                jobs.append({"label": label, "env": env_name, "task_id": None, "duration": dur, "error": r.get("message")})

    # Save state in case we want to resume polling
    (HERE / ".kling_v2v_test_jobs.json").write_text(json.dumps(jobs, indent=2))
    print(f"\n  saved job manifest: .kling_v2v_test_jobs.json")

    # 4. Poll until all done
    print("\n=== polling ===")
    results = {}
    start = time.time()
    pending = [j for j in jobs if j["task_id"]]
    while pending and time.time() - start < 1800:
        still_pending = []
        for job in pending:
            tid = job["task_id"]
            resp = get_task("omni-video", tid)
            data = resp.get("data") or {}
            status = data.get("task_status")
            tag = f"{job['label']}/{job['env']}"
            if status == "succeed":
                videos = (data.get("task_result") or {}).get("videos") or []
                url = videos[0].get("url") if videos else None
                print(f"  [{int(time.time()-start)}s] ✓ {tag}  → {url}")
                results[tag] = {"task_id": tid, "url": url}
            elif status == "failed":
                msg = json.dumps(resp)[:300]
                print(f"  [{int(time.time()-start)}s] ✗ {tag}  FAILED: {msg}")
                results[tag] = {"task_id": tid, "error": msg}
            else:
                still_pending.append(job)
        pending = still_pending
        if pending:
            print(f"  [{int(time.time()-start)}s] {len(pending)} still running...")
            time.sleep(20)

    # 5. Download outputs
    print("\n=== downloading ===")
    for tag, info in results.items():
        if not info.get("url"):
            continue
        label, env = tag.split("/")
        shot_folder = SPLITS / label / "kling edit outputs (not underwater)"
        shot_folder.mkdir(parents=True, exist_ok=True)
        out = shot_folder / f"kling_v2v_{env}.mp4"
        try:
            data = requests.get(info["url"], timeout=300).content
            out.write_bytes(data)
            size_mb = out.stat().st_size / 1024 / 1024
            print(f"  ✓ {out}  ({size_mb:.1f}MB)")
        except Exception as e:
            print(f"  ✗ {tag}  download failed: {e}")

    print(f"\nTotal wall time: {time.time()-start:.1f}s")
    print(f"Successful: {sum(1 for r in results.values() if r.get('url'))} / {len(jobs)}")


if __name__ == "__main__":
    main()

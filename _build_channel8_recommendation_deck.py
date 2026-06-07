#!/usr/bin/env python3
"""Mirror Landed Outputs → Drive folder, then build & upload the
'OUR RECOMMENDATION — Channel 8 Underwater Reskin' HTML deck.

- Uploads any file in the local folder that's missing from Drive
- Trashes any Drive file that's no longer in the local folder
- Generates a single HTML deck with preface + 6 sample cards + user captions
- Uploads the deck to the same Drive folder
- Opens the deck locally and the Drive folder
"""
import os, sys, subprocess, html
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from auth import get_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

LANDED = Path("/Users/raymuschang/Desktop/Channel 8 Underwater — Landed Outputs")
FOLDER_NAME = "Channel 8 Underwater — Seedance Outputs"

# User's ordered sample list with captions (in their voice)
SAMPLES = [
    {
        "file": "emperor_2subjects_v1_720p_15s.mp4",
        "title": "Emperor + 2 Subjects — angles only",
        "caption": ("These are just some angles of the characters in the scene. There is no acting. "
                    "We have to shoot the actors closely with the composition we lock in the animatic. "
                    "Then the video of the actors acting can fuel the performance in this shot. "
                    "So in the end, it is their acting."),
    },
    {
        "file": "seedance_test.mp4",
        "title": "Space + Angles showcase",
        "caption": ("Here is a showcase of the possibilities of arranging the space and the angles we can get. "
                    "Same protocol — we lock the shot in the animatic, then shoot exactly the same to "
                    "infuse the acting into the shot."),
    },
    {
        "file": "shot_01_underwater_v1_720p_8s.mp4",
        "files_grouped": [
            "shot_01_underwater_v1_720p_8s.mp4",
            "shot_01_underwater_v3_with_location_720p_8s.mp4",
        ],
        "title": "Shot 01 — Jib down on emperor pinned by pillar (v1 + v3)",
        "caption": ("After the jib down, unfortunately we have to cut to an ECU or CU to "
                    "incorporate the acting inside."),
    },
    {
        "file": "shot_08_underwater_v4_3sFF_720p_15s.mp4",
        "title": "Shot 08 — Throne hall variation",
        "caption": ("This is a variation of the underwater palace. Some things are wrong with the blocking, "
                    "but this sequence shows the variety of shots we can take — even overhead shots. "
                    "We even did a costume change to show what can be done."),
    },
    {
        "file": "shot_08_underwater_v5_collage_4char_720p_15s.mp4",
        "title": "Shot 08 — Angles variation",
        "caption": ("This is a variation for the angles. Ignore the dialogue — it is purely AI generated. "
                    "We need to have the actors in."),
    },
]


def get_or_create_folder(drive):
    res = drive.files().list(
        q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id,webViewLink)").execute()
    if res.get("files"):
        return res["files"][0]["id"], res["files"][0].get("webViewLink")
    f = drive.files().create(
        body={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
        fields="id,webViewLink").execute()
    drive.permissions().create(fileId=f["id"], body={"role":"reader","type":"anyone"}, fields="id").execute()
    return f["id"], f.get("webViewLink")


def list_folder(drive, folder_id):
    out = {}
    page = None
    while True:
        res = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id,name,mimeType)",
            pageToken=page).execute()
        for f in res.get("files", []):
            out[f["name"]] = f
        page = res.get("nextPageToken")
        if not page: break
    return out


def upload_or_replace(drive, folder_id, local: Path, mime: str, existing: dict):
    """Upload `local` to Drive if missing, or replace contents if already present."""
    if local.name in existing:
        fid = existing[local.name]["id"]
        # Update file contents (keep same id so existing links don't break)
        media = MediaFileUpload(str(local), mimetype=mime, resumable=True, chunksize=2*1024*1024)
        drive.files().update(fileId=fid, media_body=media, fields="id").execute()
        print(f"  ↻ replaced contents: {local.name}  (id {fid})")
    else:
        print(f"  ◦ uploading: {local.name} ({local.stat().st_size/1024/1024:.1f} MB)...")
        media = MediaFileUpload(str(local), mimetype=mime, resumable=True, chunksize=2*1024*1024)
        f = drive.files().create(
            body={"name": local.name, "parents": [folder_id]},
            media_body=media, fields="id").execute()
        fid = f["id"]
        drive.permissions().create(fileId=fid, body={"role":"reader","type":"anyone"}, fields="id").execute()
        print(f"    ✓ id {fid}")
    return fid


def trash_file(drive, fid, name):
    try:
        drive.files().update(fileId=fid, body={"trashed": True}).execute()
        print(f"  🗑 trashed (no longer in local): {name}  (id {fid})")
    except Exception as e:
        print(f"  ! failed to trash {name}: {e}")


def mime_for(p: Path) -> str:
    ext = p.suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".html": "text/html",
        ".md": "text/markdown",
        ".png": "image/png",
        ".jpg": "image/jpeg",
    }.get(ext, "application/octet-stream")


def build_deck_html(file_ids: dict) -> str:
    def stream(fid): return f"https://drive.google.com/uc?export=download&id={fid}"

    cards_html = []
    for s in SAMPLES:
        title = html.escape(s["title"])
        caption = html.escape(s["caption"])
        if s.get("files_grouped"):
            videos = ""
            for fname in s["files_grouped"]:
                fid = file_ids.get(fname)
                if not fid:
                    videos += f'<div class="missing">⚠ missing: {html.escape(fname)}</div>'
                    continue
                videos += f'''<div class="vid">
                  <video src="{stream(fid)}" autoplay loop muted playsinline controls preload="metadata"></video>
                  <div class="fname">{html.escape(fname)}</div>
                </div>'''
            cards_html.append(f'''
            <section class="card grouped">
              <h3>{title}</h3>
              <div class="grid-two">{videos}</div>
              <p class="caption">{caption}</p>
            </section>''')
        else:
            fname = s["file"]
            fid = file_ids.get(fname)
            if not fid:
                vid_html = f'<div class="missing">⚠ missing: {html.escape(fname)}</div>'
            else:
                vid_html = f'''<video src="{stream(fid)}" autoplay loop muted playsinline controls preload="metadata"></video>
                <div class="fname">{html.escape(fname)}</div>'''
            cards_html.append(f'''
            <section class="card">
              <h3>{title}</h3>
              {vid_html}
              <p class="caption">{caption}</p>
            </section>''')

    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>OUR RECOMMENDATION — Channel 8 Underwater Reskin</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 40px 64px;
    background: #0a0e13; color: #e7ecf3;
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
    max-width: 1280px; margin: 0 auto;
  }}
  header {{ margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid #1c2733; }}
  .eyebrow {{
    color: #38bdf8; letter-spacing: .12em; font-size: 11px;
    text-transform: uppercase; font-weight: 700; margin-bottom: 8px;
  }}
  h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: -.2px; }}
  .sub {{ color: #8a96a3; font-size: 14px; }}
  .preface {{
    margin: 26px 0 36px;
    padding: 20px 24px;
    background: linear-gradient(135deg, #0f1923 0%, #0d1a26 100%);
    border-left: 3px solid #38bdf8;
    border-radius: 6px;
  }}
  .preface .label {{
    display: inline-block; font-size: 11px; font-weight: 700;
    letter-spacing: .15em; color: #38bdf8; margin-bottom: 8px;
    text-transform: uppercase;
  }}
  .preface p {{ margin: 0; font-size: 15px; color: #c8d2dd; line-height: 1.6; }}
  .preface b {{ color: #fbbf24; }}
  section.card {{
    margin-bottom: 36px;
    padding: 22px 24px 24px;
    background: #131922;
    border: 1px solid #1f2a37;
    border-radius: 10px;
  }}
  section.card h3 {{
    margin: 0 0 14px; font-size: 17px; color: #e7ecf3; font-weight: 600;
  }}
  section.card video {{
    width: 100%; max-height: 540px; border-radius: 6px;
    background: #000; display: block;
  }}
  .fname {{
    color: #5b6675; font-size: 11px; font-family: ui-monospace, Menlo, monospace;
    margin-top: 6px;
  }}
  .caption {{
    margin-top: 14px; padding: 14px 16px;
    background: #0c1219; border-radius: 6px;
    color: #b8c2cd; font-size: 14px; line-height: 1.6;
    border-left: 2px solid #475569;
  }}
  .grid-two {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
  }}
  .grid-two .vid {{ display: flex; flex-direction: column; }}
  .grid-two video {{ max-height: 360px; }}
  .controls {{
    position: sticky; top: 0; z-index: 10;
    background: rgba(10,14,19,.95); backdrop-filter: blur(8px);
    margin: -32px -40px 24px;
    padding: 14px 40px; border-bottom: 1px solid #1c2733;
    display: flex; gap: 10px; align-items: center;
  }}
  button {{
    background: #1c2733; color: #e7ecf3;
    border: 1px solid #2a3543;
    padding: 7px 14px; border-radius: 6px;
    cursor: pointer; font-size: 13px;
  }}
  button:hover {{ background: #25313f; }}
  .controls .spacer {{ flex: 1; }}
  .controls .meta {{ color: #5b6675; font-size: 12px; }}
  .missing {{ color: #fca5a5; padding: 14px; background: #1e1414; border-radius: 6px; }}
  footer {{
    margin-top: 60px; padding-top: 24px;
    border-top: 1px solid #1c2733;
    color: #5b6675; font-size: 12px;
  }}
</style>
</head><body>
<div class="controls">
  <button onclick="document.querySelectorAll('video').forEach(v=>{{v.muted=false; v.play()}})">Unmute all</button>
  <button onclick="document.querySelectorAll('video').forEach(v=>{{v.muted=true}})">Mute all</button>
  <button onclick="document.querySelectorAll('video').forEach(v=>{{v.currentTime=0; v.play()}})">Sync restart</button>
  <div class="spacer"></div>
  <div class="meta">Auto-loop · streaming from Drive · no transcode wait</div>
</div>

<header>
  <div class="eyebrow">Channel 8 Underwater Reskin · Production Test</div>
  <h1>Our Recommendation</h1>
  <div class="sub">Workflow proof-of-concept · BytePlus Seedance 2.0 · 720p · 16:9</div>
</header>

<div class="preface">
  <div class="label">Important context</div>
  <p>The samples below are <b>100% AI-generated</b>. They demonstrate environment integration, lighting, proportion, angle variety, and location consistency — <b>not performance.</b> Acting beats will come from filmed actors locked to the animatic compositions, then fused into these frames. The AI gives us the world and the camera; the actors give us the performance.</p>
</div>

{''.join(cards_html)}

<footer>
  Six samples · 100% AI-generated · Drive folder mirrors this deck.<br>
  Streams play instantly from Drive's direct-stream URL (bypasses preview transcode wait).<br>
  Full technical notes available as <code>TECH_NOTES.md</code> in the same Drive folder.
</footer>
</body></html>'''


def main():
    creds = get_credentials()
    drive = build("drive", "v3", credentials=creds)

    folder_id, folder_link = get_or_create_folder(drive)
    print(f"Drive folder: {folder_link}")

    existing = list_folder(drive, folder_id)

    # Mirror: upload anything in local that's missing/changed; track which local names exist
    local_files = [p for p in LANDED.iterdir() if p.is_file() and not p.name.startswith(".")
                   and p.suffix.lower() in (".mp4", ".md")]
    file_ids = {}
    local_names = set()
    for p in sorted(local_files):
        local_names.add(p.name)
        fid = upload_or_replace(drive, folder_id, p, mime_for(p), existing)
        file_ids[p.name] = fid

    # Trash any Drive files no longer present locally (except OUR_RECOMMENDATION.html which we'll re-upload)
    keep_on_drive = local_names | {"OUR_RECOMMENDATION.html", "gallery_drive.html"}
    for name, info in existing.items():
        if name not in keep_on_drive:
            trash_file(drive, info["id"], name)

    # Build & upload deck
    print("\n=== Building OUR RECOMMENDATION deck ===")
    deck_html = build_deck_html(file_ids)
    deck_path = LANDED / "OUR_RECOMMENDATION.html"
    deck_path.write_text(deck_html)
    print(f"  local: {deck_path}")

    deck_fid = upload_or_replace(drive, folder_id, deck_path, "text/html", existing)
    print(f"  Drive deck id: {deck_fid}")
    print(f"  Drive deck view: https://drive.google.com/file/d/{deck_fid}/view")

    print(f"\n📦 Drive folder:  {folder_link}")
    print(f"📺 Local deck:    {deck_path}")

    # Open both
    subprocess.run(["open", str(deck_path)])
    subprocess.run(["open", folder_link])


if __name__ == "__main__":
    main()

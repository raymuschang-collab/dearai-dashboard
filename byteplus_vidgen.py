#!/usr/bin/env python3
"""
byteplus_vidgen.py — Replaces fal_vidgen.py. Routes Seedance 2.0 video gen
through BytePlus ARK API (the HK company's $1M wallet account).

Workflow:
  1. Read storyboard set body from Storyboard Prompts tab
  2. refs_audit pattern: detect bible names (chars/locs/props/costume/fx) in body
  3. Asset Library lookup: bible name → BytePlus asset_id (col C)
  4. Build Seedance prompt (camera/audio/realism preamble + body)
  5. Submit task to BytePlus ARK content_generation/tasks/create
  6. Poll /tasks/{id} until succeeded
  7. Download MP4 from results url (24-hour expiry — must be fast)
  8. Upload to Drive videos/set-NN/, archive prior file
  9. Write URL to Storyboard Prompts!L (slot 1) or M (slot 2)
 10. --confirm gate prints refs + waits [y/N] before submit (anti ref-bleed)
 11. Append usage to .byteplus_expense.json (cumulative spend tally)

Usage:
  python3 byteplus_vidgen.py --sheet <ID> --set N --slot 1|2 [--iter 3|4]
  python3 byteplus_vidgen.py --sheet <ID> --set N --slot 1 --confirm
  python3 byteplus_vidgen.py --sheet <ID> --set N --slot 1 --duration 8 --resolution 720p --fast
"""
from __future__ import annotations

import argparse
import builtins as _builtins

# Resilient print() — survives parent (Dash) restart killing our stdout pipe.
_orig_print = _builtins.print


def _safe_print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    except BrokenPipeError:
        try:
            import sys as _sys, os as _os
            _sys.stdout = open(_os.devnull, "w")
            _sys.stderr = open(_os.devnull, "w")
        except Exception:
            pass


_builtins.print = _safe_print
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import gspread
import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

# Resolve auth.py
def _resolve_auth():
    candidates = [
        os.path.join(os.getcwd(), "auth.py"),
        os.path.join(str(HERE), "auth.py"),
        os.path.expanduser("~/Desktop/Shotlist Workflows/auth.py"),
    ]
    for c in candidates:
        if os.path.exists(c):
            sys.path.insert(0, os.path.dirname(c))
            from auth import get_credentials  # type: ignore
            return get_credentials
    raise SystemExit("Could not find auth.py")

get_credentials = _resolve_auth()

ARK_API_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = os.getenv("BYTEPLUS_ARK_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3")

# Slot → Storyboard Prompts col index (0-based)
# Storyboard Prompts schema (post-2026-05-05):
#   L = Location (SOT)  ← reserved, do NOT write here from vidgen
#   M = Video Iter 1 URL
#   N = Video Iter 2 URL
SLOT_TO_COL = {1: "M", 2: "N"}
ITER_TO_COL = {3: "J", 4: "K"}  # storyboard iter URL columns

EXPENSE_LOG = HERE / ".byteplus_expense.json"


def parse_sheet_id(s: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", s)
    return m.group(1) if m else s.strip()


def drive_id(url: str) -> str | None:
    if not url: return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m: return m.group(1)
    return None


def lh3_url(file_id: str, w: int = 1024) -> str:
    return f"https://lh3.googleusercontent.com/d/{file_id}=w{w}"


def _build_location_aliases(sh) -> dict[str, list[str]]:
    """{canonical: [alias1, alias2, …]} from LOCATIONS bible col O.
    Aliases are semicolon-separated lowercase substrings authored per show.
    Empty result is fine — falls back to canonical-only matching."""
    out: dict[str, list[str]] = {}
    try:
        rows = sh.worksheet("LOCATIONS").get(
            "A5:O100", value_render_option="FORMATTED_VALUE")
        for row in rows:
            row = (row + [""] * 15)[:15]
            name = (row[0] or "").strip()
            aliases_str = (row[14] or "").strip()
            if not name or not aliases_str:
                continue
            out.setdefault(name, [])
            for a in aliases_str.split(";"):
                a = a.strip().lower()
                if a and a not in out[name]:
                    out[name].append(a)
    except Exception:
        pass
    return out


def detect_bible_refs(body: str, sh) -> list[dict]:
    """
    Walk Asset Library tab, find which bible entries are mentioned in body.
    Returns list of dicts: {name, bible_tab, asset_code, source_url}.
    Only includes rows where Status='Uploaded' and Asset Code is set.

    Match strategies (in order, first hit wins per row):
      1. Whole-name match: re.search r"\\b<name>\\b" in body
      2. CHARACTERS — split name, match any word ≥4 chars (so
         "TARA ANJANI" matches body "TARA"; "LEE JOON-HO" matches "JOON-HO")
      3. LOCATIONS — match any alias from LOCATIONS!O (built once per call)
    """
    try:
        ws = sh.worksheet("Asset Library")
    except Exception:
        print(f"  ⚠ no 'Asset Library' tab — refs cannot be resolved to asset codes")
        return []
    rows = ws.get("A5:L500", value_render_option="FORMATTED_VALUE")
    body_lc = body.lower()
    detected = []
    # Dedup by asset_code — NOT by name. A canonical can appear in multiple
    # Asset Library rows (e.g. PARK MIN-JUN with both a still photo and a
    # video face-loop ref); we want all of them attached when matched.
    seen_codes = set()
    loc_aliases = _build_location_aliases(sh)

    for r in rows:
        if not r or not r[0].strip(): continue
        name = r[0].strip()
        bible_tab = r[1].strip() if len(r) > 1 else ""
        asset_code = r[2].strip() if len(r) > 2 else ""
        source_url = r[3].strip() if len(r) > 3 else ""
        asset_type = r[4].strip().lower() if len(r) > 4 else ""
        status = r[5].strip() if len(r) > 5 else ""
        if status != "Uploaded" or not asset_code: continue
        if asset_code in seen_codes: continue

        matched = False
        # 1. Whole canonical name
        if re.search(r"\b" + re.escape(name) + r"\b", body, re.IGNORECASE):
            matched = True
        # 2. Split-name fallback for CHARACTERS — any word ≥4 chars
        if not matched and bible_tab == "CHARACTERS":
            for word in re.findall(r"[A-Za-z][\w\-]+", name):
                if len(word) >= 4 and re.search(
                        r"\b" + re.escape(word) + r"\b", body, re.IGNORECASE):
                    matched = True
                    break
        # 3. Bible-alias fallback for LOCATIONS — col O entries
        if not matched and bible_tab == "LOCATIONS":
            for alias in loc_aliases.get(name, []):
                if alias in body_lc:
                    matched = True
                    break

        if matched:
            seen_codes.add(asset_code)
            detected.append({
                "name": name,
                "bible_tab": bible_tab,
                "asset_code": asset_code,
                "source_url": source_url,
                "asset_type": asset_type,  # "image" / "video" — vidgen uses for role
            })
    return detected


def detect_shotlist_tab(sh) -> str | None:
    non_shotlist = {"Storyboard Prompts", "Video Prompts", "CHARACTERS", "LOCATIONS",
                    "PROPS", "COSTUME", "EFFECTS", "README", "Asset Library"}
    for ws in sh.worksheets():
        if ws.title not in non_shotlist:
            return ws.title
    return None


def read_video_prompt_payload(sh, set_num: int) -> tuple[str, str, str, str]:
    """Return camera/audio/setting globals plus the per-set shot payload."""
    global_camera = ""
    global_audio = ""
    global_setting = ""
    try:
        vp_ws = sh.worksheet("Video Prompts")
        gvals = vp_ws.get("A1:B6", value_render_option="FORMATTED_VALUE")
        for r in gvals:
            r = (r + ["", ""])[:2]
            label = (r[0] or "").strip().lower()
            val = r[1] or ""
            if label == "camera global":
                global_camera = val
            elif label == "audio/dialogue global":
                global_audio = val
            elif label == "setting global":
                global_setting = val
    except Exception:
        global_camera = "Shot with Arri 35."

    shot_payloads = []
    try:
        shotlist_tab = detect_shotlist_tab(sh) or "Shotlist"
        sl_ws = sh.worksheet(shotlist_tab)
        sl_rows = sl_ws.get("A2:R200", value_render_option="FORMATTED_VALUE")
        first_shot = (set_num - 1) * 5 + 1
        last_shot = set_num * 5
        for r in sl_rows:
            r = (r + [""] * 18)[:18]
            shot_num = (r[0] or "").strip()
            if not shot_num.isdigit():
                continue
            shot_n = int(shot_num)
            if first_shot <= shot_n <= last_shot and (r[16] or "").strip():
                shot_payloads.append(r[16])
    except Exception:
        pass

    body = "\n\n".join(shot_payloads)
    return global_camera, global_audio, global_setting, body


def submit_seedance_task(prompt: str, ref_urls: list[dict], aspect_ratio: str = "9:16",
                         duration: int = 15, resolution: str = "1080p", fast: bool = False) -> tuple[str | None, str | None]:
    """
    Submit task to BytePlus ARK Seedance 2.0.
    Returns (task_id, error).
    ref_urls: list of {"type": "image|video", "url": "https://...", "role": "subject"}.
    NOTE: references[] array is the correct slot — content[].image_url triggers moderation.
    """
    model = "dreamina-seedance-2-0-fast-260128" if fast else "dreamina-seedance-2-0-260128"
    endpoint = f"{ARK_BASE}/contents/generations/tasks"
    headers = {"Authorization": f"Bearer {ARK_API_KEY}", "Content-Type": "application/json"}

    # SCHEMA NOTE (verified via probes):
    #  - top-level `references` field is silently dropped by BytePlus
    #  - correct slot for refs is content[].image_url / content[].video_url
    #    with role="reference_image" / "reference_video"
    #  - real-person face URLs trigger PrivacyInformation moderation gate
    #    → upload to private asset library, use asset://asset-<id>
    #  - non-face plain HTTPS URLs (storyboards, locations, props) pass
    #    cleanly — DON'T skip them or composition refs never reach Seedance
    #  - cap at 6 refs total — Seedance 2.0 starts to dilute identity past
    #    that. Order is preserved (storyboard first, then chars, then
    #    locations) so the most-specific anchors get priority slots.
    MAX_REFS = 6
    content = [{"type": "text", "text": prompt}]
    accepted_refs = []
    for ref in ref_urls or []:
        url = ref.get("url", "")
        if not url:
            continue
        if len(accepted_refs) >= MAX_REFS:
            print(f"  ⚠ ref limit ({MAX_REFS}) hit — dropping {url[:60]}…")
            continue
        accepted_refs.append(ref)
        if ref.get("type") == "video":
            content.append({"type": "video_url",
                            "video_url": {"url": url},
                            "role": "reference_video"})
        else:
            content.append({"type": "image_url",
                            "image_url": {"url": url},
                            "role": "reference_image"})
    print(f"  → submitting {len(accepted_refs)} refs: "
          + ", ".join(r['url'][:50] + ('…' if len(r['url']) > 50 else '')
                      for r in accepted_refs))
    body = {
        "model": model,
        "content": content,
        "ratio": aspect_ratio,
        "duration": duration,
        "resolution": resolution,
        "watermark": False,
    }

    try:
        r = requests.post(endpoint, headers=headers, json=body, timeout=60)
        if r.status_code != 200:
            return None, f"submit failed: {r.status_code} {r.text[:300]}"
        resp = r.json()
        task_id = resp.get("id") or resp.get("task_id") or resp.get("data", {}).get("id")
        if not task_id:
            return None, f"no task_id in response: {resp}"
        return task_id, None
    except Exception as e:
        return None, f"exception: {e}"


def poll_task(task_id: str, max_wait_sec: int = 600) -> tuple[dict | None, str | None]:
    """Poll task until done. Returns (result_dict_with_video_url, error)."""
    endpoint = f"{ARK_BASE}/contents/generations/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {ARK_API_KEY}"}
    start = time.time()
    last_status = None
    while time.time() - start < max_wait_sec:
        try:
            r = requests.get(endpoint, headers=headers, timeout=30)
            if r.status_code != 200:
                return None, f"poll failed: {r.status_code} {r.text[:200]}"
            resp = r.json()
            status = resp.get("status") or resp.get("data", {}).get("status")
            if status != last_status:
                print(f"  [{int(time.time()-start)}s] status: {status}")
                last_status = status
            if status in ("succeeded", "completed", "success"):
                return resp, None
            if status in ("failed", "expired", "cancelled"):
                return None, f"task failed: status={status} resp={resp}"
        except Exception as e:
            print(f"  poll exception (non-fatal): {e}")
        time.sleep(15)
    return None, "max wait exceeded (10 min)"


def log_expense(task_id: str, model: str, duration: int, resolution: str,
                aspect: str, set_num: int, slot: int):
    """Append to .byteplus_expense.json — cumulative spend tally for /byteplus-expense."""
    # Rough cost estimate (per apidog: ~$0.66 for 5s/1080p ≈ $0.132/sec at 1080p)
    cost_per_sec = {"480p": 0.05, "720p": 0.08, "1080p": 0.132, "2K": 0.20}.get(resolution, 0.132)
    if "fast" in model:
        cost_per_sec *= 0.5  # fast tier roughly half
    est_cost = round(cost_per_sec * duration, 4)

    try:
        log = json.loads(EXPENSE_LOG.read_text()) if EXPENSE_LOG.exists() else {"entries": [], "cumulative_usd": 0.0}
    except Exception:
        log = {"entries": [], "cumulative_usd": 0.0}
    log["entries"].append({
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": task_id, "model": model, "duration": duration,
        "resolution": resolution, "aspect": aspect, "set": set_num, "slot": slot,
        "estimated_usd": est_cost,
    })
    log["cumulative_usd"] = round(sum(e["estimated_usd"] for e in log["entries"]), 2)
    EXPENSE_LOG.write_text(json.dumps(log, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--set", type=int, required=True, dest="set_num")
    ap.add_argument("--slot", type=int, default=1, choices=[1, 2])
    ap.add_argument("--iter", type=int, default=3, choices=[3, 4],
                    help="(DEPRECATED) Storyboard iter URL col J/K — legacy schema")
    ap.add_argument("--sb-slot", type=int, default=None, choices=[1, 2],
                    dest="sb_slot",
                    help="Which Storyboard Prompts iter to attach as composition ref. "
                         "1 → SP!G (Iter 1), 2 → SP!H (Iter 2). Default: matches --slot.")
    ap.add_argument("--duration", type=int, default=15)
    ap.add_argument("--resolution", default="1080p", choices=["480p","720p","1080p","2K"])
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--fast", action="store_true", help="Use fast tier (cheaper, slightly lower quality)")
    ap.add_argument("--confirm", action="store_true",
                    help="Print refs + prompt, wait [y/N] before submit")
    args = ap.parse_args()

    if not ARK_API_KEY:
        sys.exit("BYTEPLUS_ARK_API_KEY not set in .env")

    sheet_id = parse_sheet_id(args.sheet)
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(sheet_id)
    sb_ws = sh.worksheet("Storyboard Prompts")

    set_row = 10 + args.set_num  # row mapping per v2.2 spec
    global_camera, global_audio, global_setting, body = read_video_prompt_payload(sh, args.set_num)

    if not body.strip():
        sys.exit(f"Shotlist video prompt payload for set {args.set_num} is empty")

    # Storyboard composition reference — pencil-on-paper iter, attached as
    # FIRST reference_image so Seedance treats it as the canonical composition
    # anchor (camera angle, blocking, depth). Plain Drive URL is fine: no
    # real-person face → no PrivacyInformation moderation gate. NOT uploaded
    # to the BytePlus asset library — just submitted as an external image ref.
    sb_slot_for_ref = args.sb_slot if args.sb_slot is not None else args.slot
    sb_col = "G" if sb_slot_for_ref == 1 else "H"
    sb_drive_url = ""
    try:
        cell = sb_ws.get(f"{sb_col}{set_row}", value_render_option="FORMATTED_VALUE")
        sb_drive_url = (cell[0][0] if cell and cell[0] else "").strip()
    except Exception as e:
        print(f"  ⚠ couldn't read storyboard ref from {sb_col}{set_row}: {e}")

    def _drive_id(u: str) -> str:
        m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", u or "")
        if m: return m.group(1)
        m = re.search(r"id=([a-zA-Z0-9_-]+)", u or "")
        return m.group(1) if m else ""

    sb_url = ""
    if sb_drive_url:
        # Drive's /view URL is an HTML viewer page — Seedance rejects that
        # as InvalidParameter.UnsupportedImageFormat. Use the lh3 binary URL
        # pattern (same one we use for dashboard thumbnails) so Seedance gets
        # the raw image.
        sb_id = _drive_id(sb_drive_url)
        if sb_id:
            sb_url = f"https://lh3.googleusercontent.com/d/{sb_id}=w2048"
    ref_urls = []
    if sb_url:
        ref_urls.append({
            "type": "image",
            "url": sb_url,
            "role": "reference_image",
        })
        print(f"  + storyboard ref ({sb_col}{set_row}): {sb_url}")
    else:
        print(f"  ⚠ no storyboard iter at {sb_col}{set_row} — proceeding without composition ref")

    # Detect bible refs from Asset Library — chars + locations get asset://
    # codes (face-moderation-bypass). Sort so CHARACTERS (identity) come
    # before LOCATIONS (background) — when the 6-ref cap kicks in we want
    # to keep identity refs over scenery refs.
    refs = detect_bible_refs(body, sh)
    bible_priority = {"CHARACTERS": 0, "LOCATIONS": 1, "COSTUME": 2,
                      "PROPS": 3, "EFFECTS": 4}
    refs.sort(key=lambda r: bible_priority.get(r.get("bible_tab", ""), 99))

    # CRITICAL — Seedance accepts `asset://asset-<id>` directly. DO NOT
    # resolve to a TOS URL: TOS URLs are plain HTTPS from the API's
    # perspective and they trigger the PrivacyInformation moderation gate
    # for real-person photos. Asset library protocol bypasses that gate
    # only when the scheme stays `asset://`. Confirmed via probe: bare
    # asset_id → 400 InvalidParameter; asset:// → 200 OK; TOS URL → 400
    # PrivacyInformation.
    for r in refs:
        asset_code = (r.get("asset_code") or "").strip()
        source_url = (r.get("source_url") or "").strip()
        asset_type = (r.get("asset_type") or "").strip().lower()
        if asset_code:
            url = (asset_code if asset_code.startswith("asset://")
                   else f"asset://{asset_code}")
            print(f"  + asset {asset_code} ({asset_type or 'image'})")
        elif source_url:
            url = source_url
            print(f"  + source URL ({asset_type or 'image'}): {url[:60]}…")
        else:
            continue
        is_video = (asset_type == "video"
                    or url.lower().endswith((".mp4", ".mov", ".webm")))
        ref_urls.append({
            "type": "video" if is_video else "image",
            "url": url,
            "role": "reference_video" if is_video else "reference_image",
        })

    # Build prompt
    # Composition directive — sits below the camera global so Seedance sees
    # the storyboard as the canonical layout anchor BEFORE the per-shot body.
    sb_directive = ("Follow the storyboard reference for composition, framing, "
                    "and blocking on every shot." if sb_url else "")
    realism = ("Documentary editorial photography aesthetic, natural skin texture, "
               "Kodak Portra 400 color science, no airbrushing, no game-engine rendering. "
               "Subtle film grain. Muted desaturated palette. Natural lighting only.")
    format_directive = f"VERTICAL {args.aspect} drama format. The video should follow these shots in sequence:"
    prompt = "\n".join([s for s in [
        global_camera, sb_directive, global_audio, global_setting,
        realism, format_directive, body
    ] if s])

    print(f"\n=== Set {args.set_num} slot {args.slot} → BytePlus Seedance 2 ===")
    print(f"  resolution: {args.resolution}  duration: {args.duration}s  aspect: {args.aspect}  fast: {args.fast}")
    print(f"  asset refs detected ({len(refs)}):")
    for r in refs:
        print(f"    [{r['bible_tab']}] {r['name']:<30} → {r['asset_code']}")

    if args.confirm:
        print(f"\n  prompt preview ({len(prompt)} chars):")
        print(f"  {'-'*60}")
        print(f"  {prompt[:600]}{'...' if len(prompt)>600 else ''}")
        print(f"  {'-'*60}")
        ans = input(f"\n  Submit to BytePlus? [y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            sys.exit("  ✗ user aborted at confirm gate")

    print(f"\n  Submitting...")
    task_id, err = submit_seedance_task(prompt, ref_urls, args.aspect, args.duration, args.resolution, args.fast)
    if err:
        sys.exit(f"\n  ✗ {err}")
    print(f"  task_id: {task_id}")

    print(f"\n  Polling (typical: 30-180s)...")
    result, err = poll_task(task_id)
    if err:
        sys.exit(f"\n  ✗ {err}")

    # Find video URL in response (BytePlus puts it at content.video_url)
    video_url = (result.get("content", {}).get("video_url")
                 or result.get("video_url") or result.get("url")
                 or result.get("data", {}).get("video_url")
                 or result.get("results", {}).get("video_url"))
    if not video_url:
        sys.exit(f"\n  ✗ no video_url in response: {json.dumps(result)[:500]}")
    print(f"\n  ✓ video ready: {video_url}")

    # Download + upload to Drive (Drive folder pattern: <show>/videos/set-NN/)
    from googleapiclient.discovery import build as gbuild
    from googleapiclient.http import MediaIoBaseUpload
    drive = gbuild("drive", "v3", credentials=get_credentials())
    sheet_meta = drive.files().get(fileId=sheet_id, fields="parents").execute()
    show_folder = sheet_meta["parents"][0]
    # videos/ folder
    q = f"'{show_folder}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='videos'"
    res = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if not res:
        videos_folder = drive.files().create(
            body={"name":"videos","mimeType":"application/vnd.google-apps.folder","parents":[show_folder]},
            fields="id").execute()["id"]
    else:
        videos_folder = res[0]["id"]
    # set-NN/
    set_folder_name = f"set-{args.set_num:02d}"
    q = f"'{videos_folder}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='{set_folder_name}'"
    res = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if not res:
        set_folder = drive.files().create(
            body={"name":set_folder_name,"mimeType":"application/vnd.google-apps.folder","parents":[videos_folder]},
            fields="id").execute()["id"]
    else:
        set_folder = res[0]["id"]
    drive.permissions().create(fileId=set_folder, body={"role":"reader","type":"anyone"}, fields="id").execute()

    # Download MP4 (24h expiry)
    mp4 = requests.get(video_url, timeout=300).content
    fname = f"video-iteration-{args.slot}-{args.resolution}-{args.duration}s.mp4"

    # Archive existing same-name file
    q = f"'{set_folder}' in parents and trashed=false and name='{fname}'"
    existing = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if existing:
        archive_name = "archive"
        q2 = f"'{set_folder}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='{archive_name}'"
        archive_res = drive.files().list(q=q2, fields="files(id)").execute().get("files", [])
        if not archive_res:
            archive_id = drive.files().create(
                body={"name":archive_name,"mimeType":"application/vnd.google-apps.folder","parents":[set_folder]},
                fields="id").execute()["id"]
            drive.permissions().create(fileId=archive_id, body={"role":"reader","type":"anyone"}, fields="id").execute()
        else:
            archive_id = archive_res[0]["id"]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for ex in existing:
            drive.files().update(fileId=ex["id"], addParents=archive_id, removeParents=set_folder,
                                 body={"name": f"{ts}_{fname}"}).execute()

    # Upload new
    media = MediaIoBaseUpload(io.BytesIO(mp4), mimetype="video/mp4", resumable=False)
    new_file = drive.files().create(
        body={"name":fname,"parents":[set_folder]}, media_body=media,
        fields="id,webViewLink").execute()
    drive.permissions().create(fileId=new_file["id"], body={"role":"reader","type":"anyone"}, fields="id").execute()
    print(f"\n  ✓ Drive: {new_file['webViewLink']}")

    # Write URL to Storyboard Prompts L or M
    target_col = SLOT_TO_COL[args.slot]
    sb_ws.update(values=[[new_file["webViewLink"]]], range_name=f"{target_col}{set_row}")
    print(f"  ✓ Storyboard Prompts!{target_col}{set_row} written")

    # Update Asset Library Last Used + First Used Shot for each ref
    if refs:
        try:
            al_ws = sh.worksheet("Asset Library")
            al_rows = al_ws.get("A5:L500", value_render_option="FORMATTED_VALUE")
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            updates = []
            for i, r in enumerate(al_rows, start=5):
                if not r or not r[0].strip(): continue
                name = r[0].strip()
                if name in {ref["name"] for ref in refs}:
                    # Update Last Used (col L) + first used shot (col H) if empty
                    if not (len(r) > 7 and r[7].strip()):
                        updates.append({"range": f"H{i}", "values": [[args.set_num * 5 - 4]]})
                    updates.append({"range": f"L{i}", "values": [[now]]})
            if updates:
                sh.values_batch_update(body={"valueInputOption":"USER_ENTERED",
                    "data": [{"range": f"'Asset Library'!{u['range']}", "values": u["values"]} for u in updates]})
        except Exception as e:
            print(f"  ⚠ couldn't update Asset Library usage: {e}")

    # Expense log
    log_expense(task_id, "fast" if args.fast else "standard", args.duration, args.resolution,
                args.aspect, args.set_num, args.slot)
    print(f"  ✓ expense logged → .byteplus_expense.json")

    print(f"\n=== DONE — Set {args.set_num} slot {args.slot} ===")


if __name__ == "__main__":
    main()

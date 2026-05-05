#!/usr/bin/env python3
"""
FLORA technique runner — submits a video gen job to FLORA's `sd2-vidgen` technique
and polls until completion. Mirrors the auto-detect logic of render_set_with_refs.py
but dispatches to FLORA's API instead of Higgsfield.

Usage:
    python3 flora_run.py --set 1 --iter 3
    python3 flora_run.py --set 1 --iter 3 --slot 2
    python3 flora_run.py --set 1 --iter 3 --technique sd2-vidgen
"""
from __future__ import annotations
import argparse
import io
import json
import os
import re
import time

from dotenv import load_dotenv
HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"), override=True)

import gspread
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"
FLORA_BASE = "https://app.flora.ai"
DEFAULT_TECHNIQUE = "sd2-vidgen"

# Location aliases (same as render_set_with_refs.py)
LOCATION_ALIASES = {
    "rooftop": "Rooftop above the Bazaar",
    "bazaar": "Peasant Bazaar",
    "marketplace": "Peasant Bazaar",
    "pyramid field": "Pyramid Field (Battlefield)",
    "battlefield": "Pyramid Field (Battlefield)",
    "pyramid": "Desert Plateau / Great Pyramid",
    "base of the pyramid": "Base of the Pyramid",
    "crater": "Impact Crater",
}


def drive_id_from_url(url):
    if not url: return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url) or re.search(r"id=([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def folder_id_from_url(url):
    if not url: return None
    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def lh3_url(file_id, w=1024):
    return f"https://lh3.googleusercontent.com/d/{file_id}=w{w}"


def detect_refs(body, sh):
    """Auto-detect refs from all bibles. Returns dict mapping slot_id → URL."""
    out = {}

    # PER-CHAR ITER PREFERENCE: KHENSU (lead) renders better with iter 2 (col U).
    # Add other character names to this set if they have a preferred iter 2.
    CHAR_PREFERRED_ITER_2 = {"KHENSU"}

    def _char_url(row):
        """Pick iter 2 (col U) for chars in CHAR_PREFERRED_ITER_2, else iter 1 (col T)."""
        name = row[0].strip()
        if name in CHAR_PREFERRED_ITER_2:
            u = row[20] if len(row) > 20 else (row[19] if len(row) > 19 else "")
        else:
            u = row[19] if len(row) > 19 else ""
        return drive_id_from_url(u)

    # Characters — apply ISFET SPAWN (2) override
    chars = sh.worksheet("CHARACTERS").get("A2:U20", value_render_option="FORMATTED_VALUE")
    char_hits = []
    for r in chars:
        if not r or not r[0]: continue
        name = r[0].strip()
        if not re.search(r"\b" + re.escape(name) + r"\b", body, re.IGNORECASE): continue
        # Skip the original "ISFET SPAWN" if "ISFET SPAWN (2)" exists — let the (2) take precedence
        if name == "ISFET SPAWN":
            # Check if (2) row also matches
            continue  # we'll let the (2) row catch it instead
        fid = _char_url(r)
        if fid:
            char_hits.append((name, lh3_url(fid)))

    # Now check (2) variants AFTER the originals
    for r in chars:
        if not r or not r[0]: continue
        name = r[0].strip()
        if "(2)" not in name: continue
        # match against the base name (e.g. "ISFET SPAWN" within body)
        base = name.replace("(2)", "").strip()
        if re.search(r"\b" + re.escape(base) + r"\b", body, re.IGNORECASE):
            fid = _char_url(r)
            if fid and not any(c[0] == name for c in char_hits):
                char_hits.append((name, lh3_url(fid)))

    # FLORA's sd2-vidgen technique caps character refs at 4. When more are
    # detected, drop ISFET SPAWN (2) FIRST — the storyboard ref already
    # encodes the spawn's appearance/scale, so we can let the protagonists
    # take the 4 slots. If still over 4, drop in detection order from the end.
    if len(char_hits) > 4:
        # Drop creature variants first
        char_hits = [c for c in char_hits if "(2)" not in c[0] and c[0] not in ("ISFET SPAWN", "TINY SCORPIONS")] \
                    + [c for c in char_hits if "(2)" in c[0] or c[0] in ("ISFET SPAWN", "TINY SCORPIONS")]
        # Now keep first 4 — creature variants go last so they get cut first
        char_hits = char_hits[:4]
        print(f"  ↳ char ref cap (FLORA=4): kept {[c[0] for c in char_hits]}")

    # Map to slots
    for i, (name, url) in enumerate(char_hits, 1):
        out[f"character-reference-{i}"] = (name, url)

    # Locations — keyword alias matching
    body_lc = body.lower()
    matched_locs = set()
    for kw, canonical in LOCATION_ALIASES.items():
        if kw in body_lc:
            matched_locs.add(canonical)
    locs = sh.worksheet("LOCATIONS").get("A5:N30", value_render_option="FORMATTED_VALUE")
    for r in locs:
        if not r or not r[0]: continue
        name = r[0].strip()
        if name in matched_locs and len(r) > 1 and r[1] == "wide":
            u = r[9] if len(r) > 9 else ""
            fid = drive_id_from_url(u)
            if fid:
                out["location-1"] = (f"{name} wide", lh3_url(fid))
                break

    # Props — substring match against PROPS col A
    props = sh.worksheet("PROPS").get("A6:G30", value_render_option="FORMATTED_VALUE")
    for r in props:
        if not r or not r[0]: continue
        name = r[0].strip()
        # First 1-2 keywords from name (e.g. "Salted fish slabs" → "salted fish")
        keywords = " ".join(name.lower().split()[:2])
        if keywords in body_lc:
            u = r[6] if len(r) > 6 else ""
            fid = drive_id_from_url(u)
            if fid:
                out["props"] = (name, lh3_url(fid))
                break

    # Costume — substring match against COSTUME col A
    cost = sh.worksheet("COSTUME").get("A6:G30", value_render_option="FORMATTED_VALUE")
    for r in cost:
        if not r or not r[0]: continue
        name = r[0].strip()
        # Match against "Sun-Guard", "Merchant", first word usually
        first_word = name.split(",")[0].split()[0]
        if first_word.lower() in body_lc and "costume-1" not in out:
            u = r[6] if len(r) > 6 else ""
            fid = drive_id_from_url(u)
            if fid:
                out["costume-1"] = (name, lh3_url(fid))

    # Effects — substring match
    fx = sh.worksheet("EFFECTS").get("A6:G30", value_render_option="FORMATTED_VALUE")
    for r in fx:
        if not r or not r[0]: continue
        name = r[0].strip()
        keywords = " ".join(name.lower().split()[:2])
        if keywords in body_lc:
            u = r[6] if len(r) > 6 else ""
            fid = drive_id_from_url(u)
            if fid:
                out["effects"] = (name, lh3_url(fid))
                break

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=int, required=True)
    ap.add_argument("--iter", type=int, choices=[3, 4], default=3)
    ap.add_argument("--slot", type=int, choices=[1, 2, 3, 4], default=1,
                    help="Video iter slot. 1→col L, 2→col M, 3→col N, 4→col O")
    ap.add_argument("--technique", default=DEFAULT_TECHNIQUE)
    ap.add_argument(
        "--skip", action="append", default=[],
        help="Slot ID to skip (uses placeholder instead). Repeatable. "
             "Example: --skip character-reference-1 --skip props",
    )
    args = ap.parse_args()

    api_key = os.getenv("FLORAFAUNA_API_KEY")
    if not api_key:
        raise SystemExit("FLORAFAUNA_API_KEY not in .env")

    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    sh = gc.open_by_key(SHEET_ID)
    sb = sh.worksheet("Storyboard Prompts")

    sheet_row = 10 + args.set
    row = sb.get(f"A{sheet_row}:M{sheet_row}", value_render_option="FORMATTED_VALUE")[0]
    set_num = row[0]
    shot_range = row[1] if len(row) > 1 else ""
    body = row[2] if len(row) > 2 else ""
    folder_url = row[4] if len(row) > 4 else ""
    iter_url = row[9] if args.iter == 3 else (row[10] if len(row) > 10 else "")

    iter_fid = drive_id_from_url(iter_url)
    if not iter_fid:
        raise SystemExit(f"No iter {args.iter} URL in row {sheet_row}")
    storyboard_url = lh3_url(iter_fid, 1600)

    # PENCIL FALLBACK: also load the corresponding pencil version (col G if --iter 3 / col H if --iter 4)
    # so the moderation cascade can swap photoreal → pencil if OpenAI's vision filter trips on photoreal faces.
    # Pencil ref = G (row[6]) for iter 3, H (row[7]) for iter 4.
    pencil_idx = 6 if args.iter == 3 else 7
    pencil_url_raw = row[pencil_idx] if len(row) > pencil_idx else ""
    pencil_fid = drive_id_from_url(pencil_url_raw) if pencil_url_raw else None
    pencil_storyboard_url = lh3_url(pencil_fid, 1600) if pencil_fid else None
    if pencil_storyboard_url:
        print(f"  pencil fallback ref available: {pencil_storyboard_url[:80]}")
    else:
        print(f"  pencil fallback: NONE (col {chr(65+pencil_idx)} empty — moderation cascade can't swap)")

    # Video globals
    vp = sh.worksheet("Video Prompts")
    vp_globals = "\n".join(r[0] for r in vp.get("B1:B4", value_render_option="FORMATTED_VALUE") if r and r[0])
    realism = (
        "Documentary editorial photography aesthetic, natural skin texture with visible pores, "
        "Kodak Portra 400 color science, no airbrushing, no game-engine rendering, no movie-poster polish. "
        "Subtle film grain. Muted, desaturated palette. Natural lighting only — practical sources."
    )
    storyboard_directive = (
        "CRITICAL — FOLLOW THE STORYBOARD REFERENCE IMAGE: The first image (the storyboard panel) "
        "is the visual blueprint for this video. Match each shot's blocking, framing, camera angle, "
        "character positions, and composition to the corresponding panel in the storyboard. The storyboard "
        "image is the ground truth for what each beat should look like — treat it as a directing reference, "
        "not loose inspiration. Use the character/location/costume reference images for identity and "
        "appearance fidelity within that storyboard-defined composition."
    )
    text_prompt = f"{vp_globals}\n\n{realism}\n\n{storyboard_directive}\n\nVERTICAL 9:16 vertical drama format. Follow this shot sequence:\n\n{body}"

    print(f"=== Set {set_num} — Shots {shot_range} ===")
    print(f"  technique: {args.technique}")
    print(f"  iter ref: J/K col {args.iter} → {storyboard_url[:80]}")

    # Auto-detect refs
    refs = detect_refs(body, sh)
    refs["storyboard"] = ("storyboard", storyboard_url)

    # Apply --skip flags (force placeholder for these slots — useful for
    # bypassing OpenAI moderation triggers on photoreal character refs)
    for skip_slot in args.skip:
        if skip_slot in refs:
            print(f"  ✗ skipping {skip_slot} (was: {refs[skip_slot][0]}) per --skip flag")
            del refs[skip_slot]

    print(f"\n  Auto-detected slot fills:")
    for slot, (label, url) in refs.items():
        print(f"    {slot:24s} ← {label}")

    # FLORA enforces positional ordering — inputs must arrive in the exact order
    # they're declared in the technique definition. Fetch the technique to get
    # the canonical order, then build the inputs array to match.
    H = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    tdef = requests.get(
        f"{FLORA_BASE}/api/v1/techniques/{args.technique}",
        headers=H, timeout=20,
    ).json()
    placeholder_url = storyboard_url
    inputs = []
    for slot_def in tdef.get("inputs", []):
        slot_id = slot_def["id"]
        slot_type = slot_def["type"]
        if slot_type == "text":
            inputs.append({"id": slot_id, "type": "text", "value": text_prompt})
        else:  # imageUrl
            url = refs[slot_id][1] if slot_id in refs else placeholder_url
            inputs.append({"id": slot_id, "type": slot_type, "value": url})
    print(f"\n  Sending {len(inputs)} inputs in technique-defined order")
    # End of input build — submission happens below

    # Submit run with auto-retry-on-moderation:
    # If FLORA returns GENERATION_PROMPT_MODERATED, progressively drop character refs:
    #   attempt 1: all detected refs
    #   attempt 2: drop character-reference-1 (most-likely human-likeness photoreal)
    #   attempt 3: drop ALL character refs (1-4)
    H = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def submit_and_poll(inputs):
        """Returns the completed run dict, or raises with the failure payload."""
        r = requests.post(
            f"{FLORA_BASE}/api/v1/techniques/{args.technique}/runs",
            headers=H, json={"inputs": inputs, "mode": "async"}, timeout=60,
        )
        if r.status_code not in (200, 201, 202):
            return {"_submit_error": True, "status_code": r.status_code, "body": r.text}
        run = r.json()
        run_id = run.get("runId") or run.get("id")
        if not run_id:
            return {"_submit_error": True, "no_run_id": True, "body": run}
        poll_url = f"{FLORA_BASE}/api/v1/techniques/{args.technique}/runs/{run_id}"
        last_status = None
        t_start = time.time()
        while True:
            time.sleep(15)
            pr = requests.get(poll_url, headers=H, timeout=30)
            if pr.status_code != 200:
                continue
            rj = pr.json()
            status = rj.get("status")
            if status != last_status:
                print(f"    [{int(time.time()-t_start)}s] {status}")
                last_status = status
            if status in ("completed", "succeeded", "success"):
                return rj
            if status in ("failed", "error", "cancelled"):
                return rj  # caller inspects errorCode
            if time.time() - t_start > 1500:
                return {"_timeout": True, "last_status": status}

    def rebuild_inputs(refs_dict):
        out = []
        for slot_def in tdef.get("inputs", []):
            sid, stype = slot_def["id"], slot_def["type"]
            if stype == "text":
                out.append({"id": sid, "type": "text", "value": text_prompt})
            else:
                url = refs_dict[sid][1] if sid in refs_dict else placeholder_url
                out.append({"id": sid, "type": stype, "value": url})
        return out

    # Attempt 1: as-detected
    print(f"\n  Submitting run to FLORA (attempt 1, full refs)...")
    t0 = time.time()
    rj = submit_and_poll(inputs)
    err = rj.get("errorCode") if isinstance(rj, dict) else None

    # Attempt 2: SWAP photoreal storyboard for pencil version (most likely fix —
    # OpenAI moderation usually trips on photoreal face content in the storyboard).
    # Keep all other refs intact.
    if err == "GENERATION_PROMPT_MODERATED" and pencil_storyboard_url:
        print(f"  ⚠ moderation hit — retrying with PENCIL storyboard (swapping photoreal for pencil version)")
        retry_refs = dict(refs)
        retry_refs["storyboard"] = ("storyboard", pencil_storyboard_url)
        refs = retry_refs  # PERSIST pencil swap for all subsequent attempts
        inputs = rebuild_inputs(refs)
        rj = submit_and_poll(inputs)
        err = rj.get("errorCode") if isinstance(rj, dict) else None

    # Attempt 3: drop char-ref-1 if still moderated (with pencil storyboard from now on)
    if err == "GENERATION_PROMPT_MODERATED":
        print(f"  ⚠ moderation hit — retrying without character-reference-1")
        retry_refs = {k: v for k, v in refs.items() if k != "character-reference-1"}
        inputs = rebuild_inputs(retry_refs)
        rj = submit_and_poll(inputs)
        err = rj.get("errorCode") if isinstance(rj, dict) else None

    # Attempt 3: drop ALL character refs if still moderated
    if err == "GENERATION_PROMPT_MODERATED":
        print(f"  ⚠ moderation again — retrying without ANY character refs")
        retry_refs = {k: v for k, v in refs.items() if not k.startswith("character-reference-")}
        inputs = rebuild_inputs(retry_refs)
        rj = submit_and_poll(inputs)
        err = rj.get("errorCode") if isinstance(rj, dict) else None

    # Attempt 4: also drop costume + location refs (likeness might be in those)
    if err == "GENERATION_PROMPT_MODERATED":
        print(f"  ⚠ moderation again — retrying without costume/location refs (chars already dropped)")
        retry_refs = {k: v for k, v in refs.items()
                      if not k.startswith("character-reference-")
                      and not k.startswith("costume-")
                      and not k.startswith("location-")}
        inputs = rebuild_inputs(retry_refs)
        rj = submit_and_poll(inputs)
        err = rj.get("errorCode") if isinstance(rj, dict) else None

    # Attempt 5: drop EVERYTHING except storyboard (last resort — text + storyboard only)
    if err == "GENERATION_PROMPT_MODERATED":
        print(f"  ⚠ moderation persists — retrying with ONLY the storyboard ref (no chars/costume/location)")
        retry_refs = {k: v for k, v in refs.items() if k == "storyboard"}
        inputs = rebuild_inputs(retry_refs)
        rj = submit_and_poll(inputs)
        err = rj.get("errorCode") if isinstance(rj, dict) else None

    if err or rj.get("status") not in ("completed", "succeeded", "success"):
        print(f"\n  ✗ FLORA run failed: {json.dumps(rj, indent=2)[:1000]}")
        raise SystemExit("FLORA run failed after retries")

    # Find the output URL — look for "khensu-sequence" or any videoUrl output
    outputs = rj.get("outputs") or rj.get("results") or []
    video_url = None
    if isinstance(outputs, list):
        for o in outputs:
            if o.get("type") in ("videoUrl", "video"):
                video_url = o.get("value") or o.get("url")
                break
    elif isinstance(outputs, dict):
        for k, v in outputs.items():
            if isinstance(v, dict) and v.get("type") in ("videoUrl", "video"):
                video_url = v.get("value") or v.get("url")
                break
            elif isinstance(v, str) and v.startswith("http"):
                video_url = v
                break
    if not video_url:
        print(f"  full response: {json.dumps(rj, indent=2)[:2000]}")
        raise SystemExit("No video URL in completed run output")

    print(f"  video URL: {video_url}")

    # Download + upload to Drive
    vd = requests.get(video_url, timeout=300); vd.raise_for_status()
    print(f"  downloaded {len(vd.content)//1024}KB")

    # Find videos/set-NN/ folder
    storyboard_folder_id = folder_id_from_url(folder_url)
    if not storyboard_folder_id:
        raise SystemExit(f"No storyboard folder for set {set_num}")
    # storyboards/set-NN/ → ../../videos/set-NN/
    sb_folder_meta = drive.files().get(fileId=storyboard_folder_id, fields="name,parents").execute()
    storyboards_parent = sb_folder_meta["parents"][0]
    show_folder_meta = drive.files().get(fileId=storyboards_parent, fields="parents").execute()
    show_folder_id = show_folder_meta["parents"][0]
    # Find videos/ subfolder
    videos_root = drive.files().list(
        q=f"'{show_folder_id}' in parents and trashed=false and name='videos' and mimeType='application/vnd.google-apps.folder'",
        fields="files(id)", pageSize=5,
    ).execute()
    if not videos_root.get("files"):
        raise SystemExit("No videos/ folder under show folder")
    videos_root_id = videos_root["files"][0]["id"]
    set_folder_name = f"set-{int(set_num):02d}"
    set_folder = drive.files().list(
        q=f"'{videos_root_id}' in parents and trashed=false and name='{set_folder_name}'",
        fields="files(id)", pageSize=5,
    ).execute()
    if not set_folder.get("files"):
        raise SystemExit(f"No videos/{set_folder_name}/ folder")
    set_folder_id = set_folder["files"][0]["id"]

    fname = f"video-iteration-{args.slot}-flora-sd2-15s.mp4"
    # Archive any existing same-name file (don't trash). Move to archive/
    # subfolder with timestamp prefix so prior takes are recoverable.
    import datetime as _dt
    res = drive.files().list(
        q=f"'{set_folder_id}' in parents and trashed=false and name='{fname}'",
        fields="files(id, name)", pageSize=10,
    ).execute()
    existing = res.get("files", [])
    if existing:
        arch_q = (
            f"'{set_folder_id}' in parents and trashed=false "
            f"and name='archive' "
            f"and mimeType='application/vnd.google-apps.folder'"
        )
        arch_res = drive.files().list(q=arch_q, fields="files(id)", pageSize=1).execute()
        if arch_res.get("files"):
            archive_folder_id = arch_res["files"][0]["id"]
        else:
            archive_folder = drive.files().create(
                body={
                    "name": "archive",
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [set_folder_id],
                },
                fields="id",
            ).execute()
            archive_folder_id = archive_folder["id"]
            try:
                drive.permissions().create(
                    fileId=archive_folder_id,
                    body={"role": "reader", "type": "anyone"},
                    fields="id",
                ).execute()
            except Exception:
                pass
            print(f"  ✦ created archive/ subfolder in videos/set-{int(set_num):02d}/")
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        for f in existing:
            new_name = f"{ts}_{f['name']}"
            drive.files().update(
                fileId=f["id"],
                addParents=archive_folder_id,
                removeParents=set_folder_id,
                body={"name": new_name},
                fields="id, parents",
            ).execute()
            print(f"  ✦ archived prior: {f['name']} → archive/{new_name}")
    media = MediaIoBaseUpload(io.BytesIO(vd.content), mimetype="video/mp4", resumable=False)
    f = drive.files().create(
        body={"name": fname, "parents": [set_folder_id]},
        media_body=media, fields="id,webViewLink",
    ).execute()
    drive.permissions().create(fileId=f["id"], body={"role":"reader","type":"anyone"}, fields="id").execute()
    print(f"\n  ✓ uploaded → {f['webViewLink']}")

    # Write to L / M / N / O based on slot
    SLOT_TO_COL = {1: "L", 2: "M", 3: "N", 4: "O"}
    target_col = SLOT_TO_COL[args.slot]
    sb.update(range_name=f"{target_col}{sheet_row}", values=[[f["webViewLink"]]], value_input_option="USER_ENTERED")
    print(f"  ✓ wrote to Storyboard Prompts!{target_col}{sheet_row}")


if __name__ == "__main__":
    main()

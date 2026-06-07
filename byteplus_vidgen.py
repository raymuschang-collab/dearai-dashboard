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
  9. Save local MP4 copy to ~/Desktop/<Project> Generated Videos/
 10. Write URL to Storyboard Prompts!M (slot 1) or N (slot 2)
 11. --confirm gate prints refs + waits [y/N] before submit (anti ref-bleed)
 12. Append usage to .byteplus_expense.json (cumulative spend tally)

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
        os.path.expanduser("~/Documents/Shotlist Workflows/auth.py"),
    ]
    for c in candidates:
        if os.path.exists(c):
            sys.path.insert(0, os.path.dirname(c))
            from auth import get_credentials  # type: ignore
            return get_credentials
    raise SystemExit("Could not find auth.py")

_get_credentials_fn = None


def get_credentials():
    """Lazy Google auth resolver for dashboard-fired vidgen jobs.

    auth.py raises SystemExit for CLI setup errors. Keep that from becoming an
    import/page-load failure, and surface missing/malformed GOOGLE_SVC_ACCOUNT_JSON
    or GOOGLE_USER_TOKEN_JSON as a normal job error instead.
    """
    global _get_credentials_fn
    if _get_credentials_fn is None:
        try:
            _get_credentials_fn = _resolve_auth()
        except SystemExit as e:
            raise RuntimeError(f"Google credentials unavailable: {e}") from None
    try:
        return _get_credentials_fn()
    except SystemExit as e:
        raise RuntimeError(f"Google credentials unavailable: {e}") from None

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

# Pending-task ledger for crash recovery. byteplus_vidgen.py writes a row
# here the moment BytePlus accepts a task_id (BEFORE the multi-minute
# download / Drive / sheet-write pipeline). If the subprocess dies after
# this point — Render redeploy, gunicorn worker bounce, OOM — the entry
# survives and `byteplus_vidgen_resume.py` can pick it up later, query
# BytePlus for the result, and complete the writeback.
#
# Schema: {"pending": [{task_id, sheet, set, slot, duration, resolution,
#   aspect, fast, submitted_at, status}, ...]}
# Status flow: submitted → done (entry removed). If terminal failure on
# resume, status is set to "failed" and entry is removed after logging.
PENDING_LOG = HERE / ".byteplus_pending.json"

# Cache for video-asset durations (probed once, reused forever). Keyed by
# asset_code if available, else source_url. Values are float seconds, or
# null when probing failed (we still cache the null so we don't re-probe
# every run — clear the cache file to retry).
DURATION_CACHE = HERE / ".byteplus_asset_durations.json"

# BytePlus rejects vidgen submissions when the SUM of video_url ref
# durations exceeds 15s. We use 14.9s as a soft cap — tiny rounding
# buffer for ffprobe drift while still allowing two 7s face refs to
# co-exist (14.0 + 7.0 + 7.0 was rejecting both for the sake of 0.1s).
VIDEO_BUDGET_SECONDS = 14.9
# Conservative fallback when ffprobe can't read a URL — most refs we've
# uploaded are 4.9s shorts, but anything legacy can be longer. Treat
# unknowns as 5s so the enforcer still keeps trimming when it has to.
VIDEO_UNKNOWN_FALLBACK = 5.0


def _load_duration_cache() -> dict:
    if DURATION_CACHE.exists():
        try:
            return json.loads(DURATION_CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save_duration_cache(cache: dict):
    try:
        DURATION_CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True))
    except Exception as e:
        print(f"  ⚠ couldn't persist duration cache: {e}")


def _drive_direct_download(url: str) -> str:
    """Convert a Drive /file/d/ID/view URL into the uc?export=download form
    that ffprobe can stream from. Pass through other URLs unchanged."""
    if not url:
        return url
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m and "drive.google.com" in url:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url


def _probe_video_duration(url: str, timeout: int = 30) -> float | None:
    """Probe a video URL with ffprobe. Returns float seconds or None on any
    failure (missing ffprobe, network error, non-video URL, etc.)."""
    if not url:
        return None
    import shutil
    import subprocess
    if not shutil.which("ffprobe"):
        return None
    probe_url = _drive_direct_download(url)
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             probe_url],
            capture_output=True, text=True, timeout=timeout,
        )
        s = (proc.stdout or "").strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def get_asset_duration(asset_code: str, source_url: str) -> float | None:
    """Cached duration lookup. Returns seconds or None when unknown.
    Probes ffprobe against source_url on cache miss; caches the result
    (including misses, so we don't re-probe every run)."""
    cache = _load_duration_cache()
    key = (asset_code or source_url or "").strip()
    if not key:
        return None
    if key in cache:
        v = cache.get(key)
        return float(v) if v is not None else None
    dur = _probe_video_duration(source_url) if source_url else None
    cache[key] = dur  # may be None
    _save_duration_cache(cache)
    return dur


def enforce_video_budget(ref_urls: list[dict],
                         max_seconds: float = VIDEO_BUDGET_SECONDS) -> list[dict]:
    """BytePlus enforces a hard 15s cap on the SUM of all video_url ref
    durations. When the cumulative budget would be exceeded, drop video
    refs from the END of the list (lowest priority — characters are added
    first, locations last) until we fit under `max_seconds`.

    Each video entry should carry an `_duration` field (set by the caller).
    Unknown durations fall back to VIDEO_UNKNOWN_FALLBACK so the enforcer
    still trims aggressively when probing fails."""
    def _dur(ru: dict) -> float:
        d = ru.get("_duration")
        if d is None:
            return VIDEO_UNKNOWN_FALLBACK
        return float(d)

    total = sum(_dur(ru) for ru in ref_urls if ru.get("type") == "video")
    if total <= max_seconds:
        return ref_urls

    print(f"  ⚠ cumulative video-ref duration {total:.1f}s exceeds "
          f"{max_seconds:.1f}s budget — dropping longest first")
    out = list(ref_urls)
    # Drop the LONGEST video ref first. This protects legitimate short
    # refs (4-5s face loops) from being killed by one rogue 30s+ video,
    # which is what happens when "drop from end" hits a list with one
    # giant ref hidden in it.
    while total > max_seconds:
        # Find the index of the longest video ref currently in the list
        longest_ix = -1
        longest_d = -1.0
        for i, ru in enumerate(out):
            if ru.get("type") != "video":
                continue
            d = _dur(ru)
            if d > longest_d:
                longest_d = d
                longest_ix = i
        if longest_ix < 0:
            # No more video refs but total still over budget —
            # impossible unless _duration was negative; bail.
            break
        url = (out[longest_ix].get("url") or "")[:60]
        ellipsis = "…" if len(out[longest_ix].get("url", "")) > 60 else ""
        print(f"    drop {url}{ellipsis} ({longest_d:.1f}s)")
        out.pop(longest_ix)
        total -= longest_d
    print(f"  ✓ post-trim cumulative video-ref duration: {total:.1f}s "
          f"({sum(1 for r in out if r.get('type')=='video')} video refs kept)")
    return out


def _load_pending() -> dict:
    if not PENDING_LOG.exists():
        return {"pending": []}
    try:
        d = json.loads(PENDING_LOG.read_text())
        if not isinstance(d, dict) or "pending" not in d:
            return {"pending": []}
        return d
    except Exception:
        return {"pending": []}


def _save_pending(data: dict):
    try:
        PENDING_LOG.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print(f"  ⚠ couldn't persist pending log: {e}")


def persist_pending(task_id: str, sheet_id: str, set_num: int, slot: int,
                    duration: int, resolution: str, aspect: str,
                    fast: bool):
    """Record a freshly-submitted BytePlus task so it survives subprocess
    death between submit and writeback. Idempotent: re-running with the
    same task_id replaces the prior entry."""
    data = _load_pending()
    data["pending"] = [e for e in data["pending"]
                        if e.get("task_id") != task_id]
    data["pending"].append({
        "task_id": task_id,
        "sheet": sheet_id,
        "set": set_num,
        "slot": slot,
        "duration": duration,
        "resolution": resolution,
        "aspect": aspect,
        "fast": fast,
        "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "submitted",
    })
    _save_pending(data)


def remove_pending(task_id: str):
    """Mark a task as complete by dropping its entry from the ledger.
    Called from main() after the sheet write succeeds — if the script
    dies before this, the entry persists and resume picks it up."""
    data = _load_pending()
    before = len(data["pending"])
    data["pending"] = [e for e in data["pending"]
                        if e.get("task_id") != task_id]
    if len(data["pending"]) != before:
        _save_pending(data)


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


def _owner_matches_body(owner: str, body: str) -> bool:
    """Does an owner-character name (e.g. "Min-jun", "Park Min-jun") appear
    in the body? Uses the same word-extraction logic CHARACTERS rows use:
    any word ≥4 chars from the owner string is searched as a whole-word
    case-insensitive match. Returns True on first hit."""
    if not owner:
        return False
    for word in re.findall(r"[A-Za-z][\w\-]+", owner):
        if len(word) >= 4 and re.search(
                r"\b" + re.escape(word) + r"\b", body, re.IGNORECASE):
            return True
    return False


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
      4. COSTUME / PROPS — owner-character auto-attach: when the entry's
         name carries a parenthetical owner (e.g. "Sous chef whites
         (Min-jun)"), the row matches whenever that owner-character
         appears in the body. Same word-extraction logic as CHARACTERS.
         Bibles can also be matched by substring on the parenthetical-
         stripped name (e.g. body says "bibimbap" → matches PROPS row
         "Bibimbap bowl").
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
    #
    # Drive-URL fallback: when a row has no asset_code (BytePlus upload
    # failed or hasn't run yet), fall back to source_url. The downstream
    # ref-builder at line ~491 already has the per-row fallback logic;
    # we just need to NOT pre-filter such rows out here.
    seen_codes = set()           # dedup keys for rows WITH asset_code
    seen_fallback = set()        # dedup keys for rows WITHOUT asset_code
                                 #   (name, type, source_url)
    loc_aliases = _build_location_aliases(sh)

    for r in rows:
        if not r or not r[0].strip(): continue
        name = r[0].strip()
        bible_tab = r[1].strip() if len(r) > 1 else ""
        asset_code = r[2].strip() if len(r) > 2 else ""
        source_url = r[3].strip() if len(r) > 3 else ""
        asset_type = r[4].strip().lower() if len(r) > 4 else ""
        status = r[5].strip() if len(r) > 5 else ""
        # Hard skip: explicitly retired rows (we mark old/orphan refs as
        # "Replaced" so the lookup ignores them) and rows with no usable URL.
        if status.lower() == "replaced":
            continue
        if not asset_code and not source_url:
            continue
        # Dedup
        if asset_code:
            if asset_code in seen_codes: continue
        else:
            fb_key = (name, asset_type, source_url)
            if fb_key in seen_fallback: continue

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
        # 4a. COSTUME / PROPS — owner-character auto-attach.
        #     Pattern: entry name carries "(Owner-name)" parenthetical
        #     (e.g. "Sous chef whites (Min-jun)"). When the owner appears
        #     in the body (whole-word match on any ≥4-char part), the
        #     attire / prop attaches automatically. Lets the team write
        #     character-anchored bibles without listing wardrobe in every
        #     prompt.
        if not matched and bible_tab in ("COSTUME", "PROPS"):
            owner_match = re.search(r"\(([^)]+)\)", name)
            if owner_match and _owner_matches_body(owner_match.group(1), body):
                matched = True
        # 4b. COSTUME / PROPS — substring fallback on the cleaned name.
        #     Strip parenthetical first ("Bibimbap bowl (kitchen)" →
        #     "Bibimbap bowl"), then look for that substring in the body
        #     case-insensitively. Multi-word phrases match as substrings
        #     ("salted fish" matches "salted fish stand").
        if not matched and bible_tab in ("COSTUME", "PROPS", "EFFECTS"):
            cleaned = re.sub(r"\s*\([^)]+\)", "", name).strip().lower()
            if cleaned and len(cleaned) >= 4 and cleaned in body_lc:
                matched = True

        if matched:
            if asset_code:
                seen_codes.add(asset_code)
            else:
                seen_fallback.add((name, asset_type, source_url))
            detected.append({
                "name": name,
                "bible_tab": bible_tab,
                "asset_code": asset_code,
                "source_url": source_url,
                "asset_type": asset_type,  # "image" / "video" — vidgen uses for role
            })
    # Group refs so all of one character's assets are bunched together.
    # Sort key:
    #   1. bible_tab order: CHARACTERS first (identity), then COSTUME
    #      (attire — matters more than background for character consistency),
    #      then LOCATIONS, PROPS, EFFECTS. When the MAX_REFS cap forces a
    #      drop, attire survives over scenery.
    #   2. within CHARACTERS: by name (alphabetical, deterministic).
    #   3. within same name: image (locks attire/hair) → video (locks face)
    #      → audio (locks voice). Same intra-character order every time so the
    #      prompt's binding numbers (#2, #3, …) stay consistent set-to-set.
    _BIBLE_ORDER = {"CHARACTERS": 0, "COSTUME": 1, "LOCATIONS": 2,
                     "PROPS": 3, "EFFECTS": 4}
    _MEDIA_ORDER = {"image": 0, "video": 1, "audio": 2, "voice": 2}
    detected.sort(key=lambda r: (
        _BIBLE_ORDER.get(r["bible_tab"], 99),
        r["name"].lower(),
        _MEDIA_ORDER.get((r.get("asset_type") or "").lower(), 99),
    ))
    return detected


def resolve_mentioned_refs(tokens: list[str], sh) -> list[dict]:
    """
    Resolve explicit @name tokens against Asset Library rows.
    Only includes rows where Status='Uploaded' and Asset Code is set.
    Matching is case-insensitive substring against Name.
    """
    try:
        ws = sh.worksheet("Asset Library")
    except Exception:
        print(f"  ⚠ no 'Asset Library' tab — refs cannot be resolved to asset codes")
        return []

    rows = ws.get("A5:L500", value_render_option="FORMATTED_VALUE")
    refs = []
    seen_codes = set()
    for raw in tokens:
        token = (raw or "").strip().lstrip("@")
        if not token:
            continue
        token_lc = token.lower()
        matches = []
        for r in rows:
            if not r or not r[0].strip():
                continue
            name = r[0].strip()
            bible_tab = r[1].strip() if len(r) > 1 else ""
            asset_code = r[2].strip() if len(r) > 2 else ""
            source_url = r[3].strip() if len(r) > 3 else ""
            asset_type = r[4].strip().lower() if len(r) > 4 else ""
            status = r[5].strip() if len(r) > 5 else ""
            if status.lower() != "uploaded" or not asset_code:
                continue
            if token_lc not in name.lower():
                continue
            if asset_code in seen_codes:
                continue
            seen_codes.add(asset_code)
            matches.append({
                "name": name,
                "bible_tab": bible_tab,
                "asset_code": asset_code,
                "source_url": source_url,
                "asset_type": asset_type,
            })
        if not matches:
            print(f"  ⚠ @{token} not found in Asset Library — skipped")
        refs.extend(matches)
    return refs


def detect_shotlist_tab(sh) -> str | None:
    non_shotlist = {"Storyboard Prompts", "Video Prompts", "CHARACTERS", "LOCATIONS",
                    "PROPS", "COSTUME", "EFFECTS", "README", "_README",
                    "Asset Library"}
    for ws in sh.worksheets():
        if ws.title.startswith("_"):
            continue  # skip reserved tabs (_README, _GalleryConfig, etc.)
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

    # Read the actual shot range for this set from Storyboard Prompts!B{row}.
    # SP rows: row 11 = set 1, row 10+N = set N. Col B holds the range string
    # ("1-3", "4-8", etc.) that user controls. Falls back to hardcoded
    # (set-1)*5+1..set*5 if the SP row's range is empty/malformed.
    first_shot, last_shot = (set_num - 1) * 5 + 1, set_num * 5
    try:
        sp_ws = sh.worksheet("Storyboard Prompts")
        sp_row = 10 + set_num
        rng = (sp_ws.acell(f"B{sp_row}").value or "").strip()
        import re as _re
        m = _re.match(r"^\s*(\d+)\s*[-–—]\s*(\d+)\s*$", rng)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b:
                first_shot, last_shot = a, b
        elif rng.isdigit():
            first_shot = last_shot = int(rng)
    except Exception:
        pass

    shot_payloads = []
    try:
        shotlist_tab = detect_shotlist_tab(sh) or "Shotlist"
        sl_ws = sh.worksheet(shotlist_tab)
        sl_rows = sl_ws.get("A2:R200", value_render_option="FORMATTED_VALUE")
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
    #  - cap at 8 refs total — leaves room for storyboard + 3 chars'
    #    face/voice + 2 attire/location refs after the face/attire split
    #    rewire. Original cap of 6 was tight enough that COSTUME refs
    #    fell off the end. Order is preserved by detect_bible_refs() sort
    #    (CHARACTERS → COSTUME → LOCATIONS → PROPS → EFFECTS) so most-
    #    specific anchors get priority slots when the cap bites.
    MAX_REFS = 8
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
        rtype = ref.get("type", "")
        if rtype == "video":
            content.append({"type": "video_url",
                            "video_url": {"url": url},
                            "role": "reference_video"})
        elif rtype == "audio":
            # Voice ref — Seedance/Dreamina clones this voice for any
            # dialogue spoken by the bound character (binding established
            # in the prompt's Reference identities block).
            content.append({"type": "audio_url",
                            "audio_url": {"url": url},
                            "role": "reference_audio"})
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
    # Default 480p — every gallery V1/V2 button uses this default for the
    # POC-iteration cost band. Flag remains overrideable for ad-hoc CLI runs
    # (e.g. --resolution 1080p for client deliverables). Cost ratio:
    # 480p = $0.05/s, 720p = $0.08/s, 1080p = $0.132/s (1080p is ~2.6× more
    # expensive). Producers iterate at 480p, approve, then re-run a single
    # set at 1080p just before final delivery.
    ap.add_argument("--resolution", default="480p", choices=["480p","720p","1080p","2K"],
                    help="480p is the default; use 720p/1080p for hero deliverables")
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--mentions", nargs="+", default=None,
                    help="Explicit @name tokens to use as refs instead of auto-detecting from body")
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
    # codes (face-moderation-bypass). Explicit --mentions overrides body
    # auto-detect and resolves only the requested @name tokens.
    mention_tokens = [m for m in (args.mentions or []) if m.strip()]
    if mention_tokens:
        refs = resolve_mentioned_refs(mention_tokens, sh)
        print(f"Refs: explicit ({len(mention_tokens)} mentions)")
    else:
        refs = detect_bible_refs(body, sh)
        print(f"Refs: auto-detect ({len(refs)} found)")
    # Sort so CHARACTERS (identity) come before LOCATIONS (background) —
    # when the 6-ref cap kicks in we want to keep identity refs over scenery.
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
        # Asset Library!E carries a CATEGORY ("character"/"scene"/"video"/
        # "voice"/"audio"/...). Map it to the actual MEDIA type Seedance
        # expects in content[]: video / audio / image (default).
        if asset_type == "video" or url.lower().endswith((".mp4", ".mov", ".webm")):
            media = "video"
        elif asset_type in ("audio", "voice") or url.lower().endswith((".mp3", ".wav", ".m4a")):
            media = "audio"
        else:
            media = "image"
        entry = {
            "type": media,
            "url": url,
            "role": {"video": "reference_video",
                     "audio": "reference_audio",
                     "image": "reference_image"}[media],
        }
        # For video refs, attach the probed duration so the cumulative
        # 15s budget enforcer below can decide what to keep / drop.
        # source_url (Drive) is the only thing we can ffprobe — asset://
        # codes are opaque to ffprobe.
        if media == "video":
            dur = get_asset_duration(asset_code, source_url)
            entry["_duration"] = dur
            print(f"    duration: {dur:.1f}s" if dur is not None
                  else f"    duration: unknown (fallback {VIDEO_UNKNOWN_FALLBACK:.1f}s)")
        ref_urls.append(entry)

    # Enforce BytePlus's hard 15s cumulative video-ref cap. Drops video
    # refs from the end of the list until the sum fits under the soft cap
    # (14s, leaves 1s clock-drift margin). Image / audio refs are not
    # affected — only video_url entries count toward the budget.
    ref_urls = enforce_video_budget(ref_urls)

    # Build prompt
    # Composition directive — sits below the camera global so Seedance sees
    # the storyboard as the canonical layout anchor BEFORE the per-shot body.
    sb_directive = ("Follow the storyboard reference for composition, framing, "
                    "and blocking on every shot." if sb_url else "")

    # Reference-identity binding — split-role design.
    #
    # When a character has BOTH a still image AND a video face-loop in
    # the Asset Library, Seedance gets conflicting signals and faces
    # flicker. New rule: video defines FACE/identity, image defines
    # ATTIRE/wardrobe. To avoid double-anchoring the same character,
    # we DROP the character's own still image when their video exists
    # (the video already carries the appearance signal); image slots
    # then fill with COSTUME / LOCATION / PROPS / EFFECTS bible refs
    # which are about clothes/sets/objects, not identity.
    #
    # Format:  #N MEDIA: NAME — ROLE (short hint)
    # Examples:
    #   #1 image: STORYBOARD — composition anchor (camera, blocking, depth)
    #   #2 video: PARK MIN-JUN — FACE (sous chef / antagonist)
    #   #3 audio: PARK MIN-JUN — VOICE
    #   #4 image: Sous chef whites (Min-jun) — ATTIRE (worn by Min-jun)
    #   #5 image: Hanbyeol Bistro Kitchen — LOCATION (background)

    # Build a "has video" map per character, then drop redundant char-image
    # rows. Asset Library!E may store either a media type ('Video'/'Image'/
    # 'Audio') or a category label ('character'/'costume'/'scene'/...). We
    # resolve to the actual MEDIA TYPE the same way the existing code does
    # (URL extension fallback, audio/voice synonym, default=image) so the
    # filter doesn't mis-classify rows tagged with a category.
    def _resolve_media(rec):
        atype = (rec.get("asset_type") or "").lower()
        url_l = (rec.get("source_url") or "").lower()
        if atype == "video" or url_l.endswith((".mp4", ".mov", ".webm")):
            return "video"
        if atype in ("audio", "voice") or url_l.endswith((".mp3", ".wav", ".m4a")):
            return "audio"
        return "image"

    char_has_video = {r.get("name", "") for r in refs
                       if r.get("bible_tab") == "CHARACTERS"
                       and _resolve_media(r) == "video"}
    filtered_refs = []
    for r in refs:
        if (r.get("bible_tab") == "CHARACTERS"
                and _resolve_media(r) == "image"
                and r.get("name") in char_has_video):
            print(f"  ⤳ skipping char-image {r['name']} (video face-loop already attached)")
            continue
        filtered_refs.append(r)

    max_bible_refs = 5 if sb_url else 6
    if len(filtered_refs) > max_bible_refs:
        print(f"  ⚠ ref cap: keeping {max_bible_refs} bible refs "
              f"({'storyboard + ' if sb_url else ''}max 6 total)")
        filtered_refs = filtered_refs[:max_bible_refs]

    # Rebuild ref_urls in the new filtered order. The storyboard slot
    # (always at index 0 if present) is preserved; bible refs are
    # rebuilt cleanly so the budget enforcer + identity binding both
    # see the same trimmed list.
    new_ref_urls = [ref_urls[0]] if sb_url and ref_urls else []
    for r in filtered_refs:
        asset_code = (r.get("asset_code") or "").strip()
        source_url = (r.get("source_url") or "").strip()
        atype = (r.get("asset_type") or "").lower()
        if asset_code:
            url = (asset_code if asset_code.startswith("asset://")
                   else f"asset://{asset_code}")
        elif source_url:
            url = source_url
        else:
            continue
        if atype == "video" or url.lower().endswith((".mp4", ".mov", ".webm")):
            media = "video"
        elif atype in ("audio", "voice") or url.lower().endswith((".mp3", ".wav", ".m4a")):
            media = "audio"
        else:
            media = "image"
        entry = {
            "type": media, "url": url,
            "role": {"video": "reference_video",
                     "audio": "reference_audio",
                     "image": "reference_image"}[media],
        }
        if media == "video":
            entry["_duration"] = get_asset_duration(asset_code, source_url)
        new_ref_urls.append(entry)
    ref_urls = enforce_video_budget(new_ref_urls)
    refs = filtered_refs

    id_binding_lines = []
    if ref_urls:
        try:
            char_rows = sh.worksheet("CHARACTERS").get_all_records()
            char_by_name = {r.get("Name", "").strip(): r for r in char_rows
                             if r.get("Name")}
        except Exception:
            char_by_name = {}
        ref_ix = 1
        if sb_url:
            id_binding_lines.append(
                f"#{ref_ix} image: STORYBOARD — composition anchor (camera, blocking, depth)")
            ref_ix += 1
        for r in refs:
            name = r.get("name", "")
            tab = r.get("bible_tab", "")
            atype = (r.get("asset_type") or "").lower()
            if atype == "video":
                media = "video"
            elif atype in ("audio", "voice"):
                media = "audio"
            else:
                media = "image"

            if tab == "CHARACTERS":
                bible_row = char_by_name.get(name, {})
                role = (bible_row.get("Role / Archetype")
                         or bible_row.get("Role", "") or "").strip()
                role_hint = f" ({role.lower()})" if role else ""
                if media == "video":
                    id_binding_lines.append(
                        f"#{ref_ix} video: {name} — FACE{role_hint}")
                elif media == "audio":
                    id_binding_lines.append(
                        f"#{ref_ix} audio: {name} — VOICE (use for all {name} dialogue)")
                else:  # image — only when char has no video (fallback)
                    id_binding_lines.append(
                        f"#{ref_ix} image: {name} — IDENTITY{role_hint} (no video face-loop available)")
            elif tab == "COSTUME":
                # Attire anchor. If the bible name is "Sous chef whites (Min-jun)",
                # extract the parenthetical character ref so the prompt says
                # "worn by Min-jun" — links the attire to a specific character.
                worn_by = ""
                m = re.search(r"\(([^)]+)\)", name)
                if m:
                    worn_by = f" (worn by {m.group(1).strip()})"
                clean_name = re.sub(r"\s*\([^)]+\)", "", name).strip()
                id_binding_lines.append(
                    f"#{ref_ix} {media}: {clean_name} — ATTIRE{worn_by}")
            elif tab == "LOCATIONS":
                id_binding_lines.append(
                    f"#{ref_ix} {media}: {name} — LOCATION (background)")
            elif tab == "PROPS":
                id_binding_lines.append(f"#{ref_ix} {media}: {name} — PROP")
            elif tab == "EFFECTS":
                id_binding_lines.append(f"#{ref_ix} {media}: {name} — FX")
            else:
                id_binding_lines.append(
                    f"#{ref_ix} {media}: {name} ({tab[:4]})")
            ref_ix += 1
    id_binding = ("Reference identities (numbers match content[] order):\n"
                   + "\n".join(id_binding_lines)
                   if id_binding_lines else "")

    realism = ("Documentary editorial photography aesthetic, natural skin texture, "
               "Kodak Portra 400 color science, no airbrushing, no game-engine rendering. "
               "Subtle film grain. Muted desaturated palette. Natural lighting only.")
    format_directive = f"VERTICAL {args.aspect} drama format. The video should follow these shots in sequence:"
    prompt = "\n".join([s for s in [
        global_camera, sb_directive, id_binding,
        global_audio, global_setting,
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

    # CRITICAL — persist task_id before any long-running step so a
    # subprocess death between here and the sheet write doesn't lose
    # the work. byteplus_vidgen_resume.py will pick this up next run.
    persist_pending(task_id, sheet_id, args.set_num, args.slot,
                     args.duration, args.resolution, args.aspect, args.fast)

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

    project_name = sh.title
    local_folder = os.path.expanduser(f"~/Desktop/{project_name} Generated Videos/")
    os.makedirs(local_folder, exist_ok=True)
    local_filename = f"set-{args.set_num:02d}-iter-{args.slot}-{args.resolution}-{args.duration}s.mp4"
    local_path = os.path.join(local_folder, local_filename)
    with open(local_path, "wb") as f:
        f.write(mp4)
    print(f"✓ Local copy: {local_path}")

    # Write URL to Storyboard Prompts M or N
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

    # All writeback steps survived → the task is fully persisted, can
    # remove its entry from the pending ledger.
    remove_pending(task_id)

    print(f"\n=== DONE — Set {args.set_num} slot {args.slot} ===")


if __name__ == "__main__":
    main()

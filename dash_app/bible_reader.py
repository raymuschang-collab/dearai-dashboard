"""Bible + storyboard data readers for the Dash UI.
Mirrors the read patterns from production-gallery/build_gallery.py."""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def drive_id(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def thumb(file_id: str | None, w: int = 800) -> str:
    if not file_id:
        return ""
    return f"https://lh3.googleusercontent.com/d/{file_id}=w{w}"


def view(file_id: str | None) -> str:
    if not file_id:
        return ""
    return f"https://drive.google.com/file/d/{file_id}/view"


def download_url(file_id: str | None) -> str:
    """Direct Drive download URL — triggers browser download."""
    if not file_id:
        return ""
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def preview(file_id: str | None) -> str:
    """Embeddable Drive preview URL — works as <iframe src> for inline
    HTML5 playback (Drive's built-in player) of videos and PDFs."""
    if not file_id:
        return ""
    return f"https://drive.google.com/file/d/{file_id}/preview"


def _gspread():
    import warnings; warnings.filterwarnings("ignore")
    import gspread
    from auth import get_credentials
    return gspread.authorize(get_credentials())


def open_sheet(sheet_id: str):
    return _gspread().open_by_key(sheet_id)


def detect_shotlist_tab(sh) -> str | None:
    bible_tabs = {"Storyboard Prompts", "Video Prompts", "CHARACTERS", "LOCATIONS",
                  "PROPS", "COSTUME", "EFFECTS", "README", "Asset Library"}
    for w in sh.worksheets():
        if w.title not in bible_tabs:
            return w.title
    return None


def _location_aliases_from_bible(sh) -> dict[str, str]:
    """Build {lowercase-alias: canonical-name} from the LOCATIONS bible.

    Primary: col O = Aliases (semicolon-separated lowercase substrings)
    Fallback: just col A = Name (canonical) — works on bibles that don't
    have col O populated yet.

    Returns dict ordered so longest aliases win first (Python 3.7+ preserves
    insertion order). Used by `bible_reader.read_storyboards` as the dashboard's
    body-text fallback when SP!L is blank/Unspecified."""
    try:
        ws = sh.worksheet("LOCATIONS")
        raw = ws.get("A5:O100", value_render_option="FORMATTED_VALUE")
        pairs: dict[str, str] = {}
        names = set()
        for r in raw:
            r = (r + [""] * 15)[:15]
            name = (r[0] or "").strip()
            if not name:
                continue
            names.add(name)
            aliases_str = (r[14] or "").strip()  # col O
            if aliases_str:
                for a in aliases_str.split(";"):
                    a = a.strip().lower()
                    if a:
                        pairs.setdefault(a, name)
        # safety net — only the canonical name itself (lowercased) auto-matches.
        # Anything more aggressive (single-word fallback) collides because
        # words like "hanbyeol" appear in multiple canonicals.
        for n in names:
            pairs.setdefault(n.lower(), n)
        # longest-first so most-specific alias wins
        return dict(sorted(pairs.items(), key=lambda p: -len(p[0])))
    except Exception:
        return {}


# --------------------------------------------------------------------------
# Read-cache layer — keeps the dashboard under Sheets API quota when multiple
# clients are connected. ALL bible reads route through `_cached_read(...)`
# which dedupes by (resource_key, sheet_id) for `_TTL` seconds. The Refresh
# button calls `invalidate_all_caches()` to force a fresh pull.
#
# Background refresher (started by app.py at boot): warms each registered
# cache every `_BG_REFRESH_INTERVAL` seconds so users see fresh data without
# any client-side polling hitting Sheets directly.
# --------------------------------------------------------------------------

import threading
import time as _t

_TTL = 60.0  # seconds — a single Sheets read serves all clients in this window
_BG_REFRESH_INTERVAL = 45.0  # seconds — shorter than TTL so cache stays warm

# storyboards keyed by (sheet_id, bible_sheet_id); other readers keyed by sheet_id
_cache_storage: dict[str, dict] = {}
_cache_lock = threading.Lock()


def _cached_read(name: str, key, fetch_fn):
    """Generic TTL cache. `name` is a unique resource label (e.g. 'storyboards'),
    `key` is hashable identifier (sheet_id or tuple), `fetch_fn` is the slow Sheets
    fetcher. Thread-safe."""
    with _cache_lock:
        bucket = _cache_storage.setdefault(name, {})
        entry = bucket.get(key)
        if entry and (_t.time() - entry[0]) < _TTL:
            return entry[1]
    # release lock during slow read
    result = fetch_fn()
    with _cache_lock:
        _cache_storage.setdefault(name, {})[key] = (_t.time(), result)
    return result


def invalidate_all_caches():
    """Drop every cached read — bound to the dashboard's ↻ Refresh button."""
    with _cache_lock:
        _cache_storage.clear()


# Backwards-compat alias — older code calls invalidate_storyboard_cache().
def invalidate_storyboard_cache():
    invalidate_all_caches()


def read_storyboards(sheet_id: str, bible_sheet_id: str | None = None,
                      bypass_cache: bool = False) -> list[dict]:
    """Cached storyboards read. Pass `bypass_cache=True` to force fresh."""
    if bypass_cache:
        invalidate_all_caches()
    return _cached_read(
        "storyboards", (sheet_id, bible_sheet_id),
        lambda: _read_storyboards_impl(sheet_id, bible_sheet_id),
    )


# --- Background refresh thread (started once by app.py) -------------------

_bg_started = False
_bg_resources: list[tuple[str, callable]] = []


def register_bg_refresh(label: str, fn):
    """Register a fetcher to be re-run by the background warmer.
    `fn` should be a no-arg callable that re-populates its own cache."""
    _bg_resources.append((label, fn))


def start_background_refresh(get_active_sheet_id, bible_sheet_id):
    """Spawn a daemon thread that re-warms each cache every
    `_BG_REFRESH_INTERVAL` seconds. Called once from app.py at boot.

    `get_active_sheet_id` is a callable returning the current episode sheet
    (so the warmer follows the user's episode picks). `bible_sheet_id` is
    fixed per series."""
    global _bg_started
    if _bg_started:
        return
    _bg_started = True

    def _loop():
        while True:
            try:
                sid = get_active_sheet_id()
                if sid:
                    # Warm the storyboards cache (the most-polled resource).
                    read_storyboards(sid, bible_sheet_id=bible_sheet_id,
                                     bypass_cache=False)
                    # Warm bible caches for the SERIES bible sheet.
                    bsid = bible_sheet_id or sid
                    read_characters(bsid)
                    read_locations(bsid)
                    read_costumes(bsid)
                    read_props(bsid)
                    read_effects(bsid)
                    read_asset_library(bsid)
            except Exception as e:
                print(f"[bg-refresh] warmer error: {e}")
            _t.sleep(_BG_REFRESH_INTERVAL)

    threading.Thread(target=_loop, daemon=True, name="bible-bg-refresh").start()
    print(f"[bg-refresh] started — warming caches every {_BG_REFRESH_INTERVAL}s")


def _read_storyboards_impl(sheet_id: str, bible_sheet_id: str | None = None) -> list[dict]:
    """Per-set rich data for the dashboard's Storyboards tab.

    Sources:
      - Storyboard Prompts tab → set-level metadata (drive folder, SB iters,
        video iters, status). v2.2 schema, rows 11+.
      - VIDEO PROMPTS tab → the prompt body actually shown on the dashboard.
        Globals at B1 (camera) + B2 (audio/dialogue); per-shot bodies at col I.
        For set N (5 shots), we concat shots ((N-1)*5+1)..(N*5) → rows
        (5N+2)..(5N+6) in the post-migration schema.
      - LOCATIONS bible → auto-detect per-set location.

    The "storyboard prompt" (pencil-on-paper) globals (Storyboard Prompts B1-B8)
    are LOCKED — never surfaced to the dashboard editor.
    """
    sh = open_sheet(sheet_id)
    bible_sh = open_sheet(bible_sheet_id) if bible_sheet_id and bible_sheet_id != sheet_id else sh
    loc_aliases = _location_aliases_from_bible(bible_sh)

    # ---- Pull Video Prompts globals (camera, audio, setting) ----
    vp_global_camera = ""
    vp_global_audio = ""
    vp_global_setting = ""
    vp_global_camera_id = ""
    vp_global_audio_id = ""
    vp_global_setting_id = ""
    try:
        vp_ws = sh.worksheet("Video Prompts")
        gvals = vp_ws.get("A1:B6", value_render_option="FORMATTED_VALUE")
        for r in gvals:
            r = (r + ["", ""])[:2]
            label = (r[0] or "").strip().lower()
            val = r[1] or ""
            if label == "camera global":
                vp_global_camera = val
            elif label == "audio/dialogue global":
                vp_global_audio = val
            elif label == "setting global":
                vp_global_setting = val
            elif label == "bahasa camera":
                vp_global_camera_id = val
            elif label == "bahasa audio/dialogue":
                vp_global_audio_id = val
            elif label == "bahasa setting":
                vp_global_setting_id = val
    except Exception:
        pass

    # ---- Pull body content directly from Shotlist col Q (per-shot Video Prompt
    # formula). This is the SOT for per-shot text and never contains storyboard
    # preamble. Q resolves to: "No music. Dialogue in <accent> accent.\n
    # <#>, <dur>s, <type>, <camera>, <description>, <dialogue> (<microexp>), <sfx>."
    # We use the resolved value, not the formula. ----
    shot_bodies = []   # (body, bahasa) per shot, ordered shot 1..N
    try:
        sl_ws = sh.worksheet("Shotlist")
        sl_rows = sl_ws.get("A2:R200", value_render_option="FORMATTED_VALUE")
        for r in sl_rows:
            r = (r + [""] * 18)[:18]
            shot_num_str = (r[0] or "").strip()
            if not shot_num_str.isdigit():
                continue
            body = r[16] or ""   # col Q — Prompt
            bahasa = r[17] or ""  # col R — Bahasa Prompt
            shot_bodies.append((body, bahasa))
    except Exception:
        pass

    try:
        ws = sh.worksheet("Storyboard Prompts")
    except Exception:
        return []
    # Read header row 10 to find columns by name (schema may vary across shows)
    hdr_rows = ws.get("A10:Z10", value_render_option="FORMATTED_VALUE")
    hdr = (hdr_rows[0] if hdr_rows else []) + [""] * 26
    hdr_idx = {h.strip().lower(): i for i, h in enumerate(hdr) if h}

    def col(name: str, fallback: int) -> int:
        return hdr_idx.get(name.lower(), fallback)

    sb1_col   = col("iter 1 url", 6)
    sb2_col   = col("iter 2 url", 7)
    loc_col   = col("location", 11)
    vid1_col  = col("video iter 1 url", 12)
    vid2_col  = col("video iter 2 url", 13)
    # Legacy fallback: if no "Video Iter 1/2 URL" headers exist, the older
    # schema used L/M for videos. Detect that and fall back gracefully.
    if "video iter 1 url" not in hdr_idx and "location" not in hdr_idx:
        vid1_col, vid2_col = 11, 12

    raw = ws.get("A11:Z100", value_render_option="FORMATTED_VALUE")
    out = []
    for i, r in enumerate(raw):
        r = (r + [""] * 26)[:26]
        shot_range = r[1]
        if not shot_range and not (r[2] or "").strip():
            continue
        # ---- BODY: assembled from Shotlist col Q for the 5 shots in this set.
        # Col Q is the per-shot Video Prompt formula — clean of storyboard
        # preamble (no pencil-on-paper text). Each shot becomes a paragraph. ----
        set_n = i + 1
        first_shot = (set_n - 1) * 5 + 1
        last_shot = set_n * 5
        slice_bodies = shot_bodies[first_shot - 1: last_shot]
        body_parts_en = [b for b, _ in slice_bodies if (b or "").strip()]
        body_parts_id = [b for _, b in slice_bodies if (b or "").strip()]
        body = "\n\n".join(body_parts_en)
        body_bahasa = "\n\n".join(body_parts_id)
        sb1 = drive_id(r[sb1_col])
        sb2 = drive_id(r[sb2_col])
        video_urls = [r[vid1_col] or "", r[vid2_col] or ""]
        videos = []
        for idx, url in enumerate(video_urls, start=1):
            if url:
                vid = drive_id(url)
                videos.append({
                    "slot": idx,
                    "label": f"V{idx}",
                    "url": url,
                    "view": view(vid) if vid else url,
                    "download": download_url(vid) if vid else url,
                    "thumb": thumb(vid) if vid else "",
                    # /preview embeds Drive's HTML5 player in an iframe so
                    # the dashboard can play the clip inline (no new tab).
                    "preview": preview(vid) if vid else "",
                })
            else:
                videos.append(None)
        # LOCATION — primary source: col L on Storyboard Prompts (SOT). If
        # the cell is blank or "Unspecified", fall back to auto-detect from
        # body text against the LOCATIONS bible aliases.
        sot_loc = (r[loc_col] or "").strip()
        if sot_loc and sot_loc.lower() != "unspecified":
            location = sot_loc
        else:
            body_lower = body.lower()
            location = next(
                (canonical for low, canonical in loc_aliases.items() if low in body_lower),
                "Unspecified",
            )
        out.append({
            "set": set_n,
            "shots": shot_range,
            "body": body,
            "body_bahasa": body_bahasa,
            "location": location,
            "vp_global_camera": vp_global_camera,
            "vp_global_audio": vp_global_audio,
            "vp_global_setting": vp_global_setting,
            "vp_global_camera_id": vp_global_camera_id,
            "vp_global_audio_id": vp_global_audio_id,
            "vp_global_setting_id": vp_global_setting_id,
            "sb_iters": [
                {"label": "V1", "thumb": thumb(sb1, 1400), "view": view(sb1)} if sb1 else None,
                {"label": "V2", "thumb": thumb(sb2, 1400), "view": view(sb2)} if sb2 else None,
            ],
            "videos": videos,
        })
    return out


def read_characters(sheet_id: str) -> list[dict]:
    return _cached_read("characters", sheet_id,
                        lambda: _read_characters_impl(sheet_id))


def _read_characters_impl(sheet_id: str) -> list[dict]:
    sh = open_sheet(sheet_id)
    try:
        ws = sh.worksheet("CHARACTERS")
    except Exception:
        return []
    rows = ws.get_all_records()
    if not rows:
        return []
    keys = list(rows[0].keys())
    iter1_key = next((k for k in keys if "iter 1 url" in k.lower()), None)
    iter2_key = next((k for k in keys if "iter 2 url" in k.lower()), None)

    def label_from_key(k):
        m = re.search(r"\(([^)]+)\)", k or "")
        return m.group(1) if m else "iter"

    label1 = label_from_key(iter1_key)
    label2 = label_from_key(iter2_key)
    out = []
    for r in rows:
        name = (r.get("Name") or "").strip()
        if not name:
            continue
        i1 = drive_id(r.get(iter1_key) or "") if iter1_key else None
        i2 = drive_id(r.get(iter2_key) or "") if iter2_key else None
        out.append({
            "name": name,
            "alias": r.get("Alias", "") or "",
            "role": r.get("Role / Archetype", r.get("Role", "")) or "",
            "age": r.get("Age", "") or "",
            "wardrobe": r.get("Wardrobe", "") or "",
            "personality": r.get("Personality", "") or "",
            "iters": [
                {"label": label1, "thumb": thumb(i1), "view": view(i1)} if i1 else None,
                {"label": label2, "thumb": thumb(i2), "view": view(i2)} if i2 else None,
            ],
        })
    return out


def read_locations(sheet_id: str) -> list[dict]:
    return _cached_read("locations", sheet_id,
                        lambda: _read_locations_impl(sheet_id))


def _read_locations_impl(sheet_id: str) -> list[dict]:
    sh = open_sheet(sheet_id)
    try:
        ws = sh.worksheet("LOCATIONS")
    except Exception:
        return []
    raw = ws.get("A5:N100", value_render_option="FORMATTED_VALUE")
    by_name = {}
    for row in raw:
        if not row or not row[0]:
            continue
        name = row[0]
        shot_size = row[1] if len(row) > 1 else ""
        type_ = row[2] if len(row) > 2 else ""
        desc = row[3] if len(row) > 3 else ""
        lighting = row[4] if len(row) > 4 else ""
        time_of_day = row[5] if len(row) > 5 else ""
        i1 = drive_id(row[9] if len(row) > 9 else "")
        i2 = drive_id(row[10] if len(row) > 10 else "")
        if name not in by_name:
            by_name[name] = {
                "name": name, "type": type_, "description": desc,
                "lighting": lighting, "time": time_of_day, "iters": [],
            }
        for label, fid in [(f"{shot_size} – 1", i1), (f"{shot_size} – 2", i2)]:
            if fid:
                by_name[name]["iters"].append(
                    {"label": label, "thumb": thumb(fid), "view": view(fid)})
    return list(by_name.values())


def _read_simple_bible(sheet_id: str, tab: str) -> list[dict]:
    sh = open_sheet(sheet_id)
    try:
        ws = sh.worksheet(tab)
    except Exception:
        return []
    rows = ws.get("A6:K100", value_render_option="FORMATTED_VALUE")
    out = []
    for row in rows:
        if not row or not row[0]:
            continue
        i1 = drive_id(row[6] if len(row) > 6 else "")
        i2 = drive_id(row[7] if len(row) > 7 else "")
        out.append({
            "name": row[0],
            "used_by": row[1] if len(row) > 1 else "",
            "description": row[2] if len(row) > 2 else "",
            "iters": [
                {"label": "iter 1", "thumb": thumb(i1), "view": view(i1)} if i1 else None,
                {"label": "iter 2", "thumb": thumb(i2), "view": view(i2)} if i2 else None,
            ],
        })
    return out


def read_costumes(sheet_id: str) -> list[dict]:
    return _cached_read("costumes", sheet_id,
                        lambda: _read_simple_bible(sheet_id, "COSTUME"))


def read_props(sheet_id: str) -> list[dict]:
    return _cached_read("props", sheet_id,
                        lambda: _read_simple_bible(sheet_id, "PROPS"))


def read_effects(sheet_id: str) -> list[dict]:
    return _cached_read("effects", sheet_id,
                        lambda: _read_simple_bible(sheet_id, "EFFECTS"))


def read_asset_library(sheet_id: str) -> list[dict]:
    return _cached_read("asset_library", sheet_id,
                        lambda: _read_asset_library_impl(sheet_id))


def _read_asset_library_impl(sheet_id: str) -> list[dict]:
    sh = open_sheet(sheet_id)
    try:
        ws = sh.worksheet("Asset Library")
    except Exception:
        return []
    raw = ws.get("A5:L500", value_render_option="FORMATTED_VALUE")
    out = []
    for r in raw:
        r = (r + [""] * 12)[:12]
        if not r[0].strip():
            continue
        out.append({
            "name": r[0], "bible": r[1], "asset_code": r[2] or "—",
            "type": r[4], "status": r[5] or "Pending",
            "uploaded_at": (r[6] or "")[:16].replace("T", " "),
            "first_used": r[7], "last_used": r[11],
        })
    return out

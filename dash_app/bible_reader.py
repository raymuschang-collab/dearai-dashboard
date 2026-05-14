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


# Per-process MIME cache. file_id → mimeType string. Populated lazily by
# `mime_of()`. Lives for the worker's lifetime — Drive renames don't happen
# often enough to justify TTL eviction.
_mime_cache: dict[str, str] = {}


def mime_of(file_id: str | None) -> str:
    """Lookup MIME type for a Drive file ID. Cached for the worker lifetime.

    Used by `_read_characters_impl` (and any other reader) to decide whether a
    ref is an image or a video, so the gallery can pick `<img>` vs `<iframe>`
    rendering. Returns "" on lookup failure (caller should default to image)."""
    if not file_id:
        return ""
    if file_id in _mime_cache:
        return _mime_cache[file_id]
    try:
        from googleapiclient.discovery import build
        from auth import get_credentials
        drive = build("drive", "v3", credentials=get_credentials())
        meta = drive.files().get(
            fileId=file_id, fields="mimeType",
            supportsAllDrives=True,
        ).execute()
        mime = meta.get("mimeType", "")
    except Exception:
        mime = ""
    _mime_cache[file_id] = mime
    return mime


def _gspread():
    import warnings; warnings.filterwarnings("ignore")
    import gspread
    from auth import get_credentials
    try:
        creds = get_credentials()
    except SystemExit as e:
        # Page-load guard: auth.py uses SystemExit for CLI setup errors. In the
        # dashboard that bypasses callback `except Exception` handlers and turns
        # a missing/malformed GOOGLE_SVC_ACCOUNT_JSON or GOOGLE_USER_TOKEN_JSON
        # into a broken initial page load, so convert it to a renderable error.
        raise RuntimeError(f"Google credentials unavailable: {e}") from None
    return gspread.authorize(creds)


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

# TTL deliberately long: Sheets API caps reads at 60/min/user. With 2 gunicorn
# workers sharing one OAuth token, multiple bible reads per refresh, and the
# bg-warmer adding pressure, we must keep cache hits high. 10-minute TTL is
# safe for the production show data which only changes when the team edits
# the SOT (and they hit ↻ Refresh manually after).
_TTL = 600.0  # 10 min
_BG_REFRESH_INTERVAL = 180.0  # 3 min — much wider than before to cut quota
_QUOTA_BACKOFF = 60.0  # after a 429, hold off bg-warmer for 60s

# storyboards keyed by (sheet_id, bible_sheet_id); other readers keyed by sheet_id
_cache_storage: dict[str, dict] = {}
_cache_lock = threading.Lock()
# Track last 429 timestamp globally so the bg-warmer can pause after a quota hit.
_last_quota_hit = 0.0


def _is_quota_error(e: Exception) -> bool:
    """Detect Sheets-API 429 'Quota exceeded' errors so callers can fall back
    to stale cache rather than surface a crash to the user."""
    msg = str(e)
    return "429" in msg and "Quota exceeded" in msg


def _cached_read(name: str, key, fetch_fn):
    """Generic TTL cache. `name` is a unique resource label (e.g. 'storyboards'),
    `key` is hashable identifier (sheet_id or tuple), `fetch_fn` is the slow Sheets
    fetcher. Thread-safe.

    Quota resilience: on 429 ('Quota exceeded'), return the last known cache
    value even if it is older than _TTL. Better stale data than a broken UI."""
    global _last_quota_hit
    with _cache_lock:
        bucket = _cache_storage.setdefault(name, {})
        entry = bucket.get(key)
        if entry and (_t.time() - entry[0]) < _TTL:
            return entry[1]
    # release lock during slow read
    try:
        result = fetch_fn()
    except Exception as e:
        if _is_quota_error(e):
            _last_quota_hit = _t.time()
            with _cache_lock:
                stale = _cache_storage.get(name, {}).get(key)
            if stale:
                print(f"[bible_reader] 429 quota — serving stale cache for {name}:{key}")
                return stale[1]
            print(f"[bible_reader] 429 quota and no cache available for {name}:{key}")
        raise
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
            # If we recently hit a 429, sit out one full _QUOTA_BACKOFF window
            # to let the per-minute quota reset before warming again.
            since_quota = _t.time() - _last_quota_hit
            if since_quota < _QUOTA_BACKOFF:
                _t.sleep(_QUOTA_BACKOFF - since_quota)
                continue
            try:
                sid = get_active_sheet_id()
                if sid:
                    # Warm the storyboards cache (the most-polled resource).
                    read_storyboards(sid, bible_sheet_id=bible_sheet_id,
                                     bypass_cache=False)
                    # Warm bible caches for the SERIES bible sheet. Spaced
                    # with 1s gaps so the warm-up itself doesn't burst into
                    # the per-minute quota.
                    bsid = bible_sheet_id or sid
                    for fn in (read_characters, read_locations, read_costumes,
                               read_props, read_effects, read_asset_library):
                        try:
                            fn(bsid)
                        except Exception as e:
                            if _is_quota_error(e):
                                print(f"[bg-refresh] 429 during {fn.__name__}; backing off")
                                break
                            raise
                        _t.sleep(1.0)
            except Exception as e:
                print(f"[bg-refresh] warmer error: {e}")
            _t.sleep(_BG_REFRESH_INTERVAL)

    threading.Thread(target=_loop, daemon=True, name="bible-bg-refresh").start()
    print(f"[bg-refresh] started — warming caches every {_BG_REFRESH_INTERVAL}s")


_SHOT_RANGE_RE = re.compile(r"^\s*(\d+)\s*[-–—]\s*(\d+)\s*$")


def _parse_shot_range(s: str, set_n: int) -> tuple[int, int]:
    """Parse 'N-M' string into (first, last) inclusive shot numbers. Falls
    back to uniform-5 layout when the range is empty/malformed so legacy
    sheets that don't fill col B still render."""
    if s:
        m = _SHOT_RANGE_RE.match(s)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b:
                return a, b
        # Single-shot variant ("4")
        s_clean = s.strip()
        if s_clean.isdigit():
            n = int(s_clean)
            return n, n
    # Fallback: uniform 5-shot layout
    return (set_n - 1) * 5 + 1, set_n * 5


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

    # All four ranges below live on the same spreadsheet — collapse them into
    # ONE Sheets API call via values_batchGet to stay under the 60/min/user
    # quota. Was 4 round-trips, now 1.
    try:
        batch = sh.values_batch_get(
            ranges=[
                "Video Prompts!A1:B6",
                "Shotlist!A2:R200",
                "Storyboard Prompts!A10:Z10",
                "Storyboard Prompts!A11:Z100",
            ],
            params={"valueRenderOption": "FORMATTED_VALUE"},
        )
        ranges = batch.get("valueRanges", [])
    except Exception:
        ranges = [{}, {}, {}, {}]

    def _vals(idx):
        return ranges[idx].get("values", []) if idx < len(ranges) else []

    # ---- Video Prompts globals (camera, audio, setting + Bahasa) ----
    vp_global_camera = ""
    vp_global_audio = ""
    vp_global_setting = ""
    vp_global_camera_id = ""
    vp_global_audio_id = ""
    vp_global_setting_id = ""
    for r in _vals(0):
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

    # ---- Shotlist col Q (Prompt) + col R (Bahasa) per-shot bodies ----
    shot_bodies = []
    for r in _vals(1):
        r = (r + [""] * 18)[:18]
        shot_num_str = (r[0] or "").strip()
        if not shot_num_str.isdigit():
            continue
        body = r[16] or ""
        bahasa = r[17] or ""
        shot_bodies.append((body, bahasa))

    # ---- Storyboard Prompts header (row 10) → column-name → index map ----
    hdr_rows = _vals(2)
    if not hdr_rows:
        return []  # no SP tab / no header
    hdr = (hdr_rows[0] if hdr_rows else []) + [""] * 26
    hdr_idx = {h.strip().lower(): i for i, h in enumerate(hdr) if h}

    def col(name: str, fallback: int) -> int:
        return hdr_idx.get(name.lower(), fallback)

    status_col = col("status", 5)
    sb1_col   = col("iter 1 url", 6)
    sb2_col   = col("iter 2 url", 7)
    loc_col   = col("location", 11)
    vid1_col  = col("video iter 1 url", 12)
    vid2_col  = col("video iter 2 url", 13)
    # Legacy fallback: if no "Video Iter 1/2 URL" headers exist, the older
    # schema used L/M for videos. Detect that and fall back gracefully.
    if "video iter 1 url" not in hdr_idx and "location" not in hdr_idx:
        vid1_col, vid2_col = 11, 12

    raw = _vals(3)
    out = []
    for i, r in enumerate(raw):
        r = (r + [""] * 26)[:26]
        shot_range = r[1]
        if not shot_range and not (r[2] or "").strip():
            continue
        # ---- BODY: assembled from Shotlist col Q for the shots in this set.
        # Col Q is the per-shot Video Prompt formula — clean of storyboard
        # preamble (no pencil-on-paper text). Each shot becomes a paragraph.
        #
        # Sets are NON-UNIFORM in some episodes (e.g. Ep 1 has set 1=shots 1-3,
        # set 2=shots 4-7). Parse the shot-range string ("1-3", "4-7") to slice
        # the right shots; fall back to (i*5+1, (i+1)*5) for legacy uniform sets
        # where the range column is empty. ----
        set_n = i + 1
        first_shot, last_shot = _parse_shot_range(shot_range, set_n)
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
            "status": (r[status_col] or "").strip(),
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
                # Storyboard tile — w=900 is plenty for the 333px-wide column;
                # bigger is just slower Drive fetch + bigger paint. Lightbox
                # bumps to w=2048 on click via assets/zoom.js.
                {"label": "V1", "thumb": thumb(sb1, 900), "view": view(sb1)} if sb1 else None,
                {"label": "V2", "thumb": thumb(sb2, 900), "view": view(sb2)} if sb2 else None,
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
    def _iter(fid: str | None, label: str) -> dict | None:
        """Build one iter dict. Detects video vs image via Drive MIME so the
        gallery can pick <iframe> vs <img> rendering."""
        if not fid:
            return None
        mime = mime_of(fid)
        is_video = mime.startswith("video/")
        return {
            "label": label,
            "kind": "video" if is_video else "image",
            "thumb": thumb(fid),     # lh3 path — Drive auto-poster for videos works here too
            "view": view(fid),
            "embed": preview(fid) if is_video else "",
        }

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
                _iter(i1, label1),
                _iter(i2, label2),
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

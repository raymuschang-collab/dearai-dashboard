#!/usr/bin/env python3
"""
vidgen_freeform.py — Freeform Seedance 2 vidgen with @-mention asset resolution.

Built for Claude Code workflows: the team types prompts in natural language
inside Claude (e.g. "fire a video of @tara plating bibimbap in @kitchen"),
Claude calls this script with the @-mentions + body, and the script resolves
each mention live from the Asset Library tab.

Why "freeform" — there's no set/slot/storyboard requirement here. Pass any
prompt body + a list of @-mentioned asset names, get a vidgen back. No
hardcoded asset codes anywhere; resolution happens at runtime against the
LIVE Asset Library tab so asset swaps propagate instantly.

Usage:
    python3 vidgen_freeform.py \\
        --mentions "@tara,@kitchen,@bibimbap" \\
        --body "Tara stands at the pass plating a bibimbap bowl." \\
        --resolution 480p --duration 15

    # All flags:
    python3 vidgen_freeform.py \\
        --mentions "@tara,@minjun" \\
        --body "<your prompt>" \\
        [--storyboard <Drive URL>]   composition anchor (optional)
        [--sheet <bible_sheet_id>]   default: BIBLE_SHEET from .env
        [--resolution 480p|720p|1080p|2K]  default: 480p
        [--duration 4-15]             default: 15
        [--aspect 9:16|16:9]          default: 9:16
        [--out <path>]                default: /tmp/vidgen_<ts>.mp4
        [--upload-to-drive]           also push to Drive, return webViewLink
        [--drive-folder <folder_id>]  default: <show>/freeform-videos/
        [--fast]                      cheaper Seedance fast tier
        [--confirm]                   print prompt + refs before submitting

Resolves mentions by:
  1. Strip leading "@" from each token
  2. Fuzzy-match against Asset Library Name column (normalized)
  3. For chars: pull image + video + audio codes (face/attire dedup applied)
  4. For locations / props / costume / effects: pull image code

Crash recovery: persists task_id to .byteplus_pending.json BEFORE the
download/upload step, so byteplus_vidgen_resume.py can pick it up if the
script dies after BytePlus succeeds but before writeback.
"""
from __future__ import annotations

import argparse
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
sys.path.insert(0, str(HERE))
from auth import get_credentials  # type: ignore

ARK_API_KEY = os.getenv("BYTEPLUS_ARK_API_KEY")
ARK_BASE = os.getenv("BYTEPLUS_ARK_BASE",
                      "https://ark.ap-southeast.bytepluses.com/api/v3")
DEFAULT_BIBLE_SHEET = os.getenv("DEFAULT_BIBLE_SHEET",
                                 "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc")
PENDING_LOG = HERE / ".byteplus_pending.json"
EXPENSE_LOG = HERE / ".byteplus_expense.json"


# -------- Mention resolution -------------------------------------------------

def _norm(s: str) -> str:
    """Normalize for matching: lowercase, strip non-alphanumeric."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_asset_library(gc, sheet_id: str) -> list[dict]:
    """Read all Uploaded rows from Asset Library."""
    sh = gc.open_by_key(sheet_id)
    al = sh.worksheet("Asset Library")
    rows = al.get("A5:F500", value_render_option="FORMATTED_VALUE")
    out = []
    for r in rows:
        if not r or not r[0].strip():
            continue
        r = r + [""] * 6
        if r[5].strip() != "Uploaded":
            continue
        out.append({
            "name": r[0].strip(),
            "bible_tab": r[1].strip(),
            "asset_code": r[2].strip(),
            "source_url": r[3].strip(),
            "asset_type": r[4].strip().lower(),  # "image" / "video" / "audio"
        })
    return out


def resolve_mention(token: str, asset_lib: list[dict]) -> list[dict]:
    """For an @-token, return ALL matching Asset Library entries.

    Match strategy (first hit wins per pass):
      1. Exact normalized full-name match
      2. Substring contains (token in name OR name in token)
      3. Token-split: any word of the token, ≥3 chars, matches a name token
    """
    raw = token.lstrip("@").strip()
    nt = _norm(raw)
    if not nt:
        return []

    # Pass 1 — exact normalized
    exact = [a for a in asset_lib if _norm(a["name"]) == nt]
    if exact:
        return exact

    # Pass 2 — substring (one inside the other), min 4 chars
    sub = [a for a in asset_lib
           if len(nt) >= 4 and (nt in _norm(a["name"]) or _norm(a["name"]) in nt)]
    if sub:
        # Pick the shortest matching name (most specific)
        # but return all rows for that canonical name (so we get all media types)
        canon = min(sub, key=lambda a: len(a["name"]))["name"]
        return [a for a in asset_lib if a["name"] == canon]

    # Pass 3 — token split (split by - and space)
    raw_tokens = [t for t in re.split(r"[-_\s]+", raw) if len(t) >= 3]
    if not raw_tokens:
        return []
    matches = []
    for a in asset_lib:
        name_tokens = re.split(r"[-_\s\(\)]+", a["name"].lower())
        for rt in raw_tokens:
            for nt2 in name_tokens:
                if rt.lower() in nt2 or nt2 in rt.lower():
                    matches.append(a)
                    break
            else:
                continue
            break
    if matches:
        # Group by canonical name, pick the most-mentioned
        from collections import Counter
        names = Counter(a["name"] for a in matches)
        top_name = names.most_common(1)[0][0]
        return [a for a in asset_lib if a["name"] == top_name]
    return []


def apply_face_attire_dedup(refs: list[dict]) -> list[dict]:
    """When a character has both image + video, drop the image (the video
    carries the appearance signal). Identity refs stay one per character.
    Audio is kept independently."""
    char_has_video = {r["name"] for r in refs
                       if r.get("bible_tab") == "CHARACTERS"
                       and r.get("asset_type") == "video"}
    out = []
    for r in refs:
        if (r.get("bible_tab") == "CHARACTERS"
                and r.get("asset_type") == "image"
                and r.get("name") in char_has_video):
            continue  # drop redundant image
        out.append(r)
    return out


# -------- Duration helpers (cumulative video budget) -------------------------

VIDEO_BUDGET_SECONDS = 14.0
VIDEO_UNKNOWN_FALLBACK = 5.0
DURATION_CACHE = HERE / ".byteplus_asset_durations.json"


def _load_durations() -> dict:
    if DURATION_CACHE.exists():
        try:
            return json.loads(DURATION_CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save_durations(d: dict):
    try:
        DURATION_CACHE.write_text(json.dumps(d, indent=2, sort_keys=True))
    except Exception:
        pass


def _drive_dl_url(view_url: str) -> str | None:
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", view_url or "")
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return None


def probe_duration(asset_code: str, source_url: str) -> float | None:
    """Cached ffprobe duration lookup for a video ref."""
    cache = _load_durations()
    key = asset_code or source_url
    if key in cache:
        v = cache[key]
        return float(v) if v is not None else None
    import shutil, subprocess
    if not shutil.which("ffprobe"):
        return None
    probe_url = _drive_dl_url(source_url) or source_url
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", probe_url],
            capture_output=True, text=True, timeout=30)
        d = float(r.stdout.strip()) if r.stdout.strip() else None
    except Exception:
        d = None
    cache[key] = d
    _save_durations(cache)
    return d


def enforce_video_budget(content_items: list[dict], max_seconds: float = VIDEO_BUDGET_SECONDS) -> list[dict]:
    """Drop video refs (longest first) until total fits. Each video item
    must carry a `_duration` field."""
    def _d(it):
        v = it.get("_duration")
        return VIDEO_UNKNOWN_FALLBACK if v is None else float(v)
    total = sum(_d(it) for it in content_items if it.get("type") == "video_url")
    if total <= max_seconds:
        return content_items
    print(f"  ⚠ video budget {total:.1f}s > {max_seconds:.1f}s — dropping longest first")
    out = list(content_items)
    while total > max_seconds:
        idxs = [(i, _d(it)) for i, it in enumerate(out) if it.get("type") == "video_url"]
        if not idxs:
            break
        worst_idx, worst_d = max(idxs, key=lambda x: x[1])
        url = out[worst_idx].get("video_url", {}).get("url", "")[:50]
        print(f"    drop {url}… ({worst_d:.1f}s)")
        out.pop(worst_idx)
        total -= worst_d
    print(f"  ✓ post-trim total: {total:.1f}s")
    return out


# -------- BytePlus submission + polling --------------------------------------

def submit_to_byteplus(prompt: str, content_refs: list[dict],
                       aspect: str, duration: int, resolution: str,
                       fast: bool) -> tuple[str | None, str | None]:
    """Submit Seedance 2 task. Returns (task_id, error_msg)."""
    model = "dreamina-seedance-2-0-fast-260128" if fast else "dreamina-seedance-2-0-260128"
    endpoint = f"{ARK_BASE}/contents/generations/tasks"
    headers = {"Authorization": f"Bearer {ARK_API_KEY}",
                "Content-Type": "application/json"}

    # BytePlus caps at 8 refs total. Order: storyboard (if any) → CHARACTERS →
    # COSTUME → LOCATIONS → PROPS → EFFECTS. content_refs already in that order.
    MAX_REFS = 8
    content = [{"type": "text", "text": prompt}]
    for ref in content_refs[:MAX_REFS]:
        # Strip our private _duration field before transmit
        clean = {k: v for k, v in ref.items() if not k.startswith("_")}
        content.append(clean)
    if len(content_refs) > MAX_REFS:
        print(f"  ⚠ {len(content_refs) - MAX_REFS} refs dropped at MAX_REFS cap")

    body = {
        "model": model, "content": content, "ratio": aspect,
        "duration": duration, "resolution": resolution, "watermark": False,
    }
    print(f"  → submitting {len(content) - 1} refs to BytePlus…")
    try:
        r = requests.post(endpoint, headers=headers, json=body, timeout=60)
        if r.status_code != 200:
            return None, f"submit failed: {r.status_code} {r.text[:300]}"
        resp = r.json()
        task_id = (resp.get("id") or resp.get("task_id")
                    or resp.get("data", {}).get("id"))
        if not task_id:
            return None, f"no task_id in response: {resp}"
        # Log every successful submit so freeform/custom callers are counted too.
        try:
            log_expense(task_id, "fast" if fast else "standard", duration, resolution)
        except Exception:
            pass
        return task_id, None
    except Exception as e:
        return None, f"exception: {e}"


def poll_task(task_id: str, max_wait: int = 600) -> tuple[dict | None, str | None]:
    endpoint = f"{ARK_BASE}/contents/generations/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {ARK_API_KEY}"}
    start = time.time()
    last_status = None
    while time.time() - start < max_wait:
        try:
            r = requests.get(endpoint, headers=headers, timeout=30)
            if r.status_code != 200:
                return None, f"poll failed: {r.status_code}"
            resp = r.json()
            status = resp.get("status", "")
            if status != last_status:
                print(f"  [{int(time.time() - start)}s] status: {status}")
                last_status = status
            if status in ("succeeded", "completed", "success"):
                return resp, None
            if status in ("failed", "expired", "cancelled"):
                return None, f"task failed: {status}"
        except Exception as e:
            print(f"  poll exception: {e}")
        time.sleep(15)
    return None, "max wait exceeded"


# -------- Pending-task ledger (crash recovery) -------------------------------

def persist_pending(task_id: str, **meta):
    """Record a freshly-submitted task so byteplus_vidgen_resume.py can
    finish the writeback if this process dies."""
    data = {"pending": []}
    if PENDING_LOG.exists():
        try:
            data = json.loads(PENDING_LOG.read_text())
        except Exception:
            pass
    data["pending"] = [e for e in data.get("pending", [])
                        if e.get("task_id") != task_id]
    data["pending"].append({
        "task_id": task_id,
        "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "submitted",
        "kind": "freeform",
        **meta,
    })
    PENDING_LOG.write_text(json.dumps(data, indent=2))


def remove_pending(task_id: str):
    if not PENDING_LOG.exists():
        return
    try:
        data = json.loads(PENDING_LOG.read_text())
    except Exception:
        return
    data["pending"] = [e for e in data.get("pending", [])
                        if e.get("task_id") != task_id]
    PENDING_LOG.write_text(json.dumps(data, indent=2))


def log_expense(task_id: str, model: str, duration: int, resolution: str):
    cost_per_sec = {"480p": 0.05, "720p": 0.08, "1080p": 0.132, "2K": 0.20}.get(resolution, 0.132)
    if "fast" in model:
        cost_per_sec *= 0.5
    est = round(cost_per_sec * duration, 4)
    log = {"entries": [], "cumulative_usd": 0.0}
    if EXPENSE_LOG.exists():
        try:
            log = json.loads(EXPENSE_LOG.read_text())
        except Exception:
            pass
    log["entries"].append({
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": task_id, "model": model, "duration": duration,
        "resolution": resolution, "kind": "freeform", "estimated_usd": est,
    })
    log["cumulative_usd"] = round(sum(e["estimated_usd"] for e in log["entries"]), 2)
    EXPENSE_LOG.write_text(json.dumps(log, indent=2))


# -------- Main --------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mentions",
                    help="Comma-separated @-mentions or asset names. "
                         "Example: '@tara,@kitchen,@bibimbap'. Required unless "
                         "--from-set is used (where mentions are auto-detected).")
    ap.add_argument("--body",
                    help="Free-form prompt body describing the scene. "
                         "Required unless --from-set is used.")
    ap.add_argument("--from-set", type=int, default=None,
                    help="Pull body + globals from Storyboard Prompts!set N. "
                         "If set, --body is auto-filled from SP!J{10+N}. "
                         "--mentions can still be passed to OVERRIDE the auto-"
                         "detected refs (everyday case: same set body, swap "
                         "out a character or location).")
    ap.add_argument("--raw-prompt", action="store_true",
                    help="Pass --body verbatim as the full Seedance prompt — "
                         "no globals, no realism preamble, no format directive, "
                         "no auto-built ID binding lines. Use when the team "
                         "has copy-pasted a full prompt from a set card and "
                         "edited it manually (e.g. swapped character names "
                         "for @-mentions). The script still resolves any "
                         "@-tokens inside --body to BytePlus asset refs.")
    ap.add_argument("--storyboard", default=None,
                    help="Optional Drive URL to use as composition anchor. "
                         "If --from-set is used, auto-pulls SP!G{row} (Iter 1).")
    ap.add_argument("--sheet", default=DEFAULT_BIBLE_SHEET,
                    help=f"Bible sheet ID (default: {DEFAULT_BIBLE_SHEET[:20]}…)")
    ap.add_argument("--resolution", default="480p",
                    choices=["480p", "720p", "1080p", "2K"])
    ap.add_argument("--duration", type=int, default=15)
    ap.add_argument("--aspect", default="9:16", choices=["9:16", "16:9"])
    ap.add_argument("--out", default=None,
                    help="Local MP4 output path (default: /tmp/vidgen_<ts>.mp4)")
    ap.add_argument("--upload-to-drive", action="store_true",
                    help="Also upload to Drive, return webViewLink")
    ap.add_argument("--drive-folder", default=None,
                    help="Drive folder ID for upload (default: freeform-videos in show)")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    if not ARK_API_KEY:
        sys.exit("BYTEPLUS_ARK_API_KEY not set in .env")

    # 1) Load Asset Library + resolve mentions
    print(f"=== Vidgen Freeform — {datetime.now().strftime('%H:%M:%S')} ===")
    print(f"  reading Asset Library from {args.sheet[:20]}…")
    gc = gspread.authorize(get_credentials())

    # If --from-set provided, pull body + globals + storyboard ref from
    # the bible sheet's Storyboard Prompts + Video Prompts tabs. This is
    # the hybrid pattern: locked-shotlist body + (optional) ref override.
    if args.from_set is not None:
        sh_for_set = gc.open_by_key(args.sheet)
        try:
            sp = sh_for_set.worksheet("Storyboard Prompts")
            sp_row = 10 + args.from_set  # row 11 = set 1
            row_cells = sp.get(f"A{sp_row}:N{sp_row}",
                                value_render_option="FORMATTED_VALUE")
            if not row_cells or not row_cells[0]:
                sys.exit(f"--from-set {args.from_set}: row {sp_row} is empty")
            row_cells = (row_cells[0] + [""] * 14)[:14]
            sp_body = row_cells[9]   # SP!J = body
            sp_sb_url = row_cells[6] # SP!G = Iter 1 storyboard

            vp = sh_for_set.worksheet("Video Prompts")
            globals_block = vp.get("A1:B6", value_render_option="FORMATTED_VALUE")
            global_camera = global_audio = global_setting = ""
            for r in globals_block:
                r = (r + ["", ""])[:2]
                label = (r[0] or "").strip().lower()
                val = r[1] or ""
                if label == "camera global":
                    global_camera = val
                elif label == "audio/dialogue global":
                    global_audio = val
                elif label == "setting global":
                    global_setting = val

            # Compose body = globals + per-shot list (mirrors what
            # byteplus_vidgen.py does internally, so the prompt structure
            # is identical to a set-based fire).
            composed_body_parts = [s for s in (
                global_camera, global_audio, global_setting, sp_body) if s]
            args.body = args.body or "\n\n".join(composed_body_parts)
            if not args.storyboard and sp_sb_url:
                args.storyboard = sp_sb_url
            print(f"  --from-set {args.from_set}: pulled body from SP!J{sp_row} "
                  f"+ globals from Video Prompts!B1:B3"
                  + (f" + storyboard SP!G{sp_row}" if sp_sb_url else ""))
        except Exception as e:
            sys.exit(f"--from-set {args.from_set} failed: {e}")

    if not args.body:
        sys.exit("--body is required (or use --from-set N)")
    if not args.mentions:
        # When --from-set is used without --mentions, auto-detect from body
        # by scanning Asset Library names against the body text (same logic
        # byteplus_vidgen.py uses).
        if args.from_set is not None:
            print(f"  --mentions not set; auto-detecting from body…")
            args.mentions = ""  # let the resolver fall through with empty list
        else:
            sys.exit("--mentions is required (or use --from-set with auto-detect)")

    asset_lib = load_asset_library(gc, args.sheet)
    print(f"  loaded {len(asset_lib)} active assets")

    raw_mentions = [t.strip() for t in args.mentions.split(",") if t.strip()] if args.mentions else []

    # ALSO scan the body for inline @-tokens (e.g. "@tara @kitchen" pasted
    # mid-prompt). Combines with --mentions; deduped by token. This lets
    # the team copy-paste a full prompt, replace names with @-handles, and
    # have everything just work.
    inline_tokens = re.findall(r"@[\w\-]+", args.body or "")
    for tok in inline_tokens:
        if tok not in raw_mentions:
            raw_mentions.append(tok)
    if inline_tokens:
        print(f"  detected {len(inline_tokens)} inline @-token(s) in body: {' '.join(inline_tokens[:8])}")

    # If still empty and --from-set, scan the body for known names
    # (handles the case where the team uses --from-set without overriding
    # mentions — locked-shotlist auto-detection)
    if not raw_mentions and args.from_set is not None:
        body_lc = args.body.lower()
        for a in asset_lib:
            nlow = a["name"].lower()
            if len(nlow) >= 4 and nlow in body_lc:
                raw_mentions.append(a["name"])
        # Also try CHARACTERS first-word matching (e.g. "MIN-JUN" in body
        # matches "PARK MIN-JUN" in Asset Library)
        for a in asset_lib:
            if a["bible_tab"] != "CHARACTERS":
                continue
            for word in re.findall(r"[A-Za-z][\w\-]+", a["name"]):
                if len(word) >= 4 and re.search(
                        r"\b" + re.escape(word) + r"\b", args.body, re.IGNORECASE):
                    if a["name"] not in raw_mentions:
                        raw_mentions.append(a["name"])
                    break
        # Dedup by name
        raw_mentions = list(dict.fromkeys(raw_mentions))
        print(f"  auto-detected {len(raw_mentions)} mention(s): {', '.join(raw_mentions[:6])}")
    resolved = []
    for m in raw_mentions:
        matches = resolve_mention(m, asset_lib)
        if not matches:
            print(f"  ✗ {m}: no match in Asset Library")
            continue
        canon = matches[0]["name"]
        types = sorted({a["asset_type"] for a in matches})
        print(f"  ✓ {m} → {canon} ({len(matches)} ref{'s' if len(matches)>1 else ''}: {','.join(types)})")
        resolved.extend(matches)

    if not resolved:
        sys.exit("No mentions resolved — check spelling or Asset Library state")

    # 2) Apply face/attire dedup (drop redundant char-image when char has video)
    resolved = apply_face_attire_dedup(resolved)

    # 3) Sort by bible-tab priority for the MAX_REFS=8 cap
    BIBLE_ORDER = {"CHARACTERS": 0, "COSTUME": 1, "LOCATIONS": 2,
                    "PROPS": 3, "EFFECTS": 4}
    resolved.sort(key=lambda r: (BIBLE_ORDER.get(r["bible_tab"], 99),
                                   r["name"].lower(),
                                   {"image": 0, "video": 1, "audio": 2}.get(r["asset_type"], 9)))

    # 4) Build content[] refs (storyboard first if provided)
    content_refs = []
    if args.storyboard:
        m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", args.storyboard)
        if m:
            sb_url = f"https://lh3.googleusercontent.com/d/{m.group(1)}=w2048"
        else:
            sb_url = args.storyboard
        content_refs.append({
            "type": "image_url",
            "image_url": {"url": sb_url},
            "role": "reference_image",
        })
        print(f"  + storyboard composition anchor")

    for r in resolved:
        code = r["asset_code"]
        url = code if code.startswith("asset://") else f"asset://{code}"
        atype = r["asset_type"]
        if atype == "video":
            entry = {"type": "video_url", "video_url": {"url": url},
                     "role": "reference_video"}
            entry["_duration"] = probe_duration(code, r["source_url"])
            print(f"    + {atype} {code} ({entry['_duration']:.1f}s)" if entry["_duration"] else f"    + {atype} {code}")
        elif atype == "audio":
            entry = {"type": "audio_url", "audio_url": {"url": url},
                     "role": "reference_audio"}
            print(f"    + {atype} {code}")
        else:
            entry = {"type": "image_url", "image_url": {"url": url},
                     "role": "reference_image"}
            print(f"    + {atype} {code}")
        content_refs.append(entry)

    content_refs = enforce_video_budget(content_refs)

    # 5) Build the prompt
    realism = ("Documentary editorial photography aesthetic, natural skin texture, "
               "Kodak Portra 400 color science, no airbrushing. Subtle film grain. "
               "Muted desaturated palette. Natural lighting only.")
    format_directive = f"VERTICAL {args.aspect} drama format."

    # Identity binding block — describes each ref's role
    binding_lines = []
    ref_ix = 1
    if args.storyboard:
        binding_lines.append(f"#{ref_ix} image: STORYBOARD — composition anchor")
        ref_ix += 1
    for r in resolved:
        if r["bible_tab"] == "CHARACTERS":
            if r["asset_type"] == "video":
                binding_lines.append(f"#{ref_ix} video: {r['name']} — FACE")
            elif r["asset_type"] == "audio":
                binding_lines.append(f"#{ref_ix} audio: {r['name']} — VOICE (use for all {r['name']} dialogue)")
            else:
                binding_lines.append(f"#{ref_ix} image: {r['name']} — IDENTITY")
        elif r["bible_tab"] == "COSTUME":
            owner_match = re.search(r"\(([^)]+)\)", r["name"])
            owner = f" (worn by {owner_match.group(1).strip()})" if owner_match else ""
            clean = re.sub(r"\s*\([^)]+\)", "", r["name"]).strip()
            binding_lines.append(f"#{ref_ix} image: {clean} — ATTIRE{owner}")
        elif r["bible_tab"] == "LOCATIONS":
            binding_lines.append(f"#{ref_ix} image: {r['name']} — LOCATION")
        elif r["bible_tab"] == "PROPS":
            binding_lines.append(f"#{ref_ix} image: {r['name']} — PROP")
        elif r["bible_tab"] == "EFFECTS":
            binding_lines.append(f"#{ref_ix} image: {r['name']} — FX")
        ref_ix += 1
    id_binding = "Reference identities (numbers match content[] order):\n" + "\n".join(binding_lines)

    # Strip @-mentions from body (just keep them as plain words for the model)
    clean_body = re.sub(r"@(\w[\w\-]*)", r"\1", args.body)

    if args.raw_prompt:
        # Manual override mode — pass the body verbatim (sans @-prefixes,
        # so the model sees plain character names). Skip globals + realism +
        # format directive + ID binding entirely. The user has presumably
        # copy-pasted a fully-assembled prompt and edited it manually.
        prompt = clean_body
        print("  --raw-prompt: skipping preamble; sending body verbatim")
    else:
        prompt = "\n".join([
            "Shot with Arri 35.",
            id_binding,
            realism,
            format_directive,
            clean_body,
        ])

    # 6) Optional confirm gate
    print(f"\n=== Prompt preview ({len(prompt)} chars) ===")
    print(prompt[:500] + ("…" if len(prompt) > 500 else ""))
    print(f"\n=== Refs to attach: {len(content_refs)} ===")
    if args.confirm:
        ans = input("\nSubmit to BytePlus? [y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            sys.exit("aborted at confirm gate")

    # 7) Submit
    print(f"\n  Submitting to BytePlus…")
    task_id, err = submit_to_byteplus(
        prompt, content_refs, args.aspect, args.duration,
        args.resolution, args.fast)
    if err:
        sys.exit(f"  ✗ {err}")
    print(f"  task_id: {task_id}")
    persist_pending(task_id, body=clean_body[:200],
                     mentions=args.mentions,
                     resolution=args.resolution, duration=args.duration,
                     aspect=args.aspect)

    # 8) Poll
    print(f"\n  Polling (typical: 30-180s)…")
    result, err = poll_task(task_id)
    if err:
        sys.exit(f"  ✗ {err}")
    video_url = (result.get("content", {}).get("video_url")
                 or result.get("video_url")
                 or result.get("data", {}).get("video_url"))
    if not video_url:
        sys.exit(f"  ✗ no video_url in response")

    # 9) Download
    out_path = args.out or f"/tmp/vidgen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    print(f"  downloading to {out_path}…")
    mp4 = requests.get(video_url, timeout=300).content
    Path(out_path).write_bytes(mp4)
    print(f"  ✓ {len(mp4)/(1024*1024):.2f} MB")

    # 10) Optional Drive upload
    drive_url = None
    if args.upload_to_drive:
        from googleapiclient.discovery import build as gbuild
        from googleapiclient.http import MediaIoBaseUpload
        drive = gbuild("drive", "v3", credentials=get_credentials())
        if args.drive_folder:
            parent = args.drive_folder
        else:
            # default: <show_folder>/freeform-videos/
            sh_meta = drive.files().get(fileId=args.sheet, fields="parents").execute()
            show_folder = sh_meta["parents"][0]
            q = (f"'{show_folder}' in parents and trashed=false "
                 f"and mimeType='application/vnd.google-apps.folder' "
                 f"and name='freeform-videos'")
            res = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
            if res:
                parent = res[0]["id"]
            else:
                parent = drive.files().create(
                    body={"name": "freeform-videos",
                           "mimeType": "application/vnd.google-apps.folder",
                           "parents": [show_folder]},
                    fields="id").execute()["id"]
                drive.permissions().create(fileId=parent,
                    body={"role": "reader", "type": "anyone"}, fields="id").execute()
        fname = f"freeform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        media = MediaIoBaseUpload(io.BytesIO(mp4), mimetype="video/mp4", resumable=False)
        new_file = drive.files().create(
            body={"name": fname, "parents": [parent]}, media_body=media,
            fields="id,webViewLink").execute()
        drive.permissions().create(fileId=new_file["id"],
            body={"role": "reader", "type": "anyone"}, fields="id").execute()
        drive_url = new_file["webViewLink"]
        print(f"  ✓ Drive: {drive_url}")

    # NOTE: expense is now logged inside submit_to_byteplus() at submit time,
    # so we no longer log here (avoids double-counting).
    remove_pending(task_id)

    print(f"\n=== DONE ===")
    print(f"  Local: {out_path}")
    if drive_url:
        print(f"  Drive: {drive_url}")


if __name__ == "__main__":
    main()

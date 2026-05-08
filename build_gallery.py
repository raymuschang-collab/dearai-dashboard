#!/usr/bin/env python3
"""
build_gallery.py — single-page HTML gallery for a v2.2 SOT episode sheet.

Reads from a Google Sheet (CHARACTERS / LOCATIONS / COSTUME / PROPS / EFFECTS /
Storyboard Prompts / Shotlist) and emits a self-contained HTML viewer that:

  - Has a hero with show + episode + stat counts
  - Renders character cards with iter1/iter2 thumbs
  - Renders location cards with shot-size variants
  - Renders costume / prop / effect cards
  - Renders per-set storyboard cards: shot range, assembled body,
    storyboard image iters, video iters (when present)

NO BUTTONS. Pure read-only review surface. Re-run after sheet edits to refresh.

Usage:
  python3 build_gallery.py \\
      --sheet 1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc \\
      --show "Diam Diam Aku Cinta Sajangnim" \\
      --episode "Episode 1 — Pelarian Pertama" \\
      --output sajangnim_ep01_gallery.html

  # Or run with no args — defaults to sajangnim Ep 1.

The output HTML is fully self-contained except for image URLs (lh3.googleusercontent
CDN — embedded directly so file stays small and Drive perms are respected).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import threading
import time

import gspread
from auth import get_credentials


# ===== Bible-data cache =====
# Bibles (CHARACTERS / LOCATIONS / COSTUME / PROPS / EFFECTS / Asset Library)
# rarely change — caching them aggressively at module level eliminates the
# Sheets-API 429 quota blow-up that happens when 6 episode galleries each
# rebuild from scratch (each cold build = ~8 sheet reads × 6 eps = 48 reads
# vs. the 60-reads/min/user quota; trivially throttles).
#
# After ep01's cold build warms this cache, eps 2-6 reuse the same bible data
# and only read THEIR per-episode tabs (Storyboards + Video Globals = 2 reads).
# 10-min TTL — bible edits show up on the next refresh, plenty fresh for
# day-to-day review work.
_BIBLE_TTL = 600.0
_bible_cache: dict = {}
_bible_cache_lock = threading.Lock()


# ===== Defaults — change these to point at a different episode =====
DEFAULT_SHEET   = "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc"
DEFAULT_SHOW    = "Diam Diam Aku Cinta Sajangnim"
DEFAULT_EPISODE = "Episode 1 — Pelarian Pertama"
DEFAULT_OUTPUT  = "sajangnim_ep01_gallery.html"


# ===== Drive URL helpers =====
def drive_id(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def thumb(file_id: str | None, w: int = 1000) -> str:
    return f"https://lh3.googleusercontent.com/d/{file_id}=w{w}" if file_id else ""


def view(file_id: str | None) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view" if file_id else ""


def preview(file_id: str | None) -> str:
    """Embeddable Drive preview URL — works as <iframe src> for inline video."""
    return f"https://drive.google.com/file/d/{file_id}/preview" if file_id else ""


# ===== Sheet readers =====
def read_characters(sh) -> list[dict]:
    """CHARACTERS bible — col A=Name, T=Iter1, U=Iter2, V=Status,
    Z=Image Code, AA=Video Code, AB=Audio Code (post-2026-05-08 schema).
    Returns [] if the sheet has no CHARACTERS tab (e.g. an episode sheet that
    delegates bibles to a series-level bible sheet)."""
    try:
        ws = sh.worksheet("CHARACTERS")
    except Exception:
        return []
    # Read raw cells so we can index past col_count (asset code cols may be
    # beyond what get_all_records returns). Cols A-AB = 28 columns.
    raw = ws.get("A1:AB30", value_render_option="FORMATTED_VALUE")
    if not raw or len(raw) < 2:
        return []
    headers = raw[0] + [""] * 28
    out = []
    for r in raw[1:]:
        r = r + [""] * 28
        name = (r[0] or "").strip()
        if not name:
            continue
        i1 = drive_id(r[19])  # T = Iter 1 URL (white bg)
        i2 = drive_id(r[20])  # U = Iter 2 URL (white bg)
        out.append({
            "name": name,
            "role": r[2] or "",   # C = Role / Archetype
            "age":  r[3] or "",
            "wardrobe": r[11] or "",  # L = Wardrobe
            "image_code": (r[25] or "").strip(),  # Z
            "video_code": (r[26] or "").strip(),  # AA
            "audio_code": (r[27] or "").strip(),  # AB
            "iters": [
                {"label": "Iter 1", "thumb": thumb(i1), "view": view(i1)} if i1 else None,
                {"label": "Iter 2", "thumb": thumb(i2), "view": view(i2)} if i2 else None,
            ],
        })
    return out


def read_locations(sh) -> list[dict]:
    """LOCATIONS — col A=Name, B=Shot Size, J=Iter 1, K=Iter 2 (header row 4).
    Returns [] if the sheet has no LOCATIONS tab."""
    try:
        ws = sh.worksheet("LOCATIONS")
    except Exception:
        return []
    raw = ws.get("A5:P100", value_render_option="FORMATTED_VALUE")
    by_name: dict[str, dict] = {}
    for r in raw:
        r = r + [""] * 16
        name = (r[0] or "").strip()
        if not name:
            continue
        shot_size = r[1] or "wide"
        iters = []
        for label, url in [(f"{shot_size} – iter 1", r[9]),
                           (f"{shot_size} – iter 2", r[10])]:
            fid = drive_id(url)
            if fid:
                iters.append({"label": label, "thumb": thumb(fid), "view": view(fid)})
        if name not in by_name:
            by_name[name] = {"name": name, "description": r[3] or "",
                              "asset_code": (r[15] or "").strip(),  # P = Asset Code
                              "iters": []}
        by_name[name]["iters"].extend(iters)
    return list(by_name.values())


def read_simple_bible(sh, tab: str) -> list[dict]:
    """COSTUME / PROPS / EFFECTS — col A=Name, B=Worn By, G=Iter1, H=Iter2,
    L=Asset Code (header row 5; post-2026-05-08 schema)."""
    try:
        ws = sh.worksheet(tab)
    except Exception:
        return []
    raw = ws.get("A6:L100", value_render_option="FORMATTED_VALUE")
    out = []
    for r in raw:
        r = r + [""] * 12
        name = (r[0] or "").strip()
        if not name:
            continue
        i1 = drive_id(r[6])
        i2 = drive_id(r[7])
        out.append({
            "name": name,
            "used_by": r[1] or "",
            "description": r[2] or "",
            "asset_code": (r[11] or "").strip(),  # L = Asset Code
            "iters": [
                {"label": "Iter 1", "thumb": thumb(i1), "view": view(i1)} if i1 else None,
                {"label": "Iter 2", "thumb": thumb(i2), "view": view(i2)} if i2 else None,
            ],
        })
    return out


def read_asset_library(sh) -> list[dict]:
    """Asset Library tab — rows 5+ with cols:
      A=Bible Entry Name, B=Bible Tab, C=Asset Code, D=Source URL,
      E=Asset Type, F=Status, G=Uploaded At, ..., L=Last Used.
    Returns list of dicts; skips empty rows."""
    try:
        ws = sh.worksheet("Asset Library")
    except Exception:
        return []
    raw = ws.get("A5:L500", value_render_option="FORMATTED_VALUE")
    out = []
    for r in raw:
        r = r + [""] * 12
        name = (r[0] or "").strip()
        if not name:
            continue
        out.append({
            "name": name,
            "bible_tab": r[1] or "",
            "code": r[2] or "",
            "source_url": r[3] or "",
            "type": r[4] or "",
            "status": r[5] or "",
            "uploaded_at": r[6] or "",
        })
    return out


def read_video_globals(sh) -> dict:
    """Video Prompts B1:B6 — globals shown once at top of storyboards section."""
    try:
        ws = sh.worksheet("Video Prompts")
        vals = ws.get("A1:B6", value_render_option="FORMATTED_VALUE")
    except Exception:
        return {}
    out = {}
    for r in vals:
        r = r + ["", ""]
        label = (r[0] or "").strip().lower()
        out[label] = r[1] or ""
    return {
        "camera":  out.get("camera global", ""),
        "audio":   out.get("audio/dialogue global", ""),
        "setting": out.get("setting global", ""),
    }


def read_storyboards(sh) -> list[dict]:
    """Storyboard Prompts (header row 10, data rows 11+).
    Cols: A=Set#, B=Shot Range, C=Storyboard Prompt, D=Bahasa Prompt,
    E=Drive Folder, F=Status, G=Iter1, H=Iter2, I=Error,
    J=Body, K=Bahasa Body, L=Location, M=Video Iter1, N=Video Iter2,
    O=Reviewed (TRUE/FALSE checkbox), P=Comments (free text).

    Also detects bible refs (CHARACTERS / LOCATIONS / PROPS / COSTUME /
    EFFECTS) mentioned in each set's body so the gallery can render
    @-mention pills under each storyboard for one-click asset code copy.
    """
    ws = sh.worksheet("Storyboard Prompts")
    raw = ws.get("A11:P100", value_render_option="FORMATTED_VALUE")

    # Build asset-name → (bible_tab, codes-by-type) map from Asset Library
    # so we can detect refs per set body and surface them as pills.
    al_index: dict[str, dict] = {}
    try:
        al_rows = sh.worksheet("Asset Library").get(
            "A5:F500", value_render_option="FORMATTED_VALUE")
        for r in al_rows:
            if not r or not r[0].strip():
                continue
            r = r + [""] * 6
            if r[5].strip() != "Uploaded":
                continue
            name = r[0].strip()
            entry = al_index.setdefault(name, {
                "bible_tab": r[1].strip(), "codes": {}
            })
            atype = r[4].strip().lower()
            entry["codes"].setdefault(atype, []).append(r[2].strip())
    except Exception:
        pass

    def detect_mentions(body: str) -> list[dict]:
        """Find which Asset Library entries are referenced by this body.
        Returns a sorted list of {name, bible_tab, codes_csv} pills."""
        if not body:
            return []
        body_lc = body.lower()
        hits: list[dict] = []
        seen = set()
        for name, info in al_index.items():
            if name in seen:
                continue
            matched = False
            # Whole-name match
            if re.search(r"\b" + re.escape(name) + r"\b", body, re.IGNORECASE):
                matched = True
            # Token split for character-style names
            if not matched and info["bible_tab"] == "CHARACTERS":
                for word in re.findall(r"[A-Za-z][\w\-]+", name):
                    if len(word) >= 4 and re.search(
                            r"\b" + re.escape(word) + r"\b", body, re.IGNORECASE):
                        matched = True
                        break
            # Owner-character auto-attach for COSTUME / PROPS
            if not matched and info["bible_tab"] in ("COSTUME", "PROPS"):
                m = re.search(r"\(([^)]+)\)", name)
                if m:
                    owner = m.group(1)
                    for word in re.findall(r"[A-Za-z][\w\-]+", owner):
                        if len(word) >= 4 and re.search(
                                r"\b" + re.escape(word) + r"\b", body, re.IGNORECASE):
                            matched = True
                            break
            if not matched and info["bible_tab"] in ("COSTUME", "PROPS", "EFFECTS"):
                cleaned = re.sub(r"\s*\([^)]+\)", "", name).strip().lower()
                if cleaned and len(cleaned) >= 4 and cleaned in body_lc:
                    matched = True
            if matched:
                seen.add(name)
                # Flatten codes across all media types into one CSV the user
                # can paste into a Claude prompt
                all_codes = []
                for atype in ("image", "video", "audio"):
                    all_codes.extend(info["codes"].get(atype, []))
                hits.append({
                    "name": name, "bible_tab": info["bible_tab"],
                    "codes_csv": ",".join(all_codes),
                })
        bible_order = {"CHARACTERS": 0, "COSTUME": 1, "LOCATIONS": 2,
                        "PROPS": 3, "EFFECTS": 4}
        hits.sort(key=lambda h: (bible_order.get(h["bible_tab"], 99), h["name"]))
        return hits

    out = []
    for r in raw:
        r = r + [""] * 16
        if not r[0].strip().isdigit():
            continue
        sb1 = drive_id(r[6])
        sb2 = drive_id(r[7])
        # Reviewed: TRUE/FALSE in the sheet renders as 'TRUE' / 'FALSE'
        # under FORMATTED_VALUE. Treat anything case-insensitive 'true'
        # as checked; everything else (empty, FALSE, garbage) is unchecked.
        reviewed_raw = (r[14] or "").strip().lower()
        reviewed = reviewed_raw in ("true", "yes", "1", "✓", "x", "done")
        comments = (r[15] or "").strip()
        body = r[9] or ""
        mentions = detect_mentions(body)
        out.append({
            "set": int(r[0]),
            "shots": r[1],
            "body": body,           # SP!J — body-only English
            "body_bahasa": r[10],   # SP!K
            "location": r[11],
            "status": r[5],
            "reviewed": reviewed,
            "comments": comments,
            "mentions": mentions,
            "sb_iters": [
                {"label": "Storyboard 1", "thumb": thumb(sb1), "view": view(sb1)} if sb1 else None,
                {"label": "Storyboard 2", "thumb": thumb(sb2), "view": view(sb2)} if sb2 else None,
            ],
        })
    return out


# ===== HTML rendering =====

def render_card_grid(items: list[dict], kind: str) -> str:
    """Generic bible card grid — used for chars / locations / costume / props / fx.

    Renders BytePlus asset codes alongside the bible metadata. Characters get
    three slots (image / video / audio) since each character can have multiple
    refs. Locations / costume / props / effects get a single slot.

    Click an asset code to copy it — the JS handler at the page level (see
    `copyToClipboard` in the gallery template) is the one that actually does
    the copy + flashes a tooltip."""
    cards = []
    for it in items:
        iters_html = ""
        for i in (it.get("iters") or []):
            if not i:
                continue
            iters_html += (
                f'<a class="thumb" href="{html.escape(i["view"])}" target="_blank">'
                f'<img src="{html.escape(i["thumb"])}" alt="{html.escape(i["label"])}" loading="lazy">'
                f'<span class="label">{html.escape(i["label"])}</span>'
                f'</a>'
            )
        if not iters_html:
            iters_html = '<div class="placeholder">no iter yet</div>'
        meta_lines = []
        for k in ("role", "age", "used_by", "description"):
            if it.get(k):
                meta_lines.append(f'<div class="meta-line"><b>{k}:</b> {html.escape(str(it[k]))}</div>')

        # Asset codes — character cards get 3 slots; others get 1.
        codes_html = ""
        if kind == "char":
            slots = [("img", "Image", it.get("image_code")),
                      ("vid", "Video", it.get("video_code")),
                      ("aud", "Audio", it.get("audio_code"))]
            pills = []
            for cls, label, code in slots:
                if code:
                    short = code.split("-")[-1] if "-" in code else code[-6:]
                    pills.append(
                        f'<span class="asset-pill ok" data-code="{html.escape(code)}" '
                        f'onclick="copyAssetCode(this)" title="Click to copy {html.escape(code)}">'
                        f'<b>{label}</b> · {html.escape(short)}'
                        f'</span>'
                    )
                else:
                    pills.append(
                        f'<span class="asset-pill missing" title="No {label.lower()} ref uploaded">'
                        f'<b>{label}</b> · —'
                        f'</span>'
                    )
            codes_html = f'<div class="asset-codes">{"".join(pills)}</div>'
        else:
            code = (it.get("asset_code") or "").strip()
            if code:
                short = code.split("-")[-1] if "-" in code else code[-6:]
                codes_html = (
                    f'<div class="asset-codes">'
                    f'<span class="asset-pill ok" data-code="{html.escape(code)}" '
                    f'onclick="copyAssetCode(this)" title="Click to copy {html.escape(code)}">'
                    f'<b>BytePlus</b> · {html.escape(short)}'
                    f'</span>'
                    f'</div>'
                )
            else:
                codes_html = (
                    '<div class="asset-codes">'
                    '<span class="asset-pill missing" title="Not yet uploaded to BytePlus">'
                    '<b>BytePlus</b> · —'
                    '</span>'
                    '</div>'
                )

        cards.append(f'''
        <div class="card {kind}-card">
          <div class="card-head"><h4>{html.escape(it["name"])}</h4></div>
          <div class="card-iters">{iters_html}</div>
          {codes_html}
          {"".join(meta_lines)}
        </div>''')
    return '<div class="card-grid">' + "".join(cards) + "</div>"


# Maps the section-id (storyboards/characters/...) → BytePlus bible tab name.
# Used by the Upload Asset button to pre-fill the modal's bible_tab field.
_SECTION_TO_BIBLE = {
    "characters": "CHARACTERS",
    "locations":  "LOCATIONS",
    "costume":    "COSTUME",
    "props":      "PROPS",
    "effects":    "EFFECTS",
}


def render_set_card(s: dict, video_globals: dict | None = None) -> str:
    video_globals = video_globals or {}
    # @-mention pills aggregating ALL the bible refs detected in this set's
    # body. Click any pill → copies the full asset code(s) for that name
    # to clipboard, ready for the team to paste into a Claude prompt.
    # Codes resolve LIVE from the Asset Library (no hardcoded values), so
    # asset swaps propagate automatically.
    mention_pills_html = ""
    for m in s.get("mentions") or []:
        if not m.get("codes_csv"):
            continue
        # Normalize a friendly @-handle from the canonical name
        handle = re.sub(r"\s*\([^)]+\)", "", m["name"]).strip()
        handle = re.sub(r"\s+", "-", handle).lower()
        bible_short = {
            "CHARACTERS": "char", "LOCATIONS": "loc",
            "COSTUME": "attire", "PROPS": "prop", "EFFECTS": "fx",
        }.get(m["bible_tab"], m["bible_tab"][:4].lower())
        mention_pills_html += (
            f'<span class="mention-pill {bible_short}" '
            f'data-name="{html.escape(m["name"])}" '
            f'data-codes="{html.escape(m["codes_csv"])}" '
            f'onclick="copyMentionCodes(this)" '
            f'title="Click to copy all asset codes for {html.escape(m["name"])}">'
            f'@{html.escape(handle)}'
            f'</span>'
        )
    if not mention_pills_html:
        mention_pills_html = '<span class="mention-empty">no bible refs detected in body</span>'

    # Storyboard rendering (image only; iframes + Generate buttons removed).
    # Below each storyboard, a row of @-mention pills surfaces the bible
    # refs the team needs for vidgen — each pill copies its asset code(s).
    sb_html = ""
    for idx, sb in enumerate(s["sb_iters"], start=1):
        if sb:
            file_id = drive_id(sb["view"])
            big = thumb(file_id, 2400) if file_id else sb["thumb"]
            sb_html += (
                f'<div class="sb-block">'
                f'<a class="thumb wide lb-trigger" href="{html.escape(sb["view"])}" '
                f'data-lb-src="{html.escape(big)}" data-lb-label="Set {s["set"]} · {html.escape(sb["label"])}" '
                f'data-lb-view="{html.escape(sb["view"])}" '
                f'onclick="openLightbox(this); return false;">'
                f'<img src="{html.escape(sb["thumb"])}" alt="{html.escape(sb["label"])}" loading="lazy">'
                f'<span class="label">{html.escape(sb["label"])}</span>'
                f'</a>'
                f'<div class="mention-row">{mention_pills_html}</div>'
                f'</div>'
            )
        else:
            sb_html += (
                f'<div class="sb-block">'
                f'<div class="thumb wide placeholder">storyboard pending</div>'
                f'<div class="mention-row">{mention_pills_html}</div>'
                f'</div>'
            )

    # Three-section prompt layout: VIDEO GLOBAL → LOCATION → COMBINED PROMPT.
    # Globals come from Video Prompts B1/B2/B4 (camera/audio/setting),
    # rendered the same on every set. Location is per-set (SP!L). Combined
    # prompt is the body (5 shots from Shotlist!Q via SP!J).
    global_text = "\n".join([
        s for s in (video_globals.get("camera"), video_globals.get("audio"),
                    video_globals.get("setting")) if s
    ])
    global_html  = html.escape(global_text or "(globals unset)").replace("\n", "<br>")
    location_html = html.escape(s["location"] or "Unspecified")
    body_html     = html.escape(s["body"] or "(body pending)").replace("\n", "<br>")

    prompt_html = f'''
      <div class="prompt-section">
        <div class="prompt-label">VIDEO GLOBAL</div>
        <div class="prompt-body global">{global_html}</div>
      </div>
      <div class="prompt-section">
        <div class="prompt-label">LOCATION</div>
        <div class="prompt-body location">{location_html}</div>
      </div>
      <div class="prompt-section">
        <div class="prompt-label">COMBINED PROMPT</div>
        <div class="prompt-body combined">{body_html}</div>
      </div>'''

    # Reviewed checkbox + comments — interactive review controls. State
    # persists to SP!O (TRUE/FALSE) and SP!P (free text) via /api/set-review.
    # The team can also edit these cells directly in Sheets — gallery
    # picks up the change on next refresh.
    reviewed = bool(s.get("reviewed"))
    comments = s.get("comments") or ""
    checked_attr = ' checked' if reviewed else ''
    review_html = (
        f'<label class="set-review-check" title="Mark this set as reviewed">'
        f'<input type="checkbox"{checked_attr} '
        f'onchange="onReviewToggle({s["set"]}, this)"> '
        f'<span class="set-review-label">Reviewed</span>'
        f'<span class="set-review-status" data-set="{s["set"]}"></span>'
        f'</label>'
    )
    comments_html = (
        f'<div class="set-comments">'
        f'<label class="set-comments-label" for="set-comments-{s["set"]}">'
        f'Comments / feedback</label>'
        f'<textarea id="set-comments-{s["set"]}" class="set-comments-box" '
        f'rows="2" placeholder="Add a note for the team — auto-saves on blur" '
        f'onblur="onCommentsBlur({s["set"]}, this)" '
        f'oninput="onCommentsInput({s["set"]}, this)">{html.escape(comments)}</textarea>'
        f'<span class="set-comments-status" data-set="{s["set"]}"></span>'
        f'</div>'
    )
    return f'''
    <div class="set-card{' reviewed' if reviewed else ''}" data-set="{s["set"]}" id="set-card-{s["set"]}">
      <div class="set-head">
        <div class="set-head-left">
          {review_html}
          <h3>Set {s["set"]} · shots {html.escape(s["shots"] or "—")}</h3>
        </div>
        <div class="set-meta">
          <span class="chip">{html.escape(s["status"] or "Pending")}</span>
        </div>
      </div>
      <div class="set-grid">
        <div class="set-prompt">{prompt_html}</div>
        <div class="set-storyboards">{sb_html}</div>
      </div>
      {comments_html}
    </div>'''


def render_asset_library(assets: list[dict]) -> str:
    """Asset Library tab — table grouped by bible_tab, with status badges."""
    if not assets:
        return '<div class="empty">No Asset Library entries.</div>'
    # Group by bible_tab; keep insertion order within group
    groups: dict[str, list[dict]] = {}
    for a in assets:
        groups.setdefault(a["bible_tab"] or "—", []).append(a)
    sections = []
    for tab, items in groups.items():
        rows = []
        for a in items:
            status = (a["status"] or "").lower()
            status_class = (
                "ok" if status == "uploaded"
                else "warn" if status == "pending"
                else "fail" if status in ("failed", "error")
                else "muted" if status in ("replaced", "obsolete")
                else "muted"
            )
            code = a["code"] or "—"
            type_str = a["type"] or "—"
            url_link = (
                f'<a href="{html.escape(a["source_url"])}" target="_blank" class="al-srclink">view</a>'
                if a["source_url"] else "<span class='muted'>—</span>"
            )
            # Tiny thumbnail — `thumb_url` is precomputed in build_html with
            # source_url first, then a name+bible_tab cross-reference into
            # CHARACTERS / LOCATIONS / COSTUME / PROPS / EFFECTS so Asset
            # Library rows with empty source_url cells still get an image.
            # The same lh3.googleusercontent endpoint serves poster frames
            # for video files, so type=video also renders cleanly.
            thumb_url = a.get("thumb_url") or ""
            link_target = a["source_url"] or "#"
            if thumb_url:
                thumb_html = (
                    f'<a href="{html.escape(link_target)}" target="_blank" class="al-thumb">'
                    f'<img src="{html.escape(thumb_url)}" alt="{html.escape(a["name"])}" loading="lazy" '
                    f'onerror="this.parentElement.classList.add(\'placeholder\');this.replaceWith(document.createTextNode(\'{html.escape((a["name"][:1] or "?").upper())}\'))">'
                    f'</a>'
                )
            else:
                initial = (a["name"][:1] or "?").upper()
                thumb_html = f'<span class="al-thumb placeholder" title="no thumbnail available">{html.escape(initial)}</span>'
            rows.append(f'''
              <tr>
                <td class="al-thumb-cell">{thumb_html}</td>
                <td class="al-name">{html.escape(a["name"])}</td>
                <td class="al-type">{html.escape(type_str)}</td>
                <td class="al-code"><code>{html.escape(code)}</code></td>
                <td><span class="status-badge {status_class}">{html.escape(a["status"] or "—")}</span></td>
                <td class="al-src">{url_link}</td>
              </tr>''')
        sections.append(f'''
          <div class="al-group">
            <h3 class="al-group-title">{html.escape(tab)} <span class="al-count">({len(items)})</span></h3>
            <table class="al-table">
              <thead>
                <tr>
                  <th class="al-thumb-th"></th><th>Name</th><th>Type</th><th>Asset Code (BytePlus)</th><th>Status</th><th>Source</th>
                </tr>
              </thead>
              <tbody>{"".join(rows)}</tbody>
            </table>
          </div>''')
    return "".join(sections)


def render_html(data: dict, gallery_name: str = "") -> str:
    nav = []
    sections = []
    # Storyboards first — the most-viewed section in production review.
    # Bibles follow as reference material; Asset Library last (catalog view).
    def _render_storyboards(d):
        """Storyboards panel: sticky TOC on the left + per-set cards on
        the right. TOC shows 'reviewed' state (the producer's checkbox)
        plus a 4-dot mini-bar for SB1/SB2/V1/V2 completion. Click jumps
        to that set."""
        cards_html = "".join(render_set_card(s, d.get("video_globals"))
                              for s in d["storyboards"])
        toc_items = []
        reviewed_count = 0
        for s in d["storyboards"]:
            # Video iframes + dots removed — gallery is read-only review now.
            # TOC progress bar now reflects: SB1, SB2, mentions detected, reviewed.
            sb1 = bool(s["sb_iters"][0])
            sb2 = bool(s["sb_iters"][1])
            mentions_count = len(s.get("mentions") or [])
            reviewed = bool(s.get("reviewed"))
            if reviewed:
                reviewed_count += 1
            review_mark = ('<span class="toc-review ok" title="reviewed">✓</span>'
                            if reviewed else
                            '<span class="toc-review todo" title="not yet reviewed"></span>')
            toc_items.append(
                f'<a class="toc-set{" reviewed" if reviewed else ""}" '
                f'href="#set-card-{s["set"]}" '
                f'data-set="{s["set"]}" '
                f'onclick="scrollToSet(event, {s["set"]})">'
                f'{review_mark}'
                f'<span class="toc-num">Set {s["set"]}</span>'
                f'<span class="toc-bar">'
                f'<span class="dot {"ok" if sb1 else "todo"}" title="SB1"></span>'
                f'<span class="dot {"ok" if sb2 else "todo"}" title="SB2"></span>'
                f'<span class="dot {"ok" if mentions_count else "todo"}" title="{mentions_count} bible refs"></span>'
                f'</span></a>'
            )
        toc_html = (
            f'<aside class="set-toc">'
            f'<div class="set-toc-head">SETS · {reviewed_count}/{len(d["storyboards"])} reviewed</div>'
            f'<div class="set-toc-list">{"".join(toc_items)}</div>'
            f'</aside>'
        )
        return f'<div class="storyboards-layout">{toc_html}<div class="storyboards-cards">{cards_html}</div></div>'

    section_defs = [
        ("storyboards","Storyboards", _render_storyboards),
        ("characters", "Characters", lambda d: render_card_grid(d["characters"], "char")),
        ("locations",  "Locations",  lambda d: render_card_grid(d["locations"], "loc")),
        ("costume",    "Costume",    lambda d: render_card_grid(d["costume"], "bib")),
        ("props",      "Props",      lambda d: render_card_grid(d["props"], "bib")),
        ("effects",    "Effects",    lambda d: render_card_grid(d["effects"], "bib")),
        ("assets",     "Asset Library", lambda d: render_asset_library(d.get("asset_library", []))),
    ]
    # Default-active tab: Storyboards (the most-viewed section in production review).
    default_tab = "storyboards"
    for sid, title, render_fn in section_defs:
        is_active = " active" if sid == default_tab else ""
        nav.append(f'<button class="tab{is_active}" data-tab="{sid}">{html.escape(title)}</button>')
        # Bible tabs get a "+ Upload Asset" button next to the heading. The
        # button opens a shared modal pre-filled with this bible_tab so the
        # user only picks file + name. Server-side route writes a row to
        # Asset Library + waits for BytePlus Active before refresh.
        bible_tab = _SECTION_TO_BIBLE.get(sid, "")
        upload_btn = (
            f'<button class="upload-btn" type="button" '
            f'onclick="openUploadModal(\'{html.escape(bible_tab)}\')">+ Upload Asset</button>'
            if bible_tab and gallery_name else ""
        )
        sections.append(
            f'<section class="panel{is_active}" id="{sid}">'
            f'<div class="panel-head"><h2>{html.escape(title)}</h2>{upload_btn}</div>'
            f'{render_fn(data)}</section>'
        )

    stats = data["stats"]
    stats_html = " · ".join(f"<b>{v}</b> {k}" for k, v in stats.items() if v)

    # Canonical bible-name index for the Upload modal's name combobox.
    # JSON-encoded so the JS const below picks it up directly. Empty
    # dict when bibles are unloaded (gallery_name unset).
    bible_names_json = json.dumps(data.get("bible_names_by_tab") or {})

    # Live indicator + manual refresh link. Only renders when running through
    # the Flask /gallery/<name> route (gallery_name is set); harmless for
    # standalone CLI builds (link just doesn't render).
    refresh_link = (
        f'<a class="refresh" href="/gallery/{html.escape(gallery_name)}/refresh" '
        f'title="Force-flush server cache + reload (default 30s TTL)">↻ Refresh</a>'
        if gallery_name else ""
    )
    live_chip = (
        '<span class="live-chip">LIVE · 30s cache</span>'
        if gallery_name else ""
    )
    dark_toggle = (
        '<button id="dark-toggle" class="refresh" type="button" '
        'title="Toggle dark / light mode (saved in localStorage)" '
        'onclick="toggleDarkMode()">🌙</button>'
        if gallery_name else ""
    )
    # User chip + logout link — `__GALLERY_USER_EMAIL__` is a placeholder that
    # the Flask /gallery route swaps for the current session's email at serve
    # time (so per-user identity doesn't leak into the per-gallery HTML cache).
    # When auth is OFF (env vars unset), the placeholder stays empty and the
    # whole user-chip block is hidden via the JS-based cleanup at end-of-DOM.
    user_chip = (
        '<span id="user-chip" data-email="__GALLERY_USER_EMAIL__" '
        'title="Logged in as __GALLERY_USER_EMAIL__"></span>'
        '<a class="refresh" href="/auth/logout" '
        'title="Sign out of this Google account">Log out</a>'
        if gallery_name else ""
    )

    # Episode picker — passed in from caller (dash_app/app.py). Standalone CLI
    # builds get an empty list and the dropdown doesn't render. Selecting an
    # option navigates the browser to that gallery URL.
    episodes = data.get("episodes") or []
    if episodes and gallery_name:
        opts = "".join(
            f'<option value="{html.escape(slug)}"'
            f'{" selected" if slug == gallery_name else ""}>{html.escape(label)}</option>'
            for slug, label in episodes
        )
        episode_picker = (
            f'<select class="ep-picker" onchange="if(this.value)location.href=\'/gallery/\'+this.value">'
            f'<option value="" disabled>Switch episode…</option>'
            f'{opts}</select>'
        )
    else:
        episode_picker = ""

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(data["show"])} — {html.escape(data["episode"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #fafafa; --ink: #1a1a1a; --muted: #888; --line: #e5e5e5;
    --accent: #c11647; --chip-bg: #f0f0f0;
    --card-bg: #ffffff; --code-bg: #f5f5f5; --soft-bg: #f8f8f8;
    --hero-bg: #ffffff; --table-row-hover: #fafafa;
    --prompt-global-bg: #f0f4f8; --prompt-loc-bg: #fef7ed; --prompt-loc-text: #7a3a08;
  }}
  /* Dark-mode override — toggled by adding [data-theme="dark"] to <html>.
     Aim is comfortable for night review without losing card-edge clarity. */
  html[data-theme="dark"] {{
    --bg: #0f1115; --ink: #e8e8ea; --muted: #8a8d96; --line: #2a2d36;
    --accent: #ff5577; --chip-bg: #2a2d36;
    --card-bg: #181b22; --code-bg: #14171d; --soft-bg: #14171d;
    --hero-bg: #14171d; --table-row-hover: #1d2028;
    --prompt-global-bg: #1a2230; --prompt-loc-bg: #2a1f12; --prompt-loc-text: #e8b27d;
  }}
  html[data-theme="dark"] body {{ color-scheme: dark; }}
  html[data-theme="dark"] img {{ /* slight desaturation so storyboard whites don't burn */
    filter: brightness(0.92);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg); color: var(--ink); line-height: 1.5;
  }}
  header.hero {{
    padding: 50px 40px 30px; border-bottom: 1px solid var(--line);
    background: var(--hero-bg);
  }}
  header.hero .show {{
    color: var(--muted); font-size: 12px;
    letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 10px;
  }}
  header.hero h1 {{ font-size: 34px; font-weight: 700; margin: 0 0 14px; }}
  header.hero .stats {{ font-size: 13px; color: var(--muted); }}
  header.hero .stats b {{ color: var(--ink); font-weight: 600; }}
  header.hero .live-row {{ display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }}
  .live-chip {{
    display: inline-block;
    background: #e8f5e9; color: #2e7d32;
    padding: 3px 9px; font-size: 10px; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase;
    border-radius: 4px;
  }}
  a.refresh {{
    color: var(--muted); text-decoration: none; font-size: 11px;
    border: 1px solid var(--line); border-radius: 4px;
    padding: 3px 9px; transition: all 0.15s;
  }}
  a.refresh:hover {{ color: var(--ink); border-color: var(--ink); }}
  /* User identity chip — shows logged-in Google account email. Hidden when
     auth is disabled (the [data-email=""] selector handles that). Hover the
     chip → tooltip with full email (already in title attr). */
  #user-chip {{
    display: inline-block;
    color: var(--muted); font-size: 11px;
    border: 1px solid var(--line); border-radius: 4px;
    padding: 3px 9px;
    max-width: 180px; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap;
  }}
  #user-chip[data-email=""] {{ display: none; }}
  #user-chip[data-email=""] + a.refresh {{ display: none; }}  /* hide Log out too */
  #user-chip::before {{ content: attr(data-email); }}
  /* Job-watch banner — appears at top after a Generate click, watches the
     job through /debug/jobs polling, auto-refreshes the gallery on success. */
  #job-banner {{
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    background: #1a1a1a; color: white;
    font-family: 'Inter', sans-serif; font-size: 12px;
    padding: 10px 18px; display: none;
    border-bottom: 2px solid var(--accent);
  }}
  #job-banner.error {{ background: #c11647; }}
  #job-banner.success {{ background: #2e7d32; }}
  #job-banner .close {{
    float: right; cursor: pointer; padding: 0 6px;
    color: rgba(255,255,255,0.7);
  }}
  #job-banner .close:hover {{ color: white; }}
  nav.toc {{
    position: sticky; top: 0; z-index: 10;
    background: var(--hero-bg); border-bottom: 1px solid var(--line);
    padding: 0 40px;
    display: flex; gap: 0; flex-wrap: wrap;
    justify-content: center;
  }}
  nav.toc .tab {{
    background: none; border: 0; border-bottom: 2px solid transparent;
    color: var(--muted); font-family: inherit; font-size: 13px; font-weight: 500;
    padding: 14px 18px; cursor: pointer; transition: all 0.15s;
  }}
  nav.toc .tab:hover {{ color: var(--ink); }}
  nav.toc .tab.active {{
    color: var(--ink); border-bottom-color: var(--accent); font-weight: 600;
  }}
  section.panel {{
    display: none;
    padding: 40px; max-width: 1400px; margin: 0 auto;
  }}
  section.panel.active {{ display: block; }}
  section h2 {{
    font-size: 20px; margin: 0 0 24px; padding-bottom: 8px;
    border-bottom: 2px solid var(--ink); display: inline-block;
  }}
  .card-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 18px;
  }}
  .card {{
    background: var(--card-bg); border: 1px solid var(--line); border-radius: 10px;
    padding: 14px; display: flex; flex-direction: column; gap: 10px;
  }}
  .card-head h4 {{ margin: 0; font-size: 14px; font-weight: 600; }}
  .card-iters {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
  .thumb {{
    position: relative; aspect-ratio: 1/1;
    background: #f0f0f0; border-radius: 6px; overflow: hidden;
    display: block; text-decoration: none;
  }}
  .thumb.wide {{ aspect-ratio: 16/9; }}
  .thumb img {{ width: 100%; height: 100%; object-fit: cover; }}
  .thumb .label {{
    position: absolute; bottom: 4px; left: 4px;
    background: rgba(0,0,0,0.7); color: white; padding: 2px 6px;
    font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase;
    border-radius: 3px;
  }}
  .placeholder {{
    background: var(--code-bg); border: 1px dashed var(--line); border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    color: var(--muted); font-size: 11px; text-transform: uppercase;
    aspect-ratio: 1/1;
  }}
  .thumb.wide.placeholder {{ aspect-ratio: 16/9; }}
  .meta-line {{ font-size: 11px; color: var(--muted); }}
  .meta-line b {{ color: var(--ink); }}

  /* Asset code pills — surface each bible row's BytePlus asset code(s)
     so producers can copy them directly into prompts or test calls. */
  .asset-codes {{ display: flex; gap: 4px; flex-wrap: wrap; margin: 4px 0 2px; }}
  .asset-pill {{
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 8px; border-radius: 4px;
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    letter-spacing: 0.02em;
    border: 1px solid var(--line);
    cursor: pointer; transition: all 0.12s;
    user-select: none;
  }}
  .asset-pill b {{
    font-family: -apple-system, "SF Pro Text", system-ui, sans-serif;
    font-size: 9px; letter-spacing: 0.04em; text-transform: uppercase;
  }}
  .asset-pill.ok {{ background: var(--soft-bg); color: var(--ink); }}
  .asset-pill.ok:hover {{ background: var(--chip-bg); border-color: var(--accent); }}
  .asset-pill.ok.copied {{
    background: #2e8c4f; color: white; border-color: #2e8c4f;
  }}
  .asset-pill.missing {{
    background: transparent; color: var(--muted);
    border-style: dashed; cursor: default;
  }}

  .set-card {{
    background: var(--card-bg); border: 1px solid var(--line); border-radius: 12px;
    padding: 22px; margin-bottom: 22px;
    scroll-margin-top: 80px;  /* offset for header when jumping via TOC */
  }}
  .set-card.toc-active {{
    box-shadow: 0 0 0 2px var(--accent);  /* highlight current set on TOC nav */
  }}
  .set-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; gap: 12px; flex-wrap: wrap; }}
  .set-head h3 {{ margin: 0; font-size: 16px; font-weight: 600; }}
  .set-meta {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .set-meta .chip {{
    display: inline-block; background: var(--chip-bg); color: var(--ink);
    padding: 3px 9px; font-size: 10px; letter-spacing: 0.04em;
    text-transform: uppercase; border-radius: 4px;
  }}

  /* Per-set review controls — interactive checkbox + comments box.
     The checkbox sits at the top-left of each set head; the comments
     box pins to the bottom of the card. Both auto-save to SP!O / SP!P
     so the team can also edit them directly in Sheets. */
  .set-head-left {{ display: flex; align-items: center; gap: 14px; }}
  .set-review-check {{
    display: inline-flex; align-items: center; gap: 6px;
    cursor: pointer; user-select: none;
    padding: 5px 10px; border-radius: 6px;
    border: 1px solid var(--line);
    background: var(--soft-bg);
    font-size: 12px; font-weight: 600;
    transition: background 0.15s, border-color 0.15s;
  }}
  .set-review-check:hover {{ background: var(--chip-bg); }}
  .set-review-check input[type="checkbox"] {{
    width: 16px; height: 16px; margin: 0; cursor: pointer; accent-color: #2e8c4f;
  }}
  .set-review-label {{ color: var(--ink); }}
  .set-review-status {{
    font-size: 10px; color: var(--muted); font-weight: 500;
    transition: opacity 0.2s;
  }}
  .set-review-status.saving {{ color: #b8860b; }}
  .set-review-status.saved {{ color: #2e8c4f; }}
  .set-review-status.error {{ color: var(--accent); }}

  /* When a set is marked reviewed, soften the card chrome so the team's
     eye is drawn to unreviewed sets instead. Subtle — checkbox + green
     left border tell the story without removing visual prominence. */
  .set-card.reviewed {{
    border-left: 3px solid #2e8c4f;
  }}
  .set-card.reviewed .set-review-check {{
    background: #e9f5ee; border-color: #b6dfc4; color: #1f6f3a;
  }}

  /* Comments box — auto-saves on blur. Status indicator next to the
     label flashes "Saving…" then "Saved ✓" so the team knows their
     note didn't vanish into the ether. */
  .set-comments {{
    margin-top: 16px; padding-top: 14px;
    border-top: 1px dashed var(--line);
    display: flex; flex-direction: column; gap: 4px;
  }}
  .set-comments-label {{
    font-size: 10px; letter-spacing: 0.12em; font-weight: 600;
    color: var(--muted); text-transform: uppercase;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .set-comments-box {{
    width: 100%; box-sizing: border-box;
    background: var(--soft-bg); border: 1px solid var(--line);
    border-radius: 6px; padding: 8px 10px;
    font-family: inherit; font-size: 13px; color: var(--ink);
    resize: vertical; min-height: 40px;
    transition: border-color 0.15s;
  }}
  .set-comments-box:focus {{
    outline: none; border-color: var(--accent);
    background: var(--card-bg);
  }}
  .set-comments-status {{
    font-size: 10px; color: var(--muted); font-weight: 500;
    margin-top: 2px;
  }}
  .set-comments-status.saving {{ color: #b8860b; }}
  .set-comments-status.saved {{ color: #2e8c4f; }}
  .set-comments-status.error {{ color: var(--accent); }}
  .set-comments-status.dirty {{ color: var(--muted); font-style: italic; }}

  /* Sticky TOC — review check indicator (replaces previous done-counter).
     Reviewed sets get a green ✓ at the start of their TOC entry. */
  .toc-review {{
    width: 14px; height: 14px; flex: 0 0 14px;
    border-radius: 3px; border: 1px solid var(--line);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; color: white;
    background: transparent;
  }}
  .toc-review.ok {{ background: #2e8c4f; border-color: #2e8c4f; }}
  .toc-set.reviewed .toc-num {{ text-decoration: line-through; opacity: 0.7; }}

  /* Sticky TOC — left rail in the Storyboards panel only. Compact
     numeric list with 4-dot status mini-bar per set (SB1/SB2/V1/V2).
     Snaps to top when scrolling past the panel head. */
  .storyboards-layout {{
    display: grid; grid-template-columns: minmax(180px, 220px) 1fr;
    gap: 24px; align-items: start;
  }}
  .storyboards-cards {{ min-width: 0; }}  /* prevent grid blow-out from wide content */
  .set-toc {{
    position: sticky; top: 76px;  /* clear the fixed nav.toc above */
    align-self: start;
    background: var(--card-bg); border: 1px solid var(--line); border-radius: 10px;
    padding: 12px; max-height: calc(100vh - 96px); overflow-y: auto;
  }}
  .set-toc-head {{
    font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
    color: var(--muted); text-transform: uppercase; padding: 4px 6px 8px;
    border-bottom: 1px solid var(--line); margin-bottom: 6px;
  }}
  .set-toc-list {{ display: flex; flex-direction: column; gap: 2px; }}
  .toc-set {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 6px 8px; border-radius: 6px; text-decoration: none;
    color: var(--ink); font-size: 12px; font-weight: 500;
    transition: background 0.1s;
  }}
  .toc-set:hover {{ background: var(--soft-bg); }}
  .toc-set.active {{ background: var(--chip-bg); font-weight: 700; }}
  .toc-num {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; }}
  .toc-bar {{ display: inline-flex; gap: 2px; }}
  .toc-bar .dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--soft-bg); border: 1px solid var(--line);
    display: inline-block;
  }}
  .toc-bar .dot.ok {{ background: #2e8c4f; border-color: #2e8c4f; }}

  /* Collapse the TOC under 900px viewport — the layout falls back to
     full-width cards and the producer scrolls normally. */
  @media (max-width: 900px) {{
    .storyboards-layout {{ grid-template-columns: 1fr; }}
    .set-toc {{ display: none; }}
  }}
  .set-grid {{
    display: grid; grid-template-columns: minmax(280px, 1fr) minmax(360px, 1.6fr);
    gap: 24px; align-items: start;
  }}

  /* Storyboard block — image + @-mention pill row */
  .sb-block {{ display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }}
  .mention-row {{
    display: flex; flex-wrap: wrap; gap: 4px;
    padding: 4px 0;
  }}
  .mention-empty {{ font-size: 10px; color: var(--muted); font-style: italic; padding: 2px 0; }}
  .mention-pill {{
    display: inline-flex; align-items: center;
    padding: 3px 9px; border-radius: 999px;
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    border: 1px solid var(--line); cursor: pointer;
    transition: all 0.12s; user-select: none;
    background: var(--soft-bg);
  }}
  .mention-pill:hover {{ border-color: var(--accent); background: var(--chip-bg); }}
  .mention-pill.copied {{
    background: #2e8c4f; color: white; border-color: #2e8c4f;
    font-style: normal;
  }}
  /* Color tags by bible category */
  .mention-pill.char  {{ color: #2c4f6e; background: #e6eef7; border-color: #c6dbe9; }}
  .mention-pill.attire{{ color: #6e2c5a; background: #f7e6f0; border-color: #e9c6dc; }}
  .mention-pill.loc   {{ color: #4f6e2c; background: #eef7e6; border-color: #dbe9c6; }}
  .mention-pill.prop  {{ color: #6e562c; background: #f7efe6; border-color: #e9d7c6; }}
  .mention-pill.fx    {{ color: #6e2c2c; background: #f7e6e6; border-color: #e9c6c6; }}
  .set-body {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--ink); line-height: 1.6; white-space: pre-wrap;
    background: var(--soft-bg); padding: 12px; border-radius: 6px;
    max-height: 500px; overflow-y: auto;
  }}
  .set-prompt {{ display: flex; flex-direction: column; gap: 12px; }}
  .prompt-section {{ display: flex; flex-direction: column; gap: 4px; }}
  .prompt-label {{
    font-size: 10px; letter-spacing: 0.12em; font-weight: 600;
    color: var(--accent); text-transform: uppercase;
  }}
  .prompt-body {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--ink); line-height: 1.55;
    background: var(--soft-bg); padding: 10px 12px; border-radius: 6px;
  }}
  .prompt-body.global {{ background: var(--prompt-global-bg); }}
  .prompt-body.location {{
    background: var(--prompt-loc-bg); font-weight: 500; color: var(--prompt-loc-text);
    font-family: 'Inter', sans-serif; font-size: 12px;
  }}
  .prompt-body.combined {{
    background: var(--soft-bg);
    white-space: pre-wrap;
    /* No max-height — show all shots without scroll-trap. Long sets just
       extend the card naturally. */
  }}
  .gen-btn {{
    background: #1a1a1a; color: white;
    border: 0; border-radius: 6px;
    font-family: 'Inter', sans-serif; font-size: 11px; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase;
    padding: 11px 18px; cursor: pointer;
    transition: background 0.15s;
    margin-top: 4px; align-self: flex-start;
  }}
  .gen-btn:hover {{ background: #000; }}
  .gen-btn:disabled {{ background: #888; cursor: wait; }}
  .gen-btn.success {{ background: #2e7d32; }}
  .gen-btn.error {{ background: #c11647; }}
  .set-storyboards {{ display: flex; flex-direction: column; gap: 10px; }}
  .set-videos {{ display: flex; flex-direction: column; gap: 10px; }}
  .vid-tile {{
    aspect-ratio: 9/16; background: black; border-radius: 6px; overflow: hidden;
    position: relative;
  }}
  .vid-tile iframe {{ width: 100%; height: 100%; border: 0; display: block; }}
  .vid-tile.placeholder {{
    background: var(--code-bg); border: 1px dashed var(--line);
    display: flex; align-items: center; justify-content: center;
    color: var(--muted); font-size: 10px; text-transform: uppercase;
  }}
  .vid-tile .label {{
    position: absolute; bottom: 4px; left: 4px;
    background: rgba(0,0,0,0.7); color: white; padding: 2px 6px;
    font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase;
    border-radius: 3px; pointer-events: none;
  }}
  /* Asset Library tab */
  .al-group {{ margin-bottom: 32px; }}
  .al-group-title {{
    font-size: 14px; font-weight: 600; margin: 0 0 10px;
    color: var(--ink); text-transform: uppercase; letter-spacing: 0.08em;
  }}
  .al-group-title .al-count {{ color: var(--muted); font-weight: 400; font-size: 12px; }}
  .al-table {{
    width: 100%; border-collapse: collapse;
    background: var(--card-bg); border: 1px solid var(--line); border-radius: 8px;
    overflow: hidden; font-size: 12px;
  }}
  .al-table th {{
    text-align: left; padding: 10px 14px;
    background: var(--code-bg); color: var(--muted);
    font-weight: 500; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
    border-bottom: 1px solid var(--line);
  }}
  .al-table td {{ padding: 10px 14px; border-bottom: 1px solid var(--line); vertical-align: middle; }}
  .al-table tr:last-child td {{ border-bottom: 0; }}
  .al-table tr:hover td {{ background: var(--table-row-hover); }}
  .al-thumb-th {{ width: 56px; }}
  .al-thumb-cell {{ width: 56px; padding: 6px 14px !important; }}
  .al-thumb {{
    display: inline-block; width: 40px; height: 40px;
    border-radius: 6px; overflow: hidden;
    background: var(--code-bg); border: 1px solid var(--line);
    text-align: center; line-height: 38px;
    color: var(--muted); font-weight: 600; font-size: 13px;
    text-decoration: none;
  }}
  .al-thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .al-thumb.placeholder {{ /* type=video etc — first letter of name as fallback */
    background: var(--soft-bg);
  }}
  .al-name {{ font-weight: 500; color: var(--ink); }}
  .al-type {{ color: var(--muted); text-transform: capitalize; }}
  .al-code code {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--ink); background: var(--code-bg); padding: 2px 6px; border-radius: 3px;
  }}
  .al-srclink {{ color: var(--accent); text-decoration: none; font-size: 11px; }}
  .al-srclink:hover {{ text-decoration: underline; }}
  .status-badge {{
    display: inline-block; padding: 3px 9px; border-radius: 4px;
    font-size: 10px; letter-spacing: 0.05em; text-transform: uppercase; font-weight: 600;
  }}
  .status-badge.ok    {{ background: #e8f5e9; color: #2e7d32; }}
  .status-badge.warn  {{ background: #fff3e0; color: #e65100; }}
  .status-badge.fail  {{ background: #fde8ec; color: #c11647; }}
  .status-badge.muted {{ background: var(--chip-bg); color: var(--muted); }}
  html[data-theme="dark"] .status-badge.ok    {{ background: #1f3a23; color: #7fc788; }}
  html[data-theme="dark"] .status-badge.warn  {{ background: #3d2a13; color: #ffb868; }}
  html[data-theme="dark"] .status-badge.fail  {{ background: #3a1822; color: #ff7a90; }}
  .empty {{ color: var(--muted); font-style: italic; padding: 20px; }}

  /* Episode picker — sits next to ↻ Refresh in the hero. Native <select>
     styled to match the refresh-link chip so the row reads as one toolbar. */
  .ep-picker {{
    color: var(--muted); background: var(--card-bg);
    border: 1px solid var(--line); border-radius: 4px;
    font: inherit; font-size: 11px;
    padding: 3px 9px; cursor: pointer;
    transition: all 0.15s;
  }}
  .ep-picker:hover {{ color: var(--ink); border-color: var(--ink); }}

  /* Lightbox overlay — opens at ~90vw × 85vh (NOT fullscreen). Hidden by
     default; click-outside / Esc / × button all close. */
  #lightbox {{
    display: none;
    position: fixed; inset: 0; z-index: 200;
    background: rgba(0, 0, 0, 0.85);
    align-items: center; justify-content: center;
    padding: 5vh 5vw;
  }}
  #lightbox.open {{ display: flex; }}
  #lightbox .lb-frame {{
    position: relative;
    max-width: 90vw; max-height: 85vh;
    background: var(--card-bg); border-radius: 8px;
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6);
    display: flex; flex-direction: column;
  }}
  #lightbox img {{
    display: block; max-width: 100%; max-height: calc(85vh - 50px);
    width: auto; height: auto; object-fit: contain;
    border-radius: 8px 8px 0 0;
    /* Light grid behind the image so transparent PNGs read correctly */
    background-image: linear-gradient(45deg, #ddd 25%, transparent 25%), linear-gradient(-45deg, #ddd 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #ddd 75%), linear-gradient(-45deg, transparent 75%, #ddd 75%);
    background-size: 16px 16px;
    background-position: 0 0, 0 8px, 8px -8px, -8px 0;
  }}
  html[data-theme="dark"] #lightbox img {{
    filter: brightness(0.95);
  }}
  #lightbox .lb-meta {{
    padding: 12px 16px; border-top: 1px solid var(--line);
    display: flex; justify-content: space-between; align-items: center;
    color: var(--muted); font-size: 12px;
  }}
  #lightbox .lb-meta #lb-label {{ color: var(--ink); font-weight: 500; }}
  #lightbox .lb-meta a {{ color: var(--accent); text-decoration: none; }}
  #lightbox .lb-meta a:hover {{ text-decoration: underline; }}
  #lightbox .lb-close {{
    position: absolute; top: -16px; right: -16px; z-index: 1;
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--card-bg); border: 1px solid var(--line);
    color: var(--ink); font-size: 18px; line-height: 1;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }}
  #lightbox .lb-close:hover {{ background: var(--accent); color: white; border-color: var(--accent); }}

  /* Bible-section header — h2 + Upload button on one row */
  .panel-head {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px;
  }}
  .panel-head h2 {{ margin-bottom: 0; }}
  .upload-btn {{
    background: var(--card-bg); color: var(--ink);
    border: 1px solid var(--ink); border-radius: 6px;
    font-family: 'Inter', sans-serif; font-size: 11px; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase;
    padding: 9px 16px; cursor: pointer;
    transition: all 0.15s;
  }}
  .upload-btn:hover {{ background: var(--ink); color: var(--card-bg); }}
  /* Upload modal — same overlay pattern as lightbox but smaller, form-shaped */
  #upload-modal {{
    display: none;
    position: fixed; inset: 0; z-index: 200;
    background: rgba(0, 0, 0, 0.85);
    align-items: center; justify-content: center;
  }}
  #upload-modal.open {{ display: flex; }}
  #upload-modal .ul-frame {{
    position: relative;
    width: min(440px, 90vw);
    background: var(--card-bg); color: var(--ink);
    border-radius: 10px;
    padding: 28px 28px 22px;
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6);
  }}
  #upload-modal h3 {{
    margin: 0 0 18px; font-size: 16px; font-weight: 600;
    border-bottom: 2px solid var(--ink); padding-bottom: 8px; display: inline-block;
  }}
  .ul-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
  .ul-lbl {{
    flex: 0 0 70px; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted);
  }}
  .ul-row input[type=text], .ul-row select, .ul-row input[type=file] {{
    flex: 1; padding: 8px 10px;
    background: var(--soft-bg); color: var(--ink);
    border: 1px solid var(--line); border-radius: 4px;
    font: inherit; font-size: 12px;
  }}
  .ul-row input[readonly] {{ color: var(--muted); cursor: default; }}
  .ul-actions {{
    display: flex; justify-content: flex-end; gap: 10px;
    margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--line);
  }}
  .ul-cancel {{
    background: none; border: 1px solid var(--line);
    color: var(--muted); border-radius: 4px;
    font: inherit; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
    padding: 9px 16px; cursor: pointer;
  }}
  .ul-cancel:hover {{ color: var(--ink); border-color: var(--ink); }}
  .ul-error {{
    color: var(--accent); font-size: 12px; margin-top: 10px;
    min-height: 16px;
  }}
  .ul-hint {{
    color: var(--muted); font-size: 11px;
    padding: 0 0 0 82px; /* align with the inputs (70px label + 12px gap) */
    margin-top: -8px; margin-bottom: 8px;
    min-height: 14px;
  }}
  .ul-hint b {{ color: var(--ink); font-weight: 500; }}

  footer {{
    text-align: center; color: var(--muted); font-size: 11px;
    padding: 30px; border-top: 1px solid var(--line); margin-top: 40px;
  }}
</style>
</head>
<body>
<div id="job-banner">
  <span class="close" onclick="this.parentElement.style.display='none'">×</span>
  <span id="job-banner-text">Watching job…</span>
</div>
<!-- Lightbox overlay — click outside / press Esc / click × to close.
     Sized to ~90vw × 85vh so it's expanded but not fullscreen, keeping
     a frame of dark backdrop visible around the image. -->
<div id="lightbox" onclick="closeLightboxIfBackdrop(event)">
  <div class="lb-frame">
    <button class="lb-close" type="button" onclick="closeLightbox()" aria-label="Close">×</button>
    <img id="lb-img" alt="">
    <div class="lb-meta">
      <span id="lb-label"></span>
      <a id="lb-view" href="#" target="_blank" class="lb-view-link">View original on Drive ↗</a>
    </div>
  </div>
</div>
<!-- Upload Asset modal — opened by the "+ Upload Asset" button on each
     bible tab. Single shared modal; bible_tab is pre-filled per click.
     Submit fires /api/upload-asset (multipart) → returns job_id → existing
     watchJobs() polls /debug/jobs and reloads the gallery on Active. -->
<div id="upload-modal" onclick="closeUploadIfBackdrop(event)">
  <div class="ul-frame">
    <button class="lb-close" type="button" onclick="closeUploadModal()" aria-label="Close">×</button>
    <h3 id="ul-title">Upload Asset</h3>
    <form id="ul-form" onsubmit="submitUpload(event)">
      <label class="ul-row">
        <span class="ul-lbl">Bible</span>
        <input type="text" name="bible_tab" id="ul-bible" readonly required>
      </label>
      <label class="ul-row">
        <span class="ul-lbl">Name</span>
        <input type="text" name="name" id="ul-name" list="ul-name-list" required
               autocomplete="off"
               placeholder="Pick existing or type new">
        <datalist id="ul-name-list"></datalist>
      </label>
      <div class="ul-hint" id="ul-name-hint"></div>
      <label class="ul-row">
        <span class="ul-lbl">Type</span>
        <select name="asset_type" id="ul-type" required>
          <option value="Image" selected>Image</option>
          <option value="Video">Video</option>
        </select>
      </label>
      <label class="ul-row">
        <span class="ul-lbl">File</span>
        <input type="file" name="file" id="ul-file" accept="image/*,video/*" required>
      </label>
      <div class="ul-actions">
        <button type="button" class="ul-cancel" onclick="closeUploadModal()">Cancel</button>
        <button type="submit" id="ul-submit" class="gen-btn">Upload</button>
      </div>
      <div id="ul-error" class="ul-error"></div>
    </form>
  </div>
</div>
<header class="hero">
  <div class="live-row">{live_chip}{refresh_link}{dark_toggle}{episode_picker}{user_chip}</div>
  <div class="show">{html.escape(data["show"])}</div>
  <h1>{html.escape(data["episode"])}</h1>
  <div class="stats">{stats_html}</div>
</header>
<nav class="toc">{"".join(nav)}</nav>
{"".join(sections)}
<footer>Production review · regenerate with <code>python3 build_gallery.py</code></footer>
<script>
  // Tab switcher — single-section view. Click a tab → hide siblings, show target.
  // Hash-aware: opens the panel matching the URL hash on load if present.
  // Pinned-restore: if sessionStorage has a saved tab from a job-triggered
  // refresh, that wins over the URL hash.
  let _activate;  // hoisted for use by the watcher below
  (function() {{
    const tabs = document.querySelectorAll('nav.toc .tab');
    const panels = document.querySelectorAll('section.panel');
    function activate(id, suppressScroll) {{
      tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === id));
      panels.forEach(p => p.classList.toggle('active', p.id === id));
      if (history.replaceState) history.replaceState(null, '', '#' + id);
      if (!suppressScroll) window.scrollTo({{top: 0, behavior: 'instant'}});
    }}
    _activate = activate;
    tabs.forEach(t => t.addEventListener('click', () => activate(t.dataset.tab)));
    // Restore-from-refresh: if we just came back from /gallery/<name>/refresh
    // after a job watcher finished, restore tab + scroll without resetting.
    const savedTab = sessionStorage.getItem('gallery_active_tab');
    const savedScroll = sessionStorage.getItem('gallery_scroll_y');
    if (savedTab && document.getElementById(savedTab)) {{
      activate(savedTab, true);
      sessionStorage.removeItem('gallery_active_tab');
    }} else {{
      // Honor URL hash on first load
      const hash = location.hash.replace(/^#/, '');
      if (hash && document.getElementById(hash)) activate(hash);
    }}
    if (savedScroll) {{
      requestAnimationFrame(() => {{
        window.scrollTo({{top: parseInt(savedScroll, 10), behavior: 'instant'}});
        sessionStorage.removeItem('gallery_scroll_y');
      }});
    }}
  }})();

  // Sheet-status fallback (Codex Option B). Asks the server to read the
  // Storyboard Prompts target cell for each job_id directly. Used by
  // watchJobs() when /debug/jobs doesn't flip a job to "done" — happens
  // when Render redeploys mid-vidgen and kills the parent worker before
  // its status writeback. Returns a results map keyed by job_id, or null.
  async function sheetCheckFallback(jobIds) {{
    try {{
      const r = await fetch('/api/jobs-sheet-check', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ids: jobIds}}),
      }});
      const data = await r.json();
      return data.results || null;
    }} catch (e) {{
      return null;
    }}
  }}

  // Job watcher — after a Generate click, polls /debug/jobs every 8s until
  // the watched job(s) finish. On success, saves scroll+tab to sessionStorage
  // and force-refreshes via /gallery/<name>/refresh (which 302s back here).
  // On failure, leaves the banner up so the user can read the error.
  function watchJobs(jobIds, label) {{
    if (!Array.isArray(jobIds)) jobIds = [jobIds];
    const banner = document.getElementById('job-banner');
    const text = document.getElementById('job-banner-text');
    banner.className = '';  // reset state classes
    banner.style.display = 'block';
    text.textContent = `${{label}} queued — polling for completion…`;
    const remaining = new Set(jobIds);
    const failed = [];
    let attempts = 0;
    const MAX_ATTEMPTS = 90;  // 90 × 8s = 12 min cap; vidgen typically lands in 3-5 min
    // Option B fallback — when Render redeploys mid-job, the parent worker
    // dies before writing status=done, so /debug/jobs never flips. Every
    // FALLBACK_INTERVAL ticks, ALSO check the target sheet cell directly:
    // if a Drive URL is there, the job clearly succeeded — the runtime
    // just never recorded it. Eliminates the false "watcher gave up" red
    // banner on jobs that actually completed.
    const FALLBACK_INTERVAL = 5;  // every 5 ticks = ~40s — quota-friendly
    let resumeFired = false;
    async function tick() {{
      attempts++;
      if (attempts > MAX_ATTEMPTS) {{
        // Last-chance flow when MAX_ATTEMPTS hits:
        //   1. Sheet-check fallback (URL landed but parent died after writeback)
        //   2. /api/vidgen-resume (URL didn't land — BytePlus task succeeded
        //      but parent died BEFORE writeback; resume picks up the
        //      task_id from .byteplus_pending.json and completes it)
        //   3. Wait one more interval, sheet-check again
        //   4. Only then show red banner
        const sweep = await sheetCheckFallback(Array.from(remaining));
        if (sweep && Object.values(sweep).some(v => v && v.done)) {{
          for (const [id, v] of Object.entries(sweep)) {{
            if (v && v.done) remaining.delete(id);
          }}
          if (remaining.size === 0) {{
            text.textContent = `${{label}} complete (sheet fallback) — refreshing…`;
            banner.classList.add('success');
            sessionStorage.setItem('gallery_scroll_y', String(window.scrollY));
            const activeTab = document.querySelector('nav.toc .tab.active');
            if (activeTab) sessionStorage.setItem('gallery_active_tab', activeTab.dataset.tab);
            const gallery = location.pathname.split('/').filter(s => s).pop();
            location.href = `/gallery/${{gallery}}/refresh`;
            return;
          }}
        }}
        if (!resumeFired) {{
          // Try crash recovery — fire vidgen-resume, then give it a
          // window to finish before declaring failure.
          resumeFired = true;
          text.textContent = `${{label}} — running crash recovery (vidgen-resume)…`;
          try {{ await fetch('/api/vidgen-resume', {{method: 'POST'}}); }} catch (e) {{}}
          attempts = MAX_ATTEMPTS - 30;  // give it 30 more polls (~4 min)
          setTimeout(tick, 8000);
          return;
        }}
        text.textContent = `${{label}} — watcher gave up after ${{MAX_ATTEMPTS}} polls + recovery attempt. Check /debug/jobs manually then click ↻ Refresh.`;
        banner.classList.add('error');
        return;
      }}
      try {{
        // n=200 so jobs don't fall off /debug/jobs's default top-10 list
        // when the team fires multiple things during the 12-min watch window.
        const r = await fetch('/debug/jobs?n=200&only=all', {{cache: 'no-store'}});
        const data = await r.json();
        const byId = {{}};
        for (const j of (data.jobs || [])) byId[j.id] = j;
        for (const id of Array.from(remaining)) {{
          const j = byId[id];
          if (!j) continue;
          // run_bg writes "done"; some other paths write "succeeded" — accept both.
          if (j.status === 'done' || j.status === 'succeeded') remaining.delete(id);
          else if (j.status === 'failed' || j.status === 'errored') {{
            remaining.delete(id);
            failed.push(id);
          }}
        }}
        // Periodic sheet-check fallback — only fires for vidgen jobs the
        // /debug/jobs path hasn't already resolved. Server batches reads
        // per sheet so cost is one Sheets API call regardless of fan-out.
        if (remaining.size > 0 && attempts % FALLBACK_INTERVAL === 0) {{
          const sweep = await sheetCheckFallback(Array.from(remaining));
          if (sweep) {{
            for (const [id, v] of Object.entries(sweep)) {{
              if (v && v.done) remaining.delete(id);
            }}
          }}
        }}
        if (remaining.size === 0) {{
          if (failed.length === 0) {{
            // All succeeded — save UI state, force fresh build, reload
            text.textContent = `${{label}} complete — refreshing gallery…`;
            banner.classList.add('success');
            sessionStorage.setItem('gallery_scroll_y', String(window.scrollY));
            const activeTab = document.querySelector('nav.toc .tab.active');
            if (activeTab) sessionStorage.setItem('gallery_active_tab', activeTab.dataset.tab);
            const gallery = location.pathname.split('/').filter(s => s).pop();
            location.href = `/gallery/${{gallery}}/refresh`;
            return;
          }} else {{
            text.textContent = `${{label}} failed — see /debug/jobs for log (${{failed.join(', ')}})`;
            banner.classList.add('error');
            return;
          }}
        }}
        const status = Object.values(byId)
          .filter(j => jobIds.includes(j.id))
          .map(j => `${{j.id}}=${{j.status}}`)
          .join(', ');
        text.textContent = `${{label}} — ${{status}} (poll #${{attempts}})`;
      }} catch (e) {{
        text.textContent = `${{label}} — poll failed (${{e.message}}); retrying`;
      }}
      setTimeout(tick, 8000);
    }}
    tick();
  }}

  // Generic gen-button handler — fires the named API endpoint and cycles
  // button state. On success, hands the returned job_id(s) to watchJobs,
  // which polls /debug/jobs and auto-refreshes the gallery on completion
  // (preserving scroll position + active tab via sessionStorage).
  async function _fireGen(endpoint, body, btn, queueMins, label) {{
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Firing…';
    btn.classList.remove('success', 'error');
    try {{
      const r = await fetch(endpoint, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(body),
      }});
      const data = await r.json();
      if (r.ok && data.ok) {{
        btn.classList.add('success');
        btn.textContent = `Queued · ${{data.job_id}} · auto-refresh on completion`;
        // job_ids[] (vidgen returns 2) takes precedence; fall back to job_id (single)
        const ids = data.job_ids || [data.job_id];
        watchJobs(ids, label);
        setTimeout(() => {{ btn.disabled = false; btn.textContent = orig; btn.classList.remove('success'); }}, queueMins * 60 * 1000);
      }} else {{
        btn.classList.add('error');
        btn.textContent = 'Failed: ' + (data.error || 'unknown');
        setTimeout(() => {{ btn.disabled = false; btn.textContent = orig; btn.classList.remove('error'); }}, 8000);
      }}
    }} catch (e) {{
      btn.classList.add('error');
      btn.textContent = 'Error: ' + e.message;
      setTimeout(() => {{ btn.disabled = false; btn.textContent = orig; btn.classList.remove('error'); }}, 8000);
    }}
  }}

  // ===== Lightbox =====
  // Click a storyboard thumb → expanded view at 90vw × 85vh (not fullscreen).
  // Esc, click on backdrop, or click × all close.
  function openLightbox(el) {{
    const lb = document.getElementById('lightbox');
    const img = document.getElementById('lb-img');
    const label = document.getElementById('lb-label');
    const view = document.getElementById('lb-view');
    img.src = el.dataset.lbSrc;
    label.textContent = el.dataset.lbLabel || '';
    view.href = el.dataset.lbView || '#';
    lb.classList.add('open');
    document.body.style.overflow = 'hidden';
  }}
  function closeLightbox() {{
    document.getElementById('lightbox').classList.remove('open');
    document.body.style.overflow = '';
  }}
  function closeLightboxIfBackdrop(e) {{
    // Only close when clicking the dim backdrop, not the image / frame
    if (e.target.id === 'lightbox') closeLightbox();
  }}
  document.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape') closeLightbox();
  }});

  // ===== Dark mode =====
  // Toggle stored in localStorage so it persists across reloads + episodes.
  // Apply on page load BEFORE first paint (the inline-script runs early).
  function applyDarkMode(on) {{
    document.documentElement.setAttribute('data-theme', on ? 'dark' : 'light');
    const btn = document.getElementById('dark-toggle');
    if (btn) btn.textContent = on ? '☀' : '🌙';
  }}
  function toggleDarkMode() {{
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    applyDarkMode(!isDark);
    try {{ localStorage.setItem('gallery_dark_mode', !isDark ? '1' : '0'); }} catch (e) {{}}
  }}
  // Initial paint: read saved pref or fall back to OS preference
  (function() {{
    let saved = null;
    try {{ saved = localStorage.getItem('gallery_dark_mode'); }} catch (e) {{}}
    let on;
    if (saved === '1') on = true;
    else if (saved === '0') on = false;
    else on = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyDarkMode(on);
  }})();

  // ===== Upload Asset modal =====
  // Open from any bible tab's "+ Upload Asset" button. The bible tab name
  // is pre-filled from the click; user picks file + name + type. Submit
  // multipart-fetch /api/upload-asset → returns job_id → watchJobs reloads
  // gallery on Active. The bible read cache is flushed server-side so the
  // new row shows up on the auto-refresh.
  // Canonical bible-name index, server-injected. Keyed by upper-case bible tab.
  // Used to populate the Name combobox so users pick existing canonical entries
  // rather than creating typo-ghosts. Free-text still works for genuinely new
  // entries — the datalist is suggestion-only, not a hard restriction.
  const BIBLE_NAMES = {bible_names_json};

  function openUploadModal(bibleTab) {{
    const m = document.getElementById('upload-modal');
    document.getElementById('ul-bible').value = bibleTab;
    document.getElementById('ul-name').value = '';
    document.getElementById('ul-file').value = '';
    document.getElementById('ul-error').textContent = '';
    document.getElementById('ul-submit').disabled = false;
    document.getElementById('ul-submit').textContent = 'Upload';
    // Populate the datalist with this bible's canonical names
    const dl = document.getElementById('ul-name-list');
    const names = (BIBLE_NAMES[bibleTab] || []);
    dl.innerHTML = names.map(n => `<option value="${{n.replace(/"/g, '&quot;')}}">`).join('');
    const hint = document.getElementById('ul-name-hint');
    if (names.length) {{
      hint.innerHTML = `<b>${{names.length}}</b> existing in ${{bibleTab}} — click the field to pick, or type a new one.`;
    }} else {{
      hint.innerHTML = `No existing ${{bibleTab}} entries — type a new name.`;
    }}
    m.classList.add('open');
    document.body.style.overflow = 'hidden';
    setTimeout(() => document.getElementById('ul-name').focus(), 50);
  }}
  function closeUploadModal() {{
    document.getElementById('upload-modal').classList.remove('open');
    document.body.style.overflow = '';
  }}
  function closeUploadIfBackdrop(e) {{
    if (e.target.id === 'upload-modal') closeUploadModal();
  }}
  async function submitUpload(ev) {{
    ev.preventDefault();
    const form = document.getElementById('ul-form');
    const errEl = document.getElementById('ul-error');
    const submitBtn = document.getElementById('ul-submit');
    errEl.textContent = '';
    const fd = new FormData(form);
    const gallery = location.pathname.split('/').filter(s => s).pop();
    fd.append('gallery', gallery);
    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading…';
    try {{
      const r = await fetch('/api/upload-asset', {{method: 'POST', body: fd}});
      const data = await r.json();
      if (r.ok && data.ok) {{
        const name = fd.get('name');
        const tab = fd.get('bible_tab');
        closeUploadModal();
        watchJobs([data.job_id], `Upload ${{tab}}/${{name}}`);
      }} else {{
        errEl.textContent = 'Failed: ' + (data.error || ('HTTP ' + r.status));
        submitBtn.disabled = false;
        submitBtn.textContent = 'Upload';
      }}
    }} catch (e) {{
      errEl.textContent = 'Error: ' + e.message;
      submitBtn.disabled = false;
      submitBtn.textContent = 'Upload';
    }}
  }}

  // Click-to-copy on @-mention pills under each storyboard. Pulls the
  // canonical name + ALL associated BytePlus asset codes (image + video
  // + audio for chars; single image for everything else) from the pill's
  // data-codes attr, copies a structured snippet to clipboard, flashes
  // green for 1.5s. The team pastes the result directly into a Claude
  // prompt (`@tara → asset-...sx786, asset-...tkskm, asset-...5vhnf`).
  function copyMentionCodes(el) {{
    const name = el.dataset.name;
    const codes = el.dataset.codes;
    if (!codes) return;
    const snippet = `${{name}}: ${{codes}}`;
    navigator.clipboard.writeText(snippet).then(() => {{
      el.classList.add('copied');
      const orig = el.textContent;
      el.textContent = '✓ copied';
      setTimeout(() => {{
        el.classList.remove('copied');
        el.textContent = orig;
      }}, 1500);
    }}).catch(() => alert('Copy failed: ' + snippet));
  }}

  // Click-to-copy on bible asset code pills. Pulls the full code from the
  // pill's data-code, copies to clipboard, flashes a green confirmation.
  // The pill UI shows only the last segment (e.g. "k4rrz") to stay compact;
  // copying gives the full asset-... id needed for vidgen ref attachment.
  function copyAssetCode(el) {{
    const code = el.dataset.code;
    if (!code) return;
    navigator.clipboard.writeText(code).then(() => {{
      el.classList.add('copied');
      const orig = el.innerHTML;
      el.innerHTML = '<b>Copied</b> · ' + code.split('-').pop();
      setTimeout(() => {{
        el.classList.remove('copied');
        el.innerHTML = orig;
      }}, 1200);
    }}).catch(() => {{
      alert('Code: ' + code);
    }});
  }}

  // Storyboard gen — fal.ai gpt-image-2, ~2-3 min for 2 iters
  function fireStoryboard(setN, btn) {{
    const gallery = location.pathname.split('/').filter(s => s).pop();
    return _fireGen('/api/storyboard', {{set: setN, gallery: gallery}}, btn, 5,
                    `Storyboard set ${{setN}}`);
  }}

  // Vidgen V1/V2 — BytePlus Seedance 2.0. Each click fires BOTH slots; the
  // server returns job_ids:[v1,v2] and watchJobs waits for both before reload.
  function fireVidgen(setN, slot, btn) {{
    const gallery = location.pathname.split('/').filter(s => s).pop();
    return _fireGen('/api/vidgen', {{set: setN, slot: slot, gallery: gallery}}, btn, 8,
                    `Video set ${{setN}} (V1+V2)`);
  }}

  // ===== Per-set review controls =====
  // Reviewed checkbox + comments save handlers. POST to /api/set-review
  // which writes SP!O (TRUE/FALSE) + SP!P (free text). Status indicator
  // flashes "Saving…" then "Saved ✓" so the user knows their change
  // landed. On error, the indicator turns red and the user can retry.
  //
  // Comments use a debounce on input (visual "edited" hint), and the
  // actual save fires on blur — keeps the API call rate sane while
  // the user is typing.
  async function _postReview(setN, payload) {{
    const gallery = location.pathname.split('/').filter(s => s).pop();
    payload = Object.assign({{set: setN, gallery: gallery}}, payload);
    const r = await fetch('/api/set-review', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(payload),
    }});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    if (!data.ok) throw new Error(data.error || 'unknown');
    return data;
  }}

  function _setStatus(el, cls, text) {{
    if (!el) return;
    el.className = el.className.split(' ').filter(c =>
      !['saving','saved','error','dirty'].includes(c)).join(' ');
    if (cls) el.classList.add(cls);
    el.textContent = text || '';
  }}

  async function onReviewToggle(setN, checkbox) {{
    const status = document.querySelector(`.set-review-status[data-set="${{setN}}"]`);
    const card = document.getElementById('set-card-' + setN);
    const tocEntry = document.querySelector(`.toc-set[data-set="${{setN}}"]`);
    _setStatus(status, 'saving', 'Saving…');
    try {{
      await _postReview(setN, {{reviewed: checkbox.checked}});
      _setStatus(status, 'saved', 'Saved ✓');
      if (card) card.classList.toggle('reviewed', checkbox.checked);
      if (tocEntry) {{
        tocEntry.classList.toggle('reviewed', checkbox.checked);
        const mark = tocEntry.querySelector('.toc-review');
        if (mark) {{
          mark.classList.toggle('ok', checkbox.checked);
          mark.classList.toggle('todo', !checkbox.checked);
          mark.textContent = checkbox.checked ? '✓' : '';
          mark.title = checkbox.checked ? 'reviewed' : 'not yet reviewed';
        }}
      }}
      // Update the "N/M reviewed" counter in the TOC head
      const head = document.querySelector('.set-toc-head');
      if (head) {{
        const all = document.querySelectorAll('.toc-set').length;
        const done = document.querySelectorAll('.toc-set.reviewed').length;
        head.textContent = `SETS · ${{done}}/${{all}} reviewed`;
      }}
      setTimeout(() => _setStatus(status, '', ''), 2000);
    }} catch (e) {{
      _setStatus(status, 'error', 'Error: ' + e.message);
      // Revert the checkbox to match server state
      checkbox.checked = !checkbox.checked;
    }}
  }}

  // Track the last-saved comments string per set so blur knows whether
  // anything actually changed (skip the API call for no-op blurs).
  const _lastSavedComments = {{}};
  document.querySelectorAll('.set-comments-box').forEach(el => {{
    const setN = el.id.replace('set-comments-', '');
    _lastSavedComments[setN] = el.value;
  }});

  function onCommentsInput(setN, textarea) {{
    const status = document.querySelector(`.set-comments-status[data-set="${{setN}}"]`);
    const last = _lastSavedComments[setN] || '';
    if (textarea.value !== last) {{
      _setStatus(status, 'dirty', 'unsaved — click out to save');
    }} else {{
      _setStatus(status, '', '');
    }}
  }}

  async function onCommentsBlur(setN, textarea) {{
    const status = document.querySelector(`.set-comments-status[data-set="${{setN}}"]`);
    const last = _lastSavedComments[setN] || '';
    if (textarea.value === last) {{
      _setStatus(status, '', '');
      return;
    }}
    _setStatus(status, 'saving', 'Saving…');
    try {{
      await _postReview(setN, {{comments: textarea.value}});
      _lastSavedComments[setN] = textarea.value;
      _setStatus(status, 'saved', 'Saved ✓');
      setTimeout(() => _setStatus(status, '', ''), 2000);
    }} catch (e) {{
      _setStatus(status, 'error', 'Error: ' + e.message);
    }}
  }}

  // ===== Storyboards-tab sticky TOC =====
  // Click handler for TOC entries — smooth-scroll to the matching set
  // card and brief-highlight it so the producer's eye lands on the new
  // location. Uses scrollIntoView with `block: start` + a 60-px CSS
  // scroll-margin so it clears the fixed nav bar.
  function scrollToSet(ev, setN) {{
    if (ev) ev.preventDefault();
    const card = document.getElementById('set-card-' + setN);
    if (!card) return;
    card.scrollIntoView({{behavior: 'smooth', block: 'start'}});
    document.querySelectorAll('.set-card.toc-active').forEach(el =>
      el.classList.remove('toc-active'));
    card.classList.add('toc-active');
    setTimeout(() => card.classList.remove('toc-active'), 1500);
  }}

  // IntersectionObserver — tracks which set is currently in the viewport
  // and highlights its TOC entry. Fires on tab-switch + scroll. Threshold
  // 0.3 means a card needs ~30% visible to claim "active" — feels right
  // when scrolling slowly past large cards.
  (function setupSetTocObserver() {{
    const tocLinks = document.querySelectorAll('.set-toc .toc-set');
    if (!tocLinks.length) return;
    const tocByNum = {{}};
    tocLinks.forEach(a => {{ tocByNum[a.dataset.set] = a; }});
    const observer = new IntersectionObserver(entries => {{
      // Pick the entry closest to the top that is currently intersecting.
      let active = null;
      let bestTop = Infinity;
      entries.forEach(e => {{
        if (!e.isIntersecting) return;
        if (e.boundingClientRect.top < bestTop) {{
          bestTop = e.boundingClientRect.top;
          active = e.target;
        }}
      }});
      if (!active) return;
      const setN = active.dataset.set;
      Object.values(tocByNum).forEach(a => a.classList.remove('active'));
      const a = tocByNum[setN];
      if (a) a.classList.add('active');
    }}, {{ threshold: [0.3], rootMargin: '-80px 0px -40% 0px' }});
    document.querySelectorAll('.storyboards-cards .set-card').forEach(card => {{
      observer.observe(card);
    }});
  }})();
</script>
</body>
</html>'''


def build_html(sheet_id: str, show: str, episode: str,
               gallery_name: str = "", bible_sheet_id: str | None = None,
               episodes: list[tuple[str, str]] | None = None,
               verbose: bool = False) -> str:
    """Read a sheet end-to-end and return the rendered gallery HTML as a string.

    Used both by the CLI (main) and by the Dash app's live /gallery route.
    Reusable from any caller — pure function, no side effects on disk.

    `gallery_name` is the URL-safe slug (e.g. "sajangnim_ep01") that the Flask
    route uses to look up this gallery; passing it enables the LIVE chip + the
    /gallery/<name>/refresh button + the auto-refresh-on-job-complete watcher.
    Standalone CLI builds (where the HTML is opened off disk) leave it blank
    so those features render as no-ops.

    `bible_sheet_id` — when provided + different from sheet_id, the bible tabs
    (CHARACTERS / LOCATIONS / COSTUME / PROPS / EFFECTS / Asset Library) are
    read from THIS sheet instead of the episode sheet. This matches the
    series-centric production standard from MEMORY.md: bibles live at the
    series level (typically the ep 1 sheet), per-episode tabs (Shotlist /
    Storyboard Prompts / Video Prompts) live on each individual ep sheet.
    Default = read everything from sheet_id (back-compat for ep 1)."""
    def log(msg):
        if verbose:
            print(msg)

    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(sheet_id)

    # Bible-source key for the cache lookup. When bible_sheet_id is unset or
    # equal to sheet_id, the bibles are local to this episode (back-compat
    # for ep 1) — still cache them, just under their own key.
    bible_key = bible_sheet_id or sheet_id
    cache_hit = False
    with _bible_cache_lock:
        cached = _bible_cache.get(bible_key)
        if cached and (time.time() - cached[0]) < _BIBLE_TTL:
            bible_data = cached[1]
            cache_hit = True
            log(f"  (bibles ← cache, age {int(time.time() - cached[0])}s)")

    if not cache_hit:
        if bible_sheet_id and bible_sheet_id != sheet_id:
            bsh = gc.open_by_key(bible_sheet_id)
            log(f"  (bibles ← {bible_sheet_id[:12]}…, episode-tabs ← {sheet_id[:12]}…)")
        else:
            bsh = sh
        log("  • characters")
        characters = read_characters(bsh)
        log(f"    {len(characters)} chars")
        log("  • locations")
        locations = read_locations(bsh)
        log(f"    {len(locations)} locs")
        log("  • costume / props / effects")
        costume = read_simple_bible(bsh, "COSTUME")
        props = read_simple_bible(bsh, "PROPS")
        effects = read_simple_bible(bsh, "EFFECTS")
        log(f"    {len(costume)} costume · {len(props)} props · {len(effects)} effects")
        log("  • asset library")
        asset_library = read_asset_library(bsh)
        log(f"    {len(asset_library)} entries")
        bible_data = {
            "characters": characters,
            "locations": locations,
            "costume": costume,
            "props": props,
            "effects": effects,
            "asset_library": asset_library,
        }
        with _bible_cache_lock:
            _bible_cache[bible_key] = (time.time(), bible_data)

    characters = bible_data["characters"]
    locations = bible_data["locations"]
    costume = bible_data["costume"]
    props = bible_data["props"]
    effects = bible_data["effects"]
    asset_library = bible_data["asset_library"]

    # Thumb backfill — Asset Library rows without a populated source_url cell
    # still have an underlying bible entry with a Drive thumb. Cross-reference
    # by lower-cased name within the matching bible_tab so every row gets an
    # actual image preview instead of a letter placeholder.
    bible_thumbs: dict[tuple[str, str], str] = {}
    def _index(items: list[dict], tab_aliases: tuple[str, ...]):
        for it in items or []:
            for itr in it.get("iters") or []:
                if itr and itr.get("thumb"):
                    for tab in tab_aliases:
                        bible_thumbs[(tab, it["name"].strip().lower())] = itr["thumb"]
                    break  # first iter wins
    _index(characters, ("characters",))
    _index(locations,  ("locations",))
    _index(costume,    ("costume",))
    _index(props,      ("props",))
    _index(effects,    ("effects",))
    for a in asset_library:
        if a.get("thumb_url"):
            continue
        # Try source_url first
        fid = drive_id(a.get("source_url") or "")
        if fid:
            a["thumb_url"] = thumb(fid, 80)
            continue
        # Fall back to bible cross-reference by (tab, name)
        tab_key = (a.get("bible_tab") or "").strip().lower()
        name_key = (a.get("name") or "").strip().lower()
        a["thumb_url"] = bible_thumbs.get((tab_key, name_key), "")

    log("  • storyboards")
    storyboards = read_storyboards(sh)
    log(f"    {len(storyboards)} sets")
    log("  • video globals")
    video_globals = read_video_globals(sh)

    data = {
        "show": show,
        "episode": episode,
        "stats": {
            "characters": len(characters),
            "locations": len(locations),
            "costume": len(costume),
            "props": len(props),
            "effects": len(effects),
            "sets": len(storyboards),
        },
        "characters": characters,
        "locations": locations,
        "costume": costume,
        "props": props,
        "effects": effects,
        "storyboards": storyboards,
        "video_globals": video_globals,
        "asset_library": asset_library,
        "episodes": episodes or [],
        # Canonical bible-name index — keyed by uppercased bible_tab so the
        # Upload Asset modal's name combobox can suggest only the existing
        # canonical entries (preventing typos that create ghost rows).
        # Each list is the unique col-A names from that bible tab in original
        # order. Free-text typing still works for genuinely new entries.
        "bible_names_by_tab": {
            "CHARACTERS": [c["name"] for c in characters if c.get("name")],
            "LOCATIONS":  [l["name"] for l in locations  if l.get("name")],
            "COSTUME":    [c["name"] for c in costume    if c.get("name")],
            "PROPS":      [p["name"] for p in props      if p.get("name")],
            "EFFECTS":    [e["name"] for e in effects    if e.get("name")],
        },
    }
    return render_html(data, gallery_name=gallery_name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet",   default=DEFAULT_SHEET)
    ap.add_argument("--show",    default=DEFAULT_SHOW)
    ap.add_argument("--episode", default=DEFAULT_EPISODE)
    ap.add_argument("--output",  default=DEFAULT_OUTPUT)
    ap.add_argument("--gallery-name", default="",
                    help="URL slug (e.g. sajangnim_ep01) — wires up live chip + refresh link + job watcher")
    args = ap.parse_args()

    print(f"→ reading sheet {args.sheet}")
    html_doc = build_html(args.sheet, args.show, args.episode,
                          gallery_name=args.gallery_name, verbose=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"\n✓ wrote {args.output} ({len(html_doc) // 1024} KB)")


if __name__ == "__main__":
    main()

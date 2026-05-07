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

import gspread
from auth import get_credentials


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
    """CHARACTERS bible — col A=Name, T=Iter1, U=Iter2, V=Status (23-col schema).
    Returns [] if the sheet has no CHARACTERS tab (e.g. an episode sheet that
    delegates bibles to a series-level bible sheet)."""
    try:
        ws = sh.worksheet("CHARACTERS")
    except Exception:
        return []
    rows = ws.get_all_records()
    out = []
    for r in rows:
        name = (r.get("Name") or "").strip()
        if not name:
            continue
        i1 = drive_id(r.get("Iter 1 URL (white bg)") or r.get("Iter 1 URL") or "")
        i2 = drive_id(r.get("Iter 2 URL (white bg)") or r.get("Iter 2 URL") or "")
        out.append({
            "name": name,
            "role": r.get("Role / Archetype", "") or "",
            "age":  r.get("Age", "") or "",
            "wardrobe": r.get("Wardrobe", "") or "",
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
    raw = ws.get("A5:O100", value_render_option="FORMATTED_VALUE")
    by_name: dict[str, dict] = {}
    for r in raw:
        r = r + [""] * 15
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
            by_name[name] = {"name": name, "description": r[3] or "", "iters": []}
        by_name[name]["iters"].extend(iters)
    return list(by_name.values())


def read_simple_bible(sh, tab: str) -> list[dict]:
    """COSTUME / PROPS / EFFECTS — col A=Name, B=Worn By, G=Iter1, H=Iter2 (header row 5)."""
    try:
        ws = sh.worksheet(tab)
    except Exception:
        return []
    raw = ws.get("A6:K100", value_render_option="FORMATTED_VALUE")
    out = []
    for r in raw:
        r = r + [""] * 11
        name = (r[0] or "").strip()
        if not name:
            continue
        i1 = drive_id(r[6])
        i2 = drive_id(r[7])
        out.append({
            "name": name,
            "used_by": r[1] or "",
            "description": r[2] or "",
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
    J=Body, K=Bahasa Body, L=Location, M=Video Iter1, N=Video Iter2.
    """
    ws = sh.worksheet("Storyboard Prompts")
    raw = ws.get("A11:N100", value_render_option="FORMATTED_VALUE")
    out = []
    for r in raw:
        r = r + [""] * 14
        if not r[0].strip().isdigit():
            continue
        sb1 = drive_id(r[6])
        sb2 = drive_id(r[7])
        v1 = drive_id(r[12])
        v2 = drive_id(r[13])
        out.append({
            "set": int(r[0]),
            "shots": r[1],
            "body": r[9],          # SP!J — body-only English
            "body_bahasa": r[10],   # SP!K
            "location": r[11],
            "status": r[5],
            "sb_iters": [
                {"label": "Storyboard 1", "thumb": thumb(sb1), "view": view(sb1)} if sb1 else None,
                {"label": "Storyboard 2", "thumb": thumb(sb2), "view": view(sb2)} if sb2 else None,
            ],
            "videos": [
                {"label": "Video 1", "preview": preview(v1), "view": view(v1)} if v1 else None,
                {"label": "Video 2", "preview": preview(v2), "view": view(v2)} if v2 else None,
            ],
        })
    return out


# ===== HTML rendering =====

def render_card_grid(items: list[dict], kind: str) -> str:
    """Generic bible card grid — used for chars / locations / costume / props / fx."""
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
        cards.append(f'''
        <div class="card {kind}-card">
          <div class="card-head"><h4>{html.escape(it["name"])}</h4></div>
          <div class="card-iters">{iters_html}</div>
          {"".join(meta_lines)}
        </div>''')
    return '<div class="card-grid">' + "".join(cards) + "</div>"


def render_set_card(s: dict, video_globals: dict | None = None) -> str:
    video_globals = video_globals or {}
    sb_html = ""
    for idx, sb in enumerate(s["sb_iters"], start=1):
        # Storyboard image (or placeholder)
        if sb:
            sb_html += (
                f'<a class="thumb wide" href="{html.escape(sb["view"])}" target="_blank">'
                f'<img src="{html.escape(sb["thumb"])}" alt="{html.escape(sb["label"])}" loading="lazy">'
                f'<span class="label">{html.escape(sb["label"])}</span>'
                f'</a>'
            )
        else:
            sb_html += '<div class="thumb wide placeholder">storyboard pending</div>'
        # Generate V<n> button — fires BytePlus Seedance 2.0 with this SB as ref
        sb_html += (
            f'<button class="gen-btn vid" data-set="{s["set"]}" data-slot="{idx}" '
            f'onclick="fireVidgen({s["set"]}, {idx}, this)">Generate V{idx}</button>'
        )

    vid_html = ""
    for v in s["videos"]:
        if v:
            vid_html += (
                f'<div class="vid-tile">'
                f'<iframe src="{html.escape(v["preview"])}" allow="autoplay" loading="lazy"></iframe>'
                f'<div class="label">{html.escape(v["label"])}</div>'
                f'</div>'
            )
        else:
            vid_html += '<div class="vid-tile placeholder">video pending</div>'

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
      </div>
      <button class="gen-btn" data-set="{s["set"]}" onclick="fireStoryboard({s["set"]}, this)">
        Generate Storyboard
      </button>'''

    return f'''
    <div class="set-card" data-set="{s["set"]}">
      <div class="set-head">
        <h3>Set {s["set"]} · shots {html.escape(s["shots"] or "—")}</h3>
        <div class="set-meta">
          <span class="chip">{html.escape(s["status"] or "Pending")}</span>
        </div>
      </div>
      <div class="set-grid">
        <div class="set-prompt">{prompt_html}</div>
        <div class="set-storyboards">{sb_html}</div>
        <div class="set-videos">{vid_html}</div>
      </div>
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
            rows.append(f'''
              <tr>
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
                  <th>Name</th><th>Type</th><th>Asset Code (BytePlus)</th><th>Status</th><th>Source</th>
                </tr>
              </thead>
              <tbody>{"".join(rows)}</tbody>
            </table>
          </div>''')
    return "".join(sections)


def render_html(data: dict, gallery_name: str = "") -> str:
    nav = []
    sections = []
    section_defs = [
        ("characters", "Characters", lambda d: render_card_grid(d["characters"], "char")),
        ("locations",  "Locations",  lambda d: render_card_grid(d["locations"], "loc")),
        ("costume",    "Costume",    lambda d: render_card_grid(d["costume"], "bib")),
        ("props",      "Props",      lambda d: render_card_grid(d["props"], "bib")),
        ("effects",    "Effects",    lambda d: render_card_grid(d["effects"], "bib")),
        ("storyboards","Storyboards",lambda d: "".join(render_set_card(s, d.get("video_globals")) for s in d["storyboards"])),
        ("assets",     "Asset Library", lambda d: render_asset_library(d.get("asset_library", []))),
    ]
    # Default-active tab: Storyboards (the most-viewed section in production review).
    default_tab = "storyboards"
    for sid, title, render_fn in section_defs:
        is_active = " active" if sid == default_tab else ""
        nav.append(f'<button class="tab{is_active}" data-tab="{sid}">{html.escape(title)}</button>')
        sections.append(
            f'<section class="panel{is_active}" id="{sid}"><h2>{html.escape(title)}</h2>{render_fn(data)}</section>'
        )

    stats = data["stats"]
    stats_html = " · ".join(f"<b>{v}</b> {k}" for k, v in stats.items() if v)

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
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg); color: var(--ink); line-height: 1.5;
  }}
  header.hero {{
    padding: 50px 40px 30px; border-bottom: 1px solid var(--line);
    background: white;
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
    background: white; border-bottom: 1px solid var(--line);
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
    background: white; border: 1px solid var(--line); border-radius: 10px;
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
    background: #f5f5f5; border: 1px dashed var(--line); border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    color: var(--muted); font-size: 11px; text-transform: uppercase;
    aspect-ratio: 1/1;
  }}
  .thumb.wide.placeholder {{ aspect-ratio: 16/9; }}
  .meta-line {{ font-size: 11px; color: var(--muted); }}
  .meta-line b {{ color: var(--ink); }}

  .set-card {{
    background: white; border: 1px solid var(--line); border-radius: 12px;
    padding: 22px; margin-bottom: 22px;
  }}
  .set-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }}
  .set-head h3 {{ margin: 0; font-size: 16px; font-weight: 600; }}
  .set-meta .chip {{
    display: inline-block; background: var(--chip-bg); color: var(--ink);
    padding: 3px 9px; font-size: 10px; letter-spacing: 0.04em;
    text-transform: uppercase; border-radius: 4px; margin-left: 6px;
  }}
  .set-grid {{
    display: grid; grid-template-columns: minmax(260px, 1fr) minmax(320px, 1.4fr) minmax(180px, 0.7fr);
    gap: 18px; align-items: start;
  }}
  .set-body {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: #444; line-height: 1.6; white-space: pre-wrap;
    background: #f8f8f8; padding: 12px; border-radius: 6px;
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
    color: #444; line-height: 1.55;
    background: #f8f8f8; padding: 10px 12px; border-radius: 6px;
  }}
  .prompt-body.global {{ background: #f0f4f8; }}
  .prompt-body.location {{
    background: #fef7ed; font-weight: 500; color: #7a3a08;
    font-family: 'Inter', sans-serif; font-size: 12px;
  }}
  .prompt-body.combined {{
    background: #f8f8f8;
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
    background: #f5f5f5; border: 1px dashed var(--line);
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
    background: white; border: 1px solid var(--line); border-radius: 8px;
    overflow: hidden; font-size: 12px;
  }}
  .al-table th {{
    text-align: left; padding: 10px 14px;
    background: #f5f5f5; color: var(--muted);
    font-weight: 500; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
    border-bottom: 1px solid var(--line);
  }}
  .al-table td {{ padding: 10px 14px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
  .al-table tr:last-child td {{ border-bottom: 0; }}
  .al-table tr:hover td {{ background: #fafafa; }}
  .al-name {{ font-weight: 500; color: var(--ink); }}
  .al-type {{ color: var(--muted); text-transform: capitalize; }}
  .al-code code {{
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: #666; background: #f5f5f5; padding: 2px 6px; border-radius: 3px;
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
  .status-badge.muted {{ background: #f0f0f0; color: #888; }}
  .empty {{ color: var(--muted); font-style: italic; padding: 20px; }}

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
<header class="hero">
  <div class="live-row">{live_chip}{refresh_link}</div>
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
    async function tick() {{
      attempts++;
      if (attempts > MAX_ATTEMPTS) {{
        text.textContent = `${{label}} — watcher gave up after ${{MAX_ATTEMPTS}} polls. Check /debug/jobs manually then click ↻ Refresh.`;
        banner.classList.add('error');
        return;
      }}
      try {{
        const r = await fetch('/debug/jobs', {{cache: 'no-store'}});
        const data = await r.json();
        const byId = {{}};
        for (const j of (data.jobs || [])) byId[j.id] = j;
        for (const id of Array.from(remaining)) {{
          const j = byId[id];
          if (!j) continue;
          if (j.status === 'succeeded') remaining.delete(id);
          else if (j.status === 'failed' || j.status === 'errored') {{
            remaining.delete(id);
            failed.push(id);
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
</script>
</body>
</html>'''


def build_html(sheet_id: str, show: str, episode: str,
               gallery_name: str = "", bible_sheet_id: str | None = None,
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
    log("  • storyboards")
    storyboards = read_storyboards(sh)
    log(f"    {len(storyboards)} sets")
    log("  • video globals")
    video_globals = read_video_globals(sh)
    log("  • asset library")
    asset_library = read_asset_library(bsh)
    log(f"    {len(asset_library)} entries")

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

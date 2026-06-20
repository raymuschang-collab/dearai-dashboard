#!/usr/bin/env python3
"""build_projects_page.py — landing page (`/projects`) for the dashboard CMS.

Renders a grid of all projects from the master Projects sheet:
  • Card per project: title, type badge, status badge, owner, episode count
  • Filter chips at top: All / Active / POC / Client / In Review / Archived
  • "+ New Project" button (wired to the modal in build_gallery.py-style flow)
  • Click a card → first gallery URL of that project

Reuses the gallery's CSS design tokens (light/dark themes, hero, chips) so the
two surfaces feel like one product.

Usage from Flask:
    from build_projects_page import render_projects_page
    html = render_projects_page(projects, user_email=session.get("user_email", ""))
"""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone

from global_presets import GLOBAL_PRESETS, DEFAULT_PRESET_ID


# Status → CSS class mapping. Same vocabulary as `_create_master_projects_sheet.py`.
_STATUS_CLASS = {
    "draft":      "warn",
    "generating": "warn",
    "review":     "warn",
    "active":     "ok",
    "archived":   "muted",
}

_TYPE_CLASS = {
    "series":  "type-series",
    "poc":     "type-poc",
    "concept": "type-concept",
    "client":  "type-client",
}

_TYPE_LABEL = {
    "series":  "Series",
    "poc":     "POC",
    "concept": "Concept",
    "client":  "Client",
}


def _fmt_created_at(iso: str) -> str:
    """`2026-04-29T00:00:00Z` → `Apr 29, 2026`."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso[:10]


def _project_card(p: dict) -> str:
    """Render one project card."""
    slug = p["slug"]
    title = p["title"] or slug
    ptype = (p.get("type") or "series").lower()
    status = (p.get("status") or "draft").lower()
    owner = p.get("owner_email", "")
    ep_count = len(p.get("episodes") or [])
    created = _fmt_created_at(p.get("created_at", ""))
    cover_url = (p.get("cover_url") or "").strip()

    # Card click → first gallery URL of this project (NOT the cover area;
    # cover area opens the file picker instead — handled in JS)
    first_ep = (p.get("episodes") or [{}])[0]
    target = f"/gallery/{first_ep.get('gallery_slug', '')}" if first_ep else "#"

    type_cls = _TYPE_CLASS.get(ptype, "type-series")
    type_label = _TYPE_LABEL.get(ptype, ptype.title())
    status_cls = _STATUS_CLASS.get(status, "muted")

    notes = (p.get("notes") or "").strip()
    notes_line = (
        f'<div class="card-notes">{_html.escape(notes[:140])}{"…" if len(notes) > 140 else ""}</div>'
        if notes else ""
    )

    # Asset Library roll-up (filled by _project_media in app.py)
    hero = p.get("hero_video") or None
    n_char = int(p.get("n_characters", 0) or 0)
    n_loc = int(p.get("n_locations", 0) or 0)

    # Cover slot — three states, in priority order:
    #   1. hero ref video present → hover-play tile (poster = cover.jpg if set,
    #      else the clip's own Drive thumbnail). The playable video is a
    #      CHARACTER or LOCATION reference clip only — never a generated story
    #      clip (see _project_media). Click still opens the change-cover picker.
    #   2. cover image only → static image + "Change cover" hover overlay.
    #   3. nothing → "+ Add cover" placeholder.
    # All three keep `data-cover-slug` so the cover-upload JS still works.
    if hero:
        poster = cover_url or hero.get("poster", "")
        vsrc = f"/api/asset-video/{_html.escape(hero['file_id'])}"
        kind = _html.escape((hero.get("kind") or "ref"))
        cover_html = f'''
        <div class="card-cover vtile" data-cover-slug="{_html.escape(slug)}"
             data-vsrc="{vsrc}">
          <img class="vtile-poster" src="{_html.escape(poster)}" alt="" loading="lazy">
          <span class="vtile-play">▶</span>
          <span class="vtile-kind">{kind} ref</span>
          <div class="cover-overlay">Change cover</div>
        </div>'''
    elif cover_url:
        cover_html = f'''
        <div class="card-cover" data-cover-slug="{_html.escape(slug)}">
          <img src="{_html.escape(cover_url)}" alt="" loading="lazy">
          <div class="cover-overlay">Change cover</div>
        </div>'''
    else:
        cover_html = f'''
        <div class="card-cover empty" data-cover-slug="{_html.escape(slug)}">
          <div class="cover-plus">+</div>
          <div class="cover-add-text">Add cover</div>
        </div>'''

    # Stat roll-up line: episodes · characters · locations
    stat_bits = [f'<span><b>{ep_count}</b> ep{"s" if ep_count != 1 else ""}</span>']
    if n_char:
        stat_bits.append(f'<span><b>{n_char}</b> char</span>')
    if n_loc:
        stat_bits.append(f'<span><b>{n_loc}</b> loc</span>')
    stats_line = f'<div class="card-stats">{"".join(stat_bits)}</div>'

    # Hidden file input — outside the <a> wrapper so clicks don't propagate
    # to the gallery link. JS clicks it programmatically when cover is clicked.
    file_input_html = f'''
    <input type="file" class="cover-file-input" accept="image/jpeg,image/jpg,image/png,image/webp"
           data-slug="{_html.escape(slug)}" style="display:none">'''

    # The card itself wraps everything except the file input. The cover slot
    # has its own click handler (JS) that prevents default + opens file picker.
    return f'''
    <div class="proj-card-wrapper">
      {file_input_html}
      <a class="proj-card" href="{_html.escape(target)}">
        {cover_html}
        <div class="card-body">
          <div class="card-row1">
            <span class="type-chip {type_cls}">{_html.escape(type_label)}</span>
            <span class="status-badge {status_cls}">{_html.escape(status)}</span>
          </div>
          <h3 class="card-title">{_html.escape(title)}</h3>
          {stats_line}
          <div class="card-meta">
            <span class="card-owner">{_html.escape(owner)}</span>
            <span class="card-sep">·</span>
            <span class="card-created">created {_html.escape(created)}</span>
          </div>
          {notes_line}
          <div class="card-slug"><code>{_html.escape(slug)}</code></div>
        </div>
      </a>
    </div>'''


def render_projects_page(projects: list[dict], user_email: str = "") -> str:
    """Build the full /projects HTML page."""
    # Bucket counts for the filter chips
    counts = {"all": 0, "active": 0, "review": 0, "draft": 0, "archived": 0,
              "series": 0, "poc": 0, "concept": 0, "client": 0}
    for p in projects:
        counts["all"] += 1
        counts[p.get("status", "draft").lower()] = counts.get(p.get("status", "draft").lower(), 0) + 1
        counts[p.get("type", "series").lower()] = counts.get(p.get("type", "series").lower(), 0) + 1

    # Hide archived from default view (toggleable via filter)
    visible_default = [p for p in projects if p.get("status", "").lower() != "archived"]
    # Defensive: render each card in isolation so one malformed master-sheet row
    # can't crash the whole page (which would also kill the "+ New Project"
    # button and trap the user with no way to fix the bad row from the UI).
    card_chunks: list[str] = []
    for p in visible_default:
        try:
            card_chunks.append(_project_card(p))
        except Exception as e:
            slug = p.get("slug", "?") if isinstance(p, dict) else "?"
            card_chunks.append(
                f'<div class="empty" style="border:1px solid #c11647;color:#c11647">'
                f'⚠ failed to render <code>{_html.escape(slug)}</code>: '
                f'{_html.escape(type(e).__name__)}: {_html.escape(str(e)[:120])}'
                f'</div>'
            )
    cards_html = "".join(card_chunks)
    if not cards_html:
        cards_html = '<div class="empty">No projects yet. Click <b>+ New Project</b> to start.</div>'

    user_chip = (
        f'<span id="user-chip" data-email="{_html.escape(user_email)}" '
        f'title="Logged in as {_html.escape(user_email)}"></span>'
        f'<a class="refresh" href="/auth/logout">Log out</a>'
        if user_email else ""
    )

    # Global-style preset cards for the New Project modal (from global_presets.py).
    _gp_cards = []
    for gp in GLOBAL_PRESETS:
        sel = " selected" if gp["id"] == DEFAULT_PRESET_ID else ""
        _gp_cards.append(
            f'<div class="global-card{sel}" data-radio-group="global" '
            f'data-value="{_html.escape(gp["id"])}" '
            f'title="{_html.escape(gp["camera"])}">'
            f'<div class="gc-name">{_html.escape(gp["name"])}</div>'
            f'<div class="gc-tag">{_html.escape(gp["tagline"])}</div>'
            f'<div class="gc-ref">{_html.escape(gp["ref"])}</div>'
            f'</div>'
        )
    global_cards_html = "".join(_gp_cards)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DearAI Projects</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #fafafa; --ink: #1a1a1a; --muted: #888; --line: #e5e5e5;
    --accent: #c11647; --chip-bg: #f0f0f0;
    --card-bg: #ffffff; --code-bg: #f5f5f5; --soft-bg: #f8f8f8;
    --hero-bg: #ffffff; --table-row-hover: #fafafa;
  }}
  html[data-theme="dark"] {{
    --bg: #0f1115; --ink: #e8e8ea; --muted: #8a8d96; --line: #2a2d36;
    --accent: #ff5577; --chip-bg: #2a2d36;
    --card-bg: #181b22; --code-bg: #14171d; --soft-bg: #14171d;
    --hero-bg: #14171d; --table-row-hover: #1d2028;
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
  header.hero .live-row {{ display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }}
  header.hero h1 {{ font-size: 34px; font-weight: 700; margin: 0 0 8px; }}
  header.hero .subtitle {{ font-size: 13px; color: var(--muted); }}
  header.hero .stats b {{ color: var(--ink); font-weight: 600; }}
  a.refresh {{
    color: var(--muted); text-decoration: none; font-size: 11px;
    border: 1px solid var(--line); border-radius: 4px;
    padding: 3px 9px; transition: all 0.15s;
  }}
  a.refresh:hover {{ color: var(--ink); border-color: var(--ink); }}
  #user-chip {{
    display: inline-block; color: var(--muted); font-size: 11px;
    border: 1px solid var(--line); border-radius: 4px;
    padding: 3px 9px; max-width: 180px; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap;
  }}
  #user-chip[data-email=""] {{ display: none; }}
  #user-chip[data-email=""] + a.refresh {{ display: none; }}
  #user-chip::before {{ content: attr(data-email); }}
  #dark-toggle {{
    background: var(--card-bg); cursor: pointer;
    color: var(--muted); font-size: 11px;
    border: 1px solid var(--line); border-radius: 4px;
    padding: 3px 9px; font-family: inherit;
  }}
  #dark-toggle:hover {{ color: var(--ink); border-color: var(--ink); }}

  /* Filter bar */
  .filter-bar {{
    padding: 20px 40px; border-bottom: 1px solid var(--line);
    background: var(--hero-bg);
    display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
    position: sticky; top: 0; z-index: 10;
  }}
  .filter-chip {{
    background: none; border: 1px solid var(--line); border-radius: 16px;
    color: var(--muted); font: inherit; font-size: 12px;
    padding: 5px 12px; cursor: pointer; transition: all 0.15s;
  }}
  .filter-chip:hover {{ color: var(--ink); }}
  .filter-chip.active {{
    background: var(--ink); color: var(--card-bg); border-color: var(--ink);
  }}
  .filter-chip .count {{ opacity: 0.6; margin-left: 4px; font-variant-numeric: tabular-nums; }}
  .filter-spacer {{ flex: 1; }}
  .new-proj-btn {{
    background: var(--accent); color: white;
    border: 0; border-radius: 6px;
    font: inherit; font-size: 12px; font-weight: 600;
    letter-spacing: 0.04em; text-transform: uppercase;
    padding: 9px 18px; cursor: pointer;
    transition: opacity 0.15s;
  }}
  .new-proj-btn:hover {{ opacity: 0.9; }}
  .new-proj-btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}

  /* Project grid */
  main.grid-wrap {{
    padding: 30px 40px 60px;
    max-width: 1400px; margin: 0 auto;
  }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 18px;
  }}
  .proj-card-wrapper {{ position: relative; }}
  a.proj-card {{
    display: block; background: var(--card-bg); border: 1px solid var(--line);
    border-radius: 12px; overflow: hidden;
    text-decoration: none; color: inherit;
    transition: border-color 0.15s, transform 0.15s;
  }}
  a.proj-card:hover {{
    border-color: var(--ink); transform: translateY(-2px);
  }}
  .card-body {{
    padding: 14px 18px 18px;
    display: flex; flex-direction: column; gap: 8px;
  }}
  /* Cover slot — 16:9 image area at top of card, OR a "+" placeholder when no
     cover yet. Clicking either opens a hidden file input (handled in JS at
     end of <body>) so producers can drop a poster image without leaving the
     page. */
  .card-cover {{
    position: relative; aspect-ratio: 16/9;
    background: var(--soft-bg); cursor: pointer;
    border-bottom: 1px solid var(--line);
    overflow: hidden;
  }}
  .card-cover img {{
    width: 100%; height: 100%; object-fit: cover; display: block;
  }}
  .card-cover .cover-overlay {{
    position: absolute; inset: 0;
    background: rgba(0, 0, 0, 0.5); color: white;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase;
    opacity: 0; transition: opacity 0.15s;
  }}
  .card-cover:hover .cover-overlay {{ opacity: 1; }}
  .card-cover.empty {{
    display: flex; align-items: center; justify-content: center;
    flex-direction: column; gap: 4px;
    color: var(--muted);
    background: var(--soft-bg);
    border: 2px dashed var(--line);
    border-bottom-width: 1px; border-bottom-style: solid;
    transition: background 0.15s, color 0.15s;
  }}
  .card-cover.empty:hover {{
    background: var(--code-bg); color: var(--ink);
  }}
  .card-cover .cover-plus {{
    font-size: 36px; font-weight: 200; line-height: 1;
  }}
  .card-cover .cover-add-text {{
    font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
  }}
  .card-cover.uploading {{
    pointer-events: none; opacity: 0.6;
  }}
  .card-cover.uploading::after {{
    content: 'Uploading…';
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, 0.7); color: white;
    font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  }}
  /* Hover-play preview — a CHARACTER or LOCATION reference clip (never a
     generated story clip) fades in over the poster on hover. Mechanism ported
     from the COVEN series dashboard: poster-only until hover, same-origin
     <video> injected via /api/asset-video, torn down on leave. */
  .card-cover.vtile .vtile-video {{
    position: absolute; inset: 0; width: 100%; height: 100%;
    object-fit: cover; opacity: 0; transition: opacity 0.25s ease;
    z-index: 2; background: #000;
  }}
  .card-cover.vtile.playing .vtile-video {{ opacity: 1; }}
  .card-cover .vtile-play {{
    position: absolute; left: 10px; bottom: 10px; z-index: 3;
    width: 26px; height: 26px; border-radius: 999px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0,0,0,0.55); color: #fff; font-size: 10px;
    backdrop-filter: blur(4px); transition: opacity 0.2s ease;
    pointer-events: none;
  }}
  .card-cover.vtile.playing .vtile-play {{ opacity: 0; }}
  .card-cover .vtile-kind {{
    position: absolute; right: 8px; top: 8px; z-index: 3;
    font-size: 8px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: #fff;
    background: rgba(0,0,0,0.5); padding: 3px 7px; border-radius: 999px;
    backdrop-filter: blur(4px); pointer-events: none;
  }}

  .card-row1 {{ display: flex; gap: 6px; align-items: center; }}
  .card-title {{
    margin: 0; font-size: 16px; font-weight: 600; line-height: 1.3;
  }}
  /* Stat roll-up line — episodes / characters / locations from the Asset Library */
  .card-stats {{
    display: flex; flex-wrap: wrap; gap: 4px 12px;
    font-size: 11px; color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
  }}
  .card-stats b {{ color: var(--ink); font-weight: 600; }}
  .card-meta {{ font-size: 12px; color: var(--muted); }}
  .card-meta .card-sep {{ margin: 0 6px; opacity: 0.5; }}
  .card-notes {{
    font-size: 11px; color: var(--muted); font-style: italic;
    line-height: 1.4; margin-top: 4px;
  }}
  .card-slug {{
    margin-top: auto; padding-top: 10px;
    border-top: 1px dashed var(--line);
  }}
  .card-slug code {{
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    color: var(--muted); background: var(--code-bg);
    padding: 2px 6px; border-radius: 3px;
  }}

  .type-chip {{
    display: inline-block; padding: 3px 9px; border-radius: 4px;
    font-size: 10px; letter-spacing: 0.05em; text-transform: uppercase;
    font-weight: 600; color: white;
  }}
  .type-series  {{ background: #1a1a1a; }}
  .type-poc     {{ background: #5d3a9b; }}
  .type-concept {{ background: #2e7d32; }}
  .type-client  {{ background: var(--accent); }}
  html[data-theme="dark"] .type-series {{ background: #4a4a4a; }}

  .status-badge {{
    display: inline-block; padding: 3px 9px; border-radius: 4px;
    font-size: 10px; letter-spacing: 0.05em; text-transform: uppercase;
    font-weight: 600;
  }}
  .status-badge.ok    {{ background: #e8f5e9; color: #2e7d32; }}
  .status-badge.warn  {{ background: #fff3e0; color: #e65100; }}
  .status-badge.fail  {{ background: #fde8ec; color: #c11647; }}
  .status-badge.muted {{ background: var(--chip-bg); color: var(--muted); }}
  html[data-theme="dark"] .status-badge.ok    {{ background: #1f3a23; color: #7fc788; }}
  html[data-theme="dark"] .status-badge.warn  {{ background: #3d2a13; color: #ffb868; }}
  html[data-theme="dark"] .status-badge.fail  {{ background: #3a1822; color: #ff7a90; }}

  .empty {{
    color: var(--muted); font-style: italic; padding: 40px;
    text-align: center; border: 1px dashed var(--line); border-radius: 8px;
  }}
  .empty b {{ color: var(--accent); font-style: normal; }}

  footer {{
    text-align: center; color: var(--muted); font-size: 11px;
    padding: 30px;
  }}
  footer a {{ color: var(--muted); }}

  /* ===== New Project modal ===== */
  .modal-backdrop {{
    position: fixed; inset: 0; z-index: 100;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(4px);
    display: none;
    align-items: flex-start; justify-content: center;
    overflow-y: auto;
    padding: 40px 16px;
  }}
  .modal-backdrop.open {{ display: flex; }}
  .modal {{
    background: var(--card-bg);
    color: var(--ink);
    width: 100%; max-width: 640px;
    border-radius: 14px;
    border: 1px solid var(--line);
    padding: 28px 32px 32px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
    position: relative;
  }}
  .modal-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 18px;
  }}
  .modal-header h2 {{
    font-size: 20px; font-weight: 700; letter-spacing: -0.01em;
  }}
  .modal-close {{
    background: none; border: none; color: var(--muted);
    font-size: 22px; cursor: pointer; padding: 4px 8px;
    border-radius: 6px;
  }}
  .modal-close:hover {{ color: var(--ink); background: var(--soft-bg); }}
  .modal-body {{ display: flex; flex-direction: column; gap: 18px; }}
  .modal-field {{ display: flex; flex-direction: column; gap: 6px; }}
  .modal-field label {{
    font-size: 12px; font-weight: 600; color: var(--ink);
    text-transform: uppercase; letter-spacing: 0.06em;
  }}
  .modal-field .hint {{ font-size: 11px; color: var(--muted); font-weight: 400; text-transform: none; letter-spacing: 0; }}
  .modal-field input[type="text"],
  .modal-field textarea,
  .modal-field select {{
    background: var(--soft-bg); color: var(--ink);
    border: 1px solid var(--line); border-radius: 8px;
    padding: 10px 12px; font: inherit; font-size: 13px;
    transition: border-color 0.15s;
  }}
  .modal-field input:focus,
  .modal-field textarea:focus,
  .modal-field select:focus {{ outline: none; border-color: var(--accent); }}
  .modal-field textarea {{ resize: vertical; min-height: 60px; }}

  /* File drop zone */
  .drop-zone {{
    background: var(--soft-bg);
    border: 2px dashed var(--line);
    border-radius: 10px;
    padding: 28px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .drop-zone:hover, .drop-zone.dragover {{
    border-color: var(--accent); background: var(--code-bg);
  }}
  .drop-zone .dz-icon {{ font-size: 28px; margin-bottom: 8px; }}
  .drop-zone .dz-main {{ font-size: 14px; font-weight: 600; color: var(--ink); margin-bottom: 4px; }}
  .drop-zone .dz-sub {{ font-size: 12px; color: var(--muted); }}
  .drop-zone.has-file {{
    border-style: solid; border-color: #2e8c4f;
    background: rgba(46, 140, 79, 0.05);
  }}
  .drop-zone.has-file .dz-icon {{ color: #2e8c4f; }}

  /* Radio cards */
  .radio-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
  .radio-card {{
    background: var(--soft-bg);
    border: 1.5px solid var(--line);
    border-radius: 8px;
    padding: 10px 12px;
    cursor: pointer;
    transition: all 0.12s;
    font-size: 13px;
  }}
  .radio-card:hover {{ border-color: var(--muted); }}
  .radio-card.selected {{
    border-color: var(--accent);
    background: var(--code-bg);
  }}
  .radio-card .rc-title {{ font-weight: 600; color: var(--ink); }}
  .radio-card .rc-sub {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}

  /* Global film-look presets — compact 2-col grid of selectable cards */
  .global-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }}
  .global-card {{
    border: 1px solid var(--line); border-radius: 8px;
    padding: 9px 11px; cursor: pointer;
    background: var(--card-bg); transition: all 0.12s;
  }}
  .global-card:hover {{ border-color: var(--muted); }}
  .global-card.selected {{
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
    background: var(--soft-bg);
  }}
  .global-card .gc-name {{ font-weight: 600; font-size: 13px; color: var(--ink); }}
  .global-card .gc-tag {{ font-size: 11px; color: var(--muted); margin-top: 2px; line-height: 1.3; }}
  .global-card .gc-ref {{ font-size: 10px; color: var(--accent); margin-top: 3px; font-style: italic; }}
  @media (max-width: 560px) {{ .global-grid {{ grid-template-columns: 1fr; }} }}

  /* Depth choice — bigger cards with cost/time */
  .depth-grid {{ display: flex; flex-direction: column; gap: 8px; }}
  .depth-card {{
    background: var(--soft-bg);
    border: 1.5px solid var(--line);
    border-radius: 10px;
    padding: 14px 16px;
    cursor: pointer;
    transition: all 0.12s;
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
  }}
  .depth-card:hover {{ border-color: var(--muted); }}
  .depth-card.selected {{
    border-color: var(--accent);
    background: var(--code-bg);
    box-shadow: 0 0 0 1px var(--accent);
  }}
  .depth-card .dc-left .dc-title {{
    font-weight: 700; font-size: 14px; color: var(--ink);
  }}
  .depth-card .dc-left .dc-sub {{
    font-size: 12px; color: var(--muted); margin-top: 3px;
  }}
  .depth-card .dc-cost {{
    font-family: monospace; font-size: 12px; color: var(--muted);
    text-align: right; white-space: nowrap;
  }}

  .modal-actions {{
    display: flex; justify-content: flex-end; gap: 10px;
    margin-top: 6px; padding-top: 18px;
    border-top: 1px solid var(--line);
  }}
  .modal-actions button {{
    padding: 10px 18px; border-radius: 8px;
    font: inherit; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: all 0.12s;
  }}
  .btn-cancel {{
    background: none; border: 1px solid var(--line); color: var(--muted);
  }}
  .btn-cancel:hover {{ color: var(--ink); border-color: var(--ink); }}
  .btn-submit {{
    background: var(--accent); border: 1px solid var(--accent); color: white;
  }}
  .btn-submit:hover {{ filter: brightness(1.08); }}
  .btn-submit:disabled {{ opacity: 0.6; cursor: wait; }}

  .modal-error {{
    background: rgba(255, 80, 80, 0.1);
    border: 1px solid rgba(255, 80, 80, 0.4);
    color: #d23030;
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 13px;
    display: none;
  }}
  .modal-error.show {{ display: block; }}

  /* Form row layout (2 cols on desktop) */
  .form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}

  @media (max-width: 600px) {{
    .form-row, .radio-grid {{ grid-template-columns: 1fr; }}
    .modal {{ padding: 22px 20px 26px; }}
  }}
</style>
</head>
<body>
<header class="hero">
  <div class="live-row">
    <span class="status-badge ok">{counts['all']} projects</span>
    <button id="dark-toggle" type="button" title="Toggle dark / light"
            onclick="toggleDarkMode()">🌙</button>
    {user_chip}
  </div>
  <h1>Projects</h1>
  <div class="subtitle">DearAI Studio · Click a project to enter its gallery, or click <b>+ New Project</b> to start a new one.</div>
</header>
<div class="filter-bar">
  <button class="filter-chip active" data-filter="visible">Active &amp; In&nbsp;Review<span class="count">{counts['all'] - counts.get('archived', 0)}</span></button>
  <button class="filter-chip" data-filter="active">Active<span class="count">{counts.get('active', 0)}</span></button>
  <button class="filter-chip" data-filter="review">In Review<span class="count">{counts.get('review', 0)}</span></button>
  <button class="filter-chip" data-filter="draft">Draft<span class="count">{counts.get('draft', 0)}</span></button>
  <button class="filter-chip" data-filter="series">Series<span class="count">{counts.get('series', 0)}</span></button>
  <button class="filter-chip" data-filter="poc">POC<span class="count">{counts.get('poc', 0)}</span></button>
  <button class="filter-chip" data-filter="client">Client<span class="count">{counts.get('client', 0)}</span></button>
  <button class="filter-chip" data-filter="archived">Archived<span class="count">{counts.get('archived', 0)}</span></button>
  <button class="filter-chip" data-filter="all">All<span class="count">{counts['all']}</span></button>
  <span class="filter-spacer"></span>
  <button class="new-proj-btn" onclick="openNewProjectModal()">+ New Project</button>
</div>
<main class="grid-wrap">
  <div class="grid" id="proj-grid">
    {cards_html}
  </div>
</main>
<footer>
  Project list reads from <a href="https://docs.google.com/spreadsheets/d/1J-x4b4hshrX3wdMItboQJzcjKkAff_jnKEiIKjpy0g0" target="_blank">DearAI Projects (Master)</a> · 60s cache
</footer>
<script>
  // Dark-mode toggle (same as gallery)
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
  (function() {{
    let saved = null;
    try {{ saved = localStorage.getItem('gallery_dark_mode'); }} catch (e) {{}}
    let on;
    if (saved === '1') on = true;
    else if (saved === '0') on = false;
    else on = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyDarkMode(on);
  }})();

  // Filter chips — toggle visibility of cards by data attributes.
  // We re-derive each card's status/type from its DOM (no extra data attrs needed).
  (function() {{
    const chips = document.querySelectorAll('.filter-chip');
    const wrappers = document.querySelectorAll('.proj-card-wrapper');
    function activate(filter) {{
      chips.forEach(c => c.classList.toggle('active', c.dataset.filter === filter));
      wrappers.forEach(w => {{
        const card = w.querySelector('a.proj-card');
        const status = card.querySelector('.status-badge')?.textContent?.toLowerCase() || '';
        const type = card.querySelector('.type-chip')?.textContent?.toLowerCase() || '';
        let visible = false;
        if (filter === 'all') visible = true;
        else if (filter === 'visible') visible = status !== 'archived';
        else if (filter === 'active' || filter === 'review' || filter === 'draft' || filter === 'archived') visible = status === filter;
        else if (filter === 'series' || filter === 'poc' || filter === 'concept' || filter === 'client') visible = type === filter;
        w.style.display = visible ? '' : 'none';
      }});
    }}
    chips.forEach(c => c.addEventListener('click', () => activate(c.dataset.filter)));
  }})();

  // Cover image upload — click any card-cover slot → opens its sibling
  // <input type="file"> → uploads → reloads with the new cover.
  (function() {{
    const slots = document.querySelectorAll('.card-cover');
    slots.forEach(slot => {{
      slot.addEventListener('click', (ev) => {{
        // Stop the click from also triggering the wrapping <a> navigation
        ev.preventDefault();
        ev.stopPropagation();
        const slug = slot.dataset.coverSlug;
        const wrapper = slot.closest('.proj-card-wrapper');
        const fileInput = wrapper?.querySelector('.cover-file-input');
        if (fileInput) fileInput.click();
      }});
    }});
    document.querySelectorAll('.cover-file-input').forEach(input => {{
      input.addEventListener('change', async (ev) => {{
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        const slug = ev.target.dataset.slug;
        const wrapper = ev.target.closest('.proj-card-wrapper');
        const slot = wrapper?.querySelector('.card-cover');
        if (slot) slot.classList.add('uploading');
        try {{
          const fd = new FormData();
          fd.append('file', file);
          const r = await fetch(`/api/project-cover/${{slug}}`, {{method: 'POST', body: fd}});
          const data = await r.json();
          if (r.ok && data.ok) {{
            // Replace the cover slot with a fresh image. Bypass cache with a
            // ?t= query so the browser doesn't show the OLD cover.
            const img = document.createElement('img');
            img.src = data.cover_url + '&t=' + Date.now();
            img.alt = '';
            img.loading = 'lazy';
            slot.classList.remove('empty', 'uploading');
            slot.innerHTML = '';
            slot.appendChild(img);
            const overlay = document.createElement('div');
            overlay.className = 'cover-overlay';
            overlay.textContent = 'Change cover';
            slot.appendChild(overlay);
          }} else {{
            slot.classList.remove('uploading');
            alert('Upload failed: ' + (data.error || 'unknown'));
          }}
        }} catch (e) {{
          slot.classList.remove('uploading');
          alert('Upload error: ' + e.message);
        }}
        // Reset the file input so the same file can be re-picked if needed
        ev.target.value = '';
      }});
    }});
  }})();

  // Hover-play the CHARACTER / LOCATION reference clip over each card poster.
  // Ported from the COVEN series dashboard (mechanism A): poster-only until
  // hover, a same-origin muted <video> is injected (Drive can't be hotlinked
  // cross-origin), played with a resilient retry, and fully torn down on leave
  // so no off-screen clips keep buffering. Click is left to the cover-upload
  // handler above (change cover) / the card link.
  (function() {{
    function makeVideo(src) {{
      const v = document.createElement('video');
      v.className = 'vtile-video';
      v.muted = true; v.loop = true; v.autoplay = true;
      v.playsInline = true; v.setAttribute('playsinline', '');
      v.preload = 'auto'; v.src = src;
      return v;
    }}
    function resilientPlay(v) {{
      // The first play() can transiently reject (AbortError race); re-fire on
      // canplay/loadeddata and on two timed retries.
      const go = () => {{ const p = v.play(); if (p && p.catch) p.catch(() => {{}}); }};
      go();
      v.addEventListener('canplay', go, {{once: true}});
      v.addEventListener('loadeddata', go, {{once: true}});
      setTimeout(go, 120); setTimeout(go, 400);
    }}
    function enter(slot) {{
      if (slot.dataset.playing || !slot.dataset.vsrc) return;
      slot.dataset.playing = '1';
      const v = makeVideo(slot.dataset.vsrc);
      slot.appendChild(v);
      slot.classList.add('playing');
      resilientPlay(v);
    }}
    function leave(slot) {{
      const v = slot.querySelector('.vtile-video');
      if (v) {{ try {{ v.pause(); }} catch (e) {{}} v.removeAttribute('src'); v.load(); v.remove(); }}
      slot.classList.remove('playing');
      delete slot.dataset.playing;
    }}
    // pointerover/out BUBBLE (unlike mouseenter), so one delegated pair covers
    // every card, including ones added after load.
    document.addEventListener('pointerover', (e) => {{
      const slot = e.target.closest && e.target.closest('.card-cover.vtile');
      if (slot && !slot.contains(e.relatedTarget)) enter(slot);
    }});
    document.addEventListener('pointerout', (e) => {{
      const slot = e.target.closest && e.target.closest('.card-cover.vtile');
      if (slot && !slot.contains(e.relatedTarget)) leave(slot);
    }});
  }})();

  // ===== New Project modal =====
  let _scriptFile = null;
  function openNewProjectModal() {{
    const m = document.getElementById('new-proj-modal');
    if (m) m.classList.add('open');
  }}
  function closeNewProjectModal() {{
    const m = document.getElementById('new-proj-modal');
    if (m) m.classList.remove('open');
    _scriptFile = null;
    const dz = document.getElementById('dz');
    if (dz) {{
      dz.classList.remove('has-file');
      dz.querySelector('.dz-main').textContent = 'Drop your script here, or click to browse';
      dz.querySelector('.dz-sub').textContent = '.txt · .md · .docx · .pdf — up to 10 MB';
    }}
    const err = document.getElementById('np-error');
    if (err) err.classList.remove('show');
    const submit = document.getElementById('np-submit');
    if (submit) {{ submit.disabled = false; submit.textContent = 'Create Project'; }}
  }}

  function deriveTitleFromFilename(name) {{
    // "hollow_pilot.txt" → "Hollow Pilot"
    const base = name.replace(/\.[^.]+$/, '');
    return base.replace(/[-_]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).trim();
  }}

  function showNPError(msg) {{
    const el = document.getElementById('np-error');
    el.textContent = msg;
    el.classList.add('show');
  }}

  function selectRadio(group, value) {{
    document.querySelectorAll(`[data-radio-group="${{group}}"]`).forEach(c => {{
      c.classList.toggle('selected', c.dataset.value === value);
    }});
    document.getElementById(`np-${{group}}`).value = value;
  }}

  (function setupDropZone() {{
    document.addEventListener('DOMContentLoaded', () => {{
      const dz = document.getElementById('dz');
      const fileInput = document.getElementById('dz-file');
      if (!dz || !fileInput) return;

      function handleFile(file) {{
        if (!file) return;
        const okExt = /\.(txt|md|docx|pdf)$/i.test(file.name);
        if (!okExt) {{
          showNPError('Unsupported file type. Use .txt, .md, .docx, or .pdf.');
          return;
        }}
        if (file.size > 10 * 1024 * 1024) {{
          showNPError('File is over 10 MB.');
          return;
        }}
        _scriptFile = file;
        dz.classList.add('has-file');
        dz.querySelector('.dz-icon').textContent = '✓';
        dz.querySelector('.dz-main').textContent = file.name;
        dz.querySelector('.dz-sub').textContent = `${{(file.size/1024).toFixed(1)}} KB · ready to upload`;
        // Auto-fill title if empty
        const titleInput = document.getElementById('np-title');
        if (titleInput && !titleInput.value.trim()) {{
          titleInput.value = deriveTitleFromFilename(file.name);
        }}
        document.getElementById('np-error').classList.remove('show');
      }}

      dz.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', e => {{
        const f = e.target.files && e.target.files[0];
        if (f) handleFile(f);
      }});
      ['dragenter','dragover'].forEach(ev => dz.addEventListener(ev, e => {{
        e.preventDefault(); dz.classList.add('dragover');
      }}));
      ['dragleave','drop'].forEach(ev => dz.addEventListener(ev, e => {{
        e.preventDefault(); dz.classList.remove('dragover');
      }}));
      dz.addEventListener('drop', e => {{
        const f = e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) handleFile(f);
      }});

      // Hook radio groups
      document.querySelectorAll('[data-radio-group="type"]').forEach(c => {{
        c.addEventListener('click', () => selectRadio('type', c.dataset.value));
      }});
      document.querySelectorAll('[data-radio-group="depth"]').forEach(c => {{
        c.addEventListener('click', () => selectRadio('depth', c.dataset.value));
      }});
      document.querySelectorAll('[data-radio-group="global"]').forEach(c => {{
        c.addEventListener('click', () => selectRadio('global', c.dataset.value));
      }});

      // Submit handler
      document.getElementById('np-submit').addEventListener('click', async () => {{
        const title = document.getElementById('np-title').value.trim();
        const type = document.getElementById('np-type').value;
        const locale = document.getElementById('np-locale').value;
        const depth = document.getElementById('np-depth').value;
        const globalPreset = document.getElementById('np-global').value;
        const parentShow = document.getElementById('np-parent').value.trim();
        const notes = document.getElementById('np-notes').value.trim();

        // Validation
        if (!_scriptFile) {{ showNPError('Please upload a script first.'); return; }}
        if (!title) {{ showNPError('Title is required.'); return; }}
        if (!depth) {{ showNPError('Pick how far to take it.'); return; }}

        // Build multipart
        const fd = new FormData();
        fd.append('file', _scriptFile);
        fd.append('title', title);
        fd.append('type', type);
        fd.append('locale', locale);
        fd.append('depth', depth);
        fd.append('global_preset', globalPreset);
        if (parentShow) fd.append('parent_show', parentShow);
        if (notes) fd.append('notes', notes);

        const submitBtn = document.getElementById('np-submit');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Uploading + starting…';

        try {{
          const res = await fetch('/api/new-project', {{ method: 'POST', body: fd }});
          // Don't blindly call .json() — Render returns HTML on timeout / mid-deploy.
          // Read as text first, sniff content type, and surface a clear error.
          const raw = await res.text();
          const ct = res.headers.get('content-type') || '';
          let data;
          if (ct.includes('application/json')) {{
            try {{
              data = JSON.parse(raw);
            }} catch (_) {{
              showNPError(`Server returned malformed JSON (status ${{res.status}}). First 200 chars: ${{raw.slice(0, 200)}}`);
              submitBtn.disabled = false;
              submitBtn.textContent = 'Create Project';
              return;
            }}
          }} else {{
            // Likely an HTML error page from Render (504 gateway timeout, mid-deploy, etc.)
            const isHtml = raw.trim().startsWith('<');
            const snippet = isHtml ? '(HTML response — server may be deploying or timed out)' : raw.slice(0, 200);
            showNPError(`Server error (status ${{res.status}}): ${{snippet}}. Wait ~2 min for any deploy to complete, then retry.`);
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Project';
            return;
          }}
          if (!res.ok || !data.ok) {{
            showNPError(data.error || `Server error (${{res.status}})`);
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Project';
            return;
          }}
          // Redirect to gallery so user sees live progress
          window.location.href = data.redirect_url || `/gallery/${{data.gallery_slug}}`;
        }} catch (e) {{
          showNPError('Network error: ' + e.message + '. Check connection or wait if server is deploying.');
          submitBtn.disabled = false;
          submitBtn.textContent = 'Create Project';
        }}
      }});

      // Close on backdrop click (not modal body)
      const backdrop = document.getElementById('new-proj-modal');
      backdrop.addEventListener('click', e => {{
        if (e.target === backdrop) closeNewProjectModal();
      }});
      // ESC key
      document.addEventListener('keydown', e => {{
        if (e.key === 'Escape' && backdrop.classList.contains('open')) closeNewProjectModal();
      }});
    }});
  }})();
</script>

<!-- ===== New Project Modal ===== -->
<div class="modal-backdrop" id="new-proj-modal">
  <div class="modal">
    <div class="modal-header">
      <h2>+ New Project</h2>
      <button class="modal-close" onclick="closeNewProjectModal()">✕</button>
    </div>
    <div class="modal-body">

      <!-- File upload -->
      <div class="modal-field">
        <label>Script <span class="hint">— upload .txt, .md, .docx, or .pdf</span></label>
        <div class="drop-zone" id="dz">
          <div class="dz-icon">📄</div>
          <div class="dz-main">Drop your script here, or click to browse</div>
          <div class="dz-sub">.txt · .md · .docx · .pdf — up to 10 MB</div>
          <input type="file" id="dz-file" accept=".txt,.md,.docx,.pdf" style="display:none">
        </div>
      </div>

      <!-- Title -->
      <div class="modal-field">
        <label>Title <span class="hint">— will be the show name (auto-filled from script filename)</span></label>
        <input type="text" id="np-title" placeholder="e.g. Hollow">
      </div>

      <!-- Type + Locale -->
      <div class="form-row">
        <div class="modal-field">
          <label>Type</label>
          <div class="radio-grid">
            <div class="radio-card selected" data-radio-group="type" data-value="series">
              <div class="rc-title">Series</div><div class="rc-sub">Multi-episode</div>
            </div>
            <div class="radio-card" data-radio-group="type" data-value="poc">
              <div class="rc-title">POC</div><div class="rc-sub">Proof of concept</div>
            </div>
            <div class="radio-card" data-radio-group="type" data-value="concept">
              <div class="rc-title">Concept</div><div class="rc-sub">Pitch / treatment</div>
            </div>
            <div class="radio-card" data-radio-group="type" data-value="client">
              <div class="rc-title">Client</div><div class="rc-sub">Paid project</div>
            </div>
          </div>
          <input type="hidden" id="np-type" value="series">
        </div>
        <div class="modal-field">
          <label>Locale <span class="hint">— affects dialect + props</span></label>
          <select id="np-locale">
            <option value="generic">Generic</option>
            <option value="jakarta">Jakarta (Bahasa)</option>
            <option value="manila">Manila (Tagalog)</option>
            <option value="seoul">Seoul (Korean)</option>
          </select>
        </div>
      </div>

      <!-- Global film look (preset) -->
      <div class="modal-field">
        <label>Global film look <span class="hint">— the cinematic style prepended to every shot</span></label>
        <div class="global-grid">
          {global_cards_html}
        </div>
        <input type="hidden" id="np-global" value="{DEFAULT_PRESET_ID}">
      </div>

      <!-- Depth choice -->
      <div class="modal-field">
        <label>How far to take it</label>
        <div class="depth-grid">
          <div class="depth-card" data-radio-group="depth" data-value="text">
            <div class="dc-left">
              <div class="dc-title">🟢 Shotlist only</div>
              <div class="dc-sub">Atomize script + populate 5 bibles as text. Fastest, cheapest.</div>
            </div>
            <div class="dc-cost">~5 min<br>$0</div>
          </div>
          <div class="depth-card" data-radio-group="depth" data-value="bibles">
            <div class="dc-left">
              <div class="dc-title">🟡 + Asset refs</div>
              <div class="dc-sub">Also generate character / location / prop reference images.</div>
            </div>
            <div class="dc-cost">~30 min<br>~$3</div>
          </div>
          <div class="depth-card" data-radio-group="depth" data-value="masters">
            <div class="dc-left">
              <div class="dc-title">🔴 + Master shots</div>
              <div class="dc-sub">Full pre-production: shotlist + asset refs + 1–2 rendered master shots per scene.</div>
            </div>
            <div class="dc-cost">~60 min<br>~$5</div>
          </div>
        </div>
        <input type="hidden" id="np-depth" value="">
      </div>

      <!-- Optional fields -->
      <div class="form-row">
        <div class="modal-field">
          <label>Parent Show <span class="hint">— optional, for spinoffs</span></label>
          <input type="text" id="np-parent" placeholder="e.g. sajangnim">
        </div>
        <div class="modal-field">
          <label>Notes <span class="hint">— optional</span></label>
          <input type="text" id="np-notes" placeholder="anything to remember">
        </div>
      </div>

      <!-- Error display -->
      <div class="modal-error" id="np-error"></div>

      <!-- Actions -->
      <div class="modal-actions">
        <button class="btn-cancel" onclick="closeNewProjectModal()">Cancel</button>
        <button class="btn-submit" id="np-submit">Create Project</button>
      </div>
    </div>
  </div>
</div>

</body>
</html>'''

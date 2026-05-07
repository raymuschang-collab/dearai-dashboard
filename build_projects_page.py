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

    # Cover slot — image if cover exists, else "+" placeholder. Clicking the
    # cover OR the "+" overlay opens a hidden file input (per-card) which
    # POSTs to /api/project-cover/<slug>. Wrapping <a class="cover-link"> uses
    # `data-cover-slug` so the JS can find the matching file input.
    if cover_url:
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
          <div class="card-meta">
            <span class="card-eps">{ep_count} episode{"s" if ep_count != 1 else ""}</span>
            <span class="card-sep">·</span>
            <span class="card-owner">{_html.escape(owner)}</span>
          </div>
          <div class="card-meta">
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
    cards_html = "".join(_project_card(p) for p in visible_default)
    if not cards_html:
        cards_html = '<div class="empty">No projects yet. Click <b>+ New Project</b> to start.</div>'

    user_chip = (
        f'<span id="user-chip" data-email="{_html.escape(user_email)}" '
        f'title="Logged in as {_html.escape(user_email)}"></span>'
        f'<a class="refresh" href="/auth/logout">Log out</a>'
        if user_email else ""
    )

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
  .card-row1 {{ display: flex; gap: 6px; align-items: center; }}
  .card-title {{
    margin: 0; font-size: 16px; font-weight: 600; line-height: 1.3;
  }}
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
  <button class="new-proj-btn" onclick="alert('Coming in commit 5 — modal + form. For now, edit the master sheet directly: https://docs.google.com/spreadsheets/d/1J-x4b4hshrX3wdMItboQJzcjKkAff_jnKEiIKjpy0g0')">+ New Project</button>
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
</script>
</body>
</html>'''

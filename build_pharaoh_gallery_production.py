#!/usr/bin/env python3
"""
PRODUCTION VARIANT of build_pharaoh_gallery.py.

Differences vs the team gallery:
  - Storyboards section is a single vertical column. Each row =
    one set: [iter 1 + iter 2 storyboards on the left] | [list of
    that set's per-shot video prompts on the right]. So the production
    crew can read each shot's prompt next to the visual it belongs to.
  - Other tabs (Characters / Locations / Costume / Props / Effects)
    render the same as the team gallery.

Output: pharaoh_king_gallery_PRODUCTION.html
"""
from __future__ import annotations

import base64
import html
import json
import os
import re

import gspread

from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"
OUTPUT = "/Users/raymuschang/Desktop/Shotlist Workflows/pharaoh_king_gallery_PRODUCTION.html"
HIEROGLYPHICS_BG = "/Users/raymuschang/Desktop/Shotlist Workflows/hieroglyphics_bg.png"


def load_bg_data_url() -> str:
    """Embed hieroglyphics PNG as base64 data URL for self-contained HTML."""
    if not os.path.exists(HIEROGLYPHICS_BG):
        return ""
    with open(HIEROGLYPHICS_BG, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


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


def thumb(file_id: str | None, w: int = 1000) -> str:
    """Use Google's lh3 CDN — much more reliable for embedded images than
    drive.google.com/thumbnail (which throttles + rejects file:// origins)."""
    if not file_id:
        return ""
    return f"https://lh3.googleusercontent.com/d/{file_id}=w{w}"


def view(file_id: str | None) -> str:
    if not file_id:
        return ""
    return f"https://drive.google.com/file/d/{file_id}/view"


def main():
    bg_data_url = load_bg_data_url()
    if bg_data_url:
        print(f"  hieroglyphics bg loaded ({len(bg_data_url)//1024}KB base64)")

    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)

    # === CHARACTERS ===
    ws = sh.worksheet("CHARACTERS")
    rows = ws.get_all_records()
    characters = []
    for r in rows:
        name = (r.get("Name") or "").strip()
        if not name:
            continue
        iter1 = drive_id(r.get("Iter 1 URL (off-white bg)") or "")
        iter2 = drive_id(r.get("Iter 2 URL (dark bg)") or "")
        characters.append({
            "name": name,
            "alias": r.get("Alias", "") or "",
            "role": r.get("Role / Archetype", "") or "",
            "age": r.get("Age", "") or "",
            "personality": r.get("Personality", "") or "",
            "theme": r.get("Core theme", "") or "",
            "wardrobe": r.get("Wardrobe", "") or "",
            "feedback": r.get("Feedback", "") or "",
            "iters": [
                {"label": "Off-white bg", "id": iter1, "thumb": thumb(iter1), "url": view(iter1)} if iter1 else None,
                {"label": "Dark bg", "id": iter2, "thumb": thumb(iter2), "url": view(iter2)} if iter2 else None,
            ],
        })

    # === LOCATIONS ===
    ws = sh.worksheet("LOCATIONS")
    raw = ws.get("A5:N100", value_render_option="FORMATTED_VALUE")
    locations_by_name = {}
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
        feedback = row[13] if len(row) > 13 else ""
        if name not in locations_by_name:
            locations_by_name[name] = {
                "name": name, "type": type_, "description": desc,
                "lighting": lighting, "time": time_of_day,
                "feedback": feedback, "iters": [],
            }
        for label, fid in [(f"{shot_size} – iter 1", i1), (f"{shot_size} – iter 2", i2)]:
            if fid:
                locations_by_name[name]["iters"].append({
                    "label": label, "id": fid, "thumb": thumb(fid), "url": view(fid),
                })
    locations = list(locations_by_name.values())

    # === COSTUME / PROPS / EFFECTS — same schema ===
    def read_bible(tab_name: str):
        ws = sh.worksheet(tab_name)
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
                "first_shot": row[3] if len(row) > 3 else "",
                "feedback": row[10] if len(row) > 10 else "",
                "iters": [it for it in [
                    {"label": "Iter 1", "id": i1, "thumb": thumb(i1), "url": view(i1)} if i1 else None,
                    {"label": "Iter 2", "id": i2, "thumb": thumb(i2), "url": view(i2)} if i2 else None,
                ] if it],
            })
        return out

    costume = read_bible("COSTUME")
    props = read_bible("PROPS")
    effects = read_bible("EFFECTS")

    # === VIDEO PROMPTS — read globals (rendered once as GLOBAL block) ===
    # Living-doc simplified schema: 14-17 rows, ONE per SET.
    #   B1 = camera global ("Shot with arri 35.")
    #   B2 = audio/dialogue global
    # The per-set Video Prompt itself (col C) is a formula = globals + body
    # from Storyboard Prompts!C{row}. We don't need col C for the gallery —
    # we render the GLOBAL block once and pull the body straight from the
    # Storyboard Prompts tab below.
    ws = sh.worksheet("Video Prompts")
    global_camera = ws.acell("B1").value or ""
    global_audio  = ws.acell("B2").value or ""
    video_global = "\n".join([s for s in [global_camera, global_audio] if s])

    # === STORYBOARDS ===
    # Living-doc schema: rows 1-8 globals, row 10 headers, row 11+ data.
    # col C = body (5-shot list, no preamble), the same body referenced by
    # Video Prompts col C via formula.
    ws = sh.worksheet("Storyboard Prompts")
    sb_rows = ws.get("A11:I35", value_render_option="FORMATTED_VALUE")
    storyboards = []
    for row in sb_rows:
        if not row or not row[0]:
            continue
        body = row[2] if len(row) > 2 else ""
        i1 = drive_id(row[6] if len(row) > 6 else "")
        i2 = drive_id(row[7] if len(row) > 7 else "")
        storyboards.append({
            "set_num": row[0],
            "shot_range": row[1] if len(row) > 1 else "",
            "body": body,    # the per-set 5-shot list — rendered as COMBINED PROMPT
            "iters": [it for it in [
                {"label": "Iter 1", "id": i1, "thumb": thumb(i1, 1400), "url": view(i1)} if i1 else None,
                {"label": "Iter 2", "id": i2, "thumb": thumb(i2, 1400), "url": view(i2)} if i2 else None,
            ] if it],
        })

    data = {
        "show": "Strike! Pharaoh King",
        "episode": "Episode 1 — The Isfet Spawn",
        "stats": {
            "characters": len(characters),
            "locations": len(locations),
            "costume": len(costume),
            "props": len(props),
            "effects": len(effects),
            "storyboards": len(storyboards),
        },
        "characters": characters,
        "locations": locations,
        "costume": costume,
        "props": props,
        "effects": effects,
        "storyboards": storyboards,
        # GLOBAL preamble shared by every shot — read once from B1+B2 of the
        # Video Prompts tab. Rendered as a single block above the combined
        # prompt for each set in the production storyboard view.
        "video_global": video_global,
    }

    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(data['show'])} — {html.escape(data['episode'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=Lora:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --paper:        #f5ead2;
    --paper-deep:   #ecd9b1;
    --card:         #fff8e7;
    --card-border:  #d4b896;
    --ink:          #3a2818;
    --ink-soft:     #6b5840;
    --ink-mute:     #8c7556;
    --terracotta:   #a0552f;
    --terracotta-l: #c9803a;
    --gold:         #b8862f;
    --shadow:       rgba(80, 50, 20, 0.18);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: "Lora", Georgia, serif;
    background: var(--paper);
    color: var(--ink);
    min-height: 100vh;
    line-height: 1.55;
    position: relative;
  }}
  /* Faded Egyptian hieroglyphics background — fixed, behind everything,
     low opacity so the asset cards stay the focal point. */
  body::before {{
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background-image: url("{bg_data_url}");
    background-size: 1400px auto;
    background-repeat: repeat;
    background-position: center top;
    opacity: 0.18;
    filter: contrast(0.95) brightness(1.05);
  }}
  /* Subtle vignette + warm wash on top of the hieroglyphics */
  body::after {{
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background:
      radial-gradient(1200px 600px at 20% -10%, rgba(184, 134, 47, 0.10), transparent 60%),
      radial-gradient(1000px 500px at 80% 110%, rgba(160, 85, 47, 0.08), transparent 60%);
  }}
  .wrap {{ max-width: 1320px; margin: 0 auto; padding: 32px 28px 80px; }}
  header.hero {{
    text-align: center;
    padding: 24px 0 32px;
    border-bottom: 1px dashed var(--card-border);
    margin-bottom: 28px;
  }}
  header.hero .show {{
    font-family: "Cinzel", serif;
    font-size: 14px; letter-spacing: 4px;
    text-transform: uppercase;
    color: var(--terracotta);
    margin-bottom: 6px;
  }}
  header.hero h1 {{
    font-family: "Cinzel", serif;
    font-size: 36px; font-weight: 700;
    letter-spacing: 1px; margin: 0 0 14px;
    color: var(--ink);
  }}
  header.hero .stats {{
    display: flex; flex-wrap: wrap; gap: 28px; justify-content: center;
    font-size: 13px; color: var(--ink-soft);
    letter-spacing: 0.5px;
  }}
  header.hero .stats span b {{ color: var(--terracotta); font-weight: 600; }}

  nav.tabs {{
    display: flex; flex-wrap: wrap; gap: 4px; justify-content: center;
    margin-bottom: 28px;
    padding: 6px;
    background: rgba(255, 255, 255, 0.5);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    width: fit-content;
    margin-left: auto; margin-right: auto;
  }}
  nav.tabs button {{
    background: transparent; border: 0;
    font-family: "Cinzel", serif;
    font-size: 13px; letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--ink-soft);
    padding: 10px 18px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
  }}
  nav.tabs button:hover {{ color: var(--ink); background: rgba(255, 255, 255, 0.5); }}
  nav.tabs button.active {{
    background: var(--terracotta);
    color: #fff8e7;
    box-shadow: 0 2px 8px var(--shadow);
  }}

  section.tab-content {{ display: none; }}
  section.tab-content.active {{ display: block; }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 20px;
  }}
  .grid.wide {{ grid-template-columns: repeat(auto-fill, minmax(560px, 1fr)); }}

  .card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px var(--shadow);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    display: flex; flex-direction: column;
  }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 6px 18px var(--shadow); }}

  .card-img-grid {{
    display: grid; gap: 4px;
    background: var(--paper-deep);
  }}
  .card-img-grid.cols-1 {{ grid-template-columns: 1fr; }}
  .card-img-grid.cols-2 {{ grid-template-columns: 1fr 1fr; }}
  .card-img-grid.cols-2-tall {{ grid-template-columns: 1fr 1fr; grid-auto-rows: 1fr; }}
  .card-img-grid.cols-2-x2 {{ grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }}

  .img-cell {{
    position: relative;
    aspect-ratio: 16 / 9;
    background: var(--paper-deep);
    overflow: hidden;
    cursor: zoom-in;
  }}
  .img-cell.square {{ aspect-ratio: 1 / 1; }}
  .img-cell img {{
    width: 100%; height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.3s ease;
  }}
  .img-cell:hover img {{ transform: scale(1.04); }}
  .img-cell .label {{
    position: absolute; left: 8px; bottom: 8px;
    background: rgba(58, 40, 24, 0.78);
    color: #f5ead2;
    font-size: 10px; letter-spacing: 1px;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 4px;
    font-family: "Cinzel", serif;
  }}
  .img-cell .empty {{
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    color: var(--ink-mute); font-style: italic; font-size: 13px;
  }}

  .card-body {{ padding: 14px 18px 18px; flex: 1; }}
  .card-body h3 {{
    font-family: "Cinzel", serif;
    font-size: 17px; font-weight: 600;
    margin: 0 0 4px; color: var(--ink);
    letter-spacing: 0.5px;
  }}
  .card-body .alias {{
    color: var(--terracotta-l); font-size: 12px;
    font-style: italic; margin-bottom: 10px;
  }}
  .card-body .meta {{
    display: flex; flex-wrap: wrap; gap: 6px;
    font-size: 11px; margin: 8px 0 10px;
  }}
  .card-body .meta .chip {{
    background: rgba(184, 134, 47, 0.15);
    color: var(--ink-soft);
    padding: 2px 8px; border-radius: 4px;
    letter-spacing: 0.3px;
  }}
  .card-body .desc {{
    font-size: 13px; color: var(--ink-soft);
    line-height: 1.5;
  }}
  .card-body .desc.clamp {{
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}
  .card-body .feedback {{
    margin-top: 10px; padding: 8px 10px;
    background: rgba(255, 244, 179, 0.6);
    border-left: 3px solid var(--gold);
    font-size: 12px; color: var(--ink-soft);
    border-radius: 0 4px 4px 0;
  }}
  .card-body .feedback strong {{ color: var(--terracotta); }}

  /* Lightbox */
  .lightbox {{
    display: none;
    position: fixed; inset: 0;
    background: rgba(28, 18, 8, 0.92);
    z-index: 9999;
    align-items: center; justify-content: center;
    padding: 40px;
    cursor: zoom-out;
  }}
  .lightbox.active {{ display: flex; }}
  .lightbox img {{
    max-width: 100%; max-height: 100%;
    object-fit: contain;
    border-radius: 6px;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
  }}
  .lightbox .close {{
    position: absolute; top: 20px; right: 24px;
    color: var(--paper); background: none; border: 0;
    font-size: 28px; cursor: pointer;
    font-family: "Cinzel", serif;
  }}

  footer {{
    margin-top: 60px; padding-top: 24px;
    border-top: 1px dashed var(--card-border);
    text-align: center; font-size: 11px;
    color: var(--ink-mute); letter-spacing: 1px;
    text-transform: uppercase;
    font-family: "Cinzel", serif;
  }}

  /* ====== PRODUCTION storyboard layout ======
     Single vertical column. Each set = [storyboard panels] | [video prompts].
     The storyboard column is fixed-width-ish (~58%); the prompts column
     fills the rest. On narrow screens it stacks. */
  .sb-prod-list {{ display: flex; flex-direction: column; gap: 28px; }}
  .sb-prod-row {{
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr);
    gap: 22px;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 18px;
    box-shadow: 0 2px 8px var(--shadow);
  }}
  .sb-prod-row .sb-head {{
    grid-column: 1 / -1;
    border-bottom: 1px dashed var(--card-border);
    padding-bottom: 10px;
    margin-bottom: 4px;
  }}
  .sb-prod-row .sb-head h3 {{
    font-family: "Cinzel", serif;
    font-size: 18px;
    margin: 0;
    color: var(--ink);
    letter-spacing: 1px;
  }}
  .sb-prod-row .sb-head .shots-meta {{
    font-size: 12px;
    color: var(--terracotta);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    font-family: "Cinzel", serif;
    margin-top: 3px;
  }}
  .sb-prod-imgs {{
    display: flex; flex-direction: column; gap: 10px;
  }}
  .sb-prod-imgs .img-cell {{
    aspect-ratio: 21 / 9;
    border-radius: 6px;
    border: 1px solid var(--card-border);
  }}
  .sb-prod-prompts {{
    display: flex; flex-direction: column; gap: 10px;
    max-height: 100%;
    overflow-y: auto;
  }}
  /* Two prompt blocks per set: GLOBAL (once) + COMBINED PROMPT (all shots) */
  .sb-prod-block {{
    background: rgba(245, 234, 210, 0.55);
    border-left: 3px solid var(--terracotta-l);
    border-radius: 0 6px 6px 0;
    padding: 10px 14px;
  }}
  .sb-prod-block.global {{ border-left-color: var(--gold); }}
  .sb-prod-block .block-label {{
    font-family: "Cinzel", serif;
    font-size: 10px;
    color: var(--terracotta);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 6px;
    font-weight: 700;
  }}
  .sb-prod-block.global .block-label {{ color: var(--gold); }}
  .sb-prod-block .block-text {{
    font-size: 12.5px;
    color: var(--ink-soft);
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: "JetBrains Mono", "SF Mono", Menlo, monospace;
  }}
  .sb-prod-block.empty .block-text {{
    color: var(--ink-mute);
    font-style: italic;
    font-family: "Lora", serif;
  }}

  @media (max-width: 900px) {{
    .sb-prod-row {{ grid-template-columns: 1fr; }}
  }}

  @media (max-width: 720px) {{
    .grid {{ grid-template-columns: 1fr; }}
    header.hero h1 {{ font-size: 26px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="show">{html.escape(data['show'])}</div>
    <h1>{html.escape(data['episode'])}</h1>
    <div class="stats" id="stats"></div>
  </header>

  <nav class="tabs" id="tabs"></nav>

  <main id="main"></main>

  <footer>The Producer's Codex · Production crew reference · Refresh by re-running build_pharaoh_gallery_production.py</footer>
</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <button class="close" onclick="closeLightbox()">×</button>
  <img id="lightbox-img" src="" alt="" referrerpolicy="no-referrer">
</div>

<script>
const DATA = {embedded};

const TABS = [
  {{ key: "characters",   label: "Characters" }},
  {{ key: "locations",    label: "Locations" }},
  {{ key: "costume",      label: "Costumes" }},
  {{ key: "props",        label: "Props" }},
  {{ key: "effects",      label: "Effects" }},
  {{ key: "storyboards",  label: "Storyboards" }},
];

function escapeHtml(s) {{
  return (s || "").replace(/[&<>"']/g, c => (
    {{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]
  ));
}}

function img(it) {{
  if (!it || !it.id) return '<div class="img-cell"><div class="empty">no image</div></div>';
  const big = it.thumb.replace(/=w\d+$/, '=w2400');
  return `<div class="img-cell" onclick="openLightbox('${{big}}')">
    <img src="${{it.thumb}}" alt="${{escapeHtml(it.label)}}" loading="lazy" referrerpolicy="no-referrer">
    <div class="label">${{escapeHtml(it.label)}}</div>
  </div>`;
}}

function imgGrid(iters, layout) {{
  const cells = (iters || []).filter(Boolean).map(img).join("");
  return `<div class="card-img-grid ${{layout}}">${{cells}}</div>`;
}}

function feedbackBlock(text) {{
  if (!text || !text.trim()) return "";
  return `<div class="feedback"><strong>Feedback:</strong> ${{escapeHtml(text)}}</div>`;
}}

function renderCharacters(items) {{
  return items.map(c => {{
    const iters = (c.iters || []).filter(Boolean);
    const layout = iters.length === 2 ? "cols-2" : "cols-1";
    return `<div class="card">
      ${{imgGrid(iters, layout)}}
      <div class="card-body">
        <h3>${{escapeHtml(c.name)}}</h3>
        ${{c.alias ? `<div class="alias">${{escapeHtml(c.alias)}}</div>` : ""}}
        <div class="meta">
          ${{c.role ? `<span class="chip">${{escapeHtml(c.role)}}</span>` : ""}}
          ${{c.age ? `<span class="chip">${{escapeHtml(c.age)}}</span>` : ""}}
        </div>
        <div class="desc clamp">${{escapeHtml(c.theme || c.personality || c.wardrobe || "")}}</div>
        ${{feedbackBlock(c.feedback)}}
      </div>
    </div>`;
  }}).join("");
}}

function renderLocations(items) {{
  return items.map(l => {{
    const iters = (l.iters || []).filter(Boolean);
    const layout = iters.length >= 4 ? "cols-2-x2" : (iters.length >= 2 ? "cols-2" : "cols-1");
    return `<div class="card">
      ${{imgGrid(iters, layout)}}
      <div class="card-body">
        <h3>${{escapeHtml(l.name)}}</h3>
        <div class="meta">
          ${{l.type ? `<span class="chip">${{escapeHtml(l.type)}}</span>` : ""}}
          ${{l.time ? `<span class="chip">${{escapeHtml(l.time)}}</span>` : ""}}
        </div>
        <div class="desc clamp">${{escapeHtml(l.description || "")}}</div>
        ${{feedbackBlock(l.feedback)}}
      </div>
    </div>`;
  }}).join("");
}}

function renderBibles(items, kind) {{
  return items.map(b => {{
    const iters = (b.iters || []).filter(Boolean);
    const layout = iters.length === 2 ? "cols-2" : "cols-1";
    const cells = iters.map(it => {{
      const big = it.thumb.replace(/=w\d+$/, '=w2400');
      return `<div class="img-cell square" onclick="openLightbox('${{big}}')">
        <img src="${{it.thumb}}" alt="${{escapeHtml(it.label)}}" loading="lazy" referrerpolicy="no-referrer">
        <div class="label">${{escapeHtml(it.label)}}</div>
      </div>`;
    }}).join("") || `<div class="img-cell square"><div class="empty">no image</div></div>`;
    return `<div class="card">
      <div class="card-img-grid ${{layout}}">${{cells}}</div>
      <div class="card-body">
        <h3>${{escapeHtml(b.name)}}</h3>
        ${{b.used_by ? `<div class="alias">${{escapeHtml(b.used_by)}}</div>` : ""}}
        <div class="desc clamp">${{escapeHtml(b.description || "")}}</div>
        ${{feedbackBlock(b.feedback)}}
      </div>
    </div>`;
  }}).join("");
}}

// PRODUCTION variant: each set is one row.
//   Left:  iter 1 + iter 2 storyboards stacked vertically
//   Right: GLOBAL block (once, from Video Prompts B1+B2)
//          + COMBINED PROMPT block (the per-set 5-shot body from Storyboard Prompts col C)
function renderStoryboards(items) {{
  return items.map(s => {{
    const iters = (s.iters || []).filter(Boolean);
    const imgsHtml = iters.length
      ? iters.map(it => {{
          const big = it.thumb.replace(/=w\d+$/, '=w2400');
          return `<div class="img-cell" onclick="openLightbox('${{big}}')">
            <img src="${{it.thumb}}" alt="${{escapeHtml(it.label)}}" loading="lazy" referrerpolicy="no-referrer">
            <div class="label">${{escapeHtml(it.label)}}</div>
          </div>`;
        }}).join("")
      : `<div class="img-cell"><div class="empty">no storyboards yet</div></div>`;

    const body = (s.body || "").trim();
    const globalText = (DATA.video_global || "").trim();

    const globalBlock = globalText
      ? `<div class="sb-prod-block global">
          <div class="block-label">Global</div>
          <div class="block-text">${{escapeHtml(globalText)}}</div>
        </div>`
      : "";

    const combinedBlock = body
      ? `<div class="sb-prod-block">
          <div class="block-label">Combined Prompt · Shots ${{escapeHtml(s.shot_range)}}</div>
          <div class="block-text">${{escapeHtml(body)}}</div>
        </div>`
      : `<div class="sb-prod-block empty">
          <div class="block-label">Combined Prompt</div>
          <div class="block-text">— no prompt body yet —</div>
        </div>`;

    return `<div class="sb-prod-row">
      <div class="sb-head">
        <h3>Set ${{escapeHtml(s.set_num)}}</h3>
        <div class="shots-meta">Shots ${{escapeHtml(s.shot_range)}}</div>
      </div>
      <div class="sb-prod-imgs">${{imgsHtml}}</div>
      <div class="sb-prod-prompts">
        ${{globalBlock}}
        ${{combinedBlock}}
      </div>
    </div>`;
  }}).join("");
}}

function renderTab(key) {{
  const main = document.getElementById("main");
  let inner = "";
  if (key === "characters")  inner = renderCharacters(DATA.characters);
  else if (key === "locations")  inner = renderLocations(DATA.locations);
  else if (key === "costume")    inner = renderBibles(DATA.costume, "costume");
  else if (key === "props")      inner = renderBibles(DATA.props, "prop");
  else if (key === "effects")    inner = renderBibles(DATA.effects, "effect");
  else if (key === "storyboards") inner = renderStoryboards(DATA.storyboards);
  // Storyboards in the PRODUCTION gallery use their own list layout (sb-prod-list),
  // not the .grid card layout.
  if (key === "storyboards") {{
    main.innerHTML = `<section class="tab-content active"><div class="sb-prod-list">${{inner}}</div></section>`;
    return;
  }}
  const grid = (key === "locations" || key === "characters") ? "grid wide" : "grid";
  main.innerHTML = `<section class="tab-content active"><div class="${{grid}}">${{inner}}</div></section>`;
}}

function openLightbox(src) {{
  const lb = document.getElementById("lightbox");
  document.getElementById("lightbox-img").src = src;
  lb.classList.add("active");
}}
function closeLightbox() {{
  document.getElementById("lightbox").classList.remove("active");
  document.getElementById("lightbox-img").src = "";
}}
document.addEventListener("keydown", e => {{ if (e.key === "Escape") closeLightbox(); }});

function init() {{
  const stats = document.getElementById("stats");
  const items = [
    [`<b>${{DATA.stats.characters}}</b>`, "characters"],
    [`<b>${{DATA.stats.locations}}</b>`, "locations"],
    [`<b>${{DATA.stats.costume}}</b>`, "costumes"],
    [`<b>${{DATA.stats.props}}</b>`, "props"],
    [`<b>${{DATA.stats.effects}}</b>`, "effects"],
    [`<b>${{DATA.stats.storyboards}}</b>`, "storyboard sets"],
  ];
  stats.innerHTML = items.map(([n, l]) => `<span>${{n}} ${{l}}</span>`).join("");

  const tabsEl = document.getElementById("tabs");
  TABS.forEach((t, i) => {{
    const b = document.createElement("button");
    b.textContent = t.label;
    if (i === 0) b.classList.add("active");
    b.onclick = () => {{
      [...tabsEl.children].forEach(c => c.classList.remove("active"));
      b.classList.add("active");
      renderTab(t.key);
    }};
    tabsEl.appendChild(b);
  }});
  renderTab(TABS[0].key);
}}
init();
</script>
</body>
</html>
"""

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"✓ wrote {OUTPUT}")
    print(f"  size: {os.path.getsize(OUTPUT) // 1024} KB")


if __name__ == "__main__":
    main()

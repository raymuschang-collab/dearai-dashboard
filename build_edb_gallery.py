#!/usr/bin/env python3
"""
EDB pitch gallery builder — one HTML per concept, layout per the May 9
Look & Feel feedback (text panels stacked on top, storyboards in a
horizontal row below).

For each concept:
  1. Hero block — title + logline + counts + match-cut/strikethrough lede
  2. Full shotlist table (16-col v2.2 schema) so the team can scan all
     atomized shots in one place.
  3. Per-set cards — beat header + atomized shot list (text panels) on
     top, two storyboard iters in a row below.

Reads the live sheet for storyboard URLs so you can re-run after
generation completes and pick up new images. Self-contained HTML —
drop it on any laptop and double-click.

Usage:
    python3 build_edb_gallery.py
"""
from __future__ import annotations

import html
import re
import sys
import webbrowser
from pathlib import Path

import gspread

sys.path.insert(0, "/Users/raymuschang/Documents/Shotlist Workflows")
from auth import get_credentials  # type: ignore

CONCEPTS = [
    {
        "label": "Concept 01 — Tiny Tech, Big Lives",
        "sheet_id": "1TeAD8QAM8RfTtm8QzDzeCdNQzTKNwwOSXARn1DexM8Y",
        "logline": ("4 device setups (phone · pacemaker · EV · hearing aid) → "
                    "<em>'Every chip has a story.'</em> → 4 engineer profiles → "
                    "match-cuts back to setup. Singapore semiconductor industry "
                    "shown through the lives it touches."),
        "out": "/Users/raymuschang/Documents/Shotlist Workflows/edb_concept_01_gallery.html",
        "accent": "#22d3ee",  # cyan
    },
    {
        "label": "Concept 02 — The Semi-Con",
        "sheet_id": "1gETge6wYLD0FWQCdMP6yANsVJBiV4Lz-_ElyNH9U5F8",
        "logline": ("Direct address → 3 wrong answers struck through "
                    "(loud/dirty · repetitive · no career path) → pivot → "
                    "Vox-style mograph reveal scaling 1 transistor to <em>'1 in 10 "
                    "made here'</em>. The wordplay film."),
        "out": "/Users/raymuschang/Documents/Shotlist Workflows/edb_concept_02_gallery.html",
        "accent": "#34d399",  # mint
    },
]


def drive_id(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m: return m.group(1)
    m = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if m: return m.group(1)
    return None


def thumb(file_id: str | None, w: int = 1600) -> str:
    if not file_id:
        return ""
    return f"https://lh3.googleusercontent.com/d/{file_id}=w{w}"


def view(file_id: str | None) -> str:
    if not file_id:
        return ""
    return f"https://drive.google.com/file/d/{file_id}/view"


def beat_class(beat: str) -> str | None:
    b = (beat or "").strip().upper()
    if b == "HOOK": return "beat-hook"
    if b.startswith("JOLT"): return "beat-jolt"
    if b == "PAYOFF": return "beat-payoff"
    if b in ("CLIFF", "CLIFF SETUP", "CLIFF TAG", "TAG"): return "beat-cliff"
    if b == "FLASHBACK": return "beat-flashback"
    if b == "BRIDGE": return "beat-bridge"
    return None


def build_concept(c: dict) -> str:
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(c["sheet_id"])

    # Read full shotlist
    sl = sh.worksheet("Shotlist")
    sl_rows = sl.get("A2:P200", value_render_option="FORMATTED_VALUE")
    shots = []
    for r in sl_rows:
        r = r + [""] * 16
        if not r[0].strip().isdigit():
            continue
        shots.append({
            "num": int(r[0]), "dur": r[1], "type": r[2], "move": r[3],
            "merge": r[4], "desc": r[5], "dialogue": r[6], "accent": r[7],
            "microexp": r[8], "sfx": r[9], "props": r[10], "brand": r[11],
            "trans": r[12], "beat": r[13], "en": r[14], "prompt": r[15],
        })

    # Read SP tab for set ranges + iter URLs
    sp = sh.worksheet("Storyboard Prompts")
    sp_rows = sp.get("A11:I50", value_render_option="FORMATTED_VALUE")
    sets = []
    for r in sp_rows:
        r = r + [""] * 9
        if not r[0].strip().isdigit():
            continue
        set_num = int(r[0])
        shot_range = r[1] or ""
        status = r[5] or "Pending"
        iter1 = drive_id(r[6])
        iter2 = drive_id(r[7])
        # Pull this set's shots from the shotlist (5-shot windows)
        first = (set_num - 1) * 5
        set_shots = shots[first:first + 5]
        sets.append({
            "n": set_num, "range": shot_range, "status": status,
            "iter1": iter1, "iter2": iter2, "shots": set_shots,
        })

    # Render
    n_done = sum(1 for s in sets if s["status"].lower() == "done")
    accent = c["accent"]

    css = """
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body {
      font-family: -apple-system, "SF Pro Text", "Inter", system-ui, sans-serif;
      background: #f7f5f1; color: #1a1a1a; line-height: 1.5;
    }
    header.hero {
      max-width: 1280px; margin: 0 auto;
      padding: 56px 48px 32px;
      border-bottom: 1px solid #e8e4dc;
    }
    header.hero h1 {
      margin: 0 0 8px;
      font-family: "SF Pro Display", -apple-system, system-ui, sans-serif;
      font-size: 44px; font-weight: 700; letter-spacing: -0.02em;
    }
    header.hero h1 .accent { color: __ACCENT__; }
    header.hero .meta {
      display: flex; gap: 16px; flex-wrap: wrap;
      font-size: 13px; color: #6a6660;
    }
    header.hero .meta span:not(:last-child)::after {
      content: " · "; margin-left: 16px; color: #c8c2b6;
    }
    header.hero p.logline {
      margin: 24px 0 0; max-width: 820px;
      font-size: 17px; color: #3a3a3a; font-style: italic;
    }
    main { max-width: 1280px; margin: 0 auto; padding: 32px 48px 96px; }

    /* Section nav */
    .toc {
      display: flex; gap: 8px; flex-wrap: wrap;
      padding: 16px 0 32px; border-bottom: 1px solid #e8e4dc;
      margin-bottom: 40px;
    }
    .toc a {
      padding: 6px 14px; border-radius: 999px;
      font-size: 12px; font-weight: 600; letter-spacing: 0.02em;
      color: #1a1a1a; text-decoration: none;
      background: #fff; border: 1px solid #e8e4dc;
      transition: all 0.15s;
    }
    .toc a:hover { background: #1a1a1a; color: #f7f5f1; border-color: #1a1a1a; }
    .toc a.section { background: #1a1a1a; color: #f7f5f1; border-color: #1a1a1a; }

    /* Shotlist table */
    .shotlist-section { margin-bottom: 64px; }
    .shotlist-section h2 {
      font-size: 24px; font-weight: 700;
      margin: 0 0 16px; padding-bottom: 8px;
      border-bottom: 2px solid #1a1a1a; display: inline-block;
    }
    .shotlist-section .lede {
      font-size: 13px; color: #6a6660; margin-bottom: 18px;
    }
    table.shotlist {
      width: 100%; border-collapse: collapse;
      background: #fff; border: 1px solid #e8e4dc; border-radius: 10px;
      overflow: hidden; font-size: 12px;
    }
    table.shotlist thead {
      background: #1a1a1a; color: #f7f5f1;
    }
    table.shotlist th {
      padding: 10px 8px; text-align: left;
      font-weight: 600; font-size: 10px;
      letter-spacing: 0.06em; text-transform: uppercase;
    }
    table.shotlist td {
      padding: 9px 8px; border-bottom: 1px solid #efebe2;
      vertical-align: top;
    }
    table.shotlist tr:hover { background: #faf8f4; }
    table.shotlist .num {
      font-family: "SF Mono", monospace; font-size: 11px;
      font-weight: 700; color: #1a1a1a;
    }
    table.shotlist .dur { font-family: "SF Mono", monospace; color: #6a6660; }
    table.shotlist .pill {
      display: inline-block; padding: 1px 6px; border-radius: 3px;
      background: #efebe2; font-size: 9px; font-weight: 600;
      letter-spacing: 0.04em;
    }
    table.shotlist .desc { color: #1a1a1a; line-height: 1.4; }
    table.shotlist .dialogue {
      font-style: italic; color: #4a4a4a; font-size: 11px;
      margin-top: 3px;
    }
    table.shotlist .microexp {
      font-size: 10px; color: #8a8275;
      margin-top: 2px; font-variant-caps: small-caps;
      letter-spacing: 0.04em;
    }

    /* Beat color tags */
    .beat-pill {
      display: inline-block; padding: 1px 7px; border-radius: 3px;
      font-size: 9px; font-weight: 700; letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .beat-hook { background: #fcd34d; color: #5a3700; }
    .beat-jolt { background: #93c5fd; color: #1e3a5c; }
    .beat-payoff { background: #a7f3d0; color: #1a4a32; }
    .beat-cliff { background: #fca5a5; color: #6c1414; }
    .beat-flashback { background: #ddd6fe; color: #3a2a6c; }
    .beat-bridge { background: #e5e7eb; color: #4a4a4a; }

    /* Set cards — text on top, storyboards in a row below */
    .set-card {
      background: #fff; border: 1px solid #e8e4dc;
      border-radius: 14px; padding: 28px;
      margin-bottom: 28px;
      scroll-margin-top: 24px;
    }
    .set-head {
      display: flex; justify-content: space-between; align-items: baseline;
      margin-bottom: 20px; padding-bottom: 14px;
      border-bottom: 1px solid #efebe2;
    }
    .set-head h2 {
      margin: 0; font-size: 22px; font-weight: 700;
      letter-spacing: -0.01em;
    }
    .set-head .shots {
      font-size: 13px; color: #6a6660; font-weight: 500;
    }
    .set-head .status {
      font-size: 11px; padding: 4px 10px; border-radius: 4px;
      letter-spacing: 0.05em; text-transform: uppercase; font-weight: 600;
      background: #efebe2; color: #6a6660;
    }
    .set-head .status.done { background: #def4e2; color: #2c6c3a; }
    .set-head .status.failed { background: #f9d8d8; color: #962020; }

    /* TEXT PANELS — full width, on top */
    .shots-list {
      display: flex; flex-direction: column; gap: 10px;
      margin-bottom: 24px;
    }
    .shot {
      display: flex; gap: 14px;
      padding: 12px 14px; border-radius: 8px;
      background: #faf8f4;
    }
    .shot .num {
      flex: 0 0 36px; height: 36px;
      display: flex; align-items: center; justify-content: center;
      background: #1a1a1a; color: #f7f5f1;
      font-family: "SF Mono", monospace; font-size: 13px; font-weight: 700;
      border-radius: 6px;
    }
    .shot .body { flex: 1; min-width: 0; }
    .shot .meta {
      display: flex; gap: 8px; flex-wrap: wrap;
      font-family: "SF Mono", monospace; font-size: 10px;
      color: #6a6660; font-weight: 600;
      letter-spacing: 0.04em; margin-bottom: 4px;
    }
    .shot .meta .pill {
      padding: 1px 6px; background: #efebe2; border-radius: 3px;
    }
    .shot .meta .pill.dur { background: #fff; color: #1a1a1a; }
    .shot .desc { font-size: 13px; line-height: 1.45; }
    .shot .dialogue {
      font-size: 12px; color: #4a4a4a; font-style: italic;
      margin-top: 4px; padding-left: 10px;
      border-left: 2px solid #d8d2c4;
    }
    .shot .microexp {
      font-size: 11px; color: #8a8275;
      margin-top: 3px; font-variant-caps: small-caps;
      letter-spacing: 0.04em;
    }
    .shot .merge {
      font-size: 11px; color: __ACCENT__;
      margin-top: 4px; font-style: italic;
    }

    /* STORYBOARD ROW — 2 iters side-by-side, below the text */
    .storyboard-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    @media (max-width: 800px) {
      .storyboard-row { grid-template-columns: 1fr; }
    }
    .sb-iter {
      position: relative;
      border: 1px solid #e8e4dc; border-radius: 10px;
      overflow: hidden; background: #faf8f4;
    }
    .sb-iter img {
      width: 100%; height: auto; display: block; cursor: zoom-in;
    }
    .sb-iter .iter-label {
      position: absolute; top: 8px; left: 8px;
      padding: 3px 8px; background: rgba(0,0,0,0.7); color: #fff;
      font-size: 10px; letter-spacing: 0.05em; text-transform: uppercase;
      font-weight: 600; border-radius: 3px;
    }
    .sb-placeholder {
      aspect-ratio: 16/9;
      display: flex; align-items: center; justify-content: center;
      background: #faf8f4; border: 1px dashed #d8d2c4;
      border-radius: 10px;
      color: #a39a87; font-size: 12px;
      text-transform: uppercase; letter-spacing: 0.1em;
    }

    /* Lightbox */
    #lightbox {
      position: fixed; inset: 0; display: none;
      background: rgba(0,0,0,0.92); z-index: 100;
      align-items: center; justify-content: center;
    }
    #lightbox.open { display: flex; }
    #lightbox img { max-width: 95vw; max-height: 90vh; }
    #lightbox .close {
      position: absolute; top: 24px; right: 32px;
      color: #fff; font-size: 32px; cursor: pointer;
      background: none; border: none;
    }

    footer { max-width: 1280px; margin: 0 auto;
      padding: 32px 48px 64px; border-top: 1px solid #e8e4dc;
      font-size: 12px; color: #8a8275;
    }
    """.replace("__ACCENT__", accent)

    # Shotlist table rows
    table_rows = []
    for s in shots:
        bcls = beat_class(s["beat"])
        beat_html = (f'<span class="beat-pill {bcls}">{html.escape(s["beat"])}</span>'
                      if bcls else "")
        dialogue_html = (f'<div class="dialogue">{html.escape(s["dialogue"])}</div>'
                         if s["dialogue"] else "")
        microexp_html = (f'<div class="microexp">{html.escape(s["microexp"])}</div>'
                         if s["microexp"] else "")
        table_rows.append(f"""
          <tr>
            <td class="num">{s["num"]}</td>
            <td class="dur">{html.escape(str(s["dur"]))}s</td>
            <td><span class="pill">{html.escape(s["type"])}</span></td>
            <td><span class="pill">{html.escape(s["move"])}</span></td>
            <td>
              <div class="desc">{html.escape(s["desc"])}</div>
              {dialogue_html}{microexp_html}
            </td>
            <td>{html.escape(s["sfx"])}</td>
            <td>{beat_html}</td>
          </tr>
        """)
    shotlist_table_html = f"""
      <section class="shotlist-section" id="shotlist">
        <h2>Atomized Shotlist</h2>
        <div class="lede">{len(shots)} shots · v2.2 schema · auto-prompt formula in col P</div>
        <table class="shotlist">
          <thead>
            <tr>
              <th>#</th><th>Dur</th><th>Type</th><th>Move</th>
              <th>Description</th><th>SFX</th><th>Beat</th>
            </tr>
          </thead>
          <tbody>{"".join(table_rows)}</tbody>
        </table>
      </section>
    """

    # Set cards (text on top, storyboards in row below)
    set_blocks = []
    for s in sets:
        # Text panels — atomized shots in this set
        shot_panels = []
        for shot in s["shots"]:
            bcls = beat_class(shot["beat"])
            beat_pill = (f'<span class="beat-pill {bcls}">{html.escape(shot["beat"])}</span>'
                          if bcls else "")
            dialogue_html = (f'<div class="dialogue">{html.escape(shot["dialogue"])}</div>'
                             if shot["dialogue"] else "")
            microexp_html = (f'<div class="microexp">{html.escape(shot["microexp"])}</div>'
                             if shot["microexp"] else "")
            merge_html = (f'<div class="merge">⤳ {html.escape(shot["merge"])}</div>'
                          if shot["merge"] else "")
            shot_panels.append(f"""
              <div class="shot">
                <div class="num">{shot["num"]}</div>
                <div class="body">
                  <div class="meta">
                    <span class="pill dur">{html.escape(str(shot["dur"]))}s</span>
                    <span class="pill">{html.escape(shot["type"])}</span>
                    <span class="pill">{html.escape(shot["move"])}</span>
                    {beat_pill}
                  </div>
                  <div class="desc">{html.escape(shot["desc"])}</div>
                  {dialogue_html}{microexp_html}{merge_html}
                </div>
              </div>
            """)

        # Storyboard row — 2 iters
        sb_blocks = []
        for idx, fid in enumerate([s["iter1"], s["iter2"]], start=1):
            if fid:
                sb_blocks.append(f"""
                  <div class="sb-iter">
                    <span class="iter-label">Iter {idx}</span>
                    <img src="{thumb(fid)}" alt="Set {s["n"]} Iter {idx}"
                         data-full="{thumb(fid, 2400)}"
                         onclick="openLightbox(this)" loading="lazy">
                  </div>
                """)
            else:
                sb_blocks.append(f"""
                  <div class="sb-placeholder">storyboard pending</div>
                """)

        status_class = ("done" if s["status"].lower() == "done"
                         else "failed" if s["status"].lower() == "failed"
                         else "")
        set_blocks.append(f"""
          <section class="set-card" id="set-{s['n']}">
            <div class="set-head">
              <h2>Set {s['n']}</h2>
              <span class="shots">shots {html.escape(s["range"])}</span>
              <span class="status {status_class}">{html.escape(s["status"])}</span>
            </div>
            <div class="shots-list">{"".join(shot_panels)}</div>
            <div class="storyboard-row">{"".join(sb_blocks)}</div>
          </section>
        """)

    toc_links = (
        '<a href="#shotlist" class="section">Shotlist</a>' +
        "".join(f'<a href="#set-{s["n"]}">Set {s["n"]}</a>' for s in sets)
    )

    title_words = c["label"].split(" — ", 1)
    title_top = title_words[0] if len(title_words) > 0 else c["label"]
    title_bot = title_words[1] if len(title_words) > 1 else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(c["label"])} — EDB Pitch</title>
<style>{css}</style>
</head>
<body>

<header class="hero">
  <h1>{html.escape(title_top)}<br><span class="accent">{html.escape(title_bot)}</span></h1>
  <div class="meta">
    <span>EDB Semicon Pitch</span>
    <span>3-min film</span>
    <span>{len(shots)} shots · {len(sets)} sets</span>
    <span>{n_done}/{len(sets)} storyboards generated</span>
  </div>
  <p class="logline">{c["logline"]}</p>
</header>

<main>
  <nav class="toc">{toc_links}</nav>
  {shotlist_table_html}
  {"".join(set_blocks)}
</main>

<footer>
  EDB Semicon Pitch · {html.escape(c["label"])} · Generated by DearAI Studio · Click any storyboard to expand.
</footer>

<div id="lightbox" onclick="closeLightboxIfBackdrop(event)">
  <button class="close" onclick="closeLightbox()">×</button>
  <img id="lb-img" src="" alt="">
</div>

<script>
function openLightbox(img) {{
  const lb = document.getElementById('lightbox');
  document.getElementById('lb-img').src = img.dataset.full || img.src;
  lb.classList.add('open');
}}
function closeLightbox() {{ document.getElementById('lightbox').classList.remove('open'); }}
function closeLightboxIfBackdrop(e) {{ if (e.target.id === 'lightbox') closeLightbox(); }}
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeLightbox(); }});
</script>
</body>
</html>"""


def main():
    for c in CONCEPTS:
        print(f"\nbuilding {c['label']}…")
        out = build_concept(c)
        Path(c["out"]).write_text(out)
        print(f"  ✓ {c['out']}")
    # Open the first one
    webbrowser.open(f"file://{CONCEPTS[0]['out']}")
    webbrowser.open(f"file://{CONCEPTS[1]['out']}")


if __name__ == "__main__":
    main()

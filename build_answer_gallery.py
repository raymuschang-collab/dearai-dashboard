#!/usr/bin/env python3
"""
ANSWER · MOE Demo gallery builder.

Reads the ANSWER sheet (40 atomized shots, 8 sets) + the Storyboard Prompts
tab (8 sets × 2 storyboard iterations each) and renders a single-file HTML
that displays every set's storyboard panel alongside the 5 atomized shots
inside it. Built for the MOE pitch — clean editorial layout, click any
storyboard to expand, every shot numbered + lightly described.

Idempotent — re-run any time. Pulls the live state of the sheet, so when
storyboard_generate.py finishes another set, just re-run this and the new
storyboard appears.

Output: /Users/raymuschang/Desktop/Shotlist Workflows/answer_gallery.html
"""
from __future__ import annotations

import html
import re
import sys
import webbrowser
from pathlib import Path

import gspread

sys.path.insert(0, "/Users/raymuschang/Desktop/Shotlist Workflows")
from auth import get_credentials  # type: ignore

SHEET_ID = "1TrKp-hzqxqSv-s-wU97Ud8i98nSWQJGTr2D8npnjF3k"
OUTPUT = "/Users/raymuschang/Desktop/Shotlist Workflows/answer_gallery.html"


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


def thumb(file_id: str | None, w: int = 1600) -> str:
    if not file_id:
        return ""
    return f"https://lh3.googleusercontent.com/d/{file_id}=w{w}"


def view(file_id: str | None) -> str:
    if not file_id:
        return ""
    return f"https://drive.google.com/file/d/{file_id}/view"


def beat_color(beat: str) -> str | None:
    """Map beat name to a CSS class for the inline pill chip."""
    b = (beat or "").strip().upper()
    if not b:
        return None
    if b == "HOOK":
        return "beat-hook"
    if b.startswith("JOLT"):
        return "beat-jolt"
    if b == "PAYOFF":
        return "beat-payoff"
    if b in ("CLIFF", "CLIFF SETUP", "CLIFF TAG", "TAG"):
        return "beat-cliff"
    if b == "FLASHBACK":
        return "beat-flashback"
    if b == "BRIDGE":
        return "beat-bridge"
    return None


def build():
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)

    # Shotlist — read all 40 rows (header at row 1, data at row 2-41)
    sl = sh.worksheet("Shotlist")
    sl_rows = sl.get("A2:P41", value_render_option="FORMATTED_VALUE")

    # Storyboard Prompts — v3 schema, headers row 10, data rows 11-18
    sp = sh.worksheet("Storyboard Prompts")
    sp_rows = sp.get("A11:I18", value_render_option="FORMATTED_VALUE")

    # Build per-set view: 5 shots + 2 storyboard iters
    sets = []
    for i, sp_row in enumerate(sp_rows, start=1):
        sp_row = sp_row + [""] * 9
        set_num = int(sp_row[0]) if sp_row[0].strip().isdigit() else i
        shot_range = sp_row[1] or f"{(i-1)*5+1}-{i*5}"
        status = sp_row[5]
        iter1 = drive_id(sp_row[6])
        iter2 = drive_id(sp_row[7])

        # Pull the 5 shots in this set
        first = (set_num - 1) * 5
        shots = []
        for s in sl_rows[first:first + 5]:
            s = s + [""] * 16
            shots.append({
                "num": s[0], "dur": s[1], "type": s[2], "move": s[3],
                "desc": s[5], "dialogue": s[6], "microexp": s[8],
                "beat": s[13],
            })

        sets.append({
            "n": set_num, "range": shot_range, "status": status,
            "iter1": iter1, "iter2": iter2, "shots": shots,
        })

    # ----- HTML render -----
    css = """
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body {
      font-family: -apple-system, "SF Pro Text", "Inter", system-ui, sans-serif;
      background: #f7f5f1;
      color: #1a1a1a;
      line-height: 1.5;
    }
    header.hero {
      max-width: 1200px; margin: 0 auto;
      padding: 64px 48px 32px;
      border-bottom: 1px solid #e8e4dc;
    }
    header.hero h1 {
      margin: 0 0 8px;
      font-family: "SF Pro Display", -apple-system, system-ui, sans-serif;
      font-size: 48px; font-weight: 700; letter-spacing: -0.02em;
    }
    header.hero .meta {
      display: flex; gap: 16px; flex-wrap: wrap;
      font-size: 13px; color: #6a6660;
    }
    header.hero .meta span:not(:last-child)::after {
      content: " · "; margin-left: 16px; color: #c8c2b6;
    }
    header.hero p.logline {
      margin: 24px 0 0; max-width: 720px;
      font-size: 18px; color: #3a3a3a; font-style: italic;
    }

    main { max-width: 1200px; margin: 0 auto; padding: 32px 48px 96px; }

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

    .set {
      background: #fff;
      border: 1px solid #e8e4dc;
      border-radius: 14px;
      padding: 32px;
      margin-bottom: 32px;
      scroll-margin-top: 24px;
    }
    .set-head {
      display: flex; justify-content: space-between; align-items: baseline;
      margin-bottom: 24px; padding-bottom: 16px;
      border-bottom: 1px solid #efebe2;
    }
    .set-head h2 {
      margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.01em;
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

    .set-grid {
      display: grid;
      grid-template-columns: 1.6fr 1fr;
      gap: 32px;
      align-items: start;
    }
    @media (max-width: 900px) {
      .set-grid { grid-template-columns: 1fr; }
    }

    .storyboards { display: flex; flex-direction: column; gap: 16px; }
    .storyboards .iter {
      position: relative;
      border: 1px solid #e8e4dc; border-radius: 10px; overflow: hidden;
      background: #faf8f4;
    }
    .storyboards .iter img {
      width: 100%; height: auto; display: block;
      cursor: zoom-in;
    }
    .storyboards .iter .iter-label {
      position: absolute; top: 8px; left: 8px;
      padding: 3px 8px; background: rgba(0,0,0,0.7); color: #fff;
      font-size: 10px; letter-spacing: 0.05em; text-transform: uppercase;
      font-weight: 600; border-radius: 3px;
    }
    .storyboards .placeholder {
      aspect-ratio: 16/9;
      display: flex; align-items: center; justify-content: center;
      background: #faf8f4; border: 1px dashed #d8d2c4;
      border-radius: 10px;
      color: #a39a87; font-size: 12px; text-transform: uppercase;
      letter-spacing: 0.1em;
    }

    .shots-list { display: flex; flex-direction: column; gap: 12px; }
    .shot {
      display: flex; gap: 14px;
      padding: 12px; border-radius: 8px;
      background: #faf8f4;
    }
    .shot .num {
      flex: 0 0 36px; height: 36px;
      display: flex; align-items: center; justify-content: center;
      background: #1a1a1a; color: #f7f5f1;
      font-family: "SF Mono", "JetBrains Mono", monospace;
      font-size: 13px; font-weight: 700;
      border-radius: 6px;
    }
    .shot .body { flex: 1; min-width: 0; }
    .shot .meta {
      display: flex; gap: 8px; flex-wrap: wrap;
      font-family: "SF Mono", "JetBrains Mono", monospace;
      font-size: 10px; color: #6a6660; font-weight: 600;
      letter-spacing: 0.04em;
      margin-bottom: 4px;
    }
    .shot .meta .pill {
      padding: 1px 6px; background: #efebe2; border-radius: 3px;
    }
    .shot .meta .pill.dur { color: #1a1a1a; background: #fff; }
    .shot .desc { font-size: 13px; color: #1a1a1a; line-height: 1.45; }
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

    /* Beat pills */
    .beat-pill {
      display: inline-block; padding: 2px 8px; border-radius: 4px;
      font-size: 10px; font-weight: 700; letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-left: 8px;
    }
    .beat-hook { background: #fcd34d; color: #5a3700; }
    .beat-jolt { background: #93c5fd; color: #1e3a5c; }
    .beat-payoff { background: #a7f3d0; color: #1a4a32; }
    .beat-cliff { background: #fca5a5; color: #6c1414; }
    .beat-flashback { background: #ddd6fe; color: #3a2a6c; }
    .beat-bridge { background: #e5e7eb; color: #4a4a4a; }

    /* Lightbox */
    #lightbox {
      position: fixed; inset: 0; display: none;
      background: rgba(0,0,0,0.92);
      z-index: 100;
      align-items: center; justify-content: center;
    }
    #lightbox.open { display: flex; }
    #lightbox img { max-width: 95vw; max-height: 90vh; }
    #lightbox .close {
      position: absolute; top: 24px; right: 32px;
      color: #fff; font-size: 32px; cursor: pointer;
      background: none; border: none;
    }

    footer { max-width: 1200px; margin: 0 auto;
      padding: 32px 48px 64px; border-top: 1px solid #e8e4dc;
      font-size: 12px; color: #8a8275;
    }
    """

    # TOC links
    toc_html = "".join(
        f'<a href="#set-{s["n"]}">Set {s["n"]} · {html.escape(s["range"])}</a>'
        for s in sets
    )

    # Set blocks
    set_blocks = []
    for s in sets:
        # Storyboards (iter 1, iter 2)
        sb_blocks = []
        for idx, iter_id in enumerate([s["iter1"], s["iter2"]], start=1):
            if iter_id:
                sb_blocks.append(
                    f'<div class="iter">'
                    f'<span class="iter-label">Iter {idx}</span>'
                    f'<img src="{thumb(iter_id)}" alt="Set {s["n"]} Iter {idx}" '
                    f'data-full="{thumb(iter_id, 2400)}" '
                    f'onclick="openLightbox(this)" loading="lazy">'
                    f'</div>'
                )
            else:
                sb_blocks.append(
                    f'<div class="placeholder">storyboard pending</div>'
                )

        # 5 shots in this set
        shot_blocks = []
        for shot in s["shots"]:
            beat_cls = beat_color(shot["beat"])
            beat_pill = (
                f'<span class="beat-pill {beat_cls}">{html.escape(shot["beat"])}</span>'
                if beat_cls else ""
            )
            dialogue_html = (
                f'<div class="dialogue">{html.escape(shot["dialogue"])}</div>'
                if shot["dialogue"] else ""
            )
            microexp_html = (
                f'<div class="microexp">{html.escape(shot["microexp"])}</div>'
                if shot["microexp"] else ""
            )
            shot_blocks.append(f'''
              <div class="shot">
                <div class="num">{html.escape(str(shot["num"]))}</div>
                <div class="body">
                  <div class="meta">
                    <span class="pill dur">{html.escape(str(shot["dur"]))}s</span>
                    <span class="pill">{html.escape(shot["type"])}</span>
                    <span class="pill">{html.escape(shot["move"])}</span>
                    {beat_pill}
                  </div>
                  <div class="desc">{html.escape(shot["desc"])}</div>
                  {dialogue_html}
                  {microexp_html}
                </div>
              </div>''')

        status_class = (
            "done" if s["status"].lower() == "done"
            else "failed" if s["status"].lower() == "failed"
            else ""
        )
        set_blocks.append(f'''
        <section class="set" id="set-{s["n"]}">
          <div class="set-head">
            <h2>Set {s["n"]}</h2>
            <span class="shots">shots {html.escape(s["range"])}</span>
            <span class="status {status_class}">{html.escape(s["status"] or "Pending")}</span>
          </div>
          <div class="set-grid">
            <div class="storyboards">{"".join(sb_blocks)}</div>
            <div class="shots-list">{"".join(shot_blocks)}</div>
          </div>
        </section>''')

    js = """
    function openLightbox(img) {
      const lb = document.getElementById('lightbox');
      const lbImg = document.getElementById('lb-img');
      lbImg.src = img.dataset.full || img.src;
      lb.classList.add('open');
    }
    function closeLightbox(ev) {
      if (ev && ev.target.tagName === 'IMG') return;
      document.getElementById('lightbox').classList.remove('open');
    }
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeLightbox();
    });
    """

    n_done = sum(1 for s in sets if s["status"].lower() == "done")
    html_doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ANSWER · MOE Demo · 2026</title>
<style>{css}</style>
</head>
<body>

<header class="hero">
  <h1>ANSWER</h1>
  <div class="meta">
    <span>2-minute short film</span>
    <span>Singapore</span>
    <span>Single-protagonist</span>
    <span>Voiceover-led</span>
    <span>{len(sets)} sets · 40 shots</span>
    <span>{n_done}/{len(sets)} storyboards generated</span>
  </div>
  <p class="logline">A 14-year-old Singaporean girl can't write her school essay on
  <em>"What does it mean to be Singaporean?"</em> — until she stops trying to define it
  and starts noticing it.</p>
</header>

<main>
  <nav class="toc">{toc_html}</nav>
  {"".join(set_blocks)}
</main>

<footer>
  ANSWER · MOE Demo · 2026 · Generated by DearAI Studio · Click any storyboard to expand.
  Source script: <code>ANSWER · 2-min Short Script · Dear.AI</code>
</footer>

<div id="lightbox" onclick="closeLightbox(event)">
  <button class="close" onclick="closeLightbox()">×</button>
  <img id="lb-img" src="" alt="">
</div>

<script>{js}</script>
</body>
</html>'''

    Path(OUTPUT).write_text(html_doc)
    print(f"  ✓ wrote {OUTPUT}")
    print(f"  · {n_done}/{len(sets)} storyboards rendered (rest show placeholder)")
    return OUTPUT


if __name__ == "__main__":
    out = build()
    print(f"\nOpening {out}…")
    webbrowser.open(f"file://{out}")

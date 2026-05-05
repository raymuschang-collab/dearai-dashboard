#!/usr/bin/env python3
"""
Pull every line of dialogue from the Shotlist in shot order and render
as a screenplay-style HTML page.

Sources:
  Shotlist tab — col A=Shot #, F=Shot Description, G=Dialogue/VO,
  I=Microexpression, J=SFX, N=Beat

Output: pharaoh_king_dialogue.html
"""
from __future__ import annotations

import base64
import html
import os
import re

import gspread

from auth import get_credentials


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"
SHOTLIST_TAB = "Strike! Pharaoh King - Ep 1"
OUTPUT = "/Users/raymuschang/Desktop/Shotlist Workflows/pharaoh_king_dialogue.html"
HIEROGLYPHICS_BG = "/Users/raymuschang/Desktop/Shotlist Workflows/hieroglyphics_bg.png"

# Each dialogue line in col G usually looks like "SPEAKER: line of dialogue".
SPEAKER_LINE_RE = re.compile(r"^\s*([A-Z][A-Z0-9 _\-/]+?)\s*:\s*(.+)$", re.DOTALL)


def load_bg_data_url() -> str:
    if not os.path.exists(HIEROGLYPHICS_BG):
        return ""
    with open(HIEROGLYPHICS_BG, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def parse_dialogue(raw: str) -> list:
    """Split a Dialogue/VO cell into [{speaker, line}]. Multiple speakers
    in one cell are split on lines that look like 'NAME: ...'."""
    if not raw or not raw.strip():
        return []
    # Normalize line breaks
    text = raw.replace("\r\n", "\n").strip()
    # Split on each "NAME:" occurrence while preserving the speaker tag.
    # Walk line-by-line; each new "NAME:" starts a new entry.
    entries = []
    current_speaker = None
    current_lines: list[str] = []
    for line in text.split("\n"):
        m = SPEAKER_LINE_RE.match(line)
        if m:
            # Flush previous
            if current_speaker is not None:
                entries.append({"speaker": current_speaker, "line": "\n".join(current_lines).strip()})
            current_speaker = m.group(1).strip()
            current_lines = [m.group(2).strip()]
        else:
            current_lines.append(line.strip())
    if current_speaker is not None:
        entries.append({"speaker": current_speaker, "line": "\n".join(current_lines).strip()})
    elif text:
        # No speaker tag at all — render as VO/narration
        entries.append({"speaker": "VO", "line": text})
    return entries


def main():
    bg = load_bg_data_url()
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(SHOTLIST_TAB)

    # Pull A:N (we only need A, F, G, I, J, N)
    rows = ws.get("A2:N200", value_render_option="FORMATTED_VALUE")

    beat_groups = []  # [{beat, shots: [{shot_num, desc, dialogue: [{speaker, line}], micro, sfx}]}]
    current_beat = None
    current_group = None

    for r in rows:
        if not r or not r[0]:
            continue
        shot_num = (r[0] or "").strip()
        desc = r[5] if len(r) > 5 else ""
        dlg_raw = r[6] if len(r) > 6 else ""
        micro = r[8] if len(r) > 8 else ""
        sfx = r[9] if len(r) > 9 else ""
        beat = r[13] if len(r) > 13 else ""

        # Beat header bookkeeping (shows scene markers like HOOK / RISING / etc.)
        if beat and beat != current_beat:
            current_beat = beat
            current_group = {"beat": beat, "shots": []}
            beat_groups.append(current_group)
        elif current_group is None:
            current_group = {"beat": "", "shots": []}
            beat_groups.append(current_group)

        # Only include shots that actually have dialogue (otherwise it's
        # noise — we can include action lines too if desired)
        dialogue = parse_dialogue(dlg_raw)
        if not dialogue and not micro:
            continue

        current_group["shots"].append({
            "shot_num": shot_num,
            "desc": desc,
            "dialogue": dialogue,
            "micro": micro,
            "sfx": sfx,
        })

    # Drop empty beat groups
    beat_groups = [g for g in beat_groups if g["shots"]]

    # Stats
    total_lines = sum(len(s["dialogue"]) for g in beat_groups for s in g["shots"])
    speakers = {}
    for g in beat_groups:
        for s in g["shots"]:
            for d in s["dialogue"]:
                speakers[d["speaker"]] = speakers.get(d["speaker"], 0) + 1
    speaker_chips = sorted(speakers.items(), key=lambda x: -x[1])

    # ---- HTML ----
    bg_block = f"""
  body::before {{
    content: ""; position: fixed; inset: 0; z-index: -1;
    background-image: url("{bg}");
    background-size: 1400px auto; background-repeat: repeat;
    opacity: 0.14; filter: contrast(0.95) brightness(1.05);
    pointer-events: none;
  }}""" if bg else ""

    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Strike! Pharaoh King — Episode 1 Dialogue</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Courier+Prime:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --paper: #f5ead2;
    --paper-deep: #ecd9b1;
    --card: #fff8e7;
    --card-border: #d4b896;
    --ink: #2c1d10;
    --ink-soft: #5a4630;
    --ink-mute: #8c7556;
    --terracotta: #a0552f;
    --gold: #b8862f;
    --shadow: rgba(80, 50, 20, 0.18);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: "Cormorant Garamond", Georgia, serif;
    background: var(--paper);
    color: var(--ink);
    min-height: 100vh;
    line-height: 1.55;
    position: relative;
  }}
  {bg_block}

  .page {{ max-width: 760px; margin: 0 auto; padding: 48px 32px 80px; }}

  header.hero {{
    text-align: center;
    border-bottom: 1px dashed var(--card-border);
    padding-bottom: 30px;
    margin-bottom: 40px;
  }}
  header.hero .show {{
    font-family: "Cinzel", serif;
    font-size: 12px; letter-spacing: 5px;
    text-transform: uppercase;
    color: var(--terracotta);
    margin-bottom: 6px;
  }}
  header.hero h1 {{
    font-family: "Cinzel", serif;
    font-size: 32px; font-weight: 700;
    margin: 0 0 8px;
    letter-spacing: 2px;
    color: var(--ink);
  }}
  header.hero .sub {{
    font-style: italic;
    font-size: 14px;
    color: var(--ink-soft);
  }}
  header.hero .meta {{
    margin-top: 18px;
    font-family: "Cinzel", serif;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--ink-mute);
  }}
  header.hero .meta b {{ color: var(--terracotta); font-weight: 600; }}

  .speakers {{
    margin-top: 18px;
    display: flex; flex-wrap: wrap; justify-content: center; gap: 8px;
  }}
  .speakers .chip {{
    background: rgba(184, 134, 47, 0.13);
    color: var(--ink-soft);
    border: 1px solid var(--card-border);
    padding: 4px 10px;
    border-radius: 4px;
    font-family: "Cinzel", serif;
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
  }}
  .speakers .chip b {{ color: var(--terracotta); font-weight: 600; }}

  /* Beat header — scene break marker, like a screenplay slug */
  .beat-head {{
    text-align: center;
    margin: 50px 0 24px;
    font-family: "Cinzel", serif;
    font-size: 13px;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: var(--terracotta);
  }}
  .beat-head::before, .beat-head::after {{
    content: "❖";
    color: var(--card-border);
    margin: 0 14px;
    font-size: 11px;
  }}

  /* Shot block */
  .shot {{ margin-bottom: 26px; padding-left: 0; }}
  .shot .shot-num {{
    font-family: "Cinzel", serif;
    font-size: 10px;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: var(--gold);
    margin-bottom: 4px;
  }}
  .shot .desc {{
    font-style: italic;
    font-size: 14px;
    color: var(--ink-soft);
    margin: 0 0 14px;
    padding-left: 0;
  }}

  /* Dialogue — screenplay format: speaker centered, line below */
  .dialogue {{ margin: 14px 0 18px; }}
  .dialogue + .dialogue {{ margin-top: 10px; }}
  .speaker {{
    text-align: center;
    font-family: "Courier Prime", "Courier New", monospace;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: var(--ink);
    margin-bottom: 4px;
  }}
  .line {{
    text-align: center;
    font-family: "Courier Prime", "Courier New", monospace;
    font-size: 14px;
    color: var(--ink);
    line-height: 1.5;
    max-width: 480px;
    margin: 0 auto;
    white-space: pre-wrap;
  }}

  /* Microexpression / parenthetical */
  .paren {{
    text-align: center;
    font-style: italic;
    color: var(--ink-mute);
    font-size: 13px;
    margin: 6px auto;
    max-width: 380px;
  }}

  /* SFX line — quiet, italic, right-aligned */
  .sfx {{
    text-align: right;
    font-style: italic;
    color: var(--ink-mute);
    font-size: 11px;
    letter-spacing: 0.5px;
    margin-top: 6px;
    border-top: 1px dotted var(--card-border);
    padding-top: 4px;
  }}
  .sfx::before {{ content: "♪ "; color: var(--gold); }}

  footer {{
    text-align: center;
    margin-top: 60px;
    padding-top: 24px;
    border-top: 1px dashed var(--card-border);
    font-size: 11px;
    color: var(--ink-mute);
    letter-spacing: 2px;
    text-transform: uppercase;
    font-family: "Cinzel", serif;
  }}

  @media print {{
    body {{ background: white; }}
    body::before {{ display: none; }}
    .page {{ padding: 12pt; }}
  }}
</style>
</head>
<body>
<div class="page">

<header class="hero">
  <div class="show">Strike! Pharaoh King</div>
  <h1>Episode 1 — The Isfet Spawn</h1>
  <div class="sub">Dialogue script · in shot order</div>
  <div class="meta">
    <b>{total_lines}</b> lines · <b>{len(speakers)}</b> speakers · <b>{sum(len(g["shots"]) for g in beat_groups)}</b> shots
  </div>
  <div class="speakers">
""")
    for sp, n in speaker_chips:
        parts.append(f'    <span class="chip">{html.escape(sp)} <b>×{n}</b></span>\n')
    parts.append("""  </div>
</header>

""")

    # Render groups
    for g in beat_groups:
        beat = g["beat"]
        if beat:
            parts.append(f'<div class="beat-head">{html.escape(beat)}</div>\n')
        for s in g["shots"]:
            parts.append(f'<div class="shot">\n')
            parts.append(f'  <div class="shot-num">Shot {html.escape(s["shot_num"])}</div>\n')
            if s["desc"]:
                parts.append(f'  <div class="desc">{html.escape(s["desc"])}</div>\n')
            for d in s["dialogue"]:
                parts.append(f'  <div class="dialogue">\n')
                parts.append(f'    <div class="speaker">{html.escape(d["speaker"])}</div>\n')
                parts.append(f'    <div class="line">{html.escape(d["line"])}</div>\n')
                parts.append(f'  </div>\n')
            if s["micro"]:
                parts.append(f'  <div class="paren">({html.escape(s["micro"])})</div>\n')
            if s["sfx"] and not s["dialogue"] and not s["micro"]:
                # Skip pure-SFX shots unless explicitly wanted
                pass
            elif s["sfx"]:
                parts.append(f'  <div class="sfx">{html.escape(s["sfx"])}</div>\n')
            parts.append('</div>\n\n')

    parts.append("""
<footer>The Producer's Codex · Dialogue script</footer>

</div>
</body>
</html>
""")

    out = "".join(parts)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(out)
    size_kb = os.path.getsize(OUTPUT) // 1024
    print(f"  hieroglyphics bg loaded ({len(bg) // 1024}KB base64)" if bg else "  no bg loaded")
    print(f"✓ wrote {OUTPUT}")
    print(f"  size: {size_kb} KB · {total_lines} lines · {len(speakers)} speakers · {sum(len(g['shots']) for g in beat_groups)} shots with dialogue/micro")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
PRODUCTION VARIANT v2 — adds Frame.io feedback inline per set.

Differences vs production v1:
  - Limited to sets 1–12 (the user's current production scope)
  - Each set row gets a FEEDBACK column showing every Frame.io comment
    that maps to a shot inside this set's range
  - Comments classified as: regen / new / edit / keeper, color-coded
  - Sourced from feedback_data.py (extracted from the 4/30/26 PDF)

Output: pharaoh_king_gallery_PRODUCTION_v2.html
"""
from __future__ import annotations

import base64
import html
import json
import os
import re

import gspread

from auth import get_credentials
from feedback_data import COMMENTS, tc_to_seconds


SHEET_ID = "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE"
OUTPUT = "/Users/raymuschang/Documents/Shotlist Workflows/pharaoh_king_gallery_PRODUCTION_v2.html"
HIEROGLYPHICS_BG = "/Users/raymuschang/Documents/Shotlist Workflows/hieroglyphics_bg.png"
SHOTLIST_TAB = "Strike! Pharaoh King - Ep 1"
MAX_SET = 12  # user is only working through set 12 right now


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
    global_camera  = ws.acell("B1").value or ""
    global_audio   = ws.acell("B2").value or ""
    global_scale   = ws.acell("B3").value or ""
    global_setting = ws.acell("B4").value or ""
    video_global = "\n".join([s for s in [global_camera, global_audio, global_scale, global_setting] if s])

    # === LATEST VIDEO TRACKING ===
    # Read latest_videos.json — produced by fal_vidgen.py --mark-latest.
    # Map of {drive_file_id: {timestamp, set, slot, iter_used, no_storyboard}}.
    # Gallery renders a green "LATEST" chip on any video tile whose Drive ID
    # is a key in this map. Each new fal.ai batch should clear+rewrite this
    # file (or the user can manually clear after reviewing).
    latest_videos = {}
    latest_path = os.path.join(os.path.dirname(__file__), "latest_videos.json")
    if os.path.exists(latest_path):
        try:
            with open(latest_path) as f:
                latest_videos = (json.load(f) or {}).get("videos", {})
        except Exception:
            latest_videos = {}

    # === SHOTLIST: compute cumulative timecode per shot ===
    # Used to map each Frame.io comment timecode → shot # → set #.
    sl = sh.worksheet(SHOTLIST_TAB)
    sl_rows = sl.get("A2:B100", value_render_option="FORMATTED_VALUE")
    shot_starts = {}
    t = 0.0
    for r in sl_rows:
        if not r or not r[0]:
            continue
        try:
            sn = int(r[0])
        except ValueError:
            continue
        dur = float(r[1]) if len(r) > 1 and r[1] else 3.0
        shot_starts[sn] = t
        t += dur

    def shot_at(seconds: float):
        last = None
        for sn in sorted(shot_starts):
            if shot_starts[sn] <= seconds:
                last = sn
            else:
                break
        return last

    # === FEEDBACK: group Frame.io comments by set ===
    feedback_by_set = {}  # {set_num_int: [comment dicts]}
    for tc, reviewer, num, kind, text in COMMENTS:
        secs = tc_to_seconds(tc)
        sn = shot_at(secs)
        if sn is None:
            continue
        set_num = ((sn - 1) // 5) + 1
        if set_num > MAX_SET:
            continue
        feedback_by_set.setdefault(set_num, []).append({
            "tc": tc,
            "reviewer": reviewer,
            "num": num,
            "kind": kind,
            "text": text,
            "shot_num": sn,
        })
    # Sort each set's feedback by timecode
    for k in feedback_by_set:
        feedback_by_set[k].sort(key=lambda c: tc_to_seconds(c["tc"]))

    # === STORYBOARDS (limited to MAX_SET) ===
    # Iteration 1 (col G) + Iteration 2 (col H) — auto nano-banana-2 stick-figure storyboards.
    # Iteration 3 (col J) + Iteration 4 (col K) — manual ref-conditioned PHOTOREAL gens.
    # Video Iter 1 (col L) + 2 (col M) + 3 (col N) + 4 (col O) — final video cuts as 2x2 grid.
    ws = sh.worksheet("Storyboard Prompts")
    sb_rows = ws.get("A11:O35", value_render_option="FORMATTED_VALUE")
    storyboards = []
    for row in sb_rows:
        if not row or not row[0]:
            continue
        try:
            set_num_int = int(str(row[0]).strip())
        except ValueError:
            continue
        if set_num_int > MAX_SET:
            continue
        body = row[2] if len(row) > 2 else ""
        i1 = drive_id(row[6] if len(row) > 6 else "")
        i2 = drive_id(row[7] if len(row) > 7 else "")
        i3 = drive_id(row[9] if len(row) > 9 else "")
        i4 = drive_id(row[10] if len(row) > 10 else "")
        v1 = drive_id(row[11] if len(row) > 11 else "")
        v2 = drive_id(row[12] if len(row) > 12 else "")
        v3 = drive_id(row[13] if len(row) > 13 else "")
        v4 = drive_id(row[14] if len(row) > 14 else "")
        # PENCIL-PRIMARY schema (current):
        #   Iter 1 (pencil) = col G — primary pencil storyboard (nano_banana_2 + bibles)
        #   Iter 2 (pencil) = col H — second pencil pass
        # Photoreal cols J/K are DEPRECATED legacy — still in sheet as backup
        # but hidden from the gallery display. Pencils are now the canonical
        # production storyboard reference.
        iters = []
        if i1:
            iters.append({"label": "Iteration 1 (pencil)", "id": i1, "thumb": thumb(i1, 1400), "url": view(i1)})
        if i2:
            iters.append({"label": "Iteration 2 (pencil)", "id": i2, "thumb": thumb(i2, 1400), "url": view(i2)})
        videos = [
            {"label": "Iter 1", "id": v1},
            {"label": "Iter 2", "id": v2},
            {"label": "Iter 3", "id": v3},
            {"label": "Iter 4", "id": v4},
        ]
        # CONTEXTUAL DATA — per-set anchor: detect location + characters from body.
        # Sits between the Global block and the Combined Prompt block in the gallery
        # (matches the structure injected into vidgen prompts by fal_vidgen.py).
        body_lower = body.lower()
        loc_aliases = {
            "rooftop": "Rooftop above the Bazaar",
            "bazaar": "Peasant Bazaar",
            "marketplace": "Peasant Bazaar",
            "pyramid field": "Pyramid Field (Battlefield)",
            "battlefield": "Pyramid Field (Battlefield)",
            "pyramid": "Desert Plateau / Great Pyramid",
            "base of the pyramid": "Base of the Pyramid",
            "crater": "Impact Crater",
        }
        loc_matches = []
        for alias, canonical in loc_aliases.items():
            idx = body_lower.find(alias)
            if idx >= 0 and canonical not in [c for _, c in loc_matches]:
                loc_matches.append((idx, canonical))
        loc_matches.sort()
        location_name = loc_matches[0][1] if loc_matches else "Unspecified"

        char_names_in_bible = ["KHENSU", "AHMOSE", "TEHUTI", "SESHET", "MERCHANT", "ISFET SPAWN", "TINY SCORPIONS"]
        chars_in_scene = []
        import re as _re
        for n in char_names_in_bible:
            if _re.search(r"\b" + _re.escape(n) + r"\b", body, _re.IGNORECASE):
                chars_in_scene.append(n)
        # Apply ISFET SPAWN → ISFET SPAWN (2) display
        if "ISFET SPAWN" in chars_in_scene:
            chars_in_scene = [c if c != "ISFET SPAWN" else "ISFET SPAWN (2)" for c in chars_in_scene]

        context_text = f"Location: {location_name}\nCharacters in scene: {', '.join(chars_in_scene) if chars_in_scene else '(none)'}"

        storyboards.append({
            "set_num": row[0],
            "set_num_int": set_num_int,
            "shot_range": row[1] if len(row) > 1 else "",
            "body": body,
            "context": context_text,
            "feedback": feedback_by_set.get(set_num_int, []),
            "iters": iters,
            "videos": videos,
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
        "latest_videos": latest_videos,
    }

    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(data['show'])} — {html.escape(data['episode'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    /* Light SaaS dashboard — paper-white floating cards on cool gray.
       Color reserved for data viz / storyboard tiles. */
    --paper:        #ededed;            /* cool light gray surface */
    --paper-deep:   #e3e3e3;            /* slightly darker for nested wells */
    --card:         #ffffff;            /* paper white card */
    --card-elev:    #fdfdfd;            /* hover/elevated */
    --card-border:  rgba(0, 0, 0, 0.05);/* almost invisible */
    --ink:          #0a0a0a;            /* near black headlines */
    --ink-soft:     #5a5a5a;            /* mid gray body */
    --ink-mute:     #a0a0a0;            /* light gray labels */
    --charcoal:     #1a1a1a;            /* charcoal CTA / active */
    --terracotta:   #ff3b6b;            /* hot pink-red data accent */
    --terracotta-l: #ff6b8a;            /* lighter pink */
    --gold:         #ff8c42;            /* warm orange data accent */
    --green:        #d3eddd;            /* mint pale */
    --green-deep:   #3ad9c2;            /* mint teal */
    --shadow:       rgba(0, 0, 0, 0.06);
    --shadow-lift:  rgba(0, 0, 0, 0.10);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: "Inter", system-ui, -apple-system, sans-serif;
    background: var(--paper);
    color: var(--ink);
    min-height: 100vh;
    line-height: 1.55;
    position: relative;
  }}
  /* Clean light surface — no decorative bg. The cards do all the work. */
  body::before, body::after {{ display: none; }}
  .wrap {{ max-width: 1320px; margin: 0 auto; padding: 32px 28px 80px; }}
  /* Storyboards tab uses a wider container — its 3-column layout (storyboards
     | prompts | videos) needs more horizontal room than the other tabs. */
  body.sb-wide .wrap {{ max-width: 1700px; }}
  header.hero {{
    text-align: left;
    padding: 24px 4px 28px;
    border-bottom: 1px solid rgba(0,0,0,0.05);
    margin-bottom: 24px;
  }}
  header.hero .show {{
    font-family: "Inter", system-ui, sans-serif;
    font-size: 11px; letter-spacing: 0.6px;
    text-transform: uppercase;
    color: var(--ink-mute);
    font-weight: 500;
    margin-bottom: 4px;
  }}
  header.hero h1 {{
    font-family: "Inter", system-ui, sans-serif;
    font-size: 26px; font-weight: 600;
    letter-spacing: -0.4px; margin: 0 0 14px;
    color: var(--ink);
  }}
  header.hero .stats {{
    display: flex; flex-wrap: wrap; gap: 22px;
    font-size: 12px; color: var(--ink-mute);
    letter-spacing: 0;
  }}
  header.hero .stats span b {{ color: var(--ink); font-weight: 600; }}

  nav.tabs {{
    display: flex; flex-wrap: wrap; gap: 4px; justify-content: center;
    margin-bottom: 28px;
    padding: 5px;
    background: var(--card);
    border-radius: 14px;
    width: fit-content;
    margin-left: auto; margin-right: auto;
    box-shadow: 0 1px 3px var(--shadow), 0 4px 16px var(--shadow);
  }}
  nav.tabs button {{
    background: transparent; border: 0;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 12px; letter-spacing: 0.4px;
    font-weight: 500;
    color: var(--ink-soft);
    padding: 9px 16px;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.15s ease;
  }}
  nav.tabs button:hover {{ color: var(--ink); background: rgba(0, 0, 0, 0.03); }}
  nav.tabs button.active {{
    background: var(--charcoal);
    color: #ffffff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.18);
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
    border: 0;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 1px 3px var(--shadow), 0 6px 20px var(--shadow);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    display: flex; flex-direction: column;
  }}
  .card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 2px 6px var(--shadow), 0 10px 28px var(--shadow-lift);
  }}

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
    background: var(--charcoal);
    color: #ffffff;
    font-size: 9px; letter-spacing: 0.4px;
    text-transform: uppercase;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 6px;
    font-family: "Inter", system-ui, sans-serif;
  }}
  .img-cell .empty {{
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    color: var(--ink-mute); font-style: italic; font-size: 13px;
  }}

  .card-body {{ padding: 14px 18px 18px; flex: 1; }}
  .card-body h3 {{
    font-family: "Bebas Neue", "Helvetica Neue", sans-serif;
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
    background: rgba(255, 174, 94, 0.13);
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
    background: rgba(255, 174, 94, 0.10);
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
    font-family: "Bebas Neue", "Helvetica Neue", sans-serif;
  }}

  footer {{
    margin-top: 60px; padding-top: 24px;
    border-top: 1px dashed var(--card-border);
    text-align: center; font-size: 11px;
    color: var(--ink-mute); letter-spacing: 1px;
    text-transform: uppercase;
    font-family: "Bebas Neue", "Helvetica Neue", sans-serif;
  }}

  /* ====== PRODUCTION storyboard layout ======
     Single vertical column. Each set = [storyboard panels] | [video prompts].
     The storyboard column is fixed-width-ish (~58%); the prompts column
     fills the rest. On narrow screens it stacks. */
  .sb-prod-list {{ display: flex; flex-direction: column; gap: 28px; }}
  .sb-prod-row {{
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 0.8fr);
    gap: 22px;
    background: var(--card);
    border: 0;
    border-radius: 16px;
    padding: 22px;
    box-shadow: 0 1px 3px var(--shadow), 0 8px 28px var(--shadow);
  }}
  .sb-prod-row .sb-head {{
    grid-column: 1 / -1;
    border-bottom: 1px solid rgba(0,0,0,0.05);
    padding-bottom: 14px;
    margin-bottom: 6px;
  }}
  .sb-prod-row .sb-head h3 {{
    font-family: "Inter", system-ui, sans-serif;
    font-size: 16px;
    font-weight: 600;
    margin: 0;
    color: var(--ink);
    letter-spacing: -0.2px;
  }}
  .sb-prod-row .sb-head .shots-meta {{
    font-size: 11.5px;
    color: var(--ink-mute);
    letter-spacing: 0;
    text-transform: none;
    font-family: "Inter", system-ui, sans-serif;
    font-weight: 400;
    margin-top: 4px;
  }}
  .sb-prod-imgs {{
    display: flex; flex-direction: column; gap: 10px;
  }}
  .sb-prod-imgs .img-cell {{
    aspect-ratio: 21 / 9;
    border-radius: 10px;
    border: 0;
    box-shadow: 0 1px 2px var(--shadow);
  }}
  .sb-prod-prompts {{
    display: flex; flex-direction: column; gap: 8px;
    max-height: 100%;
    overflow-y: auto;
  }}
  /* GLOBAL + COMBINED PROMPT blocks — pale gray inset wells */
  .sb-prod-block {{
    background: rgba(0, 0, 0, 0.025);
    border-left: 2px solid var(--terracotta);
    border-radius: 8px;
    padding: 10px 14px;
  }}
  .sb-prod-block.global {{ border-left-color: var(--gold); }}
  .sb-prod-block .block-label {{
    font-family: "Inter", system-ui, sans-serif;
    font-size: 10px;
    color: var(--ink-mute);
    letter-spacing: 0.6px;
    text-transform: uppercase;
    margin-bottom: 6px;
    font-weight: 600;
  }}
  .sb-prod-block.global .block-label {{ color: var(--gold); }}
  .sb-prod-block .block-text {{
    font-size: 12px;
    color: var(--ink-soft);
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: "JetBrains Mono", "SF Mono", Menlo, monospace;
  }}
  .sb-prod-block.empty .block-text {{
    color: var(--ink-mute);
    font-style: italic;
    font-family: "Inter", system-ui, sans-serif;
  }}

  /* === FEEDBACK block — minimal SaaS look === */
  .sb-prod-feedback {{
    margin-top: 4px;
    border: 0;
    border-radius: 10px;
    overflow: hidden;
    background: rgba(0, 0, 0, 0.025);
  }}
  .sb-prod-feedback .fb-head {{
    background: transparent;
    padding: 8px 12px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 11px;
    color: var(--ink-mute);
    letter-spacing: 0.4px;
    text-transform: uppercase;
    font-weight: 600;
    border-bottom: 1px solid rgba(0,0,0,0.05);
    display: flex; justify-content: space-between; align-items: center;
  }}
  .sb-prod-feedback .fb-head .count {{
    background: var(--charcoal);
    color: #ffffff;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-family: "Inter", system-ui, sans-serif;
    font-weight: 500;
  }}
  .sb-prod-feedback .fb-list {{
    padding: 6px;
    display: flex; flex-direction: column; gap: 6px;
    background: transparent;
  }}
  .fb-item {{
    display: grid;
    grid-template-columns: auto auto 1fr;
    gap: 8px;
    align-items: start;
    padding: 8px 10px;
    background: var(--card);
    border-left: 2px solid rgba(0,0,0,0.1);
    border-radius: 0 6px 6px 0;
    font-size: 12.5px;
    line-height: 1.4;
    box-shadow: 0 1px 2px var(--shadow);
  }}
  .fb-item .fb-shot {{
    font-family: "Inter", system-ui, sans-serif;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0;
    color: var(--ink-soft);
    background: rgba(0, 0, 0, 0.05);
    padding: 2px 7px;
    border-radius: 4px;
    white-space: nowrap;
  }}
  .fb-item .fb-kind {{
    font-family: "Inter", system-ui, sans-serif;
    font-size: 9px;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
    white-space: nowrap;
  }}
  .fb-item .fb-text {{
    color: var(--ink);
    word-break: break-word;
  }}
  .fb-item .fb-text .fb-rev {{
    color: var(--ink-mute);
    font-size: 11px;
    margin-left: 4px;
    font-style: normal;
  }}

  /* Kind color coding — light, minimal pills */
  .fb-item.regen  {{ border-left-color: #ff3b6b; }}
  .fb-item.regen  .fb-kind {{ background: rgba(255, 59, 107, 0.10); color: #d12858; }}
  .fb-item.new    {{ border-left-color: #4f8df5; }}
  .fb-item.new    .fb-kind {{ background: rgba(79, 141, 245, 0.10); color: #2563eb; }}
  .fb-item.edit   {{ border-left-color: #ff8c42; }}
  .fb-item.edit   .fb-kind {{ background: rgba(255, 140, 66, 0.12); color: #d96a25; }}
  .fb-item.keeper {{ border-left-color: #3ad9c2; }}
  .fb-item.keeper .fb-kind {{ background: rgba(58, 217, 194, 0.13); color: #1a9c89; }}

  /* === Compact feedback BAR variant === */
  .sb-prod-feedback.bar .fb-head {{ padding: 5px 10px; font-size: 10px; }}
  .sb-prod-feedback.bar .fb-list {{ padding: 4px; gap: 4px; }}
  .sb-prod-feedback.bar .fb-item {{ padding: 6px 8px; font-size: 11.5px; line-height: 1.35; }}
  .sb-prod-feedback.bar .fb-item .fb-shot {{ font-size: 9px; padding: 1px 5px; }}
  .sb-prod-feedback.bar .fb-item .fb-kind {{ font-size: 8px; padding: 1px 6px; }}
  .sb-prod-feedback.bar .fb-item .fb-rev {{ font-size: 10px; }}

  /* === Video iterations column — 2x2 grid of 9:16 tiles + download all === */
  .sb-prod-videos {{
    background: #f6f6f7;
    padding: 14px;
    border-radius: 12px;
    box-shadow: 0 1px 3px var(--shadow), 0 4px 14px var(--shadow);
    display: flex; flex-direction: column; gap: 10px;
  }}
  .sb-prod-videos .download-row {{
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }}
  .sb-prod-videos .open-folder {{
    display: inline-flex;
    align-items: center;
    padding: 6px 10px;
    font-size: 12px;
    color: var(--ink-soft);
    background: var(--paper-warm-2);
    border: 1px solid var(--ink-stroke);
    border-radius: 4px;
    text-decoration: none;
    white-space: nowrap;
  }}
  .sb-prod-videos .open-folder:hover {{
    background: var(--ink-soft);
    color: var(--paper-warm-2);
  }}
  .sb-prod-videos .download-all {{
    align-self: flex-start;
    background: var(--charcoal);
    color: #ffffff;
    border: 0; border-radius: 8px;
    padding: 7px 14px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: background 0.15s ease;
  }}
  .sb-prod-videos .download-all:hover {{ background: #000; }}
  .sb-prod-videos .download-all:disabled {{
    background: #c4c4c4; color: #fff; cursor: not-allowed;
  }}
  .sb-prod-videos .video-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
    gap: 10px;
  }}
  .sb-prod-videos .video-cell {{
    display: flex; flex-direction: column; gap: 4px;
  }}
  .sb-prod-videos .latest-chip {{
    display: inline-block;
    margin-left: 6px;
    padding: 1px 6px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: #fff;
    background: #16a34a;
    border-radius: 3px;
    vertical-align: middle;
  }}
  .sb-prod-videos .video-thumb-wrap {{
    position: relative;
    width: 100%;
    aspect-ratio: 9/16;
    background: #1a1a1a;
    cursor: pointer;
    overflow: hidden;
    border-radius: 4px;
    transition: transform 0.15s;
  }}
  .sb-prod-videos .video-thumb-wrap:hover {{
    transform: scale(1.02);
  }}
  .sb-prod-videos .video-thumb-wrap.video-loaded {{
    cursor: default;
  }}
  .sb-prod-videos .video-thumb-wrap.video-loaded:hover {{
    transform: none;
  }}
  .sb-prod-videos .video-thumb {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }}
  .sb-prod-videos .video-play-overlay {{
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.15);
    transition: background 0.15s;
  }}
  .sb-prod-videos .video-thumb-wrap:hover .video-play-overlay {{
    background: rgba(0,0,0,0.35);
  }}
  .sb-prod-videos .play-circle {{
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: rgba(255,255,255,0.95);
    color: #000;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    padding-left: 4px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  }}
  .sb-prod-videos .video-slot {{
    width: 100%;
    /* aspect ratio set on .video-slot below */
  }}
  .sb-prod-videos .video-dl {{
    font-family: "Inter", system-ui, sans-serif;
    font-size: 10px;
    color: var(--ink-mute);
    text-decoration: none;
    text-align: center;
    padding: 3px 6px;
    border-radius: 4px;
    transition: background 0.12s ease, color 0.12s ease;
  }}
  .sb-prod-videos .video-dl:hover {{
    background: rgba(0, 0, 0, 0.05);
    color: var(--ink);
  }}
  .sb-prod-videos .video-dl.disabled {{
    color: #c4c4c4;
    pointer-events: none;
  }}
  .video-slot {{
    background: var(--paper-deep);
    border: 0;
    border-radius: 12px;
    overflow: hidden;
    aspect-ratio: 9 / 16;
    position: relative;
    box-shadow: 0 1px 3px var(--shadow), 0 4px 12px var(--shadow);
  }}
  .video-slot iframe {{
    width: 100%; height: 100%; border: 0; display: block;
  }}
  .video-slot .video-empty {{
    position: absolute; inset: 0;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    color: var(--ink-mute); font-style: italic; font-size: 12px;
    background: linear-gradient(135deg, rgba(255,94,58,0.06), rgba(255,174,94,0.10));
  }}
  .video-slot .video-empty .play-icon {{
    font-size: 36px; color: var(--card-border); margin-bottom: 6px;
  }}
  .video-slot .video-label {{
    position: absolute; left: 8px; top: 8px;
    background: var(--charcoal);
    color: #ffffff;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 9px; letter-spacing: 0.4px;
    text-transform: uppercase;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 6px;
    pointer-events: none;
    z-index: 2;
  }}

  @media (max-width: 900px) {{
    .sb-prod-row {{ grid-template-columns: 1fr; }}
    .sb-prod-videos {{ margin-top: 10px; }}
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

// PRODUCTION v2: each set is one row.
//   Left:  iter 1 + iter 2 storyboards stacked vertically
//   Right: GLOBAL + COMBINED PROMPT + FEEDBACK (Frame.io comments mapped to this set's shots)
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

    // CONTEXTUAL DATA — per-set anchor (location + characters in scene)
    // Renders between Global and Combined Prompt, matching the vidgen prompt structure.
    const contextText = (s.context || "").trim();
    const contextBlock = contextText
      ? `<div class="sb-prod-block context">
          <div class="block-label">Contextual Data</div>
          <div class="block-text">${{escapeHtml(contextText)}}</div>
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

    // FEEDBACK block — compact bar variant under the prompts
    const fb = s.feedback || [];
    let feedbackBlock = "";
    if (fb.length) {{
      const kindCounts = {{}};
      for (const c of fb) kindCounts[c.kind] = (kindCounts[c.kind] || 0) + 1;
      const headerSummary = ["regen", "new", "edit", "keeper"]
        .filter(k => kindCounts[k])
        .map(k => `${{kindCounts[k]}} ${{k}}`)
        .join(" · ");

      feedbackBlock = `<div class="sb-prod-feedback bar">
        <div class="fb-head">
          <span>Feedback · Frame.io 4/30</span>
          <span class="count">${{fb.length}} · ${{escapeHtml(headerSummary)}}</span>
        </div>
        <div class="fb-list">
          ${{fb.map(c => `<div class="fb-item ${{escapeHtml(c.kind)}}">
            <span class="fb-shot">Shot ${{c.shot_num}} · ${{escapeHtml(c.tc)}}</span>
            <span class="fb-kind">${{escapeHtml(c.kind)}}</span>
            <span class="fb-text">${{escapeHtml(c.text)}}<span class="fb-rev">— ${{escapeHtml(c.reviewer)}} #${{c.num}}</span></span>
          </div>`).join("")}}
        </div>
      </div>`;
    }}

    // VIDEO column — 2x2 grid of iteration slots. Each cell has the player
    // tile (Drive iframe when populated, placeholder otherwise) + a download
    // link below it. Above the grid: a "Download all" button that triggers
    // each download URL in turn.
    const videos = s.videos || [];
    const populatedIds = videos.filter(v => v && v.id).map(v => v.id);
    const dlAllDisabled = populatedIds.length === 0;
    const latestVideos = DATA.latest_videos || {{}};
    const cellsHtml = videos.map((v, idx) => {{
      const label = `Iter ${{idx + 1}}`;
      let tile, dlLink;
      if (v && v.id) {{
        const src = `https://drive.google.com/file/d/${{v.id}}/preview`;
        const dlUrl = `https://drive.google.com/uc?export=download&id=${{v.id}}`;
        const thumbUrl = `https://drive.google.com/thumbnail?id=${{v.id}}&sz=w800`;
        const isLatest = !!latestVideos[v.id];
        const latestBadge = isLatest ? `<span class="latest-chip">LATEST</span>` : "";
        // CLICK-TO-PLAY: render thumbnail + play button by default. Only mount
        // the heavy Drive iframe player when user clicks. ~10x faster initial
        // page load when there are 30+ videos in the gallery.
        tile = `<div class="video-slot">
          <div class="video-label">${{label}}${{latestBadge}}</div>
          <div class="video-thumb-wrap" data-src="${{src}}" onclick="playVideo(this)">
            <img class="video-thumb" src="${{thumbUrl}}" alt="${{label}}" loading="lazy" referrerpolicy="no-referrer">
            <div class="video-play-overlay"><div class="play-circle">▶</div></div>
          </div>
        </div>`;
        dlLink = `<a class="video-dl" href="${{dlUrl}}" download>↓ download iter ${{idx + 1}}</a>`;
      }} else {{
        tile = `<div class="video-slot">
          <div class="video-label">${{label}}</div>
          <div class="video-empty">
            <div class="play-icon">▶</div>
            <div>no video yet</div>
          </div>
        </div>`;
        dlLink = `<span class="video-dl disabled">↓ no video yet</span>`;
      }}
      return `<div class="video-cell">${{tile}}${{dlLink}}</div>`;
    }}).join("");

    const dlAllAttr = dlAllDisabled ? "disabled" : "";
    const dlAllJs = populatedIds.length
      ? `onclick="downloadAll([${{populatedIds.map(id => `'${{id}}'`).join(',')}}], ${{s.set_num_int}})"`
      : "";
    // Drive folder for the set's videos — fallback if browser throttles multi-download
    const driveFolderUrl = `https://drive.google.com/drive/search?q=set-${{String(s.set_num_int).padStart(2, "0")}}%20parent:${{"1E0qClOQ3HIY64wnp4mZ30I10u2TFePpf".replace(/_/g,"_")}}`;
    const videosHtml = `
      <div class="download-row">
        <button class="download-all" ${{dlAllAttr}} ${{dlAllJs}}>↓ Download all (${{populatedIds.length}})</button>
        <a class="open-folder" href="https://drive.google.com/drive/folders/1E0qClOQ3HIY64wnp4mZ30I10u2TFePpf" target="_blank" title="Open videos parent folder in Drive (then navigate to set-NN/ subfolder)">📁 Drive videos folder</a>
      </div>
      <div class="video-grid">${{cellsHtml}}</div>
    `;

    return `<div class="sb-prod-row">
      <div class="sb-head">
        <h3>Set ${{escapeHtml(s.set_num)}}</h3>
        <div class="shots-meta">Shots ${{escapeHtml(s.shot_range)}}${{fb.length ? ` · ${{fb.length}} feedback` : ""}}</div>
      </div>
      <div class="sb-prod-imgs">${{imgsHtml}}</div>
      <div class="sb-prod-prompts">
        ${{globalBlock}}
        ${{contextBlock}}
        ${{combinedBlock}}
        ${{feedbackBlock}}
      </div>
      <div class="sb-prod-videos">
        ${{videosHtml}}
      </div>
    </div>`;
  }}).join("");
}}

function renderTab(key) {{
  const main = document.getElementById("main");
  // Wider container for the storyboards tab so the 3-column rows breathe.
  document.body.classList.toggle("sb-wide", key === "storyboards");
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

// Triggers a sequence of Drive download URLs. Each click opens an invisible
// <a download> link, staggered by 1500ms so modern browsers don't block them.
// (Chrome/Edge throttle multiple consecutive downloads as a security measure;
// 1500ms stagger + explicit filename forces each through.)
// If user reports only the first 1-2 downloading: they need to allow
// "automatic multiple downloads" in their browser site settings, OR use the
// "Open Drive folder" button instead which lets Drive UI ZIP everything.
// Click-to-play handler — swaps thumbnail+button for the heavy Drive iframe
// only when the user clicks. Initial page render stays cheap.
function playVideo(wrap) {{
  const src = wrap.getAttribute("data-src");
  if (!src) return;
  const iframe = document.createElement("iframe");
  iframe.src = src;
  iframe.allow = "autoplay; fullscreen";
  iframe.allowFullscreen = true;
  iframe.style.cssText = "width:100%;height:100%;border:0;display:block;";
  wrap.innerHTML = "";
  wrap.appendChild(iframe);
  wrap.classList.add("video-loaded");
  wrap.onclick = null;
}}

function downloadAll(ids, setNum) {{
  if (!ids || !ids.length) return;
  console.log(`[downloadAll] Set ${{setNum}}: triggering ${{ids.length}} downloads, 1500ms stagger`);
  ids.forEach((id, i) => {{
    setTimeout(() => {{
      const a = document.createElement("a");
      a.href = `https://drive.google.com/uc?export=download&id=${{id}}`;
      a.download = `set-${{String(setNum).padStart(2, "0")}}-iter-${{i + 1}}.mp4`;
      a.target = "_blank";
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      console.log(`  [${{i + 1}}/${{ids.length}}] fired download for ${{id}}`);
    }}, i * 1500);
  }});
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

#!/usr/bin/env python3
"""Self-contained HTML dashboard builder for the X-Men shotlist.

Reads the X-Men sheet (custom 12-col schema, no Storyboard Prompts tab):
  Shotlist!A2:L20  -> Shot#/Sequence/Duration/Type/Camera/Description/
                      Microexpression/SFX/Beat/Merge/Look/Prompt
  Asset Library!A2:F -> Name/Category/Asset Code/Source URL/Type/Status

Renders a dark-theme dashboard: hero header, per-sequence Look summary,
shot cards grouped by sequence (meta pills, description, microexpression,
merge note, copyable prompt), beat-color pills, and an Asset Library
section that embeds the registered video.
"""
import html
import json
import os
import re
import webbrowser
from pathlib import Path

import gspread
from auth import get_credentials

SHEET_ID = "1oex57Ula_gWLTYHRosXgDxzZJlK_ZOO7T-Kx3syIOEw"
OUT = "/Users/raymuschang/Desktop/Shotlist Workflows/xmen_dashboard.html"


def drive_id(url):
    if not url:
        return ""
    m = re.search(r"/file/d/([A-Za-z0-9_-]+)", url) or re.search(r"[?&]id=([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else ""


def beat_class(beat):
    b = (beat or "").upper().strip()
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
    return "beat-none"


def esc(s):
    return html.escape(s or "")


def main():
    gc = gspread.authorize(get_credentials())
    sh = gc.open_by_key(SHEET_ID)
    title = sh.title

    ws = sh.worksheet("Shotlist")
    rows = ws.get("A2:L100")
    shots = [r + [""] * (12 - len(r)) for r in rows if r and r[0].strip()]

    assets = []
    try:
        al = sh.worksheet("Asset Library")
        for r in al.get("A2:F50"):
            if r and r[0].strip():
                assets.append(r + [""] * (6 - len(r)))
    except Exception:
        pass

    # group by sequence, preserving order of first appearance
    seqs = []
    seq_map = {}
    for s in shots:
        seq = s[1].strip() or "Ungrouped"
        if seq not in seq_map:
            seq_map[seq] = []
            seqs.append(seq)
        seq_map[seq].append(s)

    seq_look = {seq: (seq_map[seq][0][10] if seq_map[seq] else "") for seq in seqs}

    total_dur = 0
    for s in shots:
        try:
            total_dur += float(s[2])
        except ValueError:
            pass

    # ---- build HTML ----
    parts = []
    parts.append(f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — Shotlist Dashboard</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  background:#0b0d10; color:#e6e8eb; line-height:1.5; }}
a {{ color:#7aa2f7; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 24px 80px; }}
header.hero {{ padding:54px 24px 40px; background:linear-gradient(160deg,#141821 0%,#0b0d10 70%);
  border-bottom:1px solid #1e2530; }}
.hero-inner {{ max-width:1180px; margin:0 auto; }}
.kicker {{ letter-spacing:.28em; font-size:12px; text-transform:uppercase; color:#7c8593; margin:0 0 10px; }}
h1 {{ font-size:40px; margin:0 0 18px; font-weight:700; letter-spacing:-.01em; }}
.stats {{ display:flex; gap:30px; flex-wrap:wrap; margin-top:6px; }}
.stat {{ display:flex; flex-direction:column; }}
.stat .n {{ font-size:26px; font-weight:700; color:#fff; }}
.stat .l {{ font-size:12px; text-transform:uppercase; letter-spacing:.12em; color:#7c8593; }}
section {{ margin-top:46px; }}
.seq-head {{ display:flex; align-items:baseline; gap:14px; margin:0 0 6px; }}
.seq-head h2 {{ font-size:24px; margin:0; font-weight:700; }}
.seq-head .count {{ color:#7c8593; font-size:14px; }}
.look {{ background:#11151c; border:1px solid #1e2530; border-left:3px solid #7aa2f7;
  padding:12px 16px; border-radius:8px; font-size:13.5px; color:#aeb6c2; margin:10px 0 22px; }}
.look b {{ color:#cdd3dc; font-weight:600; }}
.cards {{ display:grid; gap:14px; }}
.card {{ background:#11151c; border:1px solid #1e2530; border-radius:12px; padding:16px 18px;
  display:grid; grid-template-columns:54px 1fr; gap:16px; }}
.num {{ font-size:22px; font-weight:700; color:#4b5565; text-align:center; padding-top:2px; }}
.card-body {{ min-width:0; }}
.meta {{ display:flex; flex-wrap:wrap; gap:7px; align-items:center; margin-bottom:9px; }}
.pill {{ font-size:11.5px; padding:3px 9px; border-radius:999px; background:#1b212c; color:#9aa4b2;
  border:1px solid #28313f; white-space:nowrap; }}
.pill.dur {{ color:#cdd3dc; }}
.pill.type {{ background:#1d2733; color:#8fb8e8; border-color:#2a3a4d; }}
.pill.cam {{ background:#231d33; color:#b89fe0; border-color:#372a4d; }}
.beat {{ font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px; text-transform:uppercase;
  letter-spacing:.04em; }}
.beat-hook {{ background:#fcd34d; color:#5a3700; }}
.beat-jolt {{ background:#93c5fd; color:#1e3a5c; }}
.beat-payoff {{ background:#a7f3d0; color:#1a4a32; }}
.beat-cliff {{ background:#fca5a5; color:#6c1414; }}
.beat-flashback {{ background:#ddd6fe; color:#3a2a6c; }}
.beat-bridge {{ background:#e5e7eb; color:#4a4a4a; }}
.desc {{ font-size:15px; color:#e6e8eb; margin:0 0 8px; }}
.micro {{ font-size:13px; color:#d6b06a; margin:0 0 6px; font-style:italic; }}
.micro::before {{ content:'◆ '; opacity:.6; }}
.sfx {{ font-size:12.5px; color:#7c8593; margin:0 0 6px; }}
.sfx::before {{ content:'♪ '; }}
.merge {{ font-size:12.5px; color:#8fb8e8; background:#13202e; border:1px dashed #2a4255;
  padding:7px 11px; border-radius:7px; margin:8px 0 0; }}
.merge::before {{ content:'⇄ MERGE  '; font-weight:700; letter-spacing:.04em; font-size:10.5px; }}
.prompt-tog {{ margin-top:10px; }}
.prompt-tog summary {{ cursor:pointer; font-size:12px; color:#7c8593; list-style:none;
  user-select:none; display:inline-flex; align-items:center; gap:6px; }}
.prompt-tog summary::-webkit-details-marker {{ display:none; }}
.prompt-tog summary::before {{ content:'▸'; transition:transform .15s; }}
.prompt-tog[open] summary::before {{ transform:rotate(90deg); }}
.prompt-box {{ position:relative; margin-top:8px; }}
.prompt-box pre {{ background:#0a0c10; border:1px solid #1e2530; border-radius:8px; padding:12px 14px;
  font-size:12px; color:#aeb6c2; white-space:pre-wrap; word-break:break-word; margin:0;
  font-family:'SF Mono',ui-monospace,Menlo,monospace; }}
.copy-btn {{ position:absolute; top:8px; right:8px; font-size:11px; background:#1b212c; color:#9aa4b2;
  border:1px solid #28313f; border-radius:6px; padding:4px 9px; cursor:pointer; }}
.copy-btn:hover {{ background:#28313f; color:#fff; }}
.gen-seq {{ margin-bottom:28px; }}
.gen-seq-h {{ font-size:17px; font-weight:700; margin:18px 0 10px; color:#cdd3dc; display:flex; align-items:baseline; gap:10px; }}
.gen-seq-c {{ font-size:12px; color:#7c8593; font-weight:400; }}
.gens {{ display:grid; gap:18px; grid-template-columns:repeat(auto-fill,minmax(440px,1fr)); }}
.gen {{ background:#11151c; border:1px solid #1e2530; border-radius:12px; overflow:hidden; }}
.gen video {{ width:100%; aspect-ratio:16/9; background:#000; display:block; }}
.gen .gcap {{ padding:12px 14px; }}
.gen .gn {{ font-weight:700; font-size:15px; }}
.gen .gm {{ font-size:12px; color:#7c8593; margin-top:4px; }}
.assets {{ display:grid; gap:16px; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); }}
.asset {{ background:#11151c; border:1px solid #1e2530; border-radius:12px; overflow:hidden; }}
.asset .frame {{ aspect-ratio:9/16; background:#000; }}
.asset .frame iframe {{ width:100%; height:100%; border:0; display:block; }}
.asset .acap {{ padding:12px 14px; }}
.asset .acap .an {{ font-weight:700; font-size:15px; }}
.asset .acap .am {{ font-size:12px; color:#7c8593; margin-top:4px; word-break:break-all; }}
.asset .acap .code {{ font-family:'SF Mono',ui-monospace,Menlo,monospace; color:#8fb8e8; }}
.badge {{ display:inline-block; font-size:10.5px; padding:2px 8px; border-radius:999px;
  background:#16331f; color:#74d99a; border:1px solid #225033; margin-top:6px; }}
footer {{ margin-top:60px; padding-top:24px; border-top:1px solid #1e2530; color:#5b6470; font-size:12px; }}
</style></head><body>""")

    n_dur = f"{total_dur:g}"
    parts.append(f"""<header class="hero"><div class="hero-inner">
<p class="kicker">DearAI · Seedance 2.0 Shotlist</p>
<h1>{esc(title)}</h1>
<div class="stats">
  <div class="stat"><span class="n">{len(shots)}</span><span class="l">Shots</span></div>
  <div class="stat"><span class="n">{len(seqs)}</span><span class="l">Sequences</span></div>
  <div class="stat"><span class="n">{n_dur}s</span><span class="l">Total footage</span></div>
  <div class="stat"><span class="n">{len(assets)}</span><span class="l">Assets</span></div>
</div></div></header>""")

    parts.append('<div class="wrap">')

    for seq in seqs:
        seq_shots = seq_map[seq]
        look = seq_look.get(seq, "")
        parts.append('<section>')
        parts.append(
            f'<div class="seq-head"><h2>{esc(seq)}</h2>'
            f'<span class="count">{len(seq_shots)} shots</span></div>'
        )
        if look:
            parts.append(f'<div class="look"><b>LOOK</b> &nbsp;{esc(look)}</div>')
        parts.append('<div class="cards">')
        for s in seq_shots:
            num, _seq, dur, stype, cam, desc, micro, sfx, beat, merge, _look, prompt = s[:12]
            meta = [f'<span class="pill dur">{esc(dur)}s</span>']
            if stype:
                meta.append(f'<span class="pill type">{esc(stype)}</span>')
            if cam:
                meta.append(f'<span class="pill cam">{esc(cam)}</span>')
            if beat:
                meta.append(f'<span class="beat {beat_class(beat)}">{esc(beat)}</span>')
            body = [f'<div class="meta">{"".join(meta)}</div>']
            if desc:
                body.append(f'<p class="desc">{esc(desc)}</p>')
            if micro:
                body.append(f'<p class="micro">{esc(micro)}</p>')
            if sfx:
                body.append(f'<p class="sfx">{esc(sfx)}</p>')
            if merge:
                body.append(f'<div class="merge">{esc(merge)}</div>')
            if prompt:
                body.append(
                    '<details class="prompt-tog"><summary>Prompt</summary>'
                    '<div class="prompt-box">'
                    '<button class="copy-btn" onclick="cp(this)">copy</button>'
                    f'<pre>{esc(prompt)}</pre></div></details>'
                )
            parts.append(
                f'<div class="card"><div class="num">{esc(num)}</div>'
                f'<div class="card-body">{"".join(body)}</div></div>'
            )
        parts.append('</div></section>')

    # generated videos — walk every MP4 in each sequence subfolder
    gen_root = Path("/Users/raymuschang/Desktop/X-men/Generated Videos")
    dash_dir = Path(OUT).parent
    if gen_root.exists():
        seq_folders = sorted([d for d in gen_root.iterdir() if d.is_dir()])
        total_mp4s = sum(len(list(d.glob("*.mp4"))) for d in seq_folders)
        if total_mp4s:
            parts.append('<section><div class="seq-head"><h2>Generated Videos</h2>'
                         f'<span class="count">{total_mp4s} renders across {len(seq_folders)} sequences</span></div>')
            for d in seq_folders:
                mp4s = sorted(d.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
                if not mp4s:
                    continue
                label = d.name.replace("_", " · ")
                parts.append(f'<div class="gen-seq"><h3 class="gen-seq-h">{esc(label)} '
                             f'<span class="gen-seq-c">{len(mp4s)} iterations</span></h3>')
                parts.append('<div class="gens">')
                for i, mp4 in enumerate(mp4s, 1):
                    try:
                        rel = os.path.relpath(mp4, dash_dir)
                    except Exception:
                        rel = str(mp4)
                    rel = rel.replace(" ", "%20").replace("#", "%23")
                    parts.append(
                        '<div class="gen"><video controls preload="metadata" '
                        f'src="{rel}"></video>'
                        f'<div class="gcap"><div class="gn">Gen {i}</div>'
                        f'<div class="gm">{esc(mp4.name)}</div></div></div>'
                    )
                parts.append('</div></div>')

    # asset library
    if assets:
        parts.append('<section><div class="seq-head"><h2>Asset Library</h2>'
                     f'<span class="count">{len(assets)} registered</span></div>')
        parts.append('<div class="assets">')
        for a in assets:
            name, cat, code, src, atype, status = a[:6]
            fid = drive_id(src)
            frame = ""
            if fid and atype.lower() == "video":
                frame = (f'<div class="frame"><iframe src="https://drive.google.com/file/d/{fid}/preview" '
                         'allow="autoplay" allowfullscreen></iframe></div>')
            elif fid and atype.lower() == "image":
                frame = (f'<div class="frame"><img src="https://lh3.googleusercontent.com/d/{fid}=w800" '
                         'style="width:100%;height:100%;object-fit:cover" alt=""></div>')
            parts.append(
                f'<div class="asset">{frame}<div class="acap">'
                f'<div class="an">{esc(name)}</div>'
                f'<div class="am">{esc(cat)} · {esc(atype)} · '
                f'<span class="code">{esc(code)}</span></div>'
                f'<span class="badge">{esc(status)}</span></div></div>'
            )
        parts.append('</div></section>')

    parts.append(f'<footer>Generated from <a href="https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit">'
                 'the source sheet</a> · DearAI production pipeline</footer>')
    parts.append('</div>')

    parts.append("""<script>
function cp(btn){
  var pre = btn.parentElement.querySelector('pre');
  navigator.clipboard.writeText(pre.innerText).then(function(){
    var o = btn.textContent; btn.textContent='copied ✓';
    setTimeout(function(){ btn.textContent=o; }, 1400);
  });
}
</script></body></html>""")

    with open(OUT, "w") as f:
        f.write("".join(parts))
    print(f"Wrote {OUT} — {len(shots)} shots, {len(seqs)} sequences, {len(assets)} assets")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build a gallery of all known Seedance (BytePlus) asset-library elements.

Pulls every asset code from local manifest JSONs, fires GetAsset on each to
refresh the signed TOS URL + metadata (name, type, group), then writes a
dark-themed HTML gallery grouped by project.
"""
import json, os, re
from pathlib import Path

env = open(".env").read()
for line in env.splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

import byteplus_asset_v2 as bp

OUT = Path("/Users/raymuschang/Desktop/Sales Decks/Seedance_Elements_Gallery.html")
HERE = Path(".")

# Friendly labels for known groups
GROUP_LABELS = {
    "group-20260505195134-wqx2b": "Channel 8 — Underwater Test",
    "group-20260512182023-fvqm7": "Raymus Personal Brand",
}

# 1. Aggregate codes from local manifests
codes_local: dict[str, list[str]] = {}
for f in list(HERE.glob(".*.json")) + list(HERE.glob("*.json")):
    try:
        data = json.loads(f.read_text())
    except Exception:
        continue
    def walk(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{prefix}.{k}" if prefix else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{prefix}[{i}]")
        elif isinstance(obj, str) and re.match(r"^asset-\d{14}-[a-z0-9]+$", obj):
            codes_local.setdefault(obj, []).append(f"{f.name}::{prefix}")
    walk(data)

print(f"local codes: {len(codes_local)}")

# 2. GetAsset on each
assets = []
for code, hints in codes_local.items():
    r = bp.get_asset(code)
    result = r.get("Result") or {}
    err = r.get("ResponseMetadata", {}).get("Error")
    if err:
        print(f"  ✗ {code}: {err.get('Code')} {err.get('Message')}")
        continue
    assets.append({
        "id": result.get("Id"),
        "name": result.get("Name") or "(unnamed)",
        "type": result.get("AssetType"),
        "url": result.get("URL"),
        "group_id": result.get("GroupId"),
        "project": result.get("ProjectName"),
        "status": result.get("Status"),
        "created": result.get("CreateTime"),
        "hint": hints[0],
    })

print(f"resolved {len(assets)} assets")

# 3. Group + sort
by_group: dict[str, list[dict]] = {}
for a in assets:
    by_group.setdefault(a["group_id"] or "unknown", []).append(a)
for gid in by_group:
    by_group[gid].sort(key=lambda x: (x["type"] or "", x["name"] or ""))

# 4. Render HTML
def tile(a: dict) -> str:
    type_class = (a["type"] or "Unknown").lower()
    name = a["name"] or "(unnamed)"
    short_id = a["id"].replace("asset-", "")
    if a["type"] == "Image":
        media = f'<img src="{a["url"]}" alt="{name}" loading="lazy" onerror="this.parentElement.classList.add(\'broken\')">'
    elif a["type"] == "Video":
        media = f'<video src="{a["url"]}" muted loop preload="metadata" onmouseover="this.play()" onmouseout="this.pause();this.currentTime=0" onerror="this.parentElement.classList.add(\'broken\')"></video>'
    elif a["type"] == "Audio":
        media = f'<div class="audio-icon">♪</div><audio src="{a["url"]}" controls preload="metadata"></audio>'
    else:
        media = f'<div class="audio-icon">?</div>'
    status_class = "ok" if a["status"] == "Active" else "warn"
    return f'''<div class="tile type-{type_class}">
  <div class="media-wrap">{media}</div>
  <div class="tile-info">
    <div class="tile-name">{name}</div>
    <div class="tile-meta"><span class="badge {type_class}">{a["type"] or "?"}</span> <span class="badge status-{status_class}">{a["status"] or "?"}</span></div>
    <div class="tile-id">{short_id}</div>
  </div>
</div>'''

sections = []
for gid in sorted(by_group, key=lambda g: GROUP_LABELS.get(g, g)):
    items = by_group[gid]
    label = GROUP_LABELS.get(gid, gid)
    counts = {}
    for a in items:
        counts[a["type"] or "?"] = counts.get(a["type"] or "?", 0) + 1
    count_str = " · ".join(f"{n} {t}" for t, n in counts.items())
    tiles_html = "".join(tile(a) for a in items)
    sections.append(f'''<section class="group">
  <header class="group-head">
    <h2>{label}</h2>
    <div class="meta">{gid} · {len(items)} assets · {count_str}</div>
  </header>
  <div class="grid">{tiles_html}</div>
</section>''')

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --cyan: #19D3F3;
  --green: #5EE7B4;
  --coral: #FF8B7B;
  --amber: #FCD34D;
  --navy: #0B1320;
  --slate: #1E293B;
  --cream: #F4FAF8;
  --muted: rgba(244,250,248,0.5);
  --display: 'Plus Jakarta Sans', 'Noto Sans SC', sans-serif;
  --body: 'Inter', 'Noto Sans SC', sans-serif;
  --gradient: linear-gradient(135deg, #19D3F3 0%, #5EE7B4 100%);
}
html, body {
  background: var(--navy);
  color: var(--cream);
  font-family: var(--body);
  -webkit-font-smoothing: antialiased;
}
body {
  background:
    radial-gradient(ellipse at 80% 5%, rgba(25,211,243,0.10) 0%, transparent 50%),
    radial-gradient(ellipse at 10% 90%, rgba(94,231,180,0.08) 0%, transparent 50%),
    linear-gradient(180deg, #0B1320 0%, #0F1A2A 100%);
  min-height: 100vh;
  padding: 40px 60px 80px;
}
header.top {
  margin-bottom: 36px;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(25,211,243,0.18);
}
header.top h1 {
  font-family: var(--display);
  font-weight: 800;
  font-size: 42px;
  letter-spacing: -0.02em;
  margin-bottom: 8px;
}
header.top h1 .gradient {
  background: var(--gradient);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
header.top .sub {
  font-size: 14px;
  color: var(--muted);
}
header.top .warn {
  margin-top: 14px;
  background: rgba(252,211,77,0.10);
  border-left: 3px solid var(--amber);
  border-radius: 0 8px 8px 0;
  padding: 10px 16px;
  color: rgba(252,211,77,0.9);
  font-size: 12px;
  max-width: 700px;
}

.group {
  margin-bottom: 48px;
}
.group-head {
  margin-bottom: 18px;
}
.group-head h2 {
  font-family: var(--display);
  font-weight: 700;
  font-size: 22px;
  letter-spacing: -0.01em;
  background: var(--gradient);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  margin-bottom: 4px;
}
.group-head .meta {
  font-size: 12px;
  color: var(--muted);
  font-family: 'JetBrains Mono', monospace, var(--body);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.tile {
  background: rgba(30,41,59,0.55);
  border: 1px solid rgba(25,211,243,0.15);
  border-radius: 10px;
  overflow: hidden;
  transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
}
.tile:hover {
  transform: translateY(-2px);
  border-color: var(--cyan);
  box-shadow: 0 8px 22px rgba(25,211,243,0.18);
}
.media-wrap {
  aspect-ratio: 16/9;
  background: rgba(11,19,32,0.6);
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.media-wrap.broken::before {
  content: '⚠ link expired or unavailable';
  position: absolute;
  inset: 0;
  display: flex; align-items: center; justify-content: center;
  color: rgba(255,139,123,0.7);
  font-size: 11px;
  background: rgba(255,139,123,0.05);
}
.tile img, .tile video {
  width: 100%; height: 100%; object-fit: cover;
  display: block;
}
.tile .audio-icon {
  font-size: 38px;
  color: var(--green);
  text-align: center;
  margin: 12px auto;
}
.tile audio {
  width: calc(100% - 16px);
  margin: 0 8px 8px;
}
.tile-info {
  padding: 10px 12px 12px;
}
.tile-name {
  font-family: var(--display);
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
  line-height: 1.3;
  word-break: break-word;
}
.tile-meta {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.badge {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(244,250,248,0.08);
  color: rgba(244,250,248,0.6);
}
.badge.image { color: var(--green); background: rgba(94,231,180,0.12); }
.badge.video { color: var(--cyan); background: rgba(25,211,243,0.12); }
.badge.audio { color: var(--amber); background: rgba(252,211,77,0.12); }
.badge.status-ok { color: var(--green); background: rgba(94,231,180,0.10); }
.badge.status-warn { color: var(--coral); background: rgba(255,139,123,0.12); }
.tile-id {
  font-family: 'JetBrains Mono', monospace, var(--body);
  font-size: 9.5px;
  color: var(--muted);
  word-break: break-all;
  line-height: 1.4;
}
"""

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Seedance Elements Gallery — BytePlus Asset Library</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>

<header class="top">
  <h1>Seedance Elements · <span class="gradient">BytePlus Asset Library</span></h1>
  <div class="sub">{len(assets)} assets across {len(by_group)} project groups · resolved {Path('byteplus_asset_v2.py').stat().st_mtime and ''}via live GetAsset</div>
  <div class="warn">⚠ Signed URLs expire ~12h after each rebuild. Re-run <code>python3 _build_seedance_elements_gallery.py</code> when tiles go blank.</div>
</header>

{''.join(sections)}

</body>
</html>
"""

OUT.write_text(HTML)
print(f"\n✓ wrote {OUT}")
print(f"  size: {OUT.stat().st_size/1024:.1f}KB")

#!/usr/bin/env python3
"""Build the Underwater Test Shoot HTML deck — bilingual (EN left / ZH right)."""
import json
from pathlib import Path

HERE = Path(__file__).parent
DRIVE = json.loads((HERE / ".channel8_drive_files.json").read_text())
OUT = Path("/Users/raymuschang/Documents/Sales Decks/UnderwaterTestShoot_Dark.html")


def fid(path: str) -> str:
    return DRIVE.get(path, "")


def vid_tile(file_id: str, label: str) -> str:
    if not file_id:
        return f'<div class="vid-tile missing"><div class="vid-label">{label} (missing)</div></div>'
    thumb = f"https://drive.google.com/thumbnail?id={file_id}&sz=w800"
    return f'''<div class="vid-tile" onclick="openLightbox('{file_id}')">
  <img loading="lazy" src="{thumb}" alt="{label}" onerror="this.style.display='none'">
  <div class="play-icon">▶</div>
  <div class="vid-label">{label}</div>
</div>'''


# ============== Curated lists ==============

ORIGINALS = [(i, fid(f"cuts/splits/shot {i:02d}/shot {i:02d}.mp4")) for i in range(1, 15)]
SEEDANCE_EXCLUDE = {
    "cuts/splits/shot 02/seedance outputs/shot_02_underwater_v2.mp4",
}
SEEDANCE_OUTPUTS = sorted([p for p in DRIVE if "seedance outputs/" in p and p.endswith(".mp4") and p not in SEEDANCE_EXCLUDE])
KLING_RAW = sorted([p for p in DRIVE if "kling mocap/" in p and p.endswith(".mp4")])
# Filter: drop intermediates (leading _), reversed-motion artifact, silent _with_element versions
# (audio _v2_audio versions kept). i2v multishot folder explicitly excluded above.
KLING_OUTPUTS = [
    p for p in KLING_RAW
    if not Path(p).name.startswith("_")
    and "reversed_motion" not in p
    and "with_element" not in p
]
KLING_EXTRAS = sorted([p for p in DRIVE if "kling outputs (Extra test)/" in p])

CHAR_REFS = [
    ("Young Emperor", "年轻皇帝", fid("character references/orbit-01-young-emperor.mp4")),
    ("Wise Elder",    "智者长老", fid("character references/orbit-02-wise-elder.mp4")),
    ("Princess",      "公主",     fid("character references/orbit-05-princess-closeup.mp4")),
    ("Minister",      "大臣",     fid("character references/minister.mp4")),
]
LOCATION_REF = fid("location-refs/Underwater Palace Montage.mp4")


def shot_label(p: str) -> str:
    import re
    parts = p.split("/")
    shot_dir = next((x for x in parts if x.startswith("shot ")), None)
    fname = parts[-1].replace(".mp4", "").replace("_", " ")
    base = shot_dir.replace("shot 0", "Shot ").replace("shot ", "Shot ") if shot_dir else "—"
    fname = re.sub(r"^shot \d+\s*", "", fname).strip()
    return f"{base} · {fname}" if fname else base


# ============== CSS ==============

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --cyan: #19D3F3;
  --green: #5EE7B4;
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
.slide {
  width: 100vw;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(ellipse at 80% 20%, rgba(25,211,243,0.18) 0%, transparent 45%),
    radial-gradient(ellipse at 15% 85%, rgba(94,231,180,0.14) 0%, transparent 45%),
    linear-gradient(180deg, #0B1320 0%, #0F1A2A 100%);
  padding: 60px 80px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.slide.scrollable { justify-content: flex-start; }

/* Bilingual two-column wrapper */
.bilingual {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 60px;
  align-items: start;
}
.lang-en { padding-right: 30px; border-right: 1px solid rgba(25,211,243,0.15); }
.lang-zh { padding-left: 30px; font-family: 'Noto Sans SC', 'Plus Jakarta Sans', sans-serif; }
.lang-zh h2.h2, .lang-zh h1.h1, .lang-zh h3.h3 { font-family: 'Noto Sans SC', 'Plus Jakarta Sans', sans-serif; }
.lang-tag {
  display: inline-block;
  font-family: var(--display);
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.32em;
  color: rgba(25,211,243,0.6);
  margin-bottom: 8px;
}

.gradient-text {
  background: var(--gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.label {
  font-family: var(--display);
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--green);
  margin-bottom: 18px;
  text-shadow: 0 0 12px rgba(94,231,180,0.3);
}
.label::after { content: ' ———•'; color: var(--cyan); }
h1.h1 {
  font-family: var(--display);
  font-weight: 800;
  font-size: clamp(40px, 5vw, 78px);
  line-height: 1.0;
  letter-spacing: -0.03em;
  margin-bottom: 24px;
}
h2.h2 {
  font-family: var(--display);
  font-weight: 700;
  font-size: clamp(28px, 3vw, 50px);
  line-height: 1.06;
  letter-spacing: -0.02em;
  margin-bottom: 22px;
}
h3.h3 {
  font-family: var(--display);
  font-weight: 600;
  font-size: clamp(18px, 1.8vw, 28px);
  margin-bottom: 14px;
}
p.body {
  font-size: clamp(15px, 1.15vw, 18px);
  line-height: 1.65;
  color: rgba(244,250,248,0.85);
  margin-bottom: 14px;
}
p.body.italic { font-style: italic; color: rgba(244,250,248,0.6); }
.subtle { color: var(--muted); font-size: 13px; }

/* Video grids */
.vid-grid {
  display: grid;
  gap: 20px;
  margin-top: 24px;
}
.vid-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
.vid-grid.cols-4 { grid-template-columns: repeat(4, 1fr); }
.vid-grid.cols-5 { grid-template-columns: repeat(5, 1fr); }
.vid-grid.cols-7 { grid-template-columns: repeat(7, 1fr); }

.vid-tile {
  position: relative;
  aspect-ratio: 16/9;
  background: rgba(30,41,59,0.6);
  border: 1px solid rgba(25,211,243,0.18);
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
}
.vid-tile:hover {
  transform: translateY(-2px);
  border-color: var(--cyan);
  box-shadow: 0 8px 24px rgba(25,211,243,0.18);
}
.vid-tile img {
  width: 100%; height: 100%; object-fit: cover;
}
.vid-tile.missing {
  background: rgba(255,80,80,0.08);
  border-color: rgba(255,80,80,0.3);
  display: flex; align-items: center; justify-content: center;
}
.vid-tile .play-icon {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 36px;
  color: var(--cream);
  background: linear-gradient(180deg, rgba(11,19,32,0.0) 0%, rgba(11,19,32,0.55) 100%);
  pointer-events: none;
  text-shadow: 0 2px 12px rgba(0,0,0,0.6);
  opacity: 0.85;
}
.vid-tile:hover .play-icon { opacity: 1; }
.vid-tile .vid-label {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--cream);
  background: linear-gradient(180deg, transparent 0%, rgba(11,19,32,0.85) 80%);
  pointer-events: none;
}

.placeholder-tile {
  aspect-ratio: 16/9;
  background: rgba(94,231,180,0.05);
  border: 2px dashed rgba(94,231,180,0.35);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: rgba(94,231,180,0.6);
  font-family: var(--display);
  font-weight: 600;
  font-size: 18px;
}

/* Lightbox */
.lightbox {
  position: fixed; inset: 0;
  background: rgba(11,19,32,0.94);
  z-index: 1000;
  display: none;
  align-items: center; justify-content: center;
  padding: 40px;
  backdrop-filter: blur(10px);
}
.lightbox.active { display: flex; }
.lightbox-inner {
  position: relative;
  width: min(90vw, 1280px);
  aspect-ratio: 16/9;
  background: black;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 30px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(25,211,243,0.25);
}
.lightbox-inner iframe { width: 100%; height: 100%; border: 0; }
.lightbox-close {
  position: absolute;
  top: -50px; right: 0;
  background: transparent;
  color: var(--cream);
  border: 1px solid rgba(244,250,248,0.3);
  border-radius: 50%;
  width: 40px; height: 40px;
  font-size: 24px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.15s, border-color 0.15s;
}
.lightbox-close:hover { background: rgba(244,250,248,0.1); border-color: var(--cyan); }

/* Slide-specific */
.title-slide {
  text-align: center;
  align-items: center;
  justify-content: center;
}
.shot-label {
  font-family: var(--display);
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.06em;
  color: rgba(244,250,248,0.7);
  text-align: center;
  margin-top: 8px;
}
.shot-cell { display: flex; flex-direction: column; align-items: center; }
.shot-cell .vid-tile { width: 100%; }

ul.bullets { list-style: none; }
ul.bullets li {
  position: relative;
  padding-left: 24px;
  margin-bottom: 12px;
  font-size: clamp(15px, 1.15vw, 18px);
  line-height: 1.55;
  color: rgba(244,250,248,0.85);
}
ul.bullets li::before {
  content: '▸';
  position: absolute;
  left: 0;
  color: var(--cyan);
  font-weight: 700;
}

.step-card {
  background: rgba(30,41,59,0.5);
  border: 1px solid rgba(25,211,243,0.2);
  border-radius: 14px;
  padding: 22px 26px;
  margin-bottom: 14px;
}
.step-num {
  display: inline-block;
  font-family: var(--display);
  font-weight: 800;
  font-size: 28px;
  background: var(--gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin-right: 10px;
  vertical-align: middle;
}

footer.slide-foot {
  position: absolute;
  bottom: 24px; left: 80px; right: 80px;
  font-size: 11px;
  color: var(--muted);
  display: flex;
  justify-content: space-between;
}

/* Flowchart (slide 10 — Step 2 process) */
.flowchart {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 18px;
  align-items: stretch;
  margin: 24px 0 28px;
}
.flow-node {
  background: rgba(30,41,59,0.55);
  border: 1px solid rgba(25,211,243,0.22);
  border-radius: 12px;
  padding: 18px 14px 16px;
  text-align: center;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
}
.flow-node.io-start { border-color: rgba(94,231,180,0.45); background: rgba(94,231,180,0.06); }
.flow-node.io-end   { border-color: rgba(94,231,180,0.55); background: rgba(94,231,180,0.10); }
.flow-node.action {
  border-color: rgba(25,211,243,0.55);
  background: linear-gradient(135deg, rgba(25,211,243,0.10), rgba(94,231,180,0.08));
}
.flow-node-num {
  font-family: var(--display);
  font-weight: 800;
  font-size: 22px;
  background: var(--gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin-bottom: 8px;
  line-height: 1;
}
.flow-node-en {
  font-family: var(--display);
  font-weight: 700;
  font-size: 12.5px;
  letter-spacing: 0.02em;
  color: var(--cream);
  line-height: 1.25;
  margin-bottom: 6px;
}
.flow-node-zh {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 11px;
  color: rgba(244,250,248,0.62);
  line-height: 1.35;
}
.flow-node:not(:last-child)::after {
  content: '▸';
  position: absolute;
  right: -14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--cyan);
  font-size: 18px;
  z-index: 2;
  text-shadow: 0 0 8px rgba(25,211,243,0.5);
}
.flow-node.iterate::before {
  content: '↺';
  position: absolute;
  top: -10px; right: -10px;
  background: var(--navy);
  border: 1px solid var(--cyan);
  border-radius: 50%;
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px;
  color: var(--cyan);
  z-index: 3;
}
.flowchart-caption {
  font-size: 12px;
  color: var(--muted);
  text-align: center;
  margin-top: -12px;
  margin-bottom: 22px;
  letter-spacing: 0.04em;
}

/* Observation blocks (Positives / Negatives) */
.obs-block {
  border-left: 3px solid;
  border-radius: 0 10px 10px 0;
  padding: 14px 20px;
  margin-bottom: 16px;
  background: rgba(30,41,59,0.35);
}
.obs-block.positive { border-color: var(--green); }
.obs-block.negative { border-color: #FF8B7B; }
.obs-block h4 {
  font-family: var(--display);
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.obs-block.positive h4 { color: var(--green); }
.obs-block.negative h4 { color: #FF8B7B; }
.obs-block ol {
  list-style: decimal;
  padding-left: 20px;
  margin: 0;
}
.obs-block ol li {
  font-size: 13px;
  line-height: 1.55;
  margin-bottom: 8px;
  color: rgba(244,250,248,0.82);
}
.obs-block ol li:last-child { margin-bottom: 0; }
"""

JS = r"""
function openLightbox(fileId) {
  const f = document.getElementById('lightbox-frame');
  f.src = 'https://drive.google.com/file/d/' + fileId + '/preview';
  document.getElementById('lightbox').classList.add('active');
  document.body.style.overflow = 'hidden';
}
function closeLightbox(e) {
  if (e && e.target && e.target.id !== 'lightbox' && e.target.className !== 'lightbox-close') return;
  document.getElementById('lightbox').classList.remove('active');
  document.getElementById('lightbox-frame').src = '';
  document.body.style.overflow = '';
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.getElementById('lightbox').classList.remove('active');
    document.getElementById('lightbox-frame').src = '';
    document.body.style.overflow = '';
  }
});
"""


# ============== Grid builders ==============

def shot_grid_14() -> str:
    cells = []
    for i, file_id in ORIGINALS:
        cells.append(f'<div class="shot-cell">{vid_tile(file_id, "")}<div class="shot-label">Shot {i} · 镜头 {i}</div></div>')
    return f'<div class="vid-grid cols-7">{"".join(cells)}</div>'


def seedance_grid() -> str:
    return f'<div class="vid-grid cols-4">{"".join(vid_tile(DRIVE[p], shot_label(p)) for p in SEEDANCE_OUTPUTS)}</div>'


def kling_grid() -> str:
    return f'<div class="vid-grid cols-3">{"".join(vid_tile(DRIVE[p], shot_label(p)) for p in KLING_OUTPUTS)}</div>'


def kling_extras_grid() -> str:
    cells = [vid_tile(DRIVE[p], Path(p).stem) for p in KLING_EXTRAS]
    return f'<div class="vid-grid cols-3">{"".join(cells)}</div>'


def char_refs_grid() -> str:
    cells = [
        f'<div class="shot-cell">{vid_tile(f_id, "")}<div class="shot-label">{en}<br>{zh}</div></div>'
        for en, zh, f_id in CHAR_REFS
    ]
    cells.append(
        f'<div class="shot-cell">{vid_tile(LOCATION_REF, "")}<div class="shot-label">Location · 场景<br>Underwater Palace · 海底宫殿</div></div>'
    )
    return f'<div class="vid-grid cols-5">{"".join(cells)}</div>'


# ============== HTML ==============

n_seedance = len(SEEDANCE_OUTPUTS)
n_seedance_shots = len({p.split('/')[2] for p in SEEDANCE_OUTPUTS})
n_kling = len(KLING_OUTPUTS)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Underwater Test Shoot · 水下场景测试 — Dear.AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>

<!-- SLIDE 1 — TITLE -->
<section class="slide title-slide">
  <div class="label">Dear.AI · R&D Test · 研发测试</div>
  <div class="bilingual" style="text-align:center; max-width:1400px;">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h1 class="h1"><span class="gradient-text">Underwater</span><br>Test Shoot</h1>
      <p class="body">VFX feasibility study · 14-shot underwater reskin</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h1 class="h1"><span class="gradient-text">水下场景</span><br>测试拍摄</h1>
      <p class="body">视觉特效可行性研究 · 14镜水下风格转换</p>
    </div>
  </div>
  <footer class="slide-foot"><span>Slide 1 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 2 — GOAL -->
<section class="slide">
  <div class="label">Slide 02 · Goal · 目标</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">The Goal</span></h2>
      <p class="body">A consistent and reliable way to create believable and high-quality underwater scenes that show some water physics. Also want character consistency and lip-syncing. Characters should blend well with environment.</p>
      <p class="body italic">Our earlier hypothesis is that wide shots and multi-person shots may be difficult to convert — but we will try all the ways to make it work.</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">目标</span></h2>
      <p class="body">建立稳定可靠的方法，制作出可信且高质量的水下场景，并呈现水流物理效果。同时确保角色一致性与对口型，让人物与环境自然融合。</p>
      <p class="body italic">我们最初的假设是：广角镜头和多人镜头可能难以转换——但我们会尝试所有方法去攻克。</p>
    </div>
  </div>
  <footer class="slide-foot"><span>Slide 2 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 3 — CHALLENGES -->
<section class="slide">
  <div class="label">Slide 03 · Challenges · 挑战</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">Challenges</span></h2>
      <ul class="bullets">
        <li><strong>Underwater physics</strong> — caustic light, suspended motion in hair and fabric, bubbles, drift of fish and particulate.</li>
        <li><strong>Repeatable, consistent location</strong> — in a drama (unlike ads or social reels), locations are revisited across shots and episodes. The set must look the same every time.</li>
      </ul>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">挑战</span></h2>
      <ul class="bullets">
        <li><strong>水下物理效果</strong>——焦散光线、头发与衣物的悬浮飘动、气泡、鱼群与微粒漂流。</li>
        <li><strong>可重复且一致的场景</strong>——在剧集中（不同于广告或社交短片），同一场景会在多个镜头与集数中重复出现，每次必须看起来完全一致。</li>
      </ul>
    </div>
  </div>
  <footer class="slide-foot"><span>Slide 3 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 4 — METHODOLOGY -->
<section class="slide scrollable">
  <div class="label">Slide 04 · Methodology · 方法论</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">Methodology</span></h2>
      <h3 class="h3">a) The cut, divided into 14 shots</h3>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">方法论</span></h2>
      <h3 class="h3">a) 将完整剪辑划分为14个镜头</h3>
    </div>
  </div>
  {shot_grid_14()}
  <div class="bilingual" style="margin-top: 28px;">
    <div class="lang-en">
      <ul class="bullets">
        <li><strong>b)</strong> Apply all the latest video-to-video VFX tools to each shot — Runway Aleph, Luma Ray 3.14, Kling Omni, Seedance 2 Pro. We even requested Seedance 2 Pro special access for human-face uploads on their console (a typically banned feature for the public).</li>
        <li><strong>c)</strong> Gather results and then make a recommendation.</li>
      </ul>
    </div>
    <div class="lang-zh">
      <ul class="bullets">
        <li><strong>b)</strong> 对每个镜头测试最新的视频转视频VFX工具——Runway Aleph、Luma Ray 3.14、Kling Omni、Seedance 2 Pro。我们甚至向 Seedance 2 Pro 申请了在其控制台上传人脸的特殊权限（这是通常对公众禁用的功能）。</li>
        <li><strong>c)</strong> 汇总结果并提出建议。</li>
      </ul>
    </div>
  </div>
  <footer class="slide-foot"><span>Slide 4 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 5 — ELIMINATING -->
<section class="slide">
  <div class="label">Slide 05 · What Doesn't Work · 已被排除</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2">Eliminating <span class="gradient-text">What 100% Does Not Work</span></h2>
      <p class="body">Runway, Luma 3.14 and Wan 2.7 do not work. Faces become different people. And underwater physics are 100% absent. After our tests — there is no meaningful discussion.</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2">排除 <span class="gradient-text">100% 不可行的方法</span></h2>
      <p class="body">Runway、Luma 3.14 和 Wan 2.7 无法胜任。人脸会变成不同的人，水下物理效果完全缺失。测试后——无需进一步讨论。</p>
    </div>
  </div>
  <footer class="slide-foot"><span>Slide 5 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 6 — SEEDANCE TEST -->
<section class="slide scrollable">
  <div class="label">Slide 06 · Seedance 2 Test · Seedance 2 测试</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">Seedance 2</span> Test</h2>
      <div class="obs-block positive">
        <h4>Strengths</h4>
        <ol>
          <li>Backgrounds can be recreated with 70–80% consistency. There is still some drift — pillars behind characters are not always in the same spot — but major features are roughly the same.</li>
          <li>Acting is 80–90% similar. There are timing differences, and sometimes a right-hand gesture maps onto the left hand in the generated video.</li>
          <li>Seedance 2 can integrate costume changes well.</li>
          <li>Seedance 2 can convert wide shots with multiple people reasonably well. Probably the best in the market right now (although not perfect).</li>
        </ol>
      </div>
      <div class="obs-block negative">
        <h4>Limitations</h4>
        <ol>
          <li>Soldiers cannot be integrated into the live-action footage — their size is inconsistent and the depth of field on the background looks very bad.</li>
          <li>The pillar on the actor's neck is too thin to meaningfully convert into a chunky pillar. The Shot 1 conversions look promising and might be 100% successful with an actual pillar prop on set.</li>
          <li>Even at 1080p, background characters start to look mushy. This is a problem with all AI video generators.</li>
          <li>Because of the fantasy setting, there's a tendency toward a "video game" look that may not be appealing for drama. Most video AIs train heavily on game data for fantastical locations — there is much less film data for underwater scenes by comparison.</li>
          <li>Seedance 2 100% cannot recreate water physics or bubbles in the shots.</li>
          <li>Overall concern: characters and environments are not perfectly integrated, due to the unique challenges of an underwater location. Two slides later, you'll see on-land locations look significantly better.</li>
        </ol>
      </div>
      <p class="body subtle">Click any tile to play in lightbox. {n_seedance} outputs across {n_seedance_shots} shots.</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">Seedance 2</span> 测试</h2>
      <div class="obs-block positive">
        <h4>优势</h4>
        <ol>
          <li>背景可以以 70–80% 的一致性重现。仍有些许偏差——角色身后的柱子位置不完全相同——但主要特征大致一致。</li>
          <li>表演相似度约 80–90%。存在时间节奏差异，有时原片中的右手动作会被映射到生成视频中的左手。</li>
          <li>Seedance 2 能很好地处理服装替换。</li>
          <li>Seedance 2 能较好地转换多人广角镜头，目前可能是市场上最强的（虽不完美）。</li>
        </ol>
      </div>
      <div class="obs-block negative">
        <h4>局限</h4>
        <ol>
          <li>士兵无法整合到实拍画面中——士兵尺寸不一致，背景纵深效果很差。</li>
          <li>颈后那根柱子太细，难以有效转换成粗壮的金柱。镜头 1 的 Seedance 2 转换效果令人期待——若现场配有实际柱子道具，可能 100% 成功。</li>
          <li>即便在 1080p 下，背景人物也开始模糊不清。这是所有 AI 视频生成器的通病。</li>
          <li>由于是奇幻场景，画面容易呈现"游戏感"，可能不适合剧集风格——许多视频 AI 在奇幻场景方面主要使用游戏数据训练，水下场景的影视训练数据相对稀缺。</li>
          <li>Seedance 2 完全无法重现镜头中的水流物理与气泡效果。</li>
          <li>总体担忧：由于水下场景的特殊挑战，本方法下角色与环境无法完美融合。请见后两张幻灯片——陆地场景的表现明显更好。</li>
        </ol>
      </div>
      <p class="body subtle">点击任意视频在弹窗中播放。共 {n_seedance} 个输出，覆盖 {n_seedance_shots} 个镜头。</p>
    </div>
  </div>
  {seedance_grid()}
  <footer class="slide-foot"><span>Slide 6 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 7 — KLING TEST -->
<section class="slide scrollable">
  <div class="label">Slide 07 · Kling Test · Kling 测试</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">Kling</span> Test</h2>
      <div class="obs-block positive">
        <h4>What Worked (with caveats)</h4>
        <ol>
          <li>The motion capture is acceptable only if the camera is generally static and slow-moving. A number of the camera movements (e.g. jib down) did NOT allow us to convert the acting footage properly, leading to weird movements and artifacts.</li>
          <li>It can actually recreate bubble effects — but the result is erratic and unnatural. It takes 3–6 tries to get a single convincing water-physics effect.</li>
        </ol>
      </div>
      <div class="obs-block negative">
        <h4>Limitations</h4>
        <ol>
          <li>This did not do well at all. Results seem very artificial and inconsistent.</li>
          <li>This was imagined to be possible for the underwater location — but it seems too difficult considering the number of characters in the scene.</li>
          <li>If a location reference is given to the AI (so that we can revisit and recreate the same set), it will affect all faces and costumes in the regeneration.</li>
        </ol>
      </div>
      <p class="body subtle">Motion-control (kling-v3) with element-locked identity. {n_kling} outputs.</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">Kling</span> 测试</h2>
      <div class="obs-block positive">
        <h4>勉强可用之处（有局限）</h4>
        <ol>
          <li>仅当摄影机基本静止或缓慢移动时，动作捕捉效果尚可。一些复杂运镜（如俯摇下降）无法正常转换表演画面，产生奇怪的动作与瑕疵。</li>
          <li>它确实能生成气泡效果——但表现不稳定、不自然，通常需要 3–6 次尝试才能得到一个可信的水流效果。</li>
        </ol>
      </div>
      <div class="obs-block negative">
        <h4>局限</h4>
        <ol>
          <li>整体表现很差——结果显得非常人工且不一致。</li>
          <li>我们原本希望它能胜任水下场景，但考虑到画面中的角色数量，难度似乎太大。</li>
          <li>若提供场景参考给 AI（以便我们能反复重现同一场景），它会同时改变所有面孔与服装。</li>
        </ol>
      </div>
      <p class="body subtle">动作控制 (kling-v3)，角色元素锁定身份。共 {n_kling} 个输出。</p>
    </div>
  </div>
  {kling_grid()}
  <footer class="slide-foot"><span>Slide 7 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 7B — KLING EXTRAS -->
<section class="slide scrollable">
  <div class="label">Slide 07b · Kling Omni (Extras) · Kling Omni（其他测试）</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">Kling Omni</span> — Extras</h2>
      <p class="body">Here are extra tests in other locations for your reference. However with this method, it is not possible to recreate the background 100% if the story comes back to this location later.</p>
      <p class="body">So this workflow is much stronger for advertisements and short reels — where locations are not revisited.</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">Kling Omni</span> — 其他测试</h2>
      <p class="body">这里是其他场景的额外测试供参考。但此方法无法100%复刻同一背景——若剧情之后回到这个场景，将无法保持一致。</p>
      <p class="body">因此，这套工作流更适合广告与短片——场景无需重复出现。</p>
    </div>
  </div>
  {kling_extras_grid()}
  <footer class="slide-foot"><span>Slide 7b / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 8 — RECOMMENDATION -->
<section class="slide scrollable">
  <div class="label">Slide 08 · Recommendation · 建议</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">Our</span> Recommendation</h2>
      <p class="body">We propose our original recommendation to AI-animate the entire sequence — here is our sample. We cut to various mid-shots, close-ups, and two-shots where we can insert performances. This ensures optimal character + environment + lighting integration. We work within the constraints of what AI can do for such a scene.</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">我们的</span>建议</h2>
      <p class="body">我们建议沿用最初的方案：将整段序列以 AI 动画方式生成——这是我们的样片。我们切到不同的中景、特写和双人镜头，在其中插入表演。这种方法能让角色、环境与灯光达到最佳融合，并在 AI 当前能力范围内最大化呈现效果。</p>
    </div>
  </div>
  <div class="vid-grid cols-3" style="margin-top: 28px;">
    <div class="placeholder-tile">Sample 1 · 样片 1</div>
    <div class="placeholder-tile">Sample 2 · 样片 2</div>
    <div class="placeholder-tile">Sample 3 · 样片 3</div>
  </div>
  <footer class="slide-foot"><span>Slide 8 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 9 — PROCESS · ASSETS -->
<section class="slide scrollable">
  <div class="label">Slide 09 · The Process · 工作流程</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">Step 1.</span> Creating Assets</h2>
      <p class="body subtle">Character orbits (face + voice training reference) + location plate.</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">第一步：</span>创建素材</h2>
      <p class="body subtle">角色环绕镜头（人脸+声音训练参考）+ 场景母板。</p>
    </div>
  </div>
  {char_refs_grid()}
  <footer class="slide-foot"><span>Slide 9 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 10 — PROCESS CONT'D -->
<section class="slide scrollable">
  <div class="label">Slide 10 · The Process (cont'd) · 工作流程（续）</div>
  <div class="bilingual">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h2 class="h2"><span class="gradient-text">Step 2 & 3.</span></h2>
      <div class="step-card">
        <span class="step-num">02</span>
        <h3 class="h3" style="display:inline; vertical-align:middle;">Creating the animation</h3>
        <p class="body" style="margin-top: 10px;">Generate underwater base sequences using composited assets + scene anchors.</p>
        <p class="body" style="margin-top: 8px; color: rgba(94,231,180,0.85);"><strong>Dear.AI acts as the AI DP &amp; Animator</strong> for the director — closer to a traditional animation workflow than a VFX one.</p>
      </div>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h2 class="h2"><span class="gradient-text">第二步与第三步</span></h2>
      <div class="step-card">
        <span class="step-num">02</span>
        <h3 class="h3" style="display:inline; vertical-align:middle;">生成动画</h3>
        <p class="body" style="margin-top: 10px;">利用合成的素材与场景锚点生成水下基础序列。</p>
        <p class="body" style="margin-top: 8px; color: rgba(94,231,180,0.85);"><strong>Dear.AI 担任导演的 AI 摄影指导与动画师</strong>——这更接近传统动画制作流程，而非特效后期。</p>
      </div>
    </div>
  </div>

  <!-- Step 2 flowchart -->
  <div class="flowchart">
    <div class="flow-node io-start">
      <div class="flow-node-num">01</div>
      <div class="flow-node-en">Script</div>
      <div class="flow-node-zh">剧本</div>
    </div>
    <div class="flow-node action">
      <div class="flow-node-num">02</div>
      <div class="flow-node-en">Dear.AI System</div>
      <div class="flow-node-zh">Dear.AI 系统</div>
    </div>
    <div class="flow-node">
      <div class="flow-node-num">03</div>
      <div class="flow-node-en">Storyboard</div>
      <div class="flow-node-zh">分镜稿</div>
    </div>
    <div class="flow-node action iterate">
      <div class="flow-node-num">04</div>
      <div class="flow-node-en">Director &amp; AI Artist iterate the scene</div>
      <div class="flow-node-zh">导演与 AI 艺术家共同打磨场景</div>
    </div>
    <div class="flow-node">
      <div class="flow-node-num">05</div>
      <div class="flow-node-en">Director confirms scene</div>
      <div class="flow-node-zh">导演确认场景</div>
    </div>
    <div class="flow-node io-end">
      <div class="flow-node-num">06</div>
      <div class="flow-node-en">Shoot the driving performances</div>
      <div class="flow-node-zh">拍摄驱动表演</div>
    </div>
  </div>
  <div class="flowchart-caption">Step 2 workflow · 第二步工作流程</div>

  <div class="bilingual">
    <div class="lang-en">
      <div class="step-card">
        <span class="step-num">03</span>
        <h3 class="h3" style="display:inline; vertical-align:middle;">Film driving performances and insert the acting</h3>
        <p class="body" style="margin-top: 10px;">Record clean blocking + dialogue takes; map them onto the AI underwater plates via motion transfer + lip-sync.</p>
      </div>
    </div>
    <div class="lang-zh">
      <div class="step-card">
        <span class="step-num">03</span>
        <h3 class="h3" style="display:inline; vertical-align:middle;">拍摄驱动表演，并植入演员表演</h3>
        <p class="body" style="margin-top: 10px;">录制干净的走位与对白镜头，通过动作迁移与对口型，将其叠加到 AI 生成的水下画面上。</p>
      </div>
    </div>
  </div>
  <footer class="slide-foot"><span>Slide 10 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- SLIDE 11 — THANK YOU -->
<section class="slide title-slide">
  <div class="bilingual" style="text-align:center;">
    <div class="lang-en">
      <span class="lang-tag">EN</span>
      <h1 class="h1"><span class="gradient-text">Thank You</span></h1>
      <p class="body">Dear.AI · raymus@dearai.com</p>
    </div>
    <div class="lang-zh">
      <span class="lang-tag">中文</span>
      <h1 class="h1"><span class="gradient-text">谢谢</span></h1>
      <p class="body">Dear.AI · raymus@dearai.com</p>
    </div>
  </div>
  <footer class="slide-foot"><span>Slide 11 / 11</span><span>Dear.AI</span></footer>
</section>

<!-- LIGHTBOX -->
<div id="lightbox" class="lightbox" onclick="closeLightbox(event)">
  <div class="lightbox-inner" onclick="event.stopPropagation()">
    <button class="lightbox-close" onclick="closeLightbox({{target:{{id:'lightbox'}}}})">×</button>
    <iframe id="lightbox-frame" allow="autoplay; fullscreen" allowfullscreen></iframe>
  </div>
</div>

<script>{JS}</script>
</body>
</html>
"""

OUT.write_text(HTML)
print(f"✓ wrote {OUT}")
print(f"  size: {OUT.stat().st_size/1024:.1f}KB")

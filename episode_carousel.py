"""Build a recap carousel for PocketShow microdramas.

v2 changes:
  • Whisper-aligns each dialogue line → exact timestamp (line-start frame)
  • Per-episode overrides JSON (text edits, manual timestamps, image swaps)
  • Bahasa CTA "tonton serialnya" on end card

Usage:
    python3 episode_carousel.py <episode_id>

Where <episode_id> matches a folder under Social Media Posts (Video)/10-shows/
   e.g.  aics-ep5  ·  mbiakm-ep3  ·  aics-ep7  ·  mbiakm-ep1
"""
from __future__ import annotations
import os, sys, re, subprocess, json, base64
from pathlib import Path

# Load .env
ENV_PATH = "/Users/raymuschang/Desktop/Shotlist Workflows/.env"
for line in open(ENV_PATH):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

ROOT = Path("/Users/raymuschang/Desktop/Social Media Calendar Pipelines")
SHOWS = ROOT / "Social Media Posts (Video)" / "10-shows"
LOGO = ROOT / "Social Media Posts (Image)" / "Logos" / "PocketShow Logo.png"
OUT_ROOT = ROOT / "PocketShow" / "episode-carousels"
TRANS_CACHE = ROOT / "PocketShow" / "episode-carousels" / "_transcripts"
HANDLE = "@pocketshow.tv"
N_DIALOGUE = 4

# ─────────────────────────── overrides ───────────────────────────
# Per-episode manual overrides applied AFTER auto Whisper alignment.
#   text:        replace EN+ID at a panel index (1-based)
#   manual_ts:   override timestamp at a panel index (seconds) — extracts still here
#   swap:        list of (from, to) panel-pair swaps applied to stills (1-based)
#   add_panel:   append a panel at the end with custom timestamp + text
OVERRIDES: dict[str, dict] = {
    "aics-ep1": {
        # User: P1 = woman looking sad (new manual ts); P2 = current P4 image
        # Strategy: extract a sad-woman frame for new P1 + rotate stills so old P4 → P2
        "manual_ts": {1: 8.0},  # try near opening for sad-woman; tune later
        "swap": [(4, 2)],
    },
    "aics-ep2": {
        # P1 ↔ P2 swap + P3 dialogue text change
        "swap": [(1, 2)],
        "text": {
            3: {
                "en": "does the man who killed him know?",
                "id": "apakah pria yang membunuhnya tahu?",
            }
        },
    },
    "aics-ep3": {
        # P1 ↔ P2 swap; P3+P4 should be "the guy in blue"
        # Whisper alignment should land closer; mark for review
        "swap": [(1, 2)],
        # P3+P4 will be inspected post-Whisper; flag for manual retake if still off
    },
    "aics-ep4": {
        # No explicit overrides — Whisper alignment alone should fix
    },
    "aics-ep5": {
        # Rotation: 3→1, 4→2, 2→3, 1→4
        "rotate": [3, 4, 2, 1],  # new order of OLD panel indices (1-based)
    },
    "aics-ep6": {
        # P2 = dog running along road (manual ts)
        "manual_ts": {2: 18.0},  # tune; common dog-running shot mid-ep
    },
    "aics-ep7": {
        # P2 = dog licking couple's hand (manual ts); current P2 shifts to P3 → swap (2,3)
        "manual_ts": {2: 55.0},  # finale dog-licking moment (tune)
        "swap": [(2, 3)],
    },
    "mbiakm-ep1": {
        # P1 = single frame at 16.8s (was triptych — user simplified to 3rd image alone)
        # P2 = single frame at 24.2s
        # P3 = single frame at 27.2s
        "manual_ts": {1: 16.8, 2: 24.2, 3: 27.2},
    },
    "mbiakm-ep2": {},
    "mbiakm-ep3": {},
    "mbiakm-ep4": {},
}


# ─────────────────────────── helpers ───────────────────────────
def resolve_episode(eid: str) -> Path:
    matches = sorted(SHOWS.glob(f"*{eid}*"))
    if not matches:
        sys.exit(f"No episode folder matched '{eid}' under {SHOWS}")
    exact = [m for m in matches if m.name.endswith(f"_{eid}")]
    if exact:
        return exact[-1]
    return matches[-1]


def find_mp4(ep_dir: Path) -> Path:
    src = ep_dir / "00-source"
    cands = sorted(src.glob("*_original.mp4"))
    if cands:
        return cands[0]
    cands = sorted(src.glob("*.mp4"))
    if not cands:
        sys.exit(f"No MP4 in {src}")
    return cands[0]


def parse_dialogue(captions_path: Path) -> list[tuple[str, str]]:
    if not captions_path.exists():
        sys.exit(f"Captions not found: {captions_path}")
    txt = captions_path.read_text().strip()
    stanzas = [s.strip() for s in re.split(r"\n\s*\n", txt) if s.strip()]
    body = [s for s in stanzas if not s.lstrip().startswith("🎬") and not s.lstrip().startswith("#")]
    if len(body) < 2:
        sys.exit(f"Could not parse 2 bilingual stanzas from {captions_path}")
    bahasa = [ln.strip().lstrip('"').rstrip('"').rstrip(" 🌧️🧪") for ln in body[0].split("\n") if ln.strip()]
    english = [ln.strip().lstrip('"').rstrip('"') for ln in body[1].split("\n") if ln.strip()]
    return list(zip(english, bahasa))


def get_duration(mp4: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def whisper_transcribe(mp4: Path, lang: str = "id") -> list[dict]:
    """Return Whisper verbose_json segments. Cached per-MP4."""
    TRANS_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = TRANS_CACHE / f"{mp4.stem}_{lang}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())["segments"]

    # Compress to ogg/opus for speed/cost (Whisper accepts .ogg, not .opus)
    tmp_audio = Path(f"/tmp/{mp4.stem}.ogg")
    if not tmp_audio.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp4), "-vn", "-c:a", "libopus", "-b:a", "24k", "-ac", "1",
             str(tmp_audio)],
            check=True, capture_output=True,
        )

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    with open(tmp_audio, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=lang,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    data = result.model_dump() if hasattr(result, "model_dump") else result
    cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"   ↻ transcribed → {cache_path.name}")
    return data["segments"]


def normalize(s: str) -> str:
    return re.sub(r"[^\w\s]", " ", s.lower()).strip()


def best_segment_match(query_id: str, segments: list[dict]) -> dict | None:
    """Find the segment whose text best overlaps with the Bahasa query."""
    from difflib import SequenceMatcher
    q = normalize(query_id)
    if not q:
        return None
    q_words = set(q.split())
    best_score = 0.0
    best_seg = None
    for seg in segments:
        seg_text = normalize(seg["text"])
        if not seg_text:
            continue
        seg_words = set(seg_text.split())
        # Combo: word-overlap + sequence ratio
        if q_words and seg_words:
            jaccard = len(q_words & seg_words) / len(q_words | seg_words)
        else:
            jaccard = 0.0
        ratio = SequenceMatcher(None, q, seg_text).ratio()
        score = 0.65 * jaccard + 0.35 * ratio
        if score > best_score:
            best_score = score
            best_seg = seg
    return best_seg if best_score >= 0.15 else None


def align_timestamps(pairs: list[tuple[str, str]], segments: list[dict], duration: float) -> list[float]:
    """For each (EN, ID) pair, find the best segment match → use its start time.
    Falls back to even distribution for unmatched lines."""
    timestamps = []
    pad = duration * 0.05
    span = duration - 2 * pad
    for i, (en, id_) in enumerate(pairs):
        seg = best_segment_match(id_, segments)
        if seg:
            timestamps.append(max(0.5, float(seg["start"])))
        else:
            fallback = pad + (i + 0.5) * span / len(pairs)
            timestamps.append(fallback)
            print(f"   ⚠ no Whisper match for '{id_[:40]}…' → fallback {fallback:.1f}s")
    return timestamps


def extract_still(mp4: Path, t: float, out_path: Path) -> Path:
    vf = "scale=1080:-2,crop=1080:1350"
    cmd = [
        "ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(mp4),
        "-frames:v", "1", "-vf", vf, "-q:v", "2", str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def extract_composite_triptych(mp4: Path, timestamps: list[float], out_path: Path) -> Path:
    """Extract N stills, slice each into a vertical strip, concat into one 1080x1350 frame.

    Each strip = 1080/N px wide × 1350 tall, taken from center of source frame.
    """
    from PIL import Image
    n = len(timestamps)
    strip_w = 1080 // n
    full_w = strip_w * n
    out_img = Image.new("RGB", (full_w, 1350))
    for i, t in enumerate(timestamps):
        # Extract full 1080x1350 frame to a temp file
        tmp = out_path.with_name(f".{out_path.stem}_strip{i}.jpg")
        extract_still(mp4, t, tmp)
        im = Image.open(tmp)
        # Center-crop a strip_w slice from the middle
        left = (im.width - strip_w) // 2
        strip = im.crop((left, 0, left + strip_w, im.height))
        out_img.paste(strip, (i * strip_w, 0))
        tmp.unlink()
    out_img.save(out_path, quality=92)
    return out_path


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def logo_data_url() -> str:
    b64 = base64.b64encode(LOGO.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"


# ─────────────────────────── HTML chassis ───────────────────────────
HTML_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Inter', sans-serif; background: #1a1a1a; color: #e5e5e5; padding: 32px; }}
  h1 {{ font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 32px; margin-bottom: 6px; }}
  .meta {{ color: #999; font-size: 13px; margin-bottom: 24px; }}
  .reel {{ display: flex; gap: 14px; overflow-x: auto; padding: 8px 4px 14px; scroll-snap-type: x mandatory; }}
  .panel {{
    flex: 0 0 auto; width: 360px; height: 450px; position: relative;
    border-radius: 4px; overflow: hidden; scroll-snap-align: start;
    box-shadow: 0 8px 28px rgba(0,0,0,0.5);
  }}
  .panel-bg {{ position: absolute; inset: 0; background-size: cover; background-position: center; }}
  .panel-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.0) 30%, rgba(0,0,0,0.0) 55%, rgba(0,0,0,0.5) 100%);
  }}
  .top-stack {{
    position: absolute; top: 14px; left: 14px; z-index: 3;
    display: flex; align-items: center; gap: 8px;
  }}
  .logo {{ width: 28px; height: 28px; background: #000; border-radius: 6px; padding: 3px; }}
  .logo img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
  .recap-pill {{
    background: #1D6F73; color: #F0EBDF;
    font-family: 'Space Grotesk', sans-serif; font-weight: 700;
    font-size: 11px; padding: 5px 10px; border-radius: 12px;
    letter-spacing: 0.12em; text-transform: uppercase;
  }}
  .recap-pill .slash {{ opacity: 0.55; margin: 0 5px; font-weight: 500; }}
  .dialogue-box {{
    position: absolute; left: 7%; right: 7%; bottom: 14%;
    background: #F0EBDF; padding: 14px 16px; border-radius: 4px;
    z-index: 2;
  }}
  .dialogue-en {{
    font-family: 'Inter', sans-serif; font-weight: 600;
    font-size: 17px; line-height: 1.22; color: #1A1611;
  }}
  .dialogue-id {{
    font-family: 'Inter', sans-serif; font-style: italic; font-weight: 500;
    font-size: 13.5px; line-height: 1.25; color: #8C6A30;
    margin-top: 6px;
  }}
  .pos-bar {{
    position: absolute; bottom: 4%; left: 50%; transform: translateX(-50%);
    z-index: 3; display: flex; align-items: center; gap: 6px;
    width: 50%; justify-content: center;
  }}
  .pos-counter {{
    font-family: 'Space Grotesk', sans-serif; font-style: italic;
    font-weight: 700; font-size: 11px; color: #F0EBDF;
    letter-spacing: 0.05em;
  }}
  .pos-track {{ display: flex; gap: 3px; flex: 1; max-width: 130px; }}
  .pos-seg {{ flex: 1; height: 2px; background: rgba(240,235,223,0.35); border-radius: 1px; }}
  .pos-seg.on {{ background: #F0EBDF; }}
  .panel.cta {{ background: #C5D5BA; }}
  .panel.cta .panel-bg, .panel.cta .panel-overlay {{ display: none; }}
  .cta-content {{
    position: absolute; inset: 0;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 7%; text-align: center;
  }}
  .cta-watch {{
    font-family: 'Space Grotesk', sans-serif; font-weight: 700;
    font-size: 38px; line-height: 1.05; color: #1A1611;
    letter-spacing: -0.01em;
  }}
  .cta-watch-id {{
    font-family: 'Inter', sans-serif; font-style: italic; font-weight: 500;
    font-size: 18px; line-height: 1.1; color: #1A1611;
    margin-top: 6px; opacity: 0.78;
  }}
  .cta-handle {{
    font-family: 'Space Grotesk', sans-serif; font-weight: 700;
    font-size: 30px; color: #E89047; margin-top: 14px;
    letter-spacing: -0.01em;
  }}
  .cta-platforms {{
    font-family: 'Inter', sans-serif; font-size: 12px; color: #1A1611;
    margin-top: 18px; opacity: 0.7; letter-spacing: 0.1em;
    text-transform: uppercase;
  }}
  .panel.cta .pos-counter {{ color: #1A1611; }}
  .panel.cta .pos-seg {{ background: rgba(26,22,17,0.30); }}
  .panel.cta .pos-seg.on {{ background: #1A1611; }}
</style></head><body>
<h1>{title}</h1>
<p class="meta">{n_panels} panels · {handle} · PocketShow recap · Whisper-aligned</p>
<div class="reel">
"""

HTML_TAIL = "</div></body></html>"


def render_panel(idx, total, still_url, en, id_, logo_data_url):
    segs = "".join(f'<div class="pos-seg{" on" if k <= idx else ""}"></div>' for k in range(total))
    return f"""<div class="panel">
  <div class="panel-bg" style="background-image:url('{still_url}');"></div>
  <div class="panel-overlay"></div>
  <div class="top-stack">
    <div class="logo"><img src="{logo_data_url}" alt="PocketShow"></div>
    <div class="recap-pill">Recap<span class="slash">/</span>Rekap</div>
  </div>
  <div class="dialogue-box">
    <div class="dialogue-en">{html_escape(en)}</div>
    <div class="dialogue-id">{html_escape(id_)}</div>
  </div>
  <div class="pos-bar">
    <div class="pos-counter">{idx+1:02d} / {total:02d}</div>
    <div class="pos-track">{segs}</div>
  </div>
</div>"""


def render_cta(idx, total, logo_data_url):
    segs = "".join(f'<div class="pos-seg{" on" if k <= idx else ""}"></div>' for k in range(total))
    return f"""<div class="panel cta">
  <div class="top-stack">
    <div class="logo"><img src="{logo_data_url}" alt="PocketShow"></div>
    <div class="recap-pill">Recap<span class="slash">/</span>Rekap</div>
  </div>
  <div class="cta-content">
    <div class="cta-watch">watch the series</div>
    <div class="cta-watch-id">tonton serialnya</div>
    <div class="cta-handle">{HANDLE}</div>
    <div class="cta-platforms">TikTok · YouTube · Instagram</div>
  </div>
  <div class="pos-bar">
    <div class="pos-counter">{idx+1:02d} / {total:02d}</div>
    <div class="pos-track">{segs}</div>
  </div>
</div>"""


# ─────────────────────────── main ───────────────────────────
def main(eid: str):
    ep_dir = resolve_episode(eid)
    mp4 = find_mp4(ep_dir)
    captions = ep_dir / "03-captions" / "tiktok_pocketshow.txt"

    pairs = parse_dialogue(captions)[:N_DIALOGUE]
    duration = get_duration(mp4)

    out_dir = OUT_ROOT / ep_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n■ Episode: {ep_dir.name}")
    print(f"  MP4:      {mp4.name}  ({duration:.1f}s)")
    print(f"  Pairs:    {len(pairs)} bilingual")
    print(f"  Output:   {out_dir}")

    # Whisper align
    print(f"   · whispering ...")
    try:
        segments = whisper_transcribe(mp4, lang="id")
        timestamps = align_timestamps(pairs, segments, duration)
    except Exception as e:
        print(f"   ✗ whisper failed: {e}, falling back to even distribution")
        pad = duration * 0.08
        span = duration - 2 * pad
        timestamps = [pad + (i + 0.5) * span / len(pairs) for i in range(len(pairs))]

    # Per-episode overrides
    ov = OVERRIDES.get(eid, {})

    # text overrides
    if "text" in ov:
        for panel_1based, t in ov["text"].items():
            i = panel_1based - 1
            if 0 <= i < len(pairs):
                pairs[i] = (t["en"], t["id"])
                print(f"   ✎ text override on P{panel_1based}: '{t['en']}'")

    # manual_ts overrides
    if "manual_ts" in ov:
        for panel_1based, t in ov["manual_ts"].items():
            i = panel_1based - 1
            if 0 <= i < len(timestamps):
                timestamps[i] = t
                print(f"   ⏱ manual timestamp on P{panel_1based}: {t:.1f}s")

    # Extract stills (one per pair, at aligned timestamps)
    composite_map = ov.get("composite", {})
    stills = []
    for i, t in enumerate(timestamps, 1):
        out = out_dir / f"still_{i:02d}.jpg"
        if i in composite_map:
            ts_list = composite_map[i]
            extract_composite_triptych(mp4, ts_list, out)
            print(f"   🎞 still_{i:02d}.jpg = composite of {ts_list}  ←  \"{pairs[i-1][0][:46]}…\"")
        else:
            extract_still(mp4, t, out)
            print(f"   📷 still_{i:02d}.jpg @ {t:.1f}s  ←  \"{pairs[i-1][0][:46]}…\"")
        stills.append(out)

    # swap overrides (operate on stills, not pairs)
    if "swap" in ov:
        for a, b in ov["swap"]:
            ai, bi = a-1, b-1
            stills[ai], stills[bi] = stills[bi], stills[ai]
            # Rename to preserve filenames on disk (swap file contents)
            tmp = stills[ai].with_suffix(".tmp.jpg")
            stills[ai].rename(tmp)
            stills[bi].rename(stills[ai].with_name(f"still_{a:02d}.jpg"))
            tmp.rename(stills[bi].with_name(f"still_{b:02d}.jpg"))
            stills[ai] = stills[ai].with_name(f"still_{a:02d}.jpg")
            stills[bi] = stills[bi].with_name(f"still_{b:02d}.jpg")
            print(f"   ↔ swapped stills P{a} ↔ P{b}")

    # rotate override: new order [r1, r2, r3, r4] means new P1 = old P[r1], etc.
    if "rotate" in ov:
        # Operate on stills array via copies, then rewrite to disk
        order = ov["rotate"]  # 1-based old indices
        rotated_pairs = [pairs[o-1] for o in order]
        # rename: copy old still file contents into new naming
        import shutil
        tmp_dir = out_dir / "_rotate_tmp"
        tmp_dir.mkdir(exist_ok=True)
        for new_i, old_i in enumerate(order, 1):
            shutil.copy(stills[old_i-1], tmp_dir / f"still_{new_i:02d}.jpg")
        for new_i in range(1, len(order)+1):
            src = tmp_dir / f"still_{new_i:02d}.jpg"
            dst = out_dir / f"still_{new_i:02d}.jpg"
            shutil.move(str(src), str(dst))
        tmp_dir.rmdir()
        stills = [out_dir / f"still_{i+1:02d}.jpg" for i in range(len(order))]
        pairs = rotated_pairs
        print(f"   ↻ rotated: new order = {order}")

    # Render
    total = len(pairs) + 1
    logo_url = logo_data_url()
    title = ep_dir.name.replace("_", " · ").upper()

    html = [HTML_HEAD.format(title=title, n_panels=total, handle=HANDLE)]
    for i, (still, (en, id_)) in enumerate(zip(stills, pairs)):
        html.append(render_panel(i, total, still.name, en, id_, logo_url))
    html.append(render_cta(total - 1, total, logo_url))
    html.append(HTML_TAIL)

    index_path = out_dir / "index.html"
    index_path.write_text("\n".join(html))
    print(f"   ✓ wrote {index_path.name}")

    # Save meta
    meta = {
        "episode": ep_dir.name,
        "mp4": str(mp4),
        "duration": duration,
        "panels": [
            {"idx": i + 1, "timestamp": ts, "en": en, "id": id_, "still": str(stills[i])}
            for i, (ts, (en, id_)) in enumerate(zip(timestamps, pairs))
        ],
        "overrides": ov,
    }
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return index_path


# ─────────────────────────── PICK MODE ───────────────────────────
def build_contact_sheet(mp4: Path, duration: float, out_dir: Path, step: float = 1.5) -> list[tuple[float, Path]]:
    """Extract small thumbnails every `step` seconds for the picker."""
    thumbs_dir = out_dir / "_thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    n = int(duration / step) + 1
    frames = []
    for i in range(n):
        t = round(i * step + 0.25, 2)
        if t >= duration:
            break
        out = thumbs_dir / f"t_{t:06.2f}.jpg"
        if not out.exists():
            subprocess.run([
                "ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(mp4),
                "-frames:v", "1", "-vf", "scale=180:-2", "-q:v", "5", str(out),
            ], check=True, capture_output=True)
        frames.append((t, out))
    return frames


def build_picker_html(pairs, frames, ep_dir_name: str, port: int) -> str:
    rel_thumbs = "_thumbs/"
    panels_html = []
    for i, (en, id_) in enumerate(pairs):
        thumb_buttons = "".join([
            f'<button class="thumb" data-panel="{i}" data-ts="{t:.2f}" style="background-image:url(\'{rel_thumbs}{p.name}\');"><span>{t:.1f}s</span></button>'
            for t, p in frames
        ])
        panels_html.append(f'''
<section class="panel-row">
  <div class="dlg">
    <div class="num">P{i+1}</div>
    <div class="text">
      <div class="en">{html_escape(en)}</div>
      <div class="id">{html_escape(id_)}</div>
    </div>
    <div class="pick-status" id="status-{i}">Not picked</div>
  </div>
  <div class="thumbs">{thumb_buttons}</div>
</section>''')
    body = "\n".join(panels_html)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Pick frames · {ep_dir_name}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',sans-serif;background:#0f0f0f;color:#eee;padding:24px}}
h1{{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:24px}}
.meta{{color:#888;font-size:13px;margin-bottom:24px}}
.panel-row{{background:#1a1a1a;padding:16px;border-radius:8px;margin-bottom:18px}}
.dlg{{display:flex;align-items:center;gap:14px;margin-bottom:10px}}
.num{{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:22px;color:#E89047;width:42px;flex-shrink:0}}
.text{{flex:1}}
.text .en{{font-weight:600;font-size:16px;color:#fff}}
.text .id{{font-style:italic;font-size:13px;color:#999;margin-top:3px}}
.pick-status{{padding:6px 12px;border-radius:14px;background:#333;font-size:12px;color:#999;white-space:nowrap}}
.pick-status.picked{{background:#1D6F73;color:#F0EBDF;font-weight:600}}
.thumbs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px;max-height:380px;overflow-y:auto;padding:4px;background:#0a0a0a;border-radius:4px}}
.thumb{{position:relative;aspect-ratio:9/16;background-size:cover;background-position:center;border:2px solid transparent;border-radius:3px;cursor:pointer;transition:transform .12s,border-color .12s;padding:0;outline:none}}
.thumb:hover{{transform:scale(1.04);border-color:#666}}
.thumb.selected{{border-color:#E89047;box-shadow:0 0 0 3px rgba(232,144,71,0.4);transform:scale(1.04)}}
.thumb span{{position:absolute;bottom:2px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.75);color:#fff;font-size:10px;font-weight:600;padding:2px 6px;border-radius:2px;font-family:'Space Grotesk',sans-serif}}
.bar{{position:sticky;bottom:16px;display:flex;gap:12px;align-items:center;background:#1a1a1a;padding:14px 18px;border-radius:8px;box-shadow:0 -4px 18px rgba(0,0,0,0.5);margin-top:24px}}
.bar .progress{{flex:1;color:#999;font-size:13px}}
.bar button{{background:#E89047;color:#1a1611;border:0;padding:12px 22px;border-radius:6px;font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:14px;cursor:pointer}}
.bar button:disabled{{background:#444;color:#888;cursor:not-allowed}}
</style></head><body>
<h1>Pick frames · {ep_dir_name}</h1>
<p class="meta">Click one thumbnail per dialogue line. Then hit <b>Build Carousel</b>.</p>
{body}
<div class="bar">
  <div class="progress" id="progress">0 of {len(pairs)} picked</div>
  <button id="submit" disabled>Build Carousel</button>
</div>
<script>
const total = {len(pairs)};
const picks = {{}};
document.querySelectorAll('.thumb').forEach(btn => {{
  btn.addEventListener('click', e => {{
    const panel = parseInt(btn.dataset.panel);
    const ts = parseFloat(btn.dataset.ts);
    // deselect siblings
    document.querySelectorAll(`.thumb[data-panel="${{panel}}"]`).forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    picks[panel] = ts;
    const status = document.getElementById('status-' + panel);
    status.textContent = '✓ ' + ts.toFixed(1) + 's';
    status.classList.add('picked');
    const n = Object.keys(picks).length;
    document.getElementById('progress').textContent = n + ' of ' + total + ' picked';
    document.getElementById('submit').disabled = (n < total);
  }});
}});
document.getElementById('submit').addEventListener('click', async () => {{
  document.getElementById('submit').textContent = 'Building...';
  document.getElementById('submit').disabled = true;
  const res = await fetch('http://localhost:{port}/submit', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(picks)
  }});
  const txt = await res.text();
  document.body.innerHTML = '<h1>Done</h1><pre style="background:#1a1a1a;padding:18px;border-radius:8px;color:#9DCB7F;font-size:13px;line-height:1.6;white-space:pre-wrap">' + txt + '</pre>';
}});
</script>
</body></html>"""


def run_pick_mode(eid: str):
    import http.server, socketserver, threading, webbrowser, time

    ep_dir = resolve_episode(eid)
    mp4 = find_mp4(ep_dir)
    captions = ep_dir / "03-captions" / "tiktok_pocketshow.txt"
    pairs = parse_dialogue(captions)[:N_DIALOGUE]
    duration = get_duration(mp4)
    out_dir = OUT_ROOT / ep_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n■ PICK MODE · {ep_dir.name}")
    print(f"  Building contact sheet ({duration:.0f}s @ 1.5s step)...")
    frames = build_contact_sheet(mp4, duration, out_dir, step=1.5)
    print(f"  ✓ {len(frames)} thumbs in _thumbs/")

    PORT = 7878
    picker_html = build_picker_html(pairs, frames, ep_dir.name, PORT)
    picker_path = out_dir / "_picker.html"
    picker_path.write_text(picker_html)

    picks_received = {}
    done_event = threading.Event()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(out_dir), **kw)
        def log_message(self, *a, **kw):
            pass
        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
        def do_POST(self):
            if self.path == "/submit":
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length).decode())
                picks_received.update(data)
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                msg = "Picks received.\n\n" + "\n".join(
                    f"  P{int(k)+1} → {v:.2f}s" for k, v in sorted(picks_received.items(), key=lambda x: int(x[0]))
                ) + "\n\nBuilding carousel — check the terminal."
                self.wfile.write(msg.encode())
                done_event.set()
            else:
                self.send_error(404)

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("localhost", PORT), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Cache-bust with timestamp so the browser always pulls a fresh picker page
    cache_bust = int(time.time())
    url = f"http://localhost:{PORT}/_picker.html?v={cache_bust}"
    print(f"  ↗ opening picker: {url}")
    webbrowser.open(url)
    print(f"  ⏳ waiting for your picks (browser tab)...")
    done_event.wait()
    server.shutdown()
    time.sleep(0.3)

    # Convert string keys to int panel indices and apply as manual_ts
    manual_ts = {int(k) + 1: float(v) for k, v in picks_received.items()}
    print(f"  ✓ received picks: {manual_ts}")

    # Inject into OVERRIDES dict in-memory.
    # In --pick mode, the user picked the EXACT frame they want per panel.
    # Strip pre-existing swap/rotate (those were guesses) — keep text edits only.
    existing = OVERRIDES.get(eid, {}).copy()
    existing.pop("swap", None)
    existing.pop("rotate", None)
    existing["manual_ts"] = manual_ts
    OVERRIDES[eid] = existing
    print(f"  ℹ pre-existing swap/rotate overrides cleared — picks are source of truth")

    # Run normal build flow
    main(eid)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 episode_carousel.py <episode_id> [--pick]")
    args = sys.argv[1:]
    eid = args[0]
    if "--pick" in args:
        run_pick_mode(eid)
    else:
        main(eid)

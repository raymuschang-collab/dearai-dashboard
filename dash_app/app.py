#!/usr/bin/env python3
"""
DearAI Production Dashboard — Plotly Dash UI mirroring pharaoh_king_gallery_PRODUCTION_v2.html.

Tabs:
  Overview      — episode stats, BytePlus spend, recent jobs
  Storyboards   — set-by-set: SB iters | prompt body | video iters (live from sheet)
  Characters    — bible cards (CHARACTERS tab)
  Locations     — bible cards with shot-size variants (LOCATIONS tab)
  Costumes      — bible cards (COSTUME tab)
  Props         — bible cards (PROPS tab)
  Effects       — bible cards (EFFECTS tab)
  Vidgen        — fire BytePlus vidgen (text-only until asset library IAM unblocks)
  Asset Library — read-only Asset Library tab status
  Expense       — full ledger from .byteplus_expense.json

Run:
  cd "/Users/raymuschang/Desktop/Shotlist Workflows" && python3 dash_app/app.py
  → http://localhost:8050
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _data_hash(d) -> str:
    """Stable short hash for a dict — used to detect bible-card content drift."""
    try:
        return hashlib.md5(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:12]
    except Exception:
        return ""

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))


def _bootstrap_higgs_credentials():
    """Materialize ~/.config/higgsfield/credentials.json from the
    HIGGSFIELD_CREDENTIALS_JSON env var, so the Higgsfield CLI shells
    fired by storyboard_generate.py / character_generate.py / higgs_gen.py
    can authenticate on Render's ephemeral filesystem.

    No-op locally: when the env var is unset (dev machines), the file
    written by `higgs auth login` already exists and is left alone.

    Idempotent — only writes if the file is missing or out of sync."""
    creds_json = os.environ.get("HIGGSFIELD_CREDENTIALS_JSON", "").strip()
    if not creds_json:
        return
    try:
        json.loads(creds_json)  # validate shape before writing
    except json.JSONDecodeError as e:
        print(f"[bootstrap] HIGGSFIELD_CREDENTIALS_JSON is set but not valid JSON: {e}")
        return
    creds_dir = Path.home() / ".config" / "higgsfield"
    creds_file = creds_dir / "credentials.json"
    try:
        if creds_file.exists() and creds_file.read_text().strip() == creds_json:
            return  # already in sync
        creds_dir.mkdir(parents=True, exist_ok=True)
        creds_file.write_text(creds_json)
        creds_file.chmod(0o600)
        print(f"[bootstrap] wrote Higgsfield credentials to {creds_file}")
    except Exception as e:
        print(f"[bootstrap] failed to write Higgsfield credentials: {e}")


_bootstrap_higgs_credentials()


import dash
from dash import Dash, dcc, html, Input, Output, State, no_update, dash_table, ALL, MATCH
import plotly.graph_objects as go

import bible_reader as br

EXPENSE_LOG = PROJECT_ROOT / ".byteplus_expense.json"
JOBS_LOG = PROJECT_ROOT / ".dash_jobs.json"
PYTHON_BIN = sys.executable

# ===== Series config =====================================================
# One dashboard = one series. Within a series, multiple episodes.
# To deploy a different series: set env var SERIES=<slug> at runtime.
# Add episodes to a series as new sheets ship.
SERIES_CONFIG = {
    "sajangnim": {
        "name": "Diam Diam Aku Cinta Sajangnim",
        # Bibles are SHOW-LEVEL — same characters, props, locations across all episodes.
        # All bible tabs read from this one sheet regardless of which episode is active.
        "bible_sheet": "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc",
        "episodes": {
            "Ep 1 — Pelarian Pertama": "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc",
            "Ep 2 — Garam Jadi Gula": "1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4",
            "Ep 3 — Kalau Aku Pergi (PAYWALL)": "10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I",
            "Ep 4 — Pukul Lima Pagi": "1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4",
            "Ep 5 — Mata yang Mengamati": "1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg",
            "Ep 6 — Sajangnim Sudah Tahu (FINALE)": "1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI",
        },
    },
    "pharaoh": {
        "name": "Strike! Pharaoh King",
        "bible_sheet": "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE",
        "episodes": {
            "Ep 1 — The Isfet Spawn": "1vYn7CjuaaaIE1UONwdfsS5ZLa0dPh8Dsl-bTY0dacTE",
        },
    },
    "ponsel": {
        "name": "Ponsel Itu",
        "bible_sheet": "1Egissfxhh6rB1GlMFuFJPtVz5J21p--_yuS2ggNN9fk",
        "episodes": {
            "Ep 2 — Dilacak": "1Egissfxhh6rB1GlMFuFJPtVz5J21p--_yuS2ggNN9fk",
        },
    },
    # Architecture probe — fresh sheet scaffolded by _create_blank_sot.py.
    # Used to verify that schemas + formulas + dashboard reads stay aligned
    # with bible/Shotlist/SP changes. Should render an empty dashboard with
    # all tabs working but zero rows.
    "blanktest": {
        "name": "TEST — Blank Architecture Probe",
        "bible_sheet": "1K2dpI-1VAd3UA4ag3jykkczsvlHqMUzXJXz-SJVK1gs",
        "episodes": {
            "Ep 1 — (blank)": "1K2dpI-1VAd3UA4ag3jykkczsvlHqMUzXJXz-SJVK1gs",
        },
    },
}
ACTIVE_SERIES = os.environ.get("SERIES", "sajangnim")
if ACTIVE_SERIES not in SERIES_CONFIG:
    print(f"⚠ unknown SERIES={ACTIVE_SERIES}, falling back to first defined")
    ACTIVE_SERIES = next(iter(SERIES_CONFIG))
SERIES = SERIES_CONFIG[ACTIVE_SERIES]
EPISODES = SERIES["episodes"]
DEFAULT_EPISODE_SHEET = next(iter(EPISODES.values()))
# Bible sheet defaults to the first episode if not set explicitly.
BIBLE_SHEET = SERIES.get("bible_sheet") or DEFAULT_EPISODE_SHEET


# -------- Shared helpers --------------------------------------------------
def load_expenses() -> dict:
    if not EXPENSE_LOG.exists():
        return {"entries": [], "cumulative_usd": 0.0}
    try:
        return json.loads(EXPENSE_LOG.read_text())
    except Exception:
        return {"entries": [], "cumulative_usd": 0.0}


def load_jobs() -> dict:
    if not JOBS_LOG.exists():
        return {"jobs": []}
    try:
        return json.loads(JOBS_LOG.read_text())
    except Exception:
        return {"jobs": []}


def save_jobs(data: dict):
    JOBS_LOG.write_text(json.dumps(data, indent=2))


def append_job(job: dict):
    data = load_jobs()
    data["jobs"].insert(0, job)
    data["jobs"] = data["jobs"][:100]
    save_jobs(data)


def update_job(job_id: str, **fields):
    data = load_jobs()
    for j in data["jobs"]:
        if j.get("id") == job_id:
            j.update(fields)
            break
    save_jobs(data)


def fmt_ts(s) -> str:
    if isinstance(s, str):
        return s[:16].replace("T", " ")
    return "—"


def run_bg(cmd: list[str], job_id: str):
    update_job(job_id, status="running")
    try:
        proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        log_lines = []
        for line in proc.stdout:
            log_lines.append(line.rstrip())
            if len(log_lines) % 5 == 0:
                update_job(job_id, log="\n".join(log_lines[-100:]))
        proc.wait()
        update_job(job_id,
                   status="done" if proc.returncode == 0 else "failed",
                   log="\n".join(log_lines[-200:]),
                   ended=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        update_job(job_id, status="failed", log=str(e),
                   ended=datetime.now(timezone.utc).isoformat())


# -------- App init -------------------------------------------------------
app = Dash(__name__, title="DearAI — Production Dashboard",
           suppress_callback_exceptions=True)
# Exposed for gunicorn — Render's Procfile binds `dash_app.app:server`.
server = app.server


# Debug route — returns recent failed-job logs as JSON so production
# regressions can be diagnosed without shell access. Read-only, no auth
# required (the dashboard URL is already private to the team). Strip if
# you ever expose the URL beyond the team.
@server.route("/debug/jobs")
def _debug_jobs():
    from flask import jsonify, request
    n = int(request.args.get("n", 10))
    only = request.args.get("only", "failed")  # "failed" | "all"
    data = load_jobs()
    jobs = data.get("jobs", [])
    if only == "failed":
        jobs = [j for j in jobs if j.get("status") == "failed"]
    out = []
    for j in jobs[:n]:
        out.append({
            "id": j.get("id"),
            "kind": j.get("kind"),
            "label": j.get("label"),
            "status": j.get("status"),
            "started": j.get("started"),
            "ended": j.get("ended"),
            "cmd": j.get("cmd"),
            "log": j.get("log") or "",
        })
    return jsonify({"count": len(out), "jobs": out})


# Live galleries — known names → (sheet_id, show, episode_title).
# Adding a new ep = one line here + push. /gallery/<name> reads this map and
# builds the HTML on demand from the SOT (5-min in-memory cache for speed).
GALLERY_REGISTRY = {
    "sajangnim_ep01": (
        "1iygU-7XAwhVKykkTYXHAqwBh0wD1d7Zk2s6OGfnLXCc",
        "Diam Diam Aku Cinta Sajangnim",
        "Episode 1 — Pelarian Pertama",
    ),
    "sajangnim_ep02": (
        "1DlnYVqa_6S4ogcaBEtjoWw5tBjrB7wPHjkMFPR5fad4",
        "Diam Diam Aku Cinta Sajangnim",
        "Episode 2 — Garam Jadi Gula",
    ),
    "sajangnim_ep03": (
        "10wcCajzknstf79pvUs9UuS28ayvVG7k_SPe8KLqyy9I",
        "Diam Diam Aku Cinta Sajangnim",
        "Episode 3 — Kalau Aku Pergi (PAYWALL)",
    ),
    "sajangnim_ep04": (
        "1khTYtHShiI1z0caqouZUQW3eZKnihScxIG7IQo3l3w4",
        "Diam Diam Aku Cinta Sajangnim",
        "Episode 4 — Pukul Lima Pagi",
    ),
    "sajangnim_ep05": (
        "1_lm-ztYiZKHODRzg0g_N3Ms6HC0Mb8WANjRblVWnnfg",
        "Diam Diam Aku Cinta Sajangnim",
        "Episode 5 — Mata yang Mengamati",
    ),
    "sajangnim_ep06": (
        "1ZIYUMH_o6PpN1-KDiEiBRT6NZcp1uO6EjEt7L13pQFI",
        "Diam Diam Aku Cinta Sajangnim",
        "Episode 6 — Sajangnim Sudah Tahu (FINALE)",
    ),
}

# In-memory cache for live galleries: name → (timestamp, html_string).
# 5-min TTL so rapid hits don't burn Sheets quota; team edit + refresh sees
# changes within 5 min (or hit /debug/refresh to force fresh).
_GALLERY_TTL = 300.0
_gallery_cache: dict = {}
_gallery_cache_lock = threading.Lock()


@server.route("/gallery/<name>")
def _gallery(name):
    """Live-build a review gallery from the SOT on demand.

    Lookup order:
      1. GALLERY_REGISTRY → live-build via build_gallery.build_html
         (5-min cache to absorb rapid hits)
      2. Static file fallback (e.g. sajangnim_ep01_gallery.html in repo root)
         for any name that's not in the registry.

    Errors during live build fall back to the static snapshot if it exists,
    or return a clear error page."""
    import time as _t
    from flask import send_file, abort, Response
    safe = "".join(c for c in name if c.isalnum() or c in "_-")

    # Live-build path
    if safe in GALLERY_REGISTRY:
        sheet_id, show, episode = GALLERY_REGISTRY[safe]
        now = _t.time()
        with _gallery_cache_lock:
            cached = _gallery_cache.get(safe)
            if cached and (now - cached[0]) < _GALLERY_TTL:
                return Response(cached[1], mimetype="text/html")
        # Build fresh
        try:
            from build_gallery import build_html
            html_doc = build_html(sheet_id, show, episode, verbose=False)
            with _gallery_cache_lock:
                _gallery_cache[safe] = (now, html_doc)
            return Response(html_doc, mimetype="text/html")
        except Exception as e:
            # Live build failed — try last-known cache value (even if expired)
            with _gallery_cache_lock:
                stale = _gallery_cache.get(safe)
            if stale:
                print(f"[gallery] live build failed for {safe} ({e}); serving stale cache ({(now - stale[0]) // 60:.0f} min old)")
                return Response(stale[1], mimetype="text/html")
            # No cache — try static fallback
            static_path = PROJECT_ROOT / f"{safe}_gallery.html"
            if static_path.exists():
                print(f"[gallery] live + cache failed for {safe}; serving static snapshot")
                return send_file(static_path, mimetype="text/html")
            return Response(
                f"<h1>Gallery error</h1><p>{name}: {e}</p>",
                status=500, mimetype="text/html",
            )

    # Static file fallback (for galleries not in registry)
    candidates = [
        PROJECT_ROOT / f"{safe}_gallery.html",
        PROJECT_ROOT / f"{safe}.html",
    ]
    for p in candidates:
        if p.exists():
            return send_file(p, mimetype="text/html")
    abort(404, description=f"No gallery found for {safe}. Available: " +
          ", ".join(GALLERY_REGISTRY.keys()))


@server.route("/api/storyboard", methods=["POST"])
def _api_storyboard():
    """Fire storyboard_generate.py for one set on the ep matched by 'gallery' name.
    Body: {"set": <N>, "gallery": "sajangnim_ep01"}.
    Returns {"ok": true, "job_id": "...", "message": "..."}.

    Uses the same storyboard_generate.py the dashboard subprocess buttons used.
    Higgsfield gpt_image_2 (chatgpt2) under the hood — pulls SP!C as the prompt
    (which already contains globals B1-B8 + the dynamic per-set body)."""
    from flask import request, jsonify
    body = request.get_json(silent=True) or {}
    set_n = body.get("set")
    gallery = body.get("gallery", "")
    if not isinstance(set_n, int) or set_n < 1:
        return jsonify({"ok": False, "error": "missing or invalid 'set'"}), 400
    if gallery not in GALLERY_REGISTRY:
        return jsonify({"ok": False,
                         "error": f"unknown gallery '{gallery}'. Known: {list(GALLERY_REGISTRY)}"}), 400
    sheet_id, _show, _ep = GALLERY_REGISTRY[gallery]
    job_id = uuid.uuid4().hex[:8]
    cmd = [PYTHON_BIN, "storyboard_generate.py",
           "--sheet", sheet_id, "--set", str(set_n), "--force"]
    append_job({
        "id": job_id,
        "label": f"sb-gen {gallery} set{set_n}",
        "status": "queued",
        "started": datetime.now(timezone.utc).isoformat(),
        "log": "",
        "cmd": " ".join(cmd),
        "kind": "storyboard",
        "set": set_n,
        "sheet": sheet_id,
    })
    threading.Thread(target=run_bg, args=(cmd, job_id), daemon=True).start()
    return jsonify({
        "ok": True,
        "job_id": job_id,
        "message": f"Queued storyboard gen for {gallery} set {set_n}; check Drive in ~5 min."
    })


@server.route("/gallery/<name>/refresh")
def _gallery_refresh(name):
    """Force-flush the cached HTML for a single gallery. Use after sheet edits
    if 5-min TTL is too slow. Just hit the URL once; redirect back to gallery."""
    from flask import redirect
    safe = "".join(c for c in name if c.isalnum() or c in "_-")
    with _gallery_cache_lock:
        _gallery_cache.pop(safe, None)
    return redirect(f"/gallery/{safe}", code=302)


@server.route("/debug/refresh")
def _debug_refresh():
    """Flush all bible_reader caches without needing the dashboard ↻ button.
    Use when sheet edits aren't surfacing because of the 10-min TTL."""
    from flask import jsonify
    br.invalidate_all_caches()
    return jsonify({"ok": True, "msg": "all bible_reader caches invalidated"})


@server.route("/debug/higgs")
def _debug_higgs():
    """Run `higgs auth token` and `higgs version` and report exit codes +
    output. Use this to figure out why the CLI auth check fails for
    storyboard / bible regen subprocesses even when credentials.json
    is on disk."""
    from flask import jsonify
    import shutil
    import subprocess as _sp
    higgs = (
        os.environ.get("HIGGS_BIN")
        or shutil.which("higgs")
        or "/opt/render/project/src/.npm-global/bin/higgs"
    )
    out = {"higgs_bin": higgs, "exists": os.path.exists(higgs)}
    creds_path = Path.home() / ".config" / "higgsfield" / "credentials.json"
    out["creds_path"] = str(creds_path)
    out["creds_exists"] = creds_path.exists()
    if creds_path.exists():
        try:
            raw = creds_path.read_text().strip()
            out["creds_size"] = len(raw)
            out["creds_keys"] = list(json.loads(raw).keys())
        except Exception as e:
            out["creds_parse_err"] = str(e)
    if not out["exists"]:
        return jsonify(out)
    for cmd in (["version"], ["auth", "token"], ["workspace", "list"]):
        try:
            r = _sp.run([higgs, *cmd], capture_output=True, text=True, timeout=10)
            out[f"_higgs_{'_'.join(cmd)}"] = {
                "rc": r.returncode,
                "stdout": (r.stdout or "")[-400:],
                "stderr": (r.stderr or "")[-400:],
            }
        except Exception as e:
            out[f"_higgs_{'_'.join(cmd)}"] = {"err": str(e)}
    return jsonify(out)


@server.route("/debug/env")
def _debug_env():
    """Return non-secret env state so we can verify Render config drift —
    presence flags only, never the values themselves for keys that look
    like secrets."""
    from flask import jsonify
    SAFE_KEYS = {"SERIES", "PORT", "PYTHON_VERSION", "RENDER", "RENDER_SERVICE_NAME",
                 "HIGGS_BIN", "PATH"}
    out = {}
    for k, v in os.environ.items():
        if k in SAFE_KEYS:
            out[k] = v
        elif any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "JSON", "CREDENTIAL")):
            out[k] = f"<set, {len(v)} chars>" if v else "<empty>"
    # Probe every reasonable place the higgs binary might live + which-style
    # PATH lookup. With the build → runtime container split on Render, we
    # need to know which path actually has the binary at runtime.
    import shutil
    candidate_paths = [
        os.environ.get("HIGGS_BIN", ""),
        "/opt/render/project/src/.npm-global/bin/higgs",
        "/opt/render/project/src/node_modules/.bin/higgs",
        os.path.expanduser("~/npm-global/bin/higgs"),
        os.path.expanduser("~/.npm-global/bin/higgs"),
        os.path.expanduser("~/.local/bin/higgs"),
    ]
    out["_higgs_bin_candidates"] = {p: os.path.exists(p) for p in candidate_paths if p}
    out["_higgs_bin_on_path"] = shutil.which("higgs") or "<not on PATH>"
    out["_higgs_creds_exists"] = (Path.home() / ".config" / "higgsfield" / "credentials.json").exists()
    out["_home"] = str(Path.home())
    out["_python_executable"] = sys.executable
    # Also list /opt/render/project/src so we can see if .npm-global/ is even there
    try:
        out["_project_root_listing"] = sorted(os.listdir("/opt/render/project/src"))[:30]
    except Exception as e:
        out["_project_root_listing"] = f"err: {e}"
    return jsonify(out)
app.index_string = """<!DOCTYPE html>
<html><head>
<title>{%title%}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
{%favicon%}{%css%}
</head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""


# -------- UI helpers -----------------------------------------------------
def stat_card(label: str, value: str, sub: str = ""):
    children = [
        html.Div(label, className="label"),
        html.Div(value, className="value"),
    ]
    if sub:
        children.append(html.Div(sub, className="sub"))
    return html.Div(className="stat-card", children=children)


def hero():
    """Headline doubles as the episode picker — click it to reveal the menu."""
    default_label = next((l for l, s in EPISODES.items() if s == DEFAULT_EPISODE_SHEET),
                         next(iter(EPISODES)))
    full_title = f"{SERIES['name']} — {default_label}"
    return html.Header(className="hero", children=[
        html.Div("DearAI Production", className="show"),
        html.Details(className="hero-title-details", id="hero-details", children=[
            html.Summary(className="hero-title-summary", children=[
                html.H1(full_title, id="hero-title-text"),
                html.Span("▾", className="hero-caret"),
            ]),
            html.Div(className="episode-menu", children=[
                html.Button(label, n_clicks=0, className="episode-menu-item",
                            type="button",
                            id={"type": "ep-pick", "sheet": sid})
                for label, sid in EPISODES.items()
            ]),
        ]),
    ])


def episode_picker(component_id: str):
    return html.Div(className="form-row", children=[
        html.Div([
            html.Label("Episode"),
            dcc.Dropdown(
                id=component_id,
                options=[{"label": label, "value": sheet_id}
                         for label, sheet_id in EPISODES.items()],
                value=DEFAULT_EPISODE_SHEET,
                clearable=False, style={"minWidth": "320px"},
            ),
        ]),
    ])


# Backward-compat alias — older callbacks still call this name
sheet_picker = episode_picker


def img_cell(src: str, label: str = "", view_url: str = "", aspect: str = "16/9"):
    """Single image tile — clicking opens the inline lightbox (NOT Drive).

    `view_url` was previously used as an `<a target="_blank">` href; we now
    keep it as a fallback `data-href` so the lightbox can offer 'open in
    Drive' if the user wants the real file. The `zoomable` class is what
    `assets/zoom.js` wires to the lightbox overlay."""
    if not src:
        return html.Div(className="img-cell", style={"aspectRatio": aspect}, children=[
            html.Div("(none)", style={"color": "#a0a0a0", "fontStyle": "italic",
                                       "display": "flex", "alignItems": "center",
                                       "justifyContent": "center", "height": "100%"})
        ])
    # Note: Dash html.Img v4.1.0 doesn't expose `loading` kwarg, so we can't
    # use native lazy-load here. The smaller-thumb size (w=900) gives most of
    # the speed win anyway.
    img = html.Img(src=src, style={"width": "100%", "height": "100%",
                                   "objectFit": "cover", "display": "block"})
    return html.Div(className="img-cell zoomable",
                    style={"aspectRatio": aspect, "position": "relative",
                           "overflow": "hidden", "borderRadius": "8px",
                           "background": "#e3e3e3", "cursor": "zoom-in"},
                    **{"data-src": src, "data-href": view_url or "",
                       "data-kind": "image"},
                    children=[
        img,
        html.Div(label, style={
            "position": "absolute", "left": "8px", "bottom": "8px",
            "background": "#1a1a1a", "color": "#fff",
            "fontSize": "9px", "letterSpacing": "0.4px",
            "textTransform": "uppercase", "fontWeight": 600,
            "padding": "3px 8px", "borderRadius": "6px",
        }) if label else None,
    ])


def bible_card(item: dict, fields: list[tuple[str, str]] | None = None,
                regen_id: dict | None = None,
                regen_status_id: dict | None = None):
    """Generic bible card: image grid on top, body below."""
    iters = [i for i in (item.get("iters") or []) if i]
    cols = "1fr" if len(iters) <= 1 else "1fr 1fr"
    grid = html.Div(style={"display": "grid", "gridTemplateColumns": cols, "gap": "4px",
                           "background": "#e3e3e3"}, children=[
        img_cell(it.get("thumb", ""), it.get("label", ""), it.get("view", ""))
        for it in iters
    ]) if iters else html.Div(style={"aspectRatio": "16/9", "background": "#e3e3e3",
                                       "display": "flex", "alignItems": "center",
                                       "justifyContent": "center",
                                       "color": "#a0a0a0", "fontStyle": "italic"},
                              children="(no refs)")

    body_children = [html.H3(item.get("name", "—"))]
    if item.get("alias"):
        body_children.append(html.Div(item["alias"], style={
            "color": "#ff6b8a", "fontSize": "12px",
            "fontStyle": "italic", "marginBottom": "8px",
        }))

    chips = []
    for label, key in fields or []:
        if item.get(key):
            chips.append(html.Span(item[key], className="chip"))
    if chips:
        body_children.append(html.Div(className="meta", children=chips))

    desc = item.get("description") or item.get("personality") or ""
    if desc:
        body_children.append(html.Div(desc[:240] + ("…" if len(desc) > 240 else ""),
                                      style={"fontSize": "13px", "color": "#5a5a5a",
                                             "lineHeight": "1.5"}))

    # Regenerate button + status sit at the bottom of the card body
    if regen_id is not None:
        body_children.append(html.Div(style={
            "display": "flex", "alignItems": "center", "gap": "10px",
            "marginTop": "12px",
        }, children=[
            html.Button("↻ Regenerate", id=regen_id, type="button",
                         className="cta", style={
                             "fontSize": "10px", "padding": "6px 12px",
                         }),
            html.Span(id=regen_status_id, style={
                "fontSize": "10px", "color": "#a0a0a0",
                "letterSpacing": "0.2px",
            }),
        ]))

    return html.Div(className="card", style={"padding": 0, "overflow": "hidden"}, children=[
        grid,
        html.Div(body_children, style={"padding": "14px 18px 18px"}),
    ])


# -------- Tab renderers --------------------------------------------------
def render_overview():
    exp = load_expenses()
    jobs = load_jobs()
    by_label = {}
    for e in exp["entries"]:
        by_label[e.get("label", "—")] = by_label.get(e.get("label", "—"), 0) + e.get("estimated_usd", 0)

    fig = go.Figure(data=[go.Bar(
        x=list(by_label.keys())[:15], y=list(by_label.values())[:15],
        marker_color="#ff3b6b",
    )])
    fig.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                      height=260, margin=dict(l=20, r=20, t=20, b=40),
                      font=dict(family="Inter", size=11, color="#5a5a5a"),
                      xaxis=dict(showgrid=False),
                      yaxis=dict(gridcolor="#e3e3e3", title="USD"))

    return html.Div([
        html.Div(className="grid bible", children=[
            stat_card("Episodes", str(len(EPISODES))),
            stat_card("BytePlus gens", str(len(exp["entries"]))),
            stat_card("Cumulative spend", f"${exp['cumulative_usd']:.2f}",
                      f"{len(exp['entries'])} calls"),
            stat_card("Active jobs", str(sum(1 for j in jobs["jobs"] if j.get("status") == "running"))),
        ]),
        html.Div(className="card", children=[
            html.H3("Spend by label"),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ]),
        html.Div(className="card", children=[
            html.H3("Recent jobs"),
            html.Div(id="recent-jobs-list"),
        ]),
        dcc.Interval(id="overview-poll", interval=30000, n_intervals=0),
    ])


def render_storyboards():
    return html.Div([
        html.Div(id="sb-content"),
        dcc.Interval(id="sb-poll", interval=15000, n_intervals=0),
    ])


def render_characters():
    return html.Div(id="ch-content")


def render_locations():
    return html.Div(id="loc-content")


def render_costumes():
    return html.Div(id="cos-content")


def render_props():
    return html.Div(id="pr-content")


def render_effects():
    return html.Div(id="fx-content")


def render_vidgen():
    """History view of all video generation jobs (filtered to vidgen labels)."""
    return html.Div([
        html.Div(className="card", children=[
            html.H3("Video generations"),
            html.P([
                "All BytePlus video gens fired from the Storyboards tab land here. ",
                "Refresh on a 4-second loop. Generation buttons themselves live next to each video tile in ",
                html.B("Storyboards"), ".",
            ], style={"fontSize": "12px", "color": "#5a5a5a"}),
            html.Div(id="vg-history"),
        ]),
        dcc.Interval(id="vg-poll", interval=4000, n_intervals=0),
    ])


def render_assetlib():
    return html.Div(id="al-content")


def render_expense():
    exp = load_expenses()
    rows = exp["entries"][::-1]
    return html.Div([
        html.Div(className="grid bible", children=[
            stat_card("Total entries", str(len(rows))),
            stat_card("Cumulative", f"${exp['cumulative_usd']:.2f}"),
            stat_card("Avg / gen", f"${exp['cumulative_usd']/max(1,len(rows)):.2f}"),
        ]),
        html.Div(className="card", children=[
            html.H3("Ledger"),
            dash_table.DataTable(
                data=rows,
                columns=[{"name": c.replace("_", " "), "id": c}
                         for c in ["ts", "label", "model", "duration", "resolution",
                                   "estimated_usd", "task_id"]],
                style_cell={"fontFamily": "Inter, sans-serif", "fontSize": 12,
                            "padding": "8px 12px", "border": "1px solid #ededed"},
                style_header={"backgroundColor": "#e3e3e3", "fontWeight": 600,
                              "fontSize": 11, "textTransform": "uppercase"},
                style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#fbfbfb"}],
                page_size=20, sort_action="native", filter_action="native",
            ),
        ]),
    ])


# -------- Layout ---------------------------------------------------------
app.layout = html.Div(className="wrap", children=[
    # Sticky top: hero (with episode-as-headline) + tabs freeze together
    html.Div(className="sticky-top", children=[
        hero(),
        dcc.Store(id="active-sheet", data=DEFAULT_EPISODE_SHEET),
        html.Div(className="tabs-wrap", children=[
            html.Button("↻ Refresh", id="global-refresh", type="button",
                        className="cta refresh-btn"),
            dcc.Tabs(id="tabs", value="storyboards",
                 persistence="dearai-tabs-v1",
                 persistence_type="session",
                 persisted_props=["value"],
                 parent_className="tabs-container",
                 className="tabs-inner", children=[
            dcc.Tab(label="Overview", value="overview",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Storyboards", value="storyboards",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Characters", value="characters",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Locations", value="locations",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Costumes", value="costumes",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Props", value="props",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Effects", value="effects",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Video Generations", value="vidgen",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Asset Library", value="assetlib",
                    className="tab--single", selected_className="tab--selected"),
            dcc.Tab(label="Expense", value="expense",
                    className="tab--single", selected_className="tab--selected"),
            ]),  # closes dcc.Tabs.children
        ]),  # closes tabs-wrap.children
        # Two thin forest-green batch buttons just BELOW the tab row
        html.Div(className="bulk-row", children=[
            html.Button("⚡ Generate all pending storyboards",
                        id="bulk-gen-sb", type="button",
                        className="bulk-btn", n_clicks=0),
            html.Button("▶ Generate all pending videos",
                        id="bulk-gen-vid", type="button",
                        className="bulk-btn", n_clicks=0),
            html.Span(id="bulk-status", className="bulk-status"),
        ]),
    ]),  # closes sticky-top.children
    dcc.Store(id="refresh-tick", data=0),
    dcc.Interval(id="bulk-poll", interval=20000, n_intervals=0),
    html.Div(id="tab-content"),
])


@app.callback(Output("refresh-tick", "data"),
              Input("global-refresh", "n_clicks"),
              State("refresh-tick", "data"))
def _bump_refresh(_n, t):
    # Drop the storyboard cache so the next read pulls fresh sheet data.
    br.invalidate_storyboard_cache()
    return (t or 0) + 1


def _walk_pending_sets(sheet_id: str, kind: str) -> list[int] | list[tuple[int, int]]:
    """Return pending generation targets for the given kind.
    kind='storyboard' -> set numbers whose storyboard iter 1 is missing.
    kind='video' -> (set, slot) pairs whose matching storyboard exists but video is missing.
    """
    try:
        sets = br.read_storyboards(sheet_id, bible_sheet_id=BIBLE_SHEET)
    except Exception:
        return []
    out = []
    for s in sets:
        if kind == "storyboard":
            if not (s["sb_iters"] and s["sb_iters"][0]):
                out.append(s["set"])
        elif kind == "video":
            for slot in (1, 2):
                sb_iter = s["sb_iters"][slot - 1] if slot - 1 < len(s["sb_iters"]) else None
                video = s["videos"][slot - 1] if slot - 1 < len(s["videos"]) else None
                if sb_iter and not video:
                    out.append((s["set"], slot))
    return out


BULK_STATE = {"active": False, "kind": None, "total": 0,
              "done": 0, "failed": 0, "current": None,
              "started": None, "pending": []}


def _bulk_run(sheet_id: str, kind: str):
    """Fire per-set jobs SEQUENTIALLY — one runs to completion before the
    next starts. Avoids hitting Higgsfield + Sheets rate limits and gives
    a clean progress story."""
    pending = _walk_pending_sets(sheet_id, kind)
    BULK_STATE.update({
        "active": True, "kind": kind, "total": len(pending),
        "done": 0, "failed": 0, "current": None,
        "started": datetime.now(timezone.utc).isoformat(),
        "pending": list(pending),
    })
    for target in pending:
        if kind == "video":
            set_n, slot = target
            current_label = f"{set_n}/V{slot}"
        else:
            set_n = target
            slot = None
            current_label = str(set_n)
        BULK_STATE["current"] = current_label
        job_id = str(uuid.uuid4())[:8]
        if kind == "storyboard":
            cmd = [PYTHON_BIN, "storyboard_generate.py",
                   "--sheet", sheet_id, "--set", str(set_n), "--force"]
            label = f"sb-gen set{set_n}"
            kind_tag = "storyboard"
        else:
            cmd = [PYTHON_BIN, "byteplus_vidgen.py",
                   "--sheet", sheet_id, "--set", str(set_n), "--slot", str(slot),
                   "--resolution", "720p", "--duration", "15"]
            label = f"vidgen set{set_n} slot{slot}"
            kind_tag = "video"
        append_job({"id": job_id, "label": label, "status": "queued",
                    "started": datetime.now(timezone.utc).isoformat(),
                    "log": "", "cmd": " ".join(cmd), "kind": kind_tag,
                    "set": set_n, "slot": slot, "sheet": sheet_id})
        # Synchronous: blocks this thread until the per-set job completes
        run_bg(cmd, job_id)
        # Tally based on final job status
        last = next((j for j in load_jobs()["jobs"] if j["id"] == job_id), None)
        if last and last.get("status") == "done":
            BULK_STATE["done"] += 1
        else:
            BULK_STATE["failed"] += 1
    BULK_STATE["active"] = False
    BULK_STATE["current"] = None


@app.callback(Output("bulk-status", "children"),
              Input("bulk-gen-sb", "n_clicks"), Input("bulk-gen-vid", "n_clicks"),
              Input("bulk-poll", "n_intervals"),
              State("active-sheet", "data"),
              prevent_initial_call=True)
def fire_bulk(_n_sb, _n_vid, _tick, sheet_id):
    triggered = dash.callback_context.triggered_id
    # Live progress poll — render whatever BULK_STATE looks like
    if triggered == "bulk-poll":
        if not BULK_STATE["active"] and BULK_STATE["total"] == 0:
            return no_update
        failed_suffix = f" · {BULK_STATE['failed']} failed" if BULK_STATE['failed'] else ""
        if BULK_STATE["active"]:
            return (f"⚡ {BULK_STATE['kind']} bulk · "
                    f"set {BULK_STATE['current']} running · "
                    f"{BULK_STATE['done']}/{BULK_STATE['total']} done"
                    f"{failed_suffix}")
        return (f"✓ {BULK_STATE['kind']} bulk complete · "
                f"{BULK_STATE['done']}/{BULK_STATE['total']} done"
                f"{failed_suffix}")

    # Button click
    if not triggered or not sheet_id:
        return no_update
    if BULK_STATE["active"]:
        return f"⚠ a {BULK_STATE['kind']} bulk run is already in progress (set {BULK_STATE['current']}/{BULK_STATE['total']})"
    kind = "storyboard" if triggered == "bulk-gen-sb" else "video"
    pending = _walk_pending_sets(sheet_id, kind)
    if not pending:
        unit = "videos" if kind == "video" else "sets"
        return f"No pending {kind} {unit} to generate."
    threading.Thread(target=_bulk_run, args=(sheet_id, kind), daemon=True).start()
    unit = "videos" if kind == "video" else "sets"
    return f"⚡ Starting {kind} bulk run · {len(pending)} {unit} queued (sequential)"


@app.callback(
    Output("active-sheet", "data"),
    Output("hero-title-text", "children"),
    Output("hero-details", "open"),
    Input({"type": "ep-pick", "sheet": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def pick_episode(_clicks):
    triggered = dash.callback_context.triggered_id
    if not triggered or not isinstance(triggered, dict):
        return no_update, no_update, no_update
    sheet_id = triggered["sheet"]
    label = next((l for l, s in EPISODES.items() if s == sheet_id), "?")
    return sheet_id, f"{SERIES['name']} — {label}", False


# -------- Callbacks ------------------------------------------------------
@app.callback(Output("tab-content", "children"),
              Input("tabs", "value"), Input("refresh-tick", "data"))
def switch_tab(tab, _refresh_tick):
    return {
        "overview": render_overview,
        "storyboards": render_storyboards,
        "characters": render_characters,
        "locations": render_locations,
        "costumes": render_costumes,
        "props": render_props,
        "effects": render_effects,
        "vidgen": render_vidgen,
        "assetlib": render_assetlib,
        "expense": render_expense,
    }.get(tab, render_overview)()


# NOTE — earlier we had a `preserve_tab_on_action_click` callback that wrote
# `tabs.value` back on every action-button click. It caused an infinite
# re-render loop: write tabs.value → switch_tab callback fires → tab-content
# re-mounts → scroll jumps to top + visible flicker. Removed because the
# `dcc.Tabs(persistence=..., persisted_props=["value"])` settings already
# defend against the snap-back without forcing tab-content to re-render.


@app.callback(Output("recent-jobs-list", "children"), Input("overview-poll", "n_intervals"))
def update_recent_jobs(_n):
    jobs = load_jobs()
    if not jobs["jobs"]:
        return html.Div("No jobs yet.", style={"fontSize": "12px", "color": "#a0a0a0"})
    return html.Table(style={"width": "100%", "fontSize": "12px"}, children=[
        html.Thead(html.Tr([
            html.Th(h, style={"textAlign": "left", "padding": "6px 8px",
                              "color": "#5a5a5a", "fontWeight": 600,
                              "letterSpacing": "0.3px", "textTransform": "uppercase",
                              "fontSize": "10px", "borderBottom": "1px solid #ededed"})
            for h in ["Started", "Label", "Status", "Cmd"]
        ])),
        html.Tbody([
            html.Tr([
                html.Td(fmt_ts(j.get("started", "")),
                        style={"padding": "6px 8px", "color": "#5a5a5a"}),
                html.Td(j.get("label", "—"), style={"padding": "6px 8px"}),
                html.Td(html.Span(j.get("status", "?"), className=f"pill {j.get('status', 'pending')}"),
                        style={"padding": "6px 8px"}),
                html.Td(html.Code((j.get("cmd", "") or "")[:80]),
                        style={"padding": "6px 8px", "color": "#a0a0a0", "fontSize": "11px"}),
            ]) for j in jobs["jobs"][:15]
        ]),
    ])


def _sb_iter_inner(it: dict | None, sheet_id: str, set_n: int, slot: int):
    """Inner children of a single SB iter block — gets swapped on live refresh.
    Empty state: a labeled placeholder so Pending sets still show context — the
    prompt body, location, and shot range render in adjacent columns regardless
    of whether the storyboard image has been generated yet."""
    if it:
        thumb_div = img_cell(it["thumb"], it["label"], it["view"], aspect="16/9")
    else:
        thumb_div = html.Div(style={
            "aspectRatio": "16/9", "background": "#f5f5f5",
            "border": "1px dashed #d0d0d0", "borderRadius": "8px",
            "display": "flex", "flexDirection": "column",
            "alignItems": "center", "justifyContent": "center",
            "color": "#999", "fontSize": "11px", "letterSpacing": "0.4px",
            "textTransform": "uppercase",
        }, children=[
            html.Div(f"Iter {slot}", style={"fontWeight": 600}),
            html.Div("pending", style={"fontSize": "10px", "marginTop": "4px",
                                        "color": "#b0b0b0", "fontStyle": "italic"}),
        ])
    return [
        thumb_div,
        html.Button(
            f"Generate V{slot}",
            id={"type": "gen-vid", "sheet": sheet_id, "set": set_n, "slot": slot},
            type="button",
            className="cta",
            style={"width": "100%", "fontSize": "11px", "padding": "9px 12px"},
            disabled=not it,
        ),
        html.Div(id={"type": "gen-vid-status", "set": set_n, "slot": slot},
                 style={"fontSize": "10px", "color": "#a0a0a0",
                        "minHeight": "14px", "textAlign": "center"}),
    ]


def _sb_iter_block(it: dict | None, sheet_id: str, set_n: int, slot: int):
    """Container for a SB iter — live-refreshed on storyboard job completion."""
    return html.Div(
        id={"type": "sb-iter-block", "set": set_n, "slot": slot},
        style={"display": "flex", "flexDirection": "column", "gap": "8px"},
        children=_sb_iter_inner(it, sheet_id, set_n, slot),
    )


def _video_block_inner(v: dict | None, slot: int):
    """Inner children of a video block — gets swapped on live refresh.
    Plain inline iframe (Drive /preview) — clip plays in place with native
    HTML5 controls, no click-to-zoom, no lightbox. Storyboard panels keep
    the lightbox; videos don't (user pref)."""
    if v:
        preview_src = v.get("preview") or v.get("url") or ""
        tile = html.Div(style={
            "position": "relative", "aspectRatio": "9/16",
            "background": "#000", "borderRadius": "8px", "overflow": "hidden",
        }, children=[
            html.Iframe(src=preview_src, style={
                "width": "100%", "height": "100%", "border": "0",
                "display": "block",
            }, allow="autoplay") if preview_src else None,
            html.Div(f"V{slot}", style={
                "position": "absolute", "left": "6px", "bottom": "6px",
                "background": "#1a1a1a", "color": "#fff",
                "fontSize": "9px", "letterSpacing": "0.4px",
                "textTransform": "uppercase", "fontWeight": 600,
                "padding": "3px 8px", "borderRadius": "5px",
                "pointerEvents": "none",
            }),
        ])
    else:
        tile = html.Div(style={
            "aspectRatio": "9/16", "background": "#e3e3e3", "borderRadius": "8px",
            "display": "flex", "alignItems": "center", "justifyContent": "center",
            "color": "#a0a0a0", "fontSize": "10px", "letterSpacing": "0.3px",
            "textTransform": "uppercase",
        }, children=f"V{slot}")
    if v:
        download_btn = html.A(
            "Download clip", href=v["download"], target="_blank", download=True,
            className="cta cta-link",
        )
    else:
        download_btn = html.Button("Download clip", className="cta", disabled=True,
                                    style={"width": "100%"})
    return [tile, download_btn]


def _video_block(v: dict | None, slot: int, set_n: int):
    """Container for a video tile — live-refreshed on video job completion."""
    return html.Div(
        id={"type": "vid-block", "set": set_n, "slot": slot},
        style={"display": "flex", "flexDirection": "column", "gap": "8px"},
        children=_video_block_inner(v, slot),
    )


# Storyboards tab — list view + per-set fire buttons (driven by global picker)
@app.callback(Output("sb-content", "children"),
              Input("active-sheet", "data"),
              Input("refresh-tick", "data"))
def sb_refresh(sheet_id, _tick):
    if not sheet_id:
        return None
    try:
        sets = br.read_storyboards(sheet_id, bible_sheet_id=BIBLE_SHEET)
    except Exception as e:
        return html.Div(f"Error: {e}", style={"color": "#c11647"})
    if not sets:
        return html.Div("No storyboard sets found.",
                        style={"color": "#a0a0a0", "fontStyle": "italic"})

    cards = []
    for s in sets:
        sb_count = sum(1 for i in s["sb_iters"] if i)
        vid_count = sum(1 for v in s["videos"] if v)

        # LEFT: prompt body in a white "lifted" card with EN/Bahasa toggle.
        # Body falls back to a useful placeholder so Pending sets still render
        # the prompt-card structure (range, location, body) even when no
        # storyboard image has been generated.
        en_text = s["body"] or f"(prompt body not yet generated for shots {s['shots'] or '—'})"
        bahasa_text = s.get("body_bahasa") or "(Bahasa version pending)"
        has_bahasa = bool(s.get("body_bahasa"))
        left_col = html.Div(style={"display": "flex", "flexDirection": "column", "gap": "12px"},
                            children=[
            html.Div(className="inner-card prompt-card", children=[
                html.Button(
                    "Bahasa",
                    id={"type": "lang-toggle", "set": s["set"]},
                    type="button",
                    className="lang-toggle-btn",
                    n_clicks=0,
                    disabled=not has_bahasa,
                    title="Toggle EN / Bahasa",
                ),
                # Section header — VIDEO prompt body (NOT storyboard prompt).
                # Storyboard prompt is a fixed global stored at Storyboard Prompts
                # B1-B8 and is LOCKED from the dashboard UI.
                html.Div("VIDEO PROMPT", className="prompt-section-label"),
                # GLOBAL — Video Prompts B1 (Camera) + B2 (Audio/Dialogue) + B3
                # (Setting). Locked from the dashboard UI. Auto-prefixed to every
                # shot at gen time.
                html.Div([
                    html.Div("GLOBAL  · locked", className="loc-label"),
                    html.Div("\n".join([t for t in [
                        s.get("vp_global_camera") or "",
                        s.get("vp_global_audio") or "",
                        s.get("vp_global_setting") or "",
                    ] if t]), className="global-text"),
                ], className="global-block"),
                # LOCATION — auto-detected from the body. Sits between the
                # (locked) global preamble and the per-set body.
                html.Div([
                    html.Span("LOCATION", className="loc-label"),
                    html.Span(s.get("location") or "Unspecified", className="loc-value"),
                ], className="loc-line"),
                html.Div(en_text,
                         id={"type": "prompt-text", "set": s["set"]},
                         style={
                             "fontSize": "13px", "color": "#5a5a5a",
                             "lineHeight": "1.55", "whiteSpace": "pre-wrap",
                         }),
                # Hidden stores carrying both languages so the toggle is instant
                dcc.Store(id={"type": "prompt-en", "set": s["set"]}, data=en_text),
                dcc.Store(id={"type": "prompt-bahasa", "set": s["set"]}, data=bahasa_text),
            ]),
            html.Button(
                "Generate Storyboard",
                id={"type": "gen-sb", "sheet": sheet_id, "set": s["set"]},
                type="button",
                className="cta",
                style={"width": "100%", "fontSize": "11px", "padding": "10px 14px"},
            ),
            html.Div(id={"type": "gen-sb-status", "set": s["set"]},
                     style={"fontSize": "11px", "color": "#a0a0a0",
                            "minHeight": "16px"}),
        ])

        # MIDDLE: SB iter 1 (16:9) + Generate V1 button, then SB iter 2 + Generate V2
        sb_col = html.Div(style={
            "display": "flex", "flexDirection": "column", "gap": "20px",
        }, children=[
            _sb_iter_block(s["sb_iters"][0], sheet_id, s["set"], 1),
            _sb_iter_block(s["sb_iters"][1], sheet_id, s["set"], 2),
        ])

        # RIGHT: white "lifted" card holding videos in a vertical column (V1 above V2)
        v1 = s["videos"][0] if len(s["videos"]) > 0 else None
        v2 = s["videos"][1] if len(s["videos"]) > 1 else None
        any_video = v1 or v2
        download_all_urls = [v["download"] for v in (v1, v2) if v]
        right_col = html.Div(style={"display": "flex", "flexDirection": "column", "gap": "12px"},
                             children=[
            html.Div(className="inner-card", children=[
                html.Div(style={
                    "display": "flex", "flexDirection": "column", "gap": "16px",
                }, children=[_video_block(v1, 1, s["set"]), _video_block(v2, 2, s["set"])]),
            ]),
            html.Button(
                "Download all",
                id={"type": "download-all", "set": s["set"]},
                type="button",
                className="cta danger",
                n_clicks=0,
                disabled=not any_video,
                style={"width": "100%", "fontSize": "11px", "padding": "10px 14px"},
            ),
            dcc.Store(id={"type": "download-all-urls", "set": s["set"]},
                      data=download_all_urls),
        ])

        cards.append(html.Div(className="card", style={"padding": "22px 26px"}, children=[
            # Ack stores — track which job IDs have been merged into the visible thumbs
            dcc.Store(id={"type": "sb-iter-ack", "set": s["set"], "slot": 1}, data=None),
            dcc.Store(id={"type": "sb-iter-ack", "set": s["set"], "slot": 2}, data=None),
            dcc.Store(id={"type": "vid-ack", "set": s["set"], "slot": 1}, data=None),
            dcc.Store(id={"type": "vid-ack", "set": s["set"], "slot": 2}, data=None),
            html.Div(style={"display": "flex", "justifyContent": "space-between",
                            "alignItems": "center", "marginBottom": "18px"}, children=[
                html.H3(f"Set {s['set']} · shots {s['shots'] or '—'}"),
                html.Div(className="meta", children=[
                    # Status chip — Done / Pending / Failed surfaced from SP col F
                    # so the team can see at-a-glance which sets need work.
                    html.Span(
                        (s.get("status") or "Pending").upper(),
                        className="chip",
                        style={
                            "background": (
                                "#e8f5e9" if (s.get("status") or "").lower() == "done"
                                else "#fff3e0" if (s.get("status") or "").lower() == "failed"
                                else "#f5f5f5"
                            ),
                            "color": (
                                "#2e7d32" if (s.get("status") or "").lower() == "done"
                                else "#e65100" if (s.get("status") or "").lower() == "failed"
                                else "#666"
                            ),
                        },
                    ),
                    html.Span(f"{sb_count}/2 SB", className="chip"),
                    html.Span(f"{vid_count}/2 VID", className="chip"),
                ]),
            ]),
            # Storyboard middle col bumped another 15% (1.45fr → 1.67fr;
            # 290 → 333px). Left text col absorbs the trim
            # (1.70fr → 1.48fr; 260 → 240px).
            html.Div(style={
                "display": "grid",
                "gridTemplateColumns": "minmax(240px, 1.48fr) minmax(333px, 1.67fr) minmax(170px, 0.85fr)",
                "gap": "22px", "alignItems": "start",
            }, children=[
                left_col,
                sb_col,
                right_col,
            ]),
        ]))
    return html.Div(cards)


# --------- Bible tabs: full render on episode switch, live refresh on tick ---
# Each card is wrapped in a stable-keyed container with a hash store.
# Live-refresh callback updates only cards whose data hash changed.
def _wrap_bible_card(item, key, fields, type_prefix):
    regen_id = {"type": "regen-bible", "bible": type_prefix, "key": str(key)}
    regen_status_id = {"type": "regen-bible-status", "bible": type_prefix, "key": str(key)}
    return html.Div(children=[
        html.Div(
            id={"type": f"{type_prefix}-content", "key": key},
            children=bible_card(item, fields=fields,
                                 regen_id=regen_id,
                                 regen_status_id=regen_status_id),
        ),
        dcc.Store(
            id={"type": f"{type_prefix}-hash", "key": key},
            data=_data_hash(item),
        ),
    ])


def _register_bible_tab(content_id: str, reader_fn, type_prefix: str,
                        fields: list, label: str, key_field: str = "name"):
    """Register a (full-render + live-refresh) callback pair for one bible tab.
    Reads from the SERIES-LEVEL bible_sheet (same across all episodes)."""

    @app.callback(Output(content_id, "children"),
                  Input("tabs", "value"))  # render once on mount
    def _full_render(_tab):
        try:
            items = reader_fn(BIBLE_SHEET)
        except Exception as e:
            return html.Div(f"Error: {e}", style={"color": "#c11647"})
        if not items:
            return html.Div(
                f"No {label} tab on the bible sheet "
                f"({BIBLE_SHEET[:8]}…). Add a {label} tab to populate this view.",
                style={"color": "#a0a0a0", "fontStyle": "italic"})
        return html.Div(className="grid bible", children=[
            _wrap_bible_card(it, it.get(key_field, str(i)), fields, type_prefix)
            for i, it in enumerate(items)
        ])

    @app.callback(
        Output({"type": f"{type_prefix}-content", "key": ALL}, "children"),
        Output({"type": f"{type_prefix}-hash", "key": ALL}, "data"),
        Input("refresh-tick", "data"),
        State({"type": f"{type_prefix}-content", "key": ALL}, "id"),
        State({"type": f"{type_prefix}-hash", "key": ALL}, "data"),
        prevent_initial_call=True,
    )
    def _live_refresh(_tick, ids, hashes):
        if not ids:
            return [], []
        try:
            items_by_key = {it.get(key_field): it for it in reader_fn(BIBLE_SHEET)}
        except Exception:
            return [no_update] * len(ids), [no_update] * len(ids)
        new_children, new_hashes = [], []
        for cid, ack in zip(ids, hashes):
            it = items_by_key.get(cid["key"])
            if not it:
                new_children.append(no_update)
                new_hashes.append(no_update)
                continue
            h = _data_hash(it)
            if h != ack:
                key_val = str(cid["key"])
                new_children.append(bible_card(
                    it, fields=fields,
                    regen_id={"type": "regen-bible", "bible": type_prefix, "key": key_val},
                    regen_status_id={"type": "regen-bible-status", "bible": type_prefix, "key": key_val},
                ))
                new_hashes.append(h)
            else:
                new_children.append(no_update)
                new_hashes.append(no_update)
        return new_children, new_hashes


_register_bible_tab(
    "ch-content", br.read_characters, "char",
    fields=[("Role", "role"), ("Age", "age"), ("Wardrobe", "wardrobe")],
    label="CHARACTERS")
_register_bible_tab(
    "loc-content", br.read_locations, "loc",
    fields=[("Type", "type"), ("Lighting", "lighting"), ("Time", "time")],
    label="LOCATIONS")
_register_bible_tab(
    "cos-content", br.read_costumes, "cos",
    fields=[("Used by", "used_by")], label="COSTUME")
_register_bible_tab(
    "pr-content", br.read_props, "pr",
    fields=[("Used by", "used_by")], label="PROPS")
_register_bible_tab(
    "fx-content", br.read_effects, "fx",
    fields=[("Used by", "used_by")], label="EFFECTS")


# --------- Per-bible Regenerate buttons ---------
# Routes per the provider memory:
#   characters       → character_generate.py (Higgsfield gpt_image_2 — bible ref sheet)
#   locations        → location_generate.py  (Reve direct)
#   costume/props/fx → bible_generate.py     (Higgsfield nano_banana_2)
BIBLE_REGEN_ROUTING = {
    "char": ("character_generate.py", ["--character", "{key}"]),
    "loc":  ("location_generate.py",  ["--location", "{key}"]),
    "cos":  ("bible_generate.py",     ["--tab", "COSTUME", "--name", "{key}"]),
    "pr":   ("bible_generate.py",     ["--tab", "PROPS",   "--name", "{key}"]),
    "fx":   ("bible_generate.py",     ["--tab", "EFFECTS", "--name", "{key}"]),
}


@app.callback(
    Output({"type": "regen-bible-status", "bible": MATCH, "key": MATCH}, "children"),
    Input({"type": "regen-bible", "bible": MATCH, "key": MATCH}, "n_clicks"),
    State({"type": "regen-bible", "bible": MATCH, "key": MATCH}, "id"),
    prevent_initial_call=True,
)
def fire_regen_bible(n_clicks, btn_id):
    if not n_clicks or not btn_id:
        return no_update
    bible = btn_id["bible"]
    key = btn_id["key"]
    if bible not in BIBLE_REGEN_ROUTING:
        return f"unknown bible: {bible}"
    script, arg_template = BIBLE_REGEN_ROUTING[bible]
    cmd = [PYTHON_BIN, script, "--sheet", BIBLE_SHEET, "--force"]
    for a in arg_template:
        cmd.append(a.format(key=key))
    job_id = str(uuid.uuid4())[:8]
    append_job({
        "id": job_id, "label": f"regen-{bible} {key}",
        "status": "queued",
        "started": datetime.now(timezone.utc).isoformat(),
        "log": "", "cmd": " ".join(cmd), "kind": f"regen-{bible}",
        "key": key, "sheet": BIBLE_SHEET,
    })
    threading.Thread(target=run_bg, args=(cmd, job_id), daemon=True).start()
    return f"queued · {job_id}"


# --------- Live in-place refresh of SB iter blocks + video tiles ---------
# Triggered by sb-poll Interval. Each card's "ack" Store records the most recent
# done-job ID we've already merged into the DOM. When a newer done-job appears
# for the same set/slot, fetch fresh sheet data and swap just the inner content
# of that block. Other cards remain untouched, so the user's scroll position
# stays put and unrelated thumbnails don't reload.
@app.callback(
    Output({"type": "sb-iter-block", "set": ALL, "slot": ALL}, "children"),
    Output({"type": "sb-iter-ack", "set": ALL, "slot": ALL}, "data"),
    Input("sb-poll", "n_intervals"),
    State({"type": "sb-iter-block", "set": ALL, "slot": ALL}, "id"),
    State({"type": "sb-iter-ack", "set": ALL, "slot": ALL}, "data"),
    State("active-sheet", "data"),
    prevent_initial_call=True,
)
def live_refresh_sb_iters(_n, ids, acks, sheet_id):
    if not ids:
        return [], []
    jobs = load_jobs()["jobs"]
    latest_by_set = {}
    for j in jobs:
        if j.get("kind") == "storyboard" and j.get("status") == "done":
            sn = j.get("set")
            ts = j.get("ended", "") or j.get("started", "")
            cur = latest_by_set.get(sn)
            if not cur or ts > cur["ts"]:
                latest_by_set[sn] = {"id": j["id"], "ts": ts}
    # Decide which sets need refresh
    sets_needing = set()
    for sid, ack in zip(ids, acks):
        sn = sid["set"]
        info = latest_by_set.get(sn)
        if info and info["id"] != ack:
            sets_needing.add(sn)
    if not sets_needing:
        return [no_update] * len(ids), [no_update] * len(ids)
    # One sheet read per refresh cycle, regardless of how many sets need it
    try:
        fresh = {s["set"]: s for s in br.read_storyboards(sheet_id, bible_sheet_id=BIBLE_SHEET)}
    except Exception:
        return [no_update] * len(ids), [no_update] * len(ids)
    new_children, new_acks = [], []
    for sid in ids:
        sn = sid["set"]
        slot = sid["slot"]
        if sn not in sets_needing or sn not in fresh:
            new_children.append(no_update)
            new_acks.append(no_update)
            continue
        it = fresh[sn]["sb_iters"][slot - 1]
        new_children.append(_sb_iter_inner(it, sheet_id, sn, slot))
        new_acks.append(latest_by_set[sn]["id"])
    return new_children, new_acks


@app.callback(
    Output({"type": "vid-block", "set": ALL, "slot": ALL}, "children"),
    Output({"type": "vid-ack", "set": ALL, "slot": ALL}, "data"),
    Input("sb-poll", "n_intervals"),
    State({"type": "vid-block", "set": ALL, "slot": ALL}, "id"),
    State({"type": "vid-ack", "set": ALL, "slot": ALL}, "data"),
    State("active-sheet", "data"),
    prevent_initial_call=True,
)
def live_refresh_videos(_n, ids, acks, sheet_id):
    if not ids:
        return [], []
    jobs = load_jobs()["jobs"]
    # Index latest done video job by (set, slot)
    latest = {}
    for j in jobs:
        if j.get("kind") == "video" and j.get("status") == "done":
            key = (j.get("set"), j.get("slot"))
            ts = j.get("ended", "") or j.get("started", "")
            cur = latest.get(key)
            if not cur or ts > cur["ts"]:
                latest[key] = {"id": j["id"], "ts": ts}
    keys_needing = set()
    for sid, ack in zip(ids, acks):
        key = (sid["set"], sid["slot"])
        info = latest.get(key)
        if info and info["id"] != ack:
            keys_needing.add(key)
    if not keys_needing:
        return [no_update] * len(ids), [no_update] * len(ids)
    try:
        fresh = {s["set"]: s for s in br.read_storyboards(sheet_id, bible_sheet_id=BIBLE_SHEET)}
    except Exception:
        return [no_update] * len(ids), [no_update] * len(ids)
    new_children, new_acks = [], []
    for sid in ids:
        key = (sid["set"], sid["slot"])
        sn, slot = key
        if key not in keys_needing or sn not in fresh:
            new_children.append(no_update)
            new_acks.append(no_update)
            continue
        v = fresh[sn]["videos"][slot - 1] if slot - 1 < len(fresh[sn]["videos"]) else None
        new_children.append(_video_block_inner(v, slot))
        new_acks.append(latest[key]["id"])
    return new_children, new_acks


@app.callback(
    Output({"type": "download-all", "set": ALL}, "disabled"),
    Output({"type": "download-all-urls", "set": ALL}, "data"),
    Input("sb-poll", "n_intervals"),
    State({"type": "download-all", "set": ALL}, "id"),
    State("active-sheet", "data"),
    prevent_initial_call=True,
)
def live_refresh_download_all(_n, ids, sheet_id):
    """Keep the per-set Download all button in sync after live video refreshes."""
    if not ids:
        return [], []
    try:
        fresh = {s["set"]: s for s in br.read_storyboards(sheet_id, bible_sheet_id=BIBLE_SHEET)}
    except Exception:
        return [no_update] * len(ids), [no_update] * len(ids)
    disabled, urls = [], []
    for sid in ids:
        s = fresh.get(sid["set"])
        if not s:
            disabled.append(no_update)
            urls.append(no_update)
            continue
        download_urls = [v["download"] for v in s["videos"] if v]
        disabled.append(not bool(download_urls))
        urls.append(download_urls)
    return disabled, urls


# Per-set "Generate storyboard" — pattern-matched button on every Storyboards card
@app.callback(
    Output({"type": "gen-sb-status", "set": MATCH}, "children"),
    Input({"type": "gen-sb", "sheet": dash.dependencies.ALL, "set": MATCH}, "n_clicks"),
    State({"type": "gen-sb", "sheet": dash.dependencies.ALL, "set": MATCH}, "id"),
    prevent_initial_call=True,
)
def fire_storyboard_for_set(n_clicks_list, ids_list):
    if not any(n_clicks_list or []):
        return no_update
    btn_id = ids_list[0]
    sheet_id = btn_id["sheet"]
    set_n = btn_id["set"]
    job_id = str(uuid.uuid4())[:8]
    cmd = [PYTHON_BIN, "storyboard_generate.py", "--sheet", sheet_id, "--set", str(set_n), "--force"]
    append_job({"id": job_id, "label": f"sb-gen set{set_n}", "status": "queued",
                "started": datetime.now(timezone.utc).isoformat(),
                "log": "", "cmd": " ".join(cmd), "kind": "storyboard",
                "set": set_n, "sheet": sheet_id})
    threading.Thread(target=run_bg, args=(cmd, job_id), daemon=True).start()
    return f"queued · {job_id}"


# Per-set+slot "Generate video" — pattern-matched
@app.callback(
    Output({"type": "gen-vid-status", "set": MATCH, "slot": MATCH}, "children"),
    Input({"type": "gen-vid", "sheet": dash.dependencies.ALL, "set": MATCH, "slot": MATCH}, "n_clicks"),
    State({"type": "gen-vid", "sheet": dash.dependencies.ALL, "set": MATCH, "slot": MATCH}, "id"),
    prevent_initial_call=True,
)
def fire_video_for_set(n_clicks_list, ids_list):
    """Fire BOTH output slots in parallel from a single button click.
    The CLICKED button's slot determines which storyboard iter is used as
    the composition reference (V1 button → SB iter 1 / SP!G; V2 button →
    SB iter 2 / SP!H). The same SB iter is passed to both vidgen jobs, so
    BytePlus produces 2 different cuts off the same composition anchor.

    Slot 1 output → SP!M; slot 2 output → SP!N. Same prompt + refs each;
    Seedance's seed variance gives them distinct motion."""
    if not any(n_clicks_list or []):
        return no_update
    triggered_idx = next((i for i, c in enumerate(n_clicks_list or []) if c), 0)
    btn_id = ids_list[triggered_idx]
    sheet_id = btn_id["sheet"]
    set_n = btn_id["set"]
    sb_slot = btn_id["slot"]   # which SB iter is the composition anchor
    fired = []
    for output_slot in (1, 2):
        job_id = str(uuid.uuid4())[:8]
        cmd = [PYTHON_BIN, "byteplus_vidgen.py",
               "--sheet", sheet_id, "--set", str(set_n),
               "--slot", str(output_slot),
               "--sb-slot", str(sb_slot),
               "--resolution", "720p", "--duration", "15"]
        append_job({"id": job_id,
                    "label": f"vidgen set{set_n} out{output_slot} sb{sb_slot}",
                    "status": "queued",
                    "started": datetime.now(timezone.utc).isoformat(),
                    "log": "", "cmd": " ".join(cmd), "kind": "video",
                    "set": set_n, "slot": output_slot, "sheet": sheet_id})
        threading.Thread(target=run_bg, args=(cmd, job_id), daemon=True).start()
        fired.append(job_id)
    return f"queued · 2 jobs (sb{sb_slot} → {fired[0]}, {fired[1]})"


# Live status updates for all per-set fire buttons
@app.callback(
    Output({"type": "gen-sb-status", "set": ALL}, "children", allow_duplicate=True),
    Input("sb-poll", "n_intervals"),
    State({"type": "gen-sb-status", "set": ALL}, "id"),
    prevent_initial_call=True,
)
def update_all_sb_statuses(_n, ids):
    jobs = load_jobs()["jobs"]
    out = []
    for sid in ids:
        set_n = sid["set"]
        # most recent storyboard job for this set
        match = next((j for j in jobs if j.get("kind") == "storyboard" and j.get("set") == set_n), None)
        if not match:
            out.append("")
        else:
            out.append(f"{match.get('status', '?')} · {match['id']}")
    return out


@app.callback(
    Output({"type": "gen-vid-status", "set": ALL, "slot": ALL}, "children", allow_duplicate=True),
    Input("sb-poll", "n_intervals"),
    State({"type": "gen-vid-status", "set": ALL, "slot": ALL}, "id"),
    prevent_initial_call=True,
)
def update_all_vid_statuses(_n, ids):
    jobs = load_jobs()["jobs"]
    out = []
    for sid in ids:
        set_n, slot = sid["set"], sid["slot"]
        match = next((j for j in jobs
                      if j.get("kind") == "video" and j.get("set") == set_n and j.get("slot") == slot),
                     None)
        if not match:
            out.append("")
        else:
            out.append(f"{match.get('status', '?')} · {match['id']}")
    return out


# Video Generations tab — history list
@app.callback(Output("vg-history", "children"), Input("vg-poll", "n_intervals"))
def vg_history(_n):
    jobs = [j for j in load_jobs()["jobs"] if j.get("kind") == "video"]
    if not jobs:
        return html.Div("No video generations fired yet.",
                        style={"color": "#a0a0a0", "fontStyle": "italic", "padding": "16px 0"})
    return html.Table(style={"width": "100%", "fontSize": "12px"}, children=[
        html.Thead(html.Tr([
            html.Th(h, style={"textAlign": "left", "padding": "8px 10px",
                              "color": "#5a5a5a", "fontWeight": 600,
                              "letterSpacing": "0.3px", "textTransform": "uppercase",
                              "fontSize": "10px", "borderBottom": "1px solid #ededed"})
            for h in ["Started", "Set / slot", "Status", "Job ID", "Cmd"]
        ])),
        html.Tbody([
            html.Tr([
                html.Td(fmt_ts(j.get("started", "")),
                        style={"padding": "8px 10px", "color": "#5a5a5a"}),
                html.Td(f"set {j.get('set', '?')} · slot {j.get('slot', '?')}",
                        style={"padding": "8px 10px"}),
                html.Td(html.Span(j.get("status", "?"), className=f"pill {j.get('status', 'pending')}"),
                        style={"padding": "8px 10px"}),
                html.Td(j["id"], style={"padding": "8px 10px",
                                        "fontFamily": "JetBrains Mono, monospace",
                                        "fontSize": "11px", "color": "#a0a0a0"}),
                html.Td(html.Code((j.get("cmd", "") or "")[:100]),
                        style={"padding": "8px 10px", "color": "#a0a0a0", "fontSize": "11px"}),
            ]) for j in jobs[:50]
        ]),
    ])


# Asset Library
@app.callback(Output("al-content", "children"),
              Input("active-sheet", "data"), Input("refresh-tick", "data"))
def al_refresh(sheet_id, _t):
    if not sheet_id:
        return None
    try:
        rows = br.read_asset_library(sheet_id)
    except Exception as e:
        return html.Div(f"Error: {e}", style={"color": "#c11647"})
    if not rows:
        return html.Div("No Asset Library tab found, or it's empty.",
                        style={"color": "#a0a0a0", "fontStyle": "italic"})
    # Default-sort: CHARACTERS first (alphabetical), then LOCATIONS / etc.
    # Sheet stores chars at rows 45-49 — without sort they'd land on page 2.
    rows_sorted = sorted(rows, key=lambda r: (r.get("bible", ""),
                                                r.get("name", "")))
    return dash_table.DataTable(
        data=rows_sorted,
        columns=[{"name": c.replace("_", " ").title(), "id": c}
                 for c in ["name", "bible", "asset_code", "type", "status",
                           "uploaded_at", "first_used", "last_used"]],
        style_cell={"fontFamily": "Inter, sans-serif", "fontSize": 12,
                    "padding": "8px 12px", "border": "1px solid #ededed",
                    "textAlign": "left"},
        style_header={"backgroundColor": "#e3e3e3", "fontWeight": 600,
                      "fontSize": 11, "textTransform": "uppercase"},
        style_data_conditional=[
            {"if": {"filter_query": '{status} = "Uploaded"', "column_id": "status"},
             "backgroundColor": "#d3eddd", "color": "#1a6b56"},
            {"if": {"filter_query": '{status} = "Pending"', "column_id": "status"},
             "backgroundColor": "rgba(255,140,66,0.18)", "color": "#b54e0e"},
            {"if": {"filter_query": '{status} = "Failed"', "column_id": "status"},
             "backgroundColor": "rgba(255,59,107,0.15)", "color": "#c11647"},
        ],
        page_size=100, sort_action="native", filter_action="native",
    )


app.clientside_callback(
    """
    function(n_clicks, urls) {
        if (!n_clicks || !urls || !urls.length) return window.dash_clientside.no_update;
        urls.forEach((url, i) => {
            setTimeout(() => {
                const a = document.createElement('a');
                a.href = url;
                a.download = '';
                a.target = '_blank';
                document.body.appendChild(a);
                a.click();
                a.remove();
            }, i * 600);
        });
        return n_clicks;
    }
    """,
    Output({"type": "download-all", "set": MATCH}, "title"),
    Input({"type": "download-all", "set": MATCH}, "n_clicks"),
    State({"type": "download-all-urls", "set": MATCH}, "data"),
)


# EN / Bahasa toggle — pure clientside, no server roundtrip.
# Odd clicks → Bahasa. Even (or zero) → English. Button label flips accordingly.
app.clientside_callback(
    """
    function(n_clicks, en_text, bahasa_text) {
        const isBahasa = (n_clicks || 0) % 2 === 1;
        return [
            isBahasa ? bahasa_text : en_text,
            isBahasa ? "English" : "Bahasa"
        ];
    }
    """,
    Output({"type": "prompt-text", "set": MATCH}, "children"),
    Output({"type": "lang-toggle", "set": MATCH}, "children"),
    Input({"type": "lang-toggle", "set": MATCH}, "n_clicks"),
    State({"type": "prompt-en", "set": MATCH}, "data"),
    State({"type": "prompt-bahasa", "set": MATCH}, "data"),
)


# --- Server-side cache warmer -------------------------------------------
# Runs once at module import (Dash production servers re-import the module
# under each worker — `start_background_refresh` is idempotent via the
# `_bg_started` guard, so multiple workers won't multiply the load).
#
# Tracks the user's CURRENT episode pick by reading the file-backed
# `active-sheet` Store. Falls back to DEFAULT_EPISODE_SHEET on first boot.
_active_sheet_holder = {"sid": DEFAULT_EPISODE_SHEET}


@app.callback(
    Output("active-sheet", "data", allow_duplicate=True),
    Input("active-sheet", "data"),
    prevent_initial_call=True,
)
def _track_active_sheet(sid):
    """Mirror the active-sheet Store into a module-level dict so the
    background warmer can follow the user's episode picks. No-op return."""
    if sid:
        _active_sheet_holder["sid"] = sid
    return no_update


br.start_background_refresh(
    get_active_sheet_id=lambda: _active_sheet_holder["sid"],
    bible_sheet_id=BIBLE_SHEET,
)


if __name__ == "__main__":
    # Local dev only. Render uses Procfile + gunicorn against `server` above.
    # PORT env honored either way (default 8050 locally; Render injects $PORT).
    port = int(os.environ.get("PORT", 8050))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"\n→ DearAI Production Dashboard: http://{host}:{port}\n")
    app.run(debug=False, host=host, port=port)

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
  cd "/Users/raymuschang/Documents/Shotlist Workflows" && python3 dash_app/app.py
  → http://localhost:8050
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
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

# Persistent state lives under DEARAI_STATE_DIR when set (point this at a Render
# persistent disk so the job queue + expense ledger survive redeploys — on the
# default ephemeral disk they're wiped on every deploy). Falls back to the repo
# root for local dev. The asset-video faststart cache also honors it.
_STATE_DIR = Path(os.environ.get("DEARAI_STATE_DIR", "").strip() or PROJECT_ROOT)
try:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    _STATE_DIR = PROJECT_ROOT  # never let a bad path break boot
EXPENSE_LOG = _STATE_DIR / ".byteplus_expense.json"
JOBS_LOG = _STATE_DIR / ".dash_jobs.json"
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
        # `start_new_session=True` detaches the subprocess from gunicorn's
        # process group on Linux/macOS. When Render redeploys and SIGTERMs
        # gunicorn workers, the running storyboard / vidgen subprocess
        # SURVIVES instead of getting orphaned mid-flight. The subprocess's
        # internal `_safe_print` already absorbs the lost stdout pipe, and
        # its sheet writeback completes regardless of the parent's death.
        # Eliminates the "stuck on Generating" + "iter1 uploaded but no
        # writeback" zombie state we kept hitting today.
        proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, start_new_session=True)
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


# ============================================================
# Google OAuth — Flask + Authlib, conditional on env vars.
# ============================================================
# When GOOGLE_CLIENT_ID is set, every request must come from a logged-in
# Google account on the allowlist (domain or individual email). When it's
# unset, the middleware short-circuits and the app stays open — so deploys
# don't break before the user finishes GCP OAuth-client setup.
#
# Required env vars on Render once you're ready to enforce auth:
#   GOOGLE_CLIENT_ID     — OAuth 2.0 Web client ID from Google Cloud Console
#   GOOGLE_CLIENT_SECRET — paired secret
#   SECRET_KEY           — random 32+ chars for Flask session signing
#   ALLOWED_DOMAINS      — comma-separated, e.g. "dearai.com"
#   ALLOWED_EMAILS       — comma-separated specific outsiders (Gmail etc.)
# At least one of ALLOWED_DOMAINS / ALLOWED_EMAILS must be non-empty,
# otherwise the allowlist denies everyone (fail closed).
#
# Redirect URI to register in Google Cloud Console:
#   https://<your-render-url>/auth/callback
# (and http://localhost:8050/auth/callback for local dev).

from datetime import timedelta
from flask import session, redirect, request, jsonify, Response
from werkzeug.middleware.proxy_fix import ProxyFix

# Render terminates HTTPS at the edge; Flask sees the inner HTTP. ProxyFix
# tells Flask to trust the X-Forwarded-* headers so url_for(_external=True)
# generates https:// URLs (required for OAuth redirect_uri matching).
server.wsgi_app = ProxyFix(server.wsgi_app, x_for=1, x_proto=1, x_host=1)


# --- gzip compression -------------------------------------------------------
# The /projects HTML and Dash's JSON payloads are large and otherwise sent
# uncompressed. gzip them (when the client accepts it) for a ~70-80% smaller
# transfer — a big load-time win on the heaviest responses. No new dependency:
# a plain after_request gzips text/JSON bodies above a small threshold.
import gzip as _gzip  # noqa: E402

_GZIP_TYPES = ("text/html", "text/css", "application/javascript",
               "text/javascript", "application/json", "image/svg+xml",
               "text/plain")
_GZIP_MIN_BYTES = 1024


@server.after_request
def _gzip_response(resp):
    try:
        from flask import request
        accept = (request.headers.get("Accept-Encoding") or "")
        if "gzip" not in accept.lower():
            return resp
        if resp.direct_passthrough or resp.status_code < 200 or resp.status_code >= 300:
            return resp
        if resp.headers.get("Content-Encoding"):
            return resp
        ctype = (resp.content_type or "").split(";")[0].strip().lower()
        if ctype not in _GZIP_TYPES:
            return resp
        data = resp.get_data()
        if len(data) < _GZIP_MIN_BYTES:
            return resp
        resp.set_data(_gzip.compress(data, 6))
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Content-Length"] = str(len(resp.get_data()))
        resp.headers.add("Vary", "Accept-Encoding")
    except Exception:
        return resp
    return resp


GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
ALLOWED_DOMAINS = {
    d.strip().lower()
    for d in os.environ.get("ALLOWED_DOMAINS", "").split(",")
    if d.strip()
}
ALLOWED_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ALLOWED_EMAILS", "").split(",")
    if e.strip()
}
AUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

if AUTH_ENABLED:
    server.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    server.config.update(
        SESSION_COOKIE_SECURE=True,       # HTTPS-only (Render terminates TLS)
        SESSION_COOKIE_HTTPONLY=True,     # block JS access
        SESSION_COOKIE_SAMESITE="Lax",    # OAuth callback works, CSRF blocked
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(server)
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    PUBLIC_PATHS = {"/login", "/auth/callback", "/auth/logout",
                    "/lyoot-gallery"}

    def _is_allowed_email(email: str) -> bool:
        """Return True if email matches the allowlist (domain or specific)."""
        if not email or "@" not in email:
            return False
        e = email.lower()
        if e in ALLOWED_EMAILS:
            return True
        domain = e.rsplit("@", 1)[-1]
        return domain in ALLOWED_DOMAINS

    @server.before_request
    def _require_login():
        # Allow OAuth dance + logout endpoints without a session
        if request.path in PUBLIC_PATHS:
            return None
        # Allow Dash's internal _dash-* routes once authed (handled by the
        # session check below) — they're called from the same browser session
        # so they ride the cookie automatically.
        email = session.get("user_email")
        if email and _is_allowed_email(email):
            return None
        # API endpoints get a 401 JSON instead of a redirect (so the gallery's
        # JS fetch() handlers can detect auth failure cleanly).
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "login required"}), 401
        # Browser navigation → redirect to /login carrying the original URL
        # so we can come back after auth completes.
        next_url = request.url if request.method == "GET" else "/"
        session["next_url"] = next_url
        return redirect("/login")

    @server.route("/login")
    def _login():
        """Kick off the OAuth flow → redirect to Google's consent screen."""
        from flask import url_for
        redirect_uri = url_for("_auth_callback", _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    @server.route("/auth/callback")
    def _auth_callback():
        """Google redirects here with ?code=…; exchange + verify allowlist."""
        try:
            token = oauth.google.authorize_access_token()
        except Exception as e:
            return Response(
                f"<h1>Login failed</h1><p>{type(e).__name__}: {e}</p>"
                "<p><a href='/login'>Try again</a></p>",
                status=400, mimetype="text/html",
            )
        userinfo = token.get("userinfo") or {}
        email = (userinfo.get("email") or "").strip().lower()
        if not _is_allowed_email(email):
            allowlist_summary = (
                f"Domains: {sorted(ALLOWED_DOMAINS) or '—'}<br>"
                f"Specific: {len(ALLOWED_EMAILS)} address(es)"
            )
            return Response(
                f"<h1>Access denied</h1>"
                f"<p><b>{email or 'unknown account'}</b> is not on the allowlist.</p>"
                f"<p>{allowlist_summary}</p>"
                f"<p>Ask your admin to add your email, then "
                f"<a href='/auth/logout'>log out</a> and try again.</p>",
                status=403, mimetype="text/html",
            )
        session.permanent = True
        session["user_email"] = email
        session["user_name"] = userinfo.get("name", "")
        session["user_picture"] = userinfo.get("picture", "")
        next_url = session.pop("next_url", "/") or "/"
        return redirect(next_url)

    @server.route("/auth/logout")
    def _auth_logout():
        """Clear the session cookie and bounce back to /login."""
        session.clear()
        return redirect("/login")

    print(f"[auth] enabled — domains={sorted(ALLOWED_DOMAINS)} "
          f"individual={len(ALLOWED_EMAILS)}")
else:
    # No GOOGLE_CLIENT_ID set → auth is OFF, app is publicly accessible.
    # This is the default state until the user finishes GCP setup.
    print("[auth] DISABLED — set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET to enable")


# Debug route — returns recent failed-job logs as JSON so production
# regressions can be diagnosed without shell access. These leak env-presence +
# project/job listings, so they're LOCKED DOWN by _debug_guard(): reachable only
# when explicitly opened for local dev (DEARAI_DEBUG_OPEN=1) or to a logged-in
# admin (session email in DEARAI_ADMIN_EMAILS, or any logged-in user if that
# allowlist is unset). Otherwise they 404 — including the dangerous auth-off
# public state.
def _debug_guard():
    """Abort 404 unless the caller may access /debug/*. Returns None when allowed."""
    if os.environ.get("DEARAI_DEBUG_OPEN", "").strip() == "1":
        return
    if AUTH_ENABLED:
        email = (session.get("user_email") or "").strip().lower()
        admins = {e.strip().lower()
                  for e in os.environ.get("DEARAI_ADMIN_EMAILS", "").split(",") if e.strip()}
        if email and (not admins or email in admins):
            return
    from flask import abort
    abort(404)


@server.route("/debug/jobs")
def _debug_jobs():
    _debug_guard()
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
            # Sheet-target metadata so the gallery watcher can run an
            # Option B fallback check (read SP!M/N directly) when the
            # parent worker dies before writing status=done. Only set
            # for jobs that actually target a sheet cell — otherwise
            # these are absent and the watcher skips the fallback.
            "set": j.get("set"),
            "slot": j.get("slot"),
            "sheet": j.get("sheet"),
        })
    return jsonify({"count": len(out), "jobs": out})


@server.route("/api/sheet-mtime")
def _api_sheet_mtime():
    """Lightweight poll endpoint: return the modifiedTime of a gallery's
    sheet so the gallery JS can detect external edits (e.g. someone
    editing the body in Claude Code) and prompt for a refresh.

    Query: ?gallery=<slug>
    Returns: {"mtime": "2026-05-08T12:34:56.789Z"} or {"error": "..."}.

    Drive API mtime updates on any cell edit anywhere in the sheet. This
    is exactly what we want — text changes / new assets / status flips /
    @-mention swaps all trigger the same update signal.
    """
    from flask import jsonify, request
    gallery = (request.args.get("gallery") or "").strip()
    if not gallery or gallery not in GALLERY_REGISTRY:
        return jsonify({"error": "unknown gallery"}), 400
    sheet_id, _show, _ep = GALLERY_REGISTRY[gallery]
    try:
        from googleapiclient.discovery import build
        from auth import get_credentials
        drive = build("drive", "v3", credentials=get_credentials())
        meta = drive.files().get(fileId=sheet_id, fields="modifiedTime").execute()
        return jsonify({"mtime": meta.get("modifiedTime", "")})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@server.route("/api/vidgen-resume", methods=["POST"])
def _api_vidgen_resume():
    """Crash-recovery for vidgen tasks.

    When the gallery watcher hits MAX_ATTEMPTS without seeing a job flip
    to done — and the sheet-status fallback also doesn't find a URL —
    that almost always means: BytePlus succeeded, but the subprocess
    died between the BytePlus succeed and the Drive/sheet writeback.
    The task_id was persisted to .byteplus_pending.json at submit time
    (by byteplus_vidgen.py) so we can pick it back up here.

    Spawns byteplus_vidgen_resume.py as a background subprocess. The
    resume script walks every entry in .byteplus_pending.json and runs
    the post-submit pipeline (GetTask → download → Drive → sheet write)
    for each one BytePlus reports as succeeded.

    Body: empty (no params needed)
    Returns: {"ok": true, "started": <pid>}
    """
    from flask import jsonify
    cmd = [PYTHON_BIN, "byteplus_vidgen_resume.py"]
    try:
        proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT),
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1, start_new_session=True)
        return jsonify({"ok": True, "started_pid": proc.pid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@server.route("/api/set-review", methods=["POST"])
def _api_set_review():
    """Persist per-set review state from the gallery to the SP sheet.

    Body: {"gallery": <slug>, "set": <int>,
           "reviewed": <bool>?, "comments": <str>?}
    Either 'reviewed' or 'comments' (or both) may be present. Missing
    fields are left untouched in the sheet.

    Writes SP!O{row} (TRUE/FALSE) and/or SP!P{row} (free text), where
    row = 10 + set_num. Invalidates the gallery HTML cache for the
    affected slug so the next page load reflects the change.

    Returns: {"ok": true} on success.
    """
    from flask import request, jsonify
    body = request.get_json(silent=True) or {}
    gallery = (body.get("gallery") or "").strip()
    set_n = body.get("set")
    if not gallery or not isinstance(set_n, int) or set_n < 1:
        return jsonify({"ok": False,
                         "error": "missing/invalid gallery or set"}), 400
    if gallery not in GALLERY_REGISTRY:
        return jsonify({"ok": False,
                         "error": f"unknown gallery '{gallery}'"}), 400
    sheet_id, _show, _ep = GALLERY_REGISTRY[gallery]

    has_reviewed = "reviewed" in body
    has_comments = "comments" in body
    if not (has_reviewed or has_comments):
        return jsonify({"ok": False,
                         "error": "no fields to update"}), 400

    try:
        import gspread
        from auth import get_credentials
        gc = gspread.authorize(get_credentials())
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet("Storyboard Prompts")
    except Exception as e:
        return jsonify({"ok": False, "error": f"sheet open: {e}"}), 500

    # Ensure the SP tab has at least 16 columns (A through P) before we
    # try to write to O/P. Many production sheets ship with 14 cols
    # (A=Set#, B=Range, … N=Video Iter 2) — extending here makes the
    # checkbox/comments feature work without a manual schema migration.
    if ws.col_count < 16:
        try:
            ws.add_cols(16 - ws.col_count)
        except Exception as e:
            return jsonify({"ok": False,
                             "error": f"sheet expand cols: {e}"}), 500

    row = 10 + set_n
    updates = []

    # Backfill the column-10 header titles ("Reviewed" + "Comments")
    # on first write so producers looking at the sheet directly see
    # what these columns hold. Only writes when the cells are empty.
    try:
        hdrs = ws.get("O10:P10", value_render_option="FORMATTED_VALUE")
        existing_o = (hdrs[0][0] if hdrs and hdrs[0] and len(hdrs[0]) > 0 else "").strip()
        existing_p = (hdrs[0][1] if hdrs and hdrs[0] and len(hdrs[0]) > 1 else "").strip()
        if not existing_o:
            updates.append({"range": "O10", "values": [["Reviewed"]]})
        if not existing_p:
            updates.append({"range": "P10", "values": [["Comments"]]})
    except Exception:
        pass  # header backfill is best-effort; never block the actual write

    if has_reviewed:
        # Boolean → TRUE/FALSE so the cell renders as a real Sheets
        # checkbox if the column has data validation set up; if not,
        # it's still a clean boolean string.
        val = "TRUE" if bool(body["reviewed"]) else "FALSE"
        updates.append({"range": f"O{row}", "values": [[val]]})
    if has_comments:
        # Free text — let Sheets' USER_ENTERED handle escaping. Strip
        # leading/trailing whitespace but keep newlines mid-string.
        val = (body["comments"] or "").strip()
        updates.append({"range": f"P{row}", "values": [[val]]})

    try:
        # Single batch update — one Sheets API call regardless of which
        # fields changed.
        sh.values_batch_update(body={
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": f"'Storyboard Prompts'!{u['range']}",
                       "values": u["values"]} for u in updates],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"sheet write: {e}"}), 500

    # Drop the gallery's HTML cache so the next page load reads the
    # fresh review state. Without this, the team's "Saved ✓" change
    # vanishes on the next refresh until the 30s TTL expires.
    try:
        with _gallery_cache_lock:
            _gallery_cache.pop(gallery, None)
    except Exception:
        pass

    return jsonify({"ok": True, "set": set_n,
                     "updated": [u["range"] for u in updates]})


@server.route("/api/edit-global", methods=["POST"])
def _api_edit_global():
    """Change a project's GLOBAL film look IN PLACE — writes camera → Video
    Prompts B1, audio → B2 (and Storyboard Prompts B1, which the master-shot
    generator reads), so every shot inherits the new look without recreating the
    project. Accepts a preset id (from global_presets) OR explicit camera/audio
    text. Flushes the bible cache so the change surfaces immediately."""
    from flask import request, jsonify
    payload = request.get_json(silent=True) or request.form
    sheet_id = (payload.get("sheet_id") or "").strip()
    preset_id = (payload.get("preset") or "").strip()
    camera = (payload.get("camera") or "").strip()
    audio = (payload.get("audio") or "").strip()
    if not sheet_id:
        return jsonify({"ok": False, "error": "sheet_id required"}), 400
    if preset_id:
        try:
            from global_presets import get_preset
            p = get_preset(preset_id)
            camera, audio = p["camera"], p["audio"]
        except Exception as e:
            return jsonify({"ok": False, "error": f"preset: {e}"}), 400
    if not camera and not audio:
        return jsonify({"ok": False, "error": "preset or camera/audio required"}), 400
    try:
        from auth import get_credentials
        import gspread
        gc = gspread.authorize(get_credentials())
        sh = gc.open_by_key(sheet_id)
        vp = sh.worksheet("Video Prompts")
        updates = []
        if camera:
            updates.append({"range": "B1", "values": [[camera]]})
        if audio:
            updates.append({"range": "B2", "values": [[audio]]})
        vp.batch_update(updates, value_input_option="RAW")
        if camera:
            # keep the storyboard/master-shot camera global aligned
            try:
                sh.worksheet("Storyboard Prompts").update(
                    "B1", [[camera]], value_input_option="RAW")
            except Exception:
                pass
        try:
            br.invalidate_all_caches()
        except Exception:
            pass
        return jsonify({"ok": True, "preset": preset_id or None,
                         "wrote": [u["range"] for u in updates]})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@server.route("/api/jobs-sheet-check", methods=["POST"])
def _api_jobs_sheet_check():
    """Option B fallback: when the watcher's /debug/jobs poll never sees a
    job flip to status=done (because Render redeployed and killed the
    parent worker before its update_job() writeback), this endpoint reads
    the target cell directly. If the URL is there, the job clearly
    completed — the runtime just never recorded it.

    Body: {"ids": ["job_a", "job_b"]}
    Returns: {"results": {"job_a": {"done": true, "url": "..."},
                           "job_b": {"done": false}, ...}}

    Only vidgen jobs are checked (set/slot/sheet present in the job
    record). Other job kinds return {"done": false} unconditionally.
    """
    from flask import jsonify, request
    body = request.get_json(silent=True) or {}
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"results": {}})

    data = load_jobs()
    by_id = {j.get("id"): j for j in data.get("jobs", []) if j.get("id")}

    # Group target cells by sheet so we can do one batch_get per sheet
    # instead of one cell read per job. Pattern: vidgen slot 1 -> M{row},
    # slot 2 -> N{row}, where row = 10 + set.
    by_sheet: dict[str, list[tuple[str, str]]] = {}  # sheet_id -> [(job_id, cell), ...]
    results: dict[str, dict] = {}
    for jid in ids:
        j = by_id.get(jid)
        results[jid] = {"done": False}
        if not j or j.get("kind") != "vidgen":
            continue
        sheet_id = j.get("sheet")
        set_n = j.get("set")
        slot = j.get("slot")
        if not (sheet_id and isinstance(set_n, int) and slot in (1, 2)):
            continue
        col = "M" if slot == 1 else "N"
        cell = f"Storyboard Prompts!{col}{10 + set_n}"
        by_sheet.setdefault(sheet_id, []).append((jid, cell))

    if not by_sheet:
        return jsonify({"results": results})

    try:
        import gspread
        from auth import get_credentials
        gc = gspread.authorize(get_credentials())
    except Exception as e:
        return jsonify({"results": results, "error": f"auth: {e}"}), 200

    # One batch_get per sheet — collapses N cell reads to 1 API call.
    # Quota-friendly even when the watcher fans this out for both V1+V2
    # at the same time.
    for sheet_id, items in by_sheet.items():
        try:
            sh = gc.open_by_key(sheet_id)
            ranges = [c for _, c in items]
            vals = sh.values_batch_get(ranges)
            value_ranges = vals.get("valueRanges", [])
            for (jid, _cell), vr in zip(items, value_ranges):
                vlist = vr.get("values") or []
                cell_val = ""
                if vlist and vlist[0]:
                    cell_val = (vlist[0][0] or "").strip()
                if cell_val.startswith("http"):
                    results[jid] = {"done": True, "url": cell_val}
        except Exception:
            # Best-effort fallback — if the sheet read fails, just leave
            # done=False and let the standard /debug/jobs path drive.
            continue

    return jsonify({"results": results})


# ============================================================
# Master Projects sheet — single source of truth for all shows.
# ============================================================
# Read from the sheet at runtime + cached 60s. Episodes are auto-discovered
# per-project by scanning the show's Drive folder for spreadsheets named
# "Ep N — ..." (multi-sheet pattern, e.g. sajangnim) OR registering the
# show's single SOT sheet as ep01 (single-sheet pattern, e.g. new POCs from
# _create_blank_sot.py).
#
# The legacy hardcoded GALLERY_REGISTRY is gone — set MASTER_PROJECTS_SHEET_ID
# in Render env vars to enable. While unset, the registry is empty and
# galleries 404 cleanly (deploy doesn't break).

MASTER_PROJECTS_SHEET_ID = os.environ.get("MASTER_PROJECTS_SHEET_ID", "").strip()

# ---------------------------------------------------------------------------
# Shared cache — Redis-backed when REDIS_URL is set, so ALL gunicorn workers
# share one warm cache instead of each holding its own (kills cross-worker
# staleness + cold-read flakiness). Falls back to a per-process in-memory dict
# when Redis is absent/unreachable, so local dev + Redis-less Render still work.
# ---------------------------------------------------------------------------
import pickle as _pickle  # noqa: E402
_redis = None
_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if _REDIS_URL:
    try:
        import redis as _redis_lib  # type: ignore
        _redis = _redis_lib.from_url(
            _REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
        _redis.ping()
        print("[cache] Redis shared cache connected")
    except Exception as _e:
        print(f"[cache] Redis unavailable ({_e}); using in-memory cache")
        _redis = None
_local_cache: dict = {}            # key -> (expires_at, value)
_local_cache_lock = threading.Lock()


def cache_get(key: str):
    """Return the cached value for key, or None if missing/expired."""
    if _redis is not None:
        try:
            raw = _redis.get(key)
            return _pickle.loads(raw) if raw is not None else None
        except Exception:
            pass  # degrade to local cache
    import time as _t
    with _local_cache_lock:
        hit = _local_cache.get(key)
        if hit and hit[0] > _t.time():
            return hit[1]
        if hit:
            _local_cache.pop(key, None)
    return None


def cache_set(key: str, value, ttl: float) -> None:
    if _redis is not None:
        try:
            _redis.setex(key, int(max(1, ttl)), _pickle.dumps(value))
            return
        except Exception:
            pass
    import time as _t
    with _local_cache_lock:
        _local_cache[key] = (_t.time() + ttl, value)


def cache_del(key: str) -> None:
    if _redis is not None:
        try:
            _redis.delete(key)
        except Exception:
            pass
    with _local_cache_lock:
        _local_cache.pop(key, None)


_PROJECTS_TTL = 300.0  # cache the parsed projects index for 5 min (edits force-flush)
_PROJECTS_KEY = "dearai:projects"
_PROJECTS_GOOD_KEY = "dearai:projects:lastgood"
_projects_cache: dict = {}          # legacy local handle (kept for shims)
_projects_cache_lock = threading.Lock()
# Permissive episode-sheet name matcher. Accepts:
#   "Ep 1 — Pelarian Pertama"
#   "Ep01_Pelarian_Pertama"
#   "EP01_Pelarian_Pertama_shotlist_v2_2"
#   "Episode 3: ..."
# First capture group is the episode number; second is the rest (title +
# optional suffixes which we'll clean up downstream for display).
_EP_NAME_RE = re.compile(r"^Ep(?:isode)?[\s_\-]*?(\d+)[\s\-—_:]+(.+)$", re.IGNORECASE)
# Strip these trailing tokens from auto-discovered episode titles before
# rendering (`shotlist`, `v2_2`, `final`, etc. are not part of the title).
# `\b` doesn't fire between letters and `_` because `_` is a word char in
# regex, so we use an explicit separator-or-end lookahead. This prevents
# false-positives like "FINALE" being treated as "FINAL" + suffix.
_EP_TITLE_TRIM_RE = re.compile(
    r"[\s_\-]+(?:shotlist|sotmaster|sot|v\d+(?:_\d+)?|final|draft)(?:$|[\s_\-].*$)",
    re.IGNORECASE,
)


def _clean_ep_title(raw: str, ep_num: int) -> str:
    """`EP01_Pelarian_Pertama_shotlist_v2_2` → `Episode 1 — Pelarian Pertama`."""
    title = _EP_TITLE_TRIM_RE.sub("", raw).strip(" _-")
    title = title.replace("_", " ").strip()
    return f"Episode {ep_num} — {title}" if title else f"Episode {ep_num}"


def _discover_episodes(slug: str, drive_folder_id: str, bible_sheet_id: str,
                       show_title: str) -> list[dict]:
    """For one show, return a list of episode dicts:
        [{gallery_slug, sheet_id, episode_title, episode_number}, ...]

    Two patterns:
      1. Multi-sheet (sajangnim): the show's Drive folder contains N
         spreadsheets named "Ep N — <title>". Each is one episode.
      2. Single-sheet (new POCs from _create_blank_sot.py): the show has
         exactly one SOT spreadsheet covering everything. Register it as
         <slug>_ep01.
    """
    if not drive_folder_id:
        # Single-sheet fallback when folder ID isn't set
        return [{
            "gallery_slug": f"{slug}_ep01",
            "sheet_id": bible_sheet_id,
            "episode_title": show_title,
            "episode_number": 1,
        }]
    try:
        from auth import get_credentials
        from googleapiclient.discovery import build as _drive_build
        creds = get_credentials()
        drive = _drive_build("drive", "v3", credentials=creds)
        files = drive.files().list(
            q=f"'{drive_folder_id}' in parents "
              f"and mimeType='application/vnd.google-apps.spreadsheet' "
              f"and trashed=false",
            fields="files(id,name)",
            supportsAllDrives=True,
        ).execute().get("files", [])
    except Exception as e:
        print(f"[projects] _discover_episodes({slug}) Drive list failed: {e}")
        return [{
            "gallery_slug": f"{slug}_ep01",
            "sheet_id": bible_sheet_id,
            "episode_title": show_title,
            "episode_number": 1,
        }]

    matched = []
    for f in files:
        m = _EP_NAME_RE.match(f["name"])
        if m:
            ep_num = int(m.group(1))
            ep_title = _clean_ep_title(m.group(2), ep_num)
            matched.append((ep_num, f["id"], ep_title))
    if matched:
        # Multi-sheet pattern — sort by ep number, register each as a gallery
        matched.sort()
        return [{
            "gallery_slug": f"{slug}_ep{ep_num:02d}",
            "sheet_id": fid,
            "episode_title": ep_title,
            "episode_number": ep_num,
        } for ep_num, fid, ep_title in matched]
    # Single-sheet — bible IS the only episode
    return [{
        "gallery_slug": f"{slug}_ep01",
        "sheet_id": bible_sheet_id,
        "episode_title": show_title,
        "episode_number": 1,
    }]


def _detect_cover(drive_folder_id: str) -> str:
    """Look for cover.{jpg,png,webp,jpeg} in the show's Drive folder.
    Returns a thumb URL (lh3 CDN) or empty string. Cached implicitly by the
    surrounding read_projects 60s TTL."""
    if not drive_folder_id:
        return ""
    try:
        from auth import get_credentials
        from googleapiclient.discovery import build as _drive_build
        creds = get_credentials()
        drive = _drive_build("drive", "v3", credentials=creds)
        files = drive.files().list(
            q=f"'{drive_folder_id}' in parents and trashed=false "
              f"and (name='cover.jpg' or name='cover.png' or name='cover.webp' or name='cover.jpeg')",
            fields="files(id,name)",
        ).execute().get("files", [])
        if not files:
            return ""
        # Most recent if multiple (shouldn't happen — endpoint trashes old)
        fid = files[0]["id"]
        return f"https://lh3.googleusercontent.com/d/{fid}=w800"
    except Exception as e:
        print(f"[projects] _detect_cover({drive_folder_id[:12]}…) failed: {e}")
        return ""


_MEDIA_TTL = 600.0  # cache per-bible Asset Library roll-up for 10 min


def _project_media(bible_sheet_id: str) -> dict:
    """Read the bible's Asset Library and pull what the /projects card needs:
      - hero_video: the first CHARACTERS (else LOCATIONS) *video* ref as
        {file_id, poster, kind, name} — used for the card's hover-play preview.
        ONLY ever a bible reference clip (characters/locations); NEVER a
        generated story clip, by design (we only look at the Asset Library).
      - n_characters / n_locations / n_assets: distinct Uploaded names, for the
        card stat roll-up.

    Cached in the shared cache (Redis if configured, else in-memory; 10 min)
    keyed by bible_sheet_id so the /projects refresh does NOT re-read every
    bible's Asset Library each pass. On read failure we reuse the last cached
    value if we have one rather than blanking the card's video/counts. Returns
    {} when nothing is available."""
    if not bible_sheet_id:
        return {}
    _mkey = f"dearai:media:{bible_sheet_id}"
    hit = cache_get(_mkey)
    if hit is not None:
        return hit
    result: dict = {}
    try:
        from auth import get_credentials
        import gspread
        from build_gallery import read_asset_library, drive_id, drive_thumb
        gc = gspread.authorize(get_credentials())
        sh = gc.open_by_key(bible_sheet_id)
        rows = read_asset_library(sh)
        live = [r for r in rows if (r.get("status") or "").strip().lower() == "uploaded"]

        def _names(tab_prefix: str) -> set:
            return {r["name"] for r in live
                    if (r.get("bible_tab") or "").upper().startswith(tab_prefix)}

        result["n_characters"] = len(_names("CHARACTER"))
        result["n_locations"] = len(_names("LOCATION"))
        result["n_assets"] = len({r["name"] for r in live})

        def _first_video(tab_prefix: str):
            for r in live:
                if (r.get("type") or "").strip().lower() == "video" and \
                   (r.get("bible_tab") or "").upper().startswith(tab_prefix):
                    fid = drive_id(r.get("source_url"))
                    if fid:
                        return {"file_id": fid, "poster": drive_thumb(fid, 800),
                                "kind": "character" if tab_prefix == "CHARACTER" else "location",
                                "name": r["name"]}
            return None

        hero = _first_video("CHARACTER") or _first_video("LOCATION")
        if hero:
            result["hero_video"] = hero
    except Exception as e:
        print(f"[projects] _project_media({bible_sheet_id[:12]}…) failed: {e}")
        stale = cache_get(_mkey + ":good")
        return stale if stale is not None else {}
    cache_set(_mkey, result, _MEDIA_TTL)
    cache_set(_mkey + ":good", result, 86400)  # last-known-good for failure reuse
    return result


def _read_projects_uncached() -> dict:
    """Read the master Projects sheet end-to-end and resolve every project's
    episodes via Drive folder scan. Returns:
        {
          "projects": [project_dict, ...],         # full row + 'episodes' list
          "registry": {gallery_slug: (sheet_id, show_title, episode_title), ...},
          "bible_for": {gallery_slug: bible_sheet_id, ...},
          "siblings_for": {gallery_slug: [(sib_slug, ep_title), ...], ...},
        }
    """
    if not MASTER_PROJECTS_SHEET_ID:
        # Legit "no master sheet configured" — _ok=True so read_projects does
        # NOT treat this as a transient failure (no serve-stale).
        return {"projects": [], "registry": {}, "bible_for": {}, "siblings_for": {}, "_ok": True}
    try:
        from auth import get_credentials
        import gspread
        gc = gspread.authorize(get_credentials())
        sh = gc.open_by_key(MASTER_PROJECTS_SHEET_ID)
        ws = sh.worksheet("Projects")
        rows = ws.get(
            "A2:L500", value_render_option="FORMATTED_VALUE"
        )
    except Exception as e:
        # Genuine read FAILURE — _ok=False so read_projects serves the last
        # known-good snapshot instead of blanking the CMS.
        print(f"[projects] master sheet read failed: {e}")
        return {"projects": [], "registry": {}, "bible_for": {}, "siblings_for": {}, "_ok": False}

    # Parse rows into project dicts (skip blank slug rows)
    projects: list[dict] = []
    for r in rows:
        r = (r + [""] * 12)[:12]
        slug = r[0].strip()
        if not slug:
            continue
        # Skip archived projects unless explicitly hit by URL
        # (status='archived' rows still get registered so old URLs keep working)
        proj = {
            "slug": slug,
            "title": r[1].strip(),
            "type": r[2].strip().lower() or "series",
            "status": r[3].strip().lower() or "draft",
            "bible_sheet_id": r[4].strip(),
            "drive_folder_id": r[5].strip(),
            "parent_show": r[6].strip(),
            "owner_email": r[7].strip(),
            "created_at": r[8].strip(),
            "script_drive_url": r[9].strip(),
            "shotlist_status": r[10].strip().lower() or "pending",
            "notes": r[11].strip(),
        }
        projects.append(proj)

    # Resolve spinoff inheritance: parent_show → use parent's bible_sheet_id
    by_slug = {p["slug"]: p for p in projects}
    for p in projects:
        if p["parent_show"] and p["parent_show"] in by_slug:
            parent = by_slug[p["parent_show"]]
            if not p["bible_sheet_id"]:
                p["bible_sheet_id"] = parent["bible_sheet_id"]

    # Resolve each project's episodes + cover + Asset Library roll-up. These are
    # the slow network-bound bits (Drive folder scans + cover lookup + Asset
    # Library read) — running them SEQUENTIALLY across N projects sums to tens of
    # seconds and on a cold load blows past Render's request timeout, so the page
    # "never loads". Run them in a thread pool: a cold load is then bounded by the
    # slowest single project, not the sum. (Creds are already warm from the master
    # read above; each helper builds its own Drive/Sheets client, so this is
    # thread-safe.)
    import concurrent.futures as _cf

    def _resolve(p: dict) -> None:
        if not p["bible_sheet_id"]:
            print(f"[projects] {p['slug']}: no bible_sheet_id, skipping")
            return
        try:
            p["episodes"] = _discover_episodes(
                slug=p["slug"], drive_folder_id=p["drive_folder_id"],
                bible_sheet_id=p["bible_sheet_id"], show_title=p["title"],
            )
            p["cover_url"] = _detect_cover(p["drive_folder_id"]) if p["drive_folder_id"] else ""
            media = _project_media(p["bible_sheet_id"])
            p["hero_video"] = media.get("hero_video")
            p["n_characters"] = media.get("n_characters", 0)
            p["n_locations"] = media.get("n_locations", 0)
            p["n_assets"] = media.get("n_assets", 0)
        except Exception as e:
            print(f"[projects] resolve {p['slug']} failed: {type(e).__name__}: {e}")

    if projects:
        with _cf.ThreadPoolExecutor(max_workers=min(8, len(projects))) as _ex:
            list(_ex.map(_resolve, projects))

    # Build the registry/bible_for/siblings serially — pure CPU, no network.
    registry: dict[str, tuple[str, str, str]] = {}
    bible_for: dict[str, str] = {}
    siblings_by_show: dict[str, list[tuple[str, str]]] = {}
    for p in projects:
        eps = p.get("episodes")
        if not eps:
            continue
        for ep in eps:
            gallery_slug = ep["gallery_slug"]
            registry[gallery_slug] = (ep["sheet_id"], p["title"], ep["episode_title"])
            bible_for[gallery_slug] = p["bible_sheet_id"]
        siblings_by_show[p["slug"]] = [
            (ep["gallery_slug"], ep["episode_title"]) for ep in eps
        ]

    siblings_for: dict[str, list[tuple[str, str]]] = {}
    for p in projects:
        for ep in p.get("episodes", []):
            siblings_for[ep["gallery_slug"]] = siblings_by_show.get(p["slug"], [])

    return {
        "projects": projects,
        "registry": registry,
        "bible_for": bible_for,
        "siblings_for": siblings_for,
        "_ok": True,
    }


def read_projects(force: bool = False) -> dict:
    """Cached wrapper (shared cache: Redis if configured, else in-memory). Use
    force=True to bypass the TTL after edits.

    Resilience: a fresh read that FAILED (transient Sheets/Drive error →
    _ok=False) must NOT clobber a previously good snapshot — one flaky read
    would otherwise blank the entire CMS for a full TTL window. We then keep
    serving the last known-good projects. A read that SUCCEEDS but is legitimately
    empty (_ok=True, e.g. the sheet was emptied) IS honored, so deletions show up
    and force=True always reflects a successful fresh read."""
    if not force:
        cached = cache_get(_PROJECTS_KEY)
        if cached is not None:
            return cached
    data = _read_projects_uncached()
    if not data.get("_ok"):
        # Serve-stale-on-FAILURE: reuse the last known-good snapshot (shared
        # across workers) rather than blanking the CMS.
        prev = cache_get(_PROJECTS_GOOD_KEY)
        if prev and prev.get("projects"):
            cache_set(_PROJECTS_KEY, prev, _PROJECTS_TTL)
            return prev
    cache_set(_PROJECTS_KEY, data, _PROJECTS_TTL)
    if data.get("projects"):
        cache_set(_PROJECTS_GOOD_KEY, data, 86400)  # last-known-good for a day
    return data


# ----- Backward-compat shims for existing route handlers ------------------
# Until the master sheet flow is fully migrated, the rest of dash_app/app.py
# still references SERIES_BIBLE_SHEETS / GALLERY_REGISTRY / _bible_sheet_for /
# _episodes_for. These shims keep that surface working — they're now backed
# by the master sheet via read_projects(), so producer-edited rows take
# effect within 60s without redeploys.

class _DynamicGalleryRegistry:
    """Dict-like view over read_projects()['registry'] — keeps the existing
    `GALLERY_REGISTRY[slug]` lookups + `slug in GALLERY_REGISTRY` checks
    working with the dynamic data.

    Cross-worker cache miss handling: gunicorn runs N workers, each with
    its own 60s _projects_cache. When /api/new-project on worker A flushes
    A's cache, worker B's cache is still stale until its own TTL expires.
    A producer who just submitted the modal can land on B and get "No
    gallery found" for their freshly-created project.

    Mitigation: on a miss (slug not in cache'd registry), force a
    cache-bypass re-read from the master sheet. If THAT still misses,
    the slug genuinely doesn't exist. This adds at most one extra sheet
    read per 404 — negligible cost, and only on the slow path."""
    def __getitem__(self, key):
        reg = read_projects()["registry"]
        if key in reg:
            return reg[key]
        # Miss — bypass cache and re-read from sheet (handles per-worker
        # cache staleness when the modal just created this project on a
        # different worker)
        return read_projects(force=True)["registry"][key]
    def __contains__(self, key):
        if key in read_projects()["registry"]:
            return True
        return key in read_projects(force=True)["registry"]
    def __iter__(self):
        return iter(read_projects()["registry"])
    def keys(self):
        return read_projects()["registry"].keys()
    def items(self):
        return read_projects()["registry"].items()
    def values(self):
        return read_projects()["registry"].values()
    def get(self, key, default=None):
        reg = read_projects()["registry"]
        if key in reg:
            return reg[key]
        return read_projects(force=True)["registry"].get(key, default)


GALLERY_REGISTRY = _DynamicGalleryRegistry()


def _bible_sheet_for(gallery_name: str) -> str | None:
    return read_projects()["bible_for"].get(gallery_name)


def _episodes_for(gallery_name: str) -> list[tuple[str, str]]:
    """Same-show siblings for the episode-picker dropdown."""
    return read_projects()["siblings_for"].get(gallery_name, [])


# `re` is imported at the top of this file (line 26).
# `build_gservice` is the same `googleapiclient.discovery.build` used elsewhere;
# imported lazily inside _discover_episodes when needed (line 437) so module
# load stays cheap if the Drive API isn't available at boot.

# In-memory cache for live galleries: name → (timestamp, html_string).
# 30s TTL — long enough that rapid hits don't burn Sheets quota, short enough
# that team sees their sheet edits / button-triggered generations promptly
# without needing a manual rebuild step. Force-flush via /gallery/<name>/refresh.
_GALLERY_TTL = 30.0
_gallery_cache: dict = {}
_gallery_cache_lock = threading.Lock()


@server.route("/recap")
def _recap_page():
    """One-off recap page for May 7, 2026 — what we shipped that day.
    Auth-gated like every other route (your team only)."""
    from flask import send_from_directory
    return send_from_directory(str(PROJECT_ROOT), "recap.html",
                                mimetype="text/html")


@server.route("/lyoot-gallery")
def _lyoot_gallery_page():
    """LYOOT results gallery — PUBLIC share link for the client.
    Listed in PUBLIC_PATHS, so it bypasses the OAuth gate. The page only
    embeds anyone-with-link Drive previews, no internal data."""
    from flask import send_from_directory
    return send_from_directory(str(PROJECT_ROOT), "lyoot_gallery.html",
                                mimetype="text/html")


@server.route("/projects")
def _projects_landing():
    """CMS landing page — grid of all projects from the master sheet.

    Uses read_projects() (60s cache). Returns a single-page HTML rendered by
    build_projects_page.render_projects_page. The "+ New Project" button
    here is a stub until commit 5 (modal + form). For now, a click on it
    points producers at the master sheet for direct row editing.
    """
    from flask import Response
    from build_projects_page import render_projects_page
    import traceback
    user_email = session.get("user_email", "") if AUTH_ENABLED else ""
    try:
        data = read_projects()
    except Exception as e:
        traceback.print_exc()
        data = {"projects": []}
    # Try to render with the loaded data. If the renderer itself crashes,
    # fall back to a minimal page that STILL has the "+ New Project" button
    # so producers aren't locked out of the CMS when a single row is bad.
    try:
        html_doc = render_projects_page(data.get("projects", []), user_email=user_email)
    except Exception as e:
        traceback.print_exc()
        err = f"{type(e).__name__}: {str(e)[:200]}"
        html_doc = (
            "<!DOCTYPE html><html><head><title>DearAI Projects</title>"
            "<style>body{font-family:Inter,system-ui,sans-serif;padding:40px;"
            "background:#fafafa;color:#1a1a1a;}button{background:#c11647;color:white;"
            "border:0;border-radius:6px;padding:10px 18px;font-size:14px;cursor:pointer;}"
            ".err{background:#fee;border:1px solid #c11647;color:#c11647;padding:12px;"
            "border-radius:4px;margin:20px 0;font-family:JetBrains Mono,monospace;"
            "font-size:12px;}</style></head><body>"
            "<h1>Projects</h1>"
            f"<div class='err'>Render failed: {err}</div>"
            "<p>You can still start a new project, or edit the master sheet directly.</p>"
            "<p><button onclick=\"alert('Modal disabled in fallback mode — '"
            "'use the master sheet directly to fix the bad row, then refresh.')\">"
            "+ New Project</button> &nbsp; "
            "<a href='https://docs.google.com/spreadsheets/d/"
            "1J-x4b4hshrX3wdMItboQJzcjKkAff_jnKEiIKjpy0g0' target='_blank'>"
            "Open master sheet</a></p></body></html>"
        )
    return Response(html_doc, mimetype="text/html",
                    headers={"Cache-Control": "max-age=30, must-revalidate"})


# Faststart video cache — on the persistent disk if DEARAI_STATE_DIR is set
# (survives redeploys), else the system temp dir (rebuilt on demand).
_ASSET_VIDEO_CACHE = (
    (_STATE_DIR / "asset_videos") if os.environ.get("DEARAI_STATE_DIR", "").strip()
    else Path(tempfile.gettempdir()) / "dearai_asset_videos"
)
_ASSET_VIDEO_MAX_FILES = 100        # cache eviction cap (oldest-mtime first)
_ASSET_VIDEO_MAX_BYTES = 80 * 1024 * 1024  # refuse pathologically large downloads
_asset_video_locks: dict = {}
_asset_video_locks_guard = threading.Lock()


def _known_asset_video_ids() -> set:
    """The Drive file IDs the /projects cards actually reference (each project's
    hero CHARACTER/LOCATION clip). The asset-video route serves ONLY these, so it
    can't be abused as a general Drive read-proxy for arbitrary file IDs — even
    when the OAuth gate is disabled. Backed by the 60s read_projects cache."""
    ids = set()
    try:
        for p in read_projects().get("projects", []):
            hv = p.get("hero_video")
            if hv and hv.get("file_id"):
                ids.add(hv["file_id"])
    except Exception:
        pass
    return ids


def _evict_asset_cache(max_files: int = _ASSET_VIDEO_MAX_FILES):
    """Keep the asset-video cache bounded — delete oldest files past the cap."""
    try:
        files = sorted(_ASSET_VIDEO_CACHE.glob("*.mp4"),
                       key=lambda f: f.stat().st_mtime)
        for f in files[:max(0, len(files) - max_files)]:
            try:
                f.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _asset_video_path(safe: str) -> Path:
    """Build (once) a same-origin, FASTSTART-remuxed local copy of a Drive
    asset video and return its path. Returns None on failure.

    Why a cache + remux instead of a passthrough stream: the source ref MP4s
    are typically NOT faststart (moov atom at the END), so a streaming proxy
    makes the browser stall re-ranging for the moov. We download the file once,
    remux to +faststart with ffmpeg (stream-copy, no re-encode — instant), and
    serve the result with Flask send_file (native, fast Range support). If
    ffmpeg isn't on PATH we still serve the cached raw bytes (much better than
    per-range Drive round-trips)."""
    import shutil as _sh
    cached = _ASSET_VIDEO_CACHE / f"{safe}.mp4"
    if cached.exists() and cached.stat().st_size > 0:
        return cached
    # One builder at a time per id (avoid duplicate downloads on concurrent hover).
    with _asset_video_locks_guard:
        lock = _asset_video_locks.setdefault(safe, threading.Lock())
    with lock:
        if cached.exists() and cached.stat().st_size > 0:
            return cached
        _ASSET_VIDEO_CACHE.mkdir(parents=True, exist_ok=True)
        _evict_asset_cache()
        raw = _ASSET_VIDEO_CACHE / f".{safe}.raw.mp4"
        try:
            from auth import get_credentials
            from google.auth.transport.requests import Request as _GReq
            import requests as _rq
            creds = get_credentials()
            if not getattr(creds, "valid", False):
                creds.refresh(_GReq())
            url = (f"https://www.googleapis.com/drive/v3/files/{safe}"
                   f"?alt=media&supportsAllDrives=true")
            # timeout kept well under the gunicorn worker --timeout (120s): a
            # 45s download + 45s remux worst-case stays inside the window so the
            # worker is never SIGKILLed mid-build.
            r = _rq.get(url, headers={"Authorization": f"Bearer {creds.token}"},
                        stream=True, timeout=45)
            if r.status_code != 200:
                print(f"[asset-video] download {r.status_code} for {safe}")
                return None
            total = 0
            with open(raw, "wb") as fh:
                for chunk in r.iter_content(chunk_size=262144):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > _ASSET_VIDEO_MAX_BYTES:
                        raise ValueError(f"asset video exceeds {_ASSET_VIDEO_MAX_BYTES} bytes")
                    fh.write(chunk)
            ff = _sh.which("ffmpeg")
            if ff:
                fs = _ASSET_VIDEO_CACHE / f".{safe}.fs.mp4"
                try:
                    import subprocess
                    subprocess.run(
                        [ff, "-y", "-loglevel", "error", "-i", str(raw),
                         "-c", "copy", "-movflags", "+faststart", str(fs)],
                        check=True, timeout=45)
                    os.replace(fs, cached)
                    raw.unlink(missing_ok=True)
                except Exception as e:
                    print(f"[asset-video] faststart remux failed for {safe}: {e}; serving raw")
                    os.replace(raw, cached)
            else:
                os.replace(raw, cached)
            return cached
        except Exception as e:
            print(f"[asset-video] cache build failed for {safe}: {e}")
            try:
                raw.unlink(missing_ok=True)
            except Exception:
                pass
            return None


@server.route("/api/asset-video/<file_id>")
def _api_asset_video(file_id):
    """Serve a CHARACTER/LOCATION reference clip as a same-origin, seekable,
    faststart MP4 for the /projects hover-play <video>. Built + cached on first
    hit by _asset_video_path; subsequent hovers are instant. Auth-gated like the
    rest of the app; the file must be readable by our credentials."""
    from flask import send_file, abort
    safe = "".join(c for c in file_id if c.isalnum() or c in "_-")
    if not safe:
        abort(404)
    # Allowlist: only serve IDs that the /projects cards actually reference, so
    # this route can never be used as a general Drive read-proxy for arbitrary
    # file IDs (confused-deputy), even if the OAuth gate is off.
    if safe not in _known_asset_video_ids():
        abort(404)
    path = _asset_video_path(safe)
    if not path:
        abort(502)
    return send_file(str(path), mimetype="video/mp4",
                     conditional=True, max_age=86400)


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

    # Browser-side cache header — match server TTL so stale tabs auto-revalidate.
    # `must-revalidate` makes browsers re-fetch instead of serving from disk
    # cache; the Render-side cache absorbs the actual sheet read load.
    cache_headers = {
        "Cache-Control": f"max-age={int(_GALLERY_TTL)}, must-revalidate",
    }

    def _personalize(html_doc: str) -> str:
        """Inject the current user's email into the cached HTML at serve time
        so the hero's user-chip + logout link show who's logged in. The HTML
        cache is per-gallery (shared across users); per-user data lives in
        these placeholders that get replaced on every request."""
        if AUTH_ENABLED:
            email = session.get("user_email", "")
        else:
            email = ""
        return html_doc.replace("__GALLERY_USER_EMAIL__", email)

    # Live-build path
    if safe in GALLERY_REGISTRY:
        sheet_id, show, episode = GALLERY_REGISTRY[safe]
        now = _t.time()
        with _gallery_cache_lock:
            cached = _gallery_cache.get(safe)
            if cached and (now - cached[0]) < _GALLERY_TTL:
                return Response(_personalize(cached[1]), mimetype="text/html", headers=cache_headers)
        # Build fresh — bibles from the series-level sheet, episode tabs from ep sheet.
        # NOTE: html_doc is cached per-gallery, NOT per-user, so user_email is
        # injected at serve-time via a string replacement below rather than baked
        # into the cached HTML.
        try:
            from build_gallery import build_html
            bible_sheet_id = _bible_sheet_for(safe)
            episodes = _episodes_for(safe)
            html_doc = build_html(
                sheet_id, show, episode,
                gallery_name=safe,
                bible_sheet_id=bible_sheet_id,
                episodes=episodes,
                verbose=False,
            )
            with _gallery_cache_lock:
                _gallery_cache[safe] = (now, html_doc)
            return Response(_personalize(html_doc), mimetype="text/html", headers=cache_headers)
        except Exception as e:
            # Live build failed — try last-known cache value (even if expired)
            with _gallery_cache_lock:
                stale = _gallery_cache.get(safe)
            if stale:
                print(f"[gallery] live build failed for {safe} ({e}); serving stale cache ({(now - stale[0]) // 60:.0f} min old)")
                return Response(_personalize(stale[1]), mimetype="text/html", headers=cache_headers)
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
           "--sheet", sheet_id, "--set", str(set_n), "--force", "--style", "master"]
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


@server.route("/api/vidgen", methods=["POST"])
def _api_vidgen():
    """Fire byteplus_vidgen.py for one set's V1 or V2 video iteration.
    Body: {"set": <N>, "slot": 1|2, "gallery": "sajangnim_ep01"}.
    Returns {"ok": true, "job_id": "...", "message": "..."}.

    Slot 1 → uses Storyboard Iter 1 as visual ref + writes video to SP!M (Video Iter 1)
    Slot 2 → uses Storyboard Iter 2 as visual ref + writes video to SP!N (Video Iter 2)

    Backed by BytePlus Seedance 2.0 via byteplus_vidgen.py (the existing
    pipeline with asset:// scheme for char refs to bypass moderation)."""
    from flask import request, jsonify
    body = request.get_json(silent=True) or {}
    set_n = body.get("set")
    slot = body.get("slot")
    gallery = body.get("gallery", "")
    if not isinstance(set_n, int) or set_n < 1:
        return jsonify({"ok": False, "error": "missing or invalid 'set'"}), 400
    if gallery not in GALLERY_REGISTRY:
        return jsonify({"ok": False,
                         "error": f"unknown gallery '{gallery}'"}), 400
    sheet_id, _show, _ep = GALLERY_REGISTRY[gallery]

    # Either V1 or V2 button click fires BOTH slots — one click → 2 videos.
    # User confirmed they want both iters every time so they can compare.
    # NO --confirm flag — that triggers an interactive y/N input() gate which
    # crashes the subprocess (no stdin); auto-submit instead, prompt preview
    # goes to the job log for /debug/jobs auditing.
    job_ids = []
    for s in (1, 2):
        job_id = uuid.uuid4().hex[:8]
        cmd = [PYTHON_BIN, "byteplus_vidgen.py",
               "--sheet", sheet_id, "--set", str(set_n),
               "--slot", str(s)]
        append_job({
            "id": job_id,
            "label": f"vidgen {gallery} set{set_n} V{s}",
            "status": "queued",
            "started": datetime.now(timezone.utc).isoformat(),
            "log": "",
            "cmd": " ".join(cmd),
            "kind": "vidgen",
            "set": set_n,
            "slot": s,
            "sheet": sheet_id,
        })
        threading.Thread(target=run_bg, args=(cmd, job_id), daemon=True).start()
        job_ids.append(job_id)

    return jsonify({
        "ok": True,
        "job_id": " + ".join(job_ids),
        "job_ids": job_ids,
        "message": f"Queued V1+V2 for {gallery} set {set_n}; check Drive in ~5 min."
    })


@server.route("/api/upload-asset", methods=["POST"])
def _api_upload_asset():
    """Accept a multipart file upload from the gallery's Upload Asset modal,
    push it to Drive (anyone-with-link reader), submit to BytePlus CreateAsset,
    poll until Active, and append a row to the Asset Library tab on the
    series-level bible sheet so the gallery picks it up on next refresh.

    Body (multipart/form-data):
      file        — the image or video to upload
      gallery     — gallery slug (e.g. sajangnim_ep01) — used to find the
                    bible sheet via SERIES_BIBLE_SHEETS
      bible_tab   — CHARACTERS / LOCATIONS / COSTUME / PROPS / EFFECTS
      name        — bible entry name (e.g. "MIN-JUN", "Walk-in cooler")
      asset_type  — Image | Video | Audio (defaults to Image)

    Returns: {ok, job_id, message} immediately; the BytePlus poll runs in a
    background thread and the gallery's existing watchJobs() picks it up
    via /debug/jobs polling.
    """
    from flask import request, jsonify
    import io
    f = request.files.get("file")
    gallery = (request.form.get("gallery") or "").strip()
    bible_tab = (request.form.get("bible_tab") or "").strip()
    name = (request.form.get("name") or "").strip()
    asset_type = (request.form.get("asset_type") or "Image").strip().capitalize()
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "no file uploaded"}), 400
    if gallery not in GALLERY_REGISTRY:
        return jsonify({"ok": False, "error": f"unknown gallery '{gallery}'"}), 400
    if not bible_tab or bible_tab.upper() not in {
        "CHARACTERS", "LOCATIONS", "COSTUME", "PROPS", "EFFECTS"
    }:
        return jsonify({"ok": False, "error": "bible_tab must be one of CHARACTERS / LOCATIONS / COSTUME / PROPS / EFFECTS"}), 400
    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    if asset_type not in {"Image", "Video", "Audio"}:
        return jsonify({"ok": False, "error": "asset_type must be Image / Video / Audio"}), 400

    bible_sheet_id = _bible_sheet_for(gallery)
    if not bible_sheet_id:
        return jsonify({"ok": False, "error": f"no series bible sheet configured for {gallery}"}), 500

    # Read file bytes once (Flask's stream is single-use, and we need them
    # for the Drive upload before the background thread starts).
    file_bytes = f.read()
    filename = f.filename
    mimetype = f.mimetype or "application/octet-stream"
    uploader_email = ""
    try:
        from flask import session as _sess
        uploader_email = (_sess.get("user_email") or "").lower()
    except Exception:
        pass

    job_id = uuid.uuid4().hex[:8]
    append_job({
        "id": job_id,
        "label": f"upload {bible_tab}/{name} ({len(file_bytes)//1024}KB)",
        "status": "queued",
        "started": datetime.now(timezone.utc).isoformat(),
        "log": "",
        "cmd": f"upload-asset gallery={gallery} bible_tab={bible_tab} name={name} type={asset_type}",
        "kind": "upload",
        "uploader": uploader_email,
        "sheet": bible_sheet_id,
    })

    def _run():
        update_job(job_id, status="running")
        log_lines: list[str] = []
        def _log(msg: str):
            log_lines.append(msg)
            update_job(job_id, log="\n".join(log_lines[-200:]))
        try:
            from auth import get_credentials
            import gspread
            from googleapiclient.discovery import build as _gbuild
            from googleapiclient.http import MediaIoBaseUpload
            creds = get_credentials()
            drive = _gbuild("drive", "v3", credentials=creds)
            gc = gspread.authorize(creds)

            # 1) Drive upload — store under <show-folder>/uploads/<bible_tab>/
            sh = gc.open_by_key(bible_sheet_id)
            show_folder = drive.files().get(fileId=bible_sheet_id, fields="parents").execute().get("parents", [None])[0]
            if not show_folder:
                raise RuntimeError(f"bible sheet {bible_sheet_id} has no parent folder")
            def _ensure_subfolder(parent: str, sub_name: str) -> str:
                q = (f"'{parent}' in parents and name='{sub_name}' "
                     f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
                hits = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
                if hits:
                    return hits[0]["id"]
                created = drive.files().create(
                    body={"name": sub_name, "parents": [parent],
                          "mimeType": "application/vnd.google-apps.folder"},
                    fields="id",
                ).execute()
                return created["id"]
            uploads_folder = _ensure_subfolder(show_folder, "uploads")
            tab_folder = _ensure_subfolder(uploads_folder, bible_tab.lower())
            # File name: <name>_<timestamp>.<ext>
            from pathlib import Path as _P
            ext = _P(filename).suffix or ".bin"
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            safe_name = "".join(c for c in name if c.isalnum() or c in "-_") or "asset"
            target_name = f"{safe_name}_{ts}{ext}"
            _log(f"[1/4] Uploading to Drive: uploads/{bible_tab.lower()}/{target_name}")
            media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype, resumable=False)
            new_file = drive.files().create(
                body={"name": target_name, "parents": [tab_folder]},
                media_body=media,
                fields="id,webViewLink",
            ).execute()
            drive.permissions().create(
                fileId=new_file["id"],
                body={"role": "reader", "type": "anyone"},
                fields="id",
            ).execute()
            drive_view_url = new_file["webViewLink"]
            drive_id_val = new_file["id"]
            # BytePlus needs a publicly-fetchable URL — use the lh3 CDN form
            # which auto-resolves redirects vs. /file/d/<id>/view.
            byteplus_source_url = f"https://lh3.googleusercontent.com/d/{drive_id_val}=w2400"
            _log(f"     ✓ Drive id={drive_id_val}")

            # 2) BytePlus CreateAsset — uses BYTEPLUS_GROUP_ID env var
            group_id = os.environ.get("BYTEPLUS_GROUP_ID", "").strip()
            if not group_id:
                raise RuntimeError(
                    "BYTEPLUS_GROUP_ID env var not set on Render. "
                    "Run `python3 byteplus_asset_v2.py create-group --name DDACS` "
                    "locally once, then add the printed GROUP_ID as an env var."
                )
            _log(f"[2/4] BytePlus CreateAsset group={group_id} type={asset_type}")
            sys.path.insert(0, str(PROJECT_ROOT))
            import byteplus_asset_v2 as bp
            asset_id = bp.create_asset(group_id, byteplus_source_url, asset_type, name=name)
            _log(f"     ✓ asset_id={asset_id}")

            # 3) Poll until Active
            _log(f"[3/4] Polling BytePlus until asset Active (~30-120s)…")
            try:
                bp.poll_asset(asset_id, timeout=300)
                _log("     ✓ asset Active")
            except SystemExit as e:
                # poll_asset calls sys.exit on Failed — translate to job failure
                raise RuntimeError(str(e))

            # 4) Append row to Asset Library tab
            _log("[4/4] Writing Asset Library row")
            try:
                ws = sh.worksheet("Asset Library")
            except Exception:
                raise RuntimeError("Asset Library tab not found on bible sheet")
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            # Asset Library cols A-L per build_gallery.read_asset_library:
            #   A=Name, B=Bible Tab, C=Asset Code, D=Source URL,
            #   E=Asset Type, F=Status, G=Uploaded At, H..L=other
            new_row = [
                name, bible_tab.upper(), asset_id, drive_view_url,
                asset_type.lower(), "Uploaded", now_iso,
                "", "", "", "", uploader_email or "",
            ]
            ws.append_row(new_row, value_input_option="USER_ENTERED",
                          insert_data_option="INSERT_ROWS",
                          table_range="A4")  # below the header at row 4

            # Flush gallery + bible caches so the new row shows up immediately
            with _gallery_cache_lock:
                _gallery_cache.clear()
            try:
                from build_gallery import _bible_cache, _bible_cache_lock
                with _bible_cache_lock:
                    _bible_cache.clear()
            except Exception:
                pass

            update_job(
                job_id, status="done",
                log="\n".join(log_lines[-200:] +
                              [f"[done] asset_id={asset_id} drive={drive_view_url}"]),
                ended=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            log_lines.append(f"[FAIL] {err}")
            update_job(job_id, status="failed",
                       log="\n".join(log_lines[-200:]),
                       ended=datetime.now(timezone.utc).isoformat())

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({
        "ok": True,
        "job_id": job_id,
        "message": f"Queued upload of {name} ({bible_tab}); typical wall time ~60-120s.",
    })


@server.route("/api/new-project", methods=["POST"])
def _api_new_project():
    """Create a new project, optionally from an uploaded script file."""
    from flask import request, jsonify

    is_multipart_request = (request.mimetype or "").lower() == "multipart/form-data"
    uploaded = request.files.get("file")
    multipart_mode = uploaded is not None
    body = {} if is_multipart_request else (request.get_json(silent=True) or {})
    form = request.form if is_multipart_request else {}

    title = ((form.get("title") if multipart_mode else body.get("title")) or "").strip()
    raw_slug = (body.get("slug") or "").strip() if not multipart_mode else ""
    ptype = ((form.get("type") if multipart_mode else body.get("type")) or "series").strip().lower()
    locale = ((form.get("locale") if multipart_mode else body.get("locale")) or "generic").strip().lower()
    depth = ((form.get("depth") if multipart_mode else body.get("depth")) or "").strip().lower()
    global_preset = ((form.get("global_preset") if multipart_mode else body.get("global_preset")) or "").strip().lower()
    parent_show = ((form.get("parent_show") if multipart_mode else body.get("parent_show")) or "").strip()
    notes = ((form.get("notes") if multipart_mode else body.get("notes")) or "").strip()

    if not title:
        return jsonify({"ok": False, "error": "Title is required"}), 400
    if ptype not in {"series", "poc", "concept", "client"}:
        return jsonify({"ok": False,
                         "error": f"type must be one of series/poc/concept/client (got {ptype!r})"}), 400
    if locale not in {"generic", "jakarta", "manila", "seoul"}:
        return jsonify({"ok": False,
                         "error": f"locale must be one of generic/jakarta/manila/seoul (got {locale!r})"}), 400
    if multipart_mode and depth not in {"text", "bibles", "masters"}:
        return jsonify({"ok": False,
                         "error": "depth must be one of text/bibles/masters"}), 400
    if is_multipart_request and not multipart_mode:
        return jsonify({"ok": False, "error": "file is required"}), 400
    if multipart_mode and (not uploaded or not uploaded.filename):
        return jsonify({"ok": False, "error": "file is required"}), 400
    if not MASTER_PROJECTS_SHEET_ID:
        return jsonify({"ok": False,
                         "error": "MASTER_PROJECTS_SHEET_ID not set on server"}), 500

    # Derive slug from title if not given. Lowercase, alnum + dashes only.
    if raw_slug:
        slug = re.sub(r"[^a-z0-9_-]+", "-", raw_slug.lower()).strip("-")
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    if not slug:
        return jsonify({"ok": False, "error": "could not derive a valid slug from the title"}), 400

    try:
        from auth import get_credentials
        import gspread
        gc_check = gspread.authorize(get_credentials())
        ws_check = gc_check.open_by_key(MASTER_PROJECTS_SHEET_ID).worksheet("Projects")
        existing_slugs = {s.strip() for s in ws_check.col_values(1)[1:] if s.strip()}
    except Exception as e:
        return jsonify({"ok": False,
                         "error": f"could not read master Projects sheet: {e}"}), 500
    if slug in existing_slugs:
        return jsonify({"ok": False,
                         "error": f"slug '{slug}' already exists. Pick a different one."}), 400

    # Owner email from session if auth is on
    owner_email = "unknown"
    try:
        owner_email = (session.get("user_email") or "").lower() or "unknown"
    except Exception:
        pass

    job_id = "job-" + datetime.utcnow().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8]
    gallery_slug = slug + "_ep01"
    redirect_url = "/gallery/" + gallery_slug
    source_path = ""
    parsed_path = ""
    source_ext = ""
    source_mimetype = "application/octet-stream"
    # Per-episode bundle: [(ep_num, title, script_txt_path, ep_text)] — populated
    # when the parser detects multiple EPISODE markers in the uploaded script.
    # Always has at least 1 entry when multipart_mode is True.
    episodes_meta: list[tuple[int, str, str, str]] = []
    if multipart_mode:
        source_ext = Path(uploaded.filename).suffix.lower()
        if source_ext not in {".txt", ".md", ".docx", ".pdf"}:
            return jsonify({"ok": False,
                             "error": "file must be one of .txt, .md, .docx, .pdf"}), 400
        source_path = f"/tmp/script_{job_id}{source_ext}"
        parsed_path = f"/tmp/script_{job_id}.txt"
        source_mimetype = uploaded.mimetype or "application/octet-stream"
        uploaded.save(source_path)
        split_dir = f"/tmp/script_{job_id}_episodes"
        try:
            from _parse_script import parse_script
            parse_result = parse_script(source_path, parsed_path, split_dir=split_dir)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        for (ep_num, title_auto, ep_text), ep_path in zip(
            parse_result["episodes"], parse_result["episode_paths"]
        ):
            episodes_meta.append((ep_num, title_auto, str(ep_path), ep_text))

    append_job({
        "id": job_id,
        "label": f"new-project {slug} ({title})",
        "status": "queued",
        "started": datetime.now(timezone.utc).isoformat(),
        "log": "",
        "cmd": f"_create_blank_sot.py --name {title!r}" +
               (f" -> generation depth={depth}" if multipart_mode else ""),
        "kind": "new-project",
        "slug": slug,
        "type": ptype,
        "depth": depth,
        "owner": owner_email,
    })

    def _run():
        update_job(job_id, status="running")
        log_lines: list[str] = []
        def _log(msg: str):
            log_lines.append(msg)
            update_job(job_id, log="\n".join(log_lines[-200:]))
        def _parse_create_stdout(stdout: str) -> tuple[str, str]:
            try:
                payload = json.loads(stdout)
                sheet = payload.get("sheet_id", "")
                folder = payload.get("drive_folder_id", "")
                if sheet and folder:
                    return sheet, folder
            except Exception:
                pass
            sheet = ""
            folder = ""
            for line in stdout.splitlines():
                m = re.search(r"folders/([a-zA-Z0-9_-]{20,})", line)
                if m and not folder:
                    folder = m.group(1)
                m = re.search(r"spreadsheets/d/([a-zA-Z0-9_-]{20,})", line)
                if m and not sheet:
                    sheet = m.group(1)
            return sheet, folder
        def _update_project_status(ws, row_num: int, status: str):
            try:
                ws.update_cell(row_num, 11, status)
            except Exception as e:
                _log(f"  ! failed to update Projects!K{row_num}: {e}")
        def _run_stage(stage: str, cmd: list[str]):
            _log(f"[stage:{stage}] {' '.join(cmd)}")
            proc = subprocess.run(
                cmd, cwd=str(PROJECT_ROOT),
                capture_output=True, text=True, timeout=3600,
            )
            if proc.stdout:
                for line in proc.stdout.splitlines():
                    _log(f"  {line}")
            if proc.stderr:
                for line in proc.stderr.splitlines():
                    _log(f"  stderr: {line}")
            if proc.returncode != 0:
                tail = "\n".join(((proc.stdout or "") + "\n" + (proc.stderr or "")).splitlines()[-20:])
                raise RuntimeError(f"{stage} failed exit={proc.returncode}\n{tail}")
        # Each per-episode sheet lives in the same show folder; the gallery
        # registry auto-detects them by name pattern (Ep N — Title).
        # ep_sheets is [(ep_num, title, sheet_id, parsed_script_path), ...] —
        # populated as we create each one. For text-only (no multipart) flow,
        # ep_sheets stays empty and the rest of the worker uses sheet_id/folder_id
        # directly like before.
        ep_sheets: list[tuple[int, str, str, str]] = []
        failed_project_status = "Failed: setup"
        try:
            # Determine sheet naming. Multi-episode → 'Ep 1 — Title' so the
            # discovery regex picks it up. Single-episode → keep '<show> — SOT'
            # for backwards compat (sajangnim-style).
            is_multi_episode = len(episodes_meta) > 1
            if is_multi_episode:
                ep1_num, ep1_title, ep1_path, _ = episodes_meta[0]
                first_sheet_name = f"Ep {ep1_num} — {ep1_title}"
                _log(f"[1/5] Detected {len(episodes_meta)} episode(s) — multi-episode mode")
                _log(f"      Ep 1 sheet name: {first_sheet_name}")
            else:
                first_sheet_name = f"{title} — SOT"
                _log(f"[1/5] _create_blank_sot.py --name {title!r}")
            # First _create_blank_sot.py run — creates the show folder + storyboards/
            # + videos/ subfolders + the FIRST spreadsheet. Subsequent episodes
            # reuse the folder via --in-folder.
            cmd = [sys.executable, "_create_blank_sot.py",
                   "--name", title, "--sheet-name", first_sheet_name]
            if global_preset:
                cmd += ["--global-preset", global_preset]
            proc = subprocess.run(
                cmd, cwd=str(PROJECT_ROOT),
                capture_output=True, text=True, timeout=3600,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            for line in stdout.splitlines():
                _log(f"  {line}")
            if proc.returncode != 0:
                if stderr:
                    _log(f"  stderr: {stderr[:500]}")
                raise RuntimeError(f"_create_blank_sot.py exit={proc.returncode}")

            sheet_id, folder_id = _parse_create_stdout(stdout)
            if not sheet_id or not folder_id:
                raise RuntimeError(
                    f"could not parse sheet/folder IDs from _create_blank_sot.py output. "
                    f"sheet={sheet_id!r}, folder={folder_id!r}. stdout: {stdout[:300]}"
                )
            _log(f"  ✓ sheet={sheet_id}, folder={folder_id}")

            # Single-episode flow: ep_sheets keeps the single-row shape
            # so [5/5] generation code can iterate uniformly. parsed_path
            # may be empty if !multipart_mode — in that case ep_sheets
            # stays empty and the for-loop runs zero times.
            if multipart_mode and episodes_meta:
                ep0_num, ep0_title, ep0_path, _ = episodes_meta[0]
                ep_sheets.append((ep0_num, ep0_title, sheet_id, ep0_path))
            # NOTE: extra episode sheets (Ep 2..N) are now created LATER, in
            # the background phase after _setup_done.set(). This keeps the
            # blocking section under Render's gateway timeout (~100s).

            script_drive_url = ""
            from auth import get_credentials
            import gspread
            from googleapiclient.discovery import build as _gbuild
            from googleapiclient.http import MediaFileUpload
            creds = get_credentials()
            gc = gspread.authorize(creds)
            drive = _gbuild("drive", "v3", credentials=creds)

            if multipart_mode:
                _log("[2/5] Uploading original + parsed script to Drive")
                original = drive.files().create(
                    body={"name": f"script{source_ext}", "parents": [folder_id]},
                    media_body=MediaFileUpload(source_path, mimetype=source_mimetype, resumable=False),
                    fields="id,webViewLink",
                    supportsAllDrives=True,
                ).execute()
                drive.permissions().create(
                    fileId=original["id"],
                    body={"role": "reader", "type": "anyone"},
                    fields="id",
                ).execute()
                script_drive_url = f"https://drive.google.com/file/d/{original['id']}/view"
                parsed = drive.files().create(
                    body={"name": "script_parsed.txt", "parents": [folder_id]},
                    media_body=MediaFileUpload(parsed_path, mimetype="text/plain", resumable=False),
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
                drive.permissions().create(
                    fileId=parsed["id"],
                    body={"role": "reader", "type": "anyone"},
                    fields="id",
                ).execute()
                _log(f"  ✓ script={original['id']} parsed={parsed['id']}")

                # Multi-episode: also upload per-episode script files for
                # producer reference (one .txt per episode in the show folder)
                if len(episodes_meta) > 1:
                    for ep_num, ep_title, ep_path, _ in episodes_meta:
                        try:
                            ep_uploaded = drive.files().create(
                                body={"name": f"ep_{ep_num:02d}_script.txt",
                                      "parents": [folder_id]},
                                media_body=MediaFileUpload(
                                    ep_path, mimetype="text/plain", resumable=False),
                                fields="id",
                                supportsAllDrives=True,
                            ).execute()
                            drive.permissions().create(
                                fileId=ep_uploaded["id"],
                                body={"role": "reader", "type": "anyone"},
                                fields="id",
                            ).execute()
                        except Exception as e:
                            _log(f"  ! ep_{ep_num:02d}_script.txt upload failed: {e}")
                    _log(f"  ✓ uploaded {len(episodes_meta)} per-episode script(s)")

            _log("[3/5] Appending row to master Projects sheet")
            sh = gc.open_by_key(MASTER_PROJECTS_SHEET_ID)
            ws = sh.worksheet("Projects")
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            new_row = [
                slug, title, ptype, "draft",
                sheet_id, folder_id, parent_show, owner_email, now_iso,
                script_drive_url,
                "generating" if multipart_mode else "pending",
                notes,
            ]
            append_result = ws.append_row(
                new_row, value_input_option="USER_ENTERED",
                insert_data_option="INSERT_ROWS", table_range="A1"
            )
            row_num = 0
            updated_range = ((append_result or {}).get("updates") or {}).get("updatedRange", "")
            m = re.search(r"!A(\d+):", updated_range)
            if m:
                row_num = int(m.group(1))
            if not row_num:
                found = ws.find(slug, in_column=1)
                row_num = found.row if found else 0
            _log(f"  ✓ row appended at Projects!A{row_num or '?'}")

            _log("[4/5] Flushing read_projects cache")
            cache_del(_PROJECTS_KEY)
            _log("  ✓ cache flushed; new project visible at /projects")

            # Setup is complete — the gallery URL is now addressable. Signal
            # the endpoint to return success. The generation chain below
            # continues in this same thread but the user is no longer blocked.
            _setup_done.set()

            # Multi-episode background phase: create Ep 2..N sheets NOW that
            # the user has been redirected. Each _create_blank_sot.py --in-folder
            # run takes ~15-25s; doing this serially in the background keeps the
            # blocking section fast while still landing all episodes within
            # a few minutes total.
            if is_multi_episode and multipart_mode:
                _log(f"[5/5-pre] Creating {len(episodes_meta) - 1} additional episode sheet(s) in background")
                for ep_num, ep_title, ep_path, _ in episodes_meta[1:]:
                    extra_sheet_name = f"Ep {ep_num} — {ep_title}"
                    _log(f"  _create_blank_sot.py --in-folder ... '{extra_sheet_name}'")
                    cmd_extra = [sys.executable, "_create_blank_sot.py",
                                 "--name", f"{title} Ep {ep_num}",
                                 "--in-folder", folder_id,
                                 "--sheet-name", extra_sheet_name]
                    if global_preset:
                        cmd_extra += ["--global-preset", global_preset]
                    proc_extra = subprocess.run(
                        cmd_extra, cwd=str(PROJECT_ROOT),
                        capture_output=True, text=True, timeout=3600,
                    )
                    stdout_extra = proc_extra.stdout or ""
                    if proc_extra.returncode != 0:
                        if proc_extra.stderr:
                            _log(f"    stderr: {proc_extra.stderr[:500]}")
                        raise RuntimeError(
                            f"_create_blank_sot.py (ep {ep_num}) exit={proc_extra.returncode}")
                    extra_sheet, _ = _parse_create_stdout(stdout_extra)
                    if not extra_sheet:
                        raise RuntimeError(
                            f"could not parse sheet ID for ep {ep_num}. stdout: {stdout_extra[:200]}")
                    ep_sheets.append((ep_num, ep_title, extra_sheet, ep_path))
                    _log(f"    ✓ ep {ep_num} sheet={extra_sheet}")

            if multipart_mode and ep_sheets:
                ep_count = len(ep_sheets)
                _log(f"[5/5] Running generation chain depth={depth} across {ep_count} episode(s)")

                def _setup_storyboard_folders(ep_num: int, ep_sheet_id: str) -> None:
                    """Per-episode: create storyboards/ep_NN/set-NN/ folders +
                    populate Storyboard Prompts!E with their URLs. Without
                    this, storyboard_generate.py fails every set with
                    'bad folder url'.

                    Reads the actual set count from the Storyboard Prompts
                    tab (Claude wrote rows for each set of 5 shots), so this
                    must run AFTER shotlist_gen.py.
                    """
                    try:
                        sp_ws = gc.open_by_key(ep_sheet_id).worksheet("Storyboard Prompts")
                        set_nums = [r[0] for r in sp_ws.get("A11:A100") if r and r[0].strip()]
                        if not set_nums:
                            _log(f"    no sets in Storyboard Prompts — skipping folder setup")
                            return
                        # Find/create the storyboards/ subfolder under the show folder
                        sb_parent = drive.files().list(
                            q=f"'{folder_id}' in parents and name='storyboards' and "
                              f"mimeType='application/vnd.google-apps.folder' and trashed=false",
                            fields="files(id)", supportsAllDrives=True,
                        ).execute().get("files", [])
                        if not sb_parent:
                            _log(f"    no storyboards/ subfolder found — skipping")
                            return
                        sb_parent_id = sb_parent[0]["id"]
                        # ep_NN/ subfolder
                        ep_folder_name = f"ep_{ep_num:02d}"
                        ep_existing = drive.files().list(
                            q=f"'{sb_parent_id}' in parents and name='{ep_folder_name}' and "
                              f"mimeType='application/vnd.google-apps.folder' and trashed=false",
                            fields="files(id)", supportsAllDrives=True,
                        ).execute().get("files", [])
                        if ep_existing:
                            ep_folder_id_local = ep_existing[0]["id"]
                        else:
                            ep_folder = drive.files().create(body={
                                "name": ep_folder_name,
                                "mimeType": "application/vnd.google-apps.folder",
                                "parents": [sb_parent_id],
                            }, fields="id", supportsAllDrives=True).execute()
                            ep_folder_id_local = ep_folder["id"]
                        # set-NN/ subfolders + URLs
                        urls = []
                        for s in set_nums:
                            set_name = f"set-{int(s):02d}"
                            existing = drive.files().list(
                                q=f"'{ep_folder_id_local}' in parents and name='{set_name}' and "
                                  f"mimeType='application/vnd.google-apps.folder' and trashed=false",
                                fields="files(id)", supportsAllDrives=True,
                            ).execute().get("files", [])
                            if existing:
                                set_id = existing[0]["id"]
                            else:
                                set_f = drive.files().create(body={
                                    "name": set_name,
                                    "mimeType": "application/vnd.google-apps.folder",
                                    "parents": [ep_folder_id_local],
                                }, fields="id", supportsAllDrives=True).execute()
                                set_id = set_f["id"]
                                try:
                                    drive.permissions().create(
                                        fileId=set_id,
                                        body={"role": "reader", "type": "anyone"},
                                        fields="id",
                                    ).execute()
                                except Exception:
                                    pass
                            urls.append([f"https://drive.google.com/drive/folders/{set_id}"])
                        sp_ws.update(
                            range_name=f"E11:E{10 + len(urls)}",
                            values=urls,
                            value_input_option="USER_ENTERED",
                        )
                        _log(f"    ✓ created storyboards/{ep_folder_name}/set-NN/ × {len(urls)} + wrote col E")
                    except Exception as e:
                        _log(f"    ! folder setup failed: {type(e).__name__}: {e}")

                try:
                    for ep_num, ep_title, ep_sheet_id, ep_script_path in ep_sheets:
                        ep_label = f"Ep {ep_num} — {ep_title}"
                        _log(f"  -- {ep_label} -> {ep_sheet_id}")
                        _run_stage(f"shotlist-ep{ep_num}", [
                            sys.executable, "shotlist_gen.py",
                            "--script", ep_script_path,
                            "--sheet", ep_sheet_id,
                            "--name", ep_label,
                            "--locale", locale,
                        ])
                        # New pipeline (no stick-figure storyboards):
                        #   shotlist -> asset refs -> 1-2 master shots/scene.
                        # 1) Asset reference images (character/location/prop bibles)
                        if depth in {"bibles", "masters"}:
                            _run_stage(f"asset-refs-ep{ep_num}", [
                                sys.executable, "imggen_all_assets.py",
                                "--sheet", ep_sheet_id,
                            ])
                        # 2) Master shots — 1-2 rendered wide establishing frames
                        # per scene, in the chosen global look. Reuses the
                        # storyboard folder tree + storyboard_generate's --style
                        # master mode (writes to Storyboard Prompts G/H).
                        if depth == "masters":
                            _setup_storyboard_folders(ep_num, ep_sheet_id)
                            _run_stage(f"masters-ep{ep_num}", [
                                sys.executable, "storyboard_generate.py",
                                "--sheet", ep_sheet_id, "--style", "master",
                            ])
                except Exception as e:
                    stage = "generation"
                    msg = str(e)
                    if msg.startswith("shotlist"):
                        stage = "shotlist"
                    elif msg.startswith("asset-refs"):
                        stage = "asset refs"
                    elif msg.startswith("masters"):
                        stage = "master shots"
                    elif msg.startswith("bibles"):
                        stage = "bibles"
                    failed_project_status = f"Failed: {stage}"
                    if row_num:
                        _update_project_status(ws, row_num, failed_project_status)
                    raise
                if row_num:
                    _update_project_status(ws, row_num, "Done")
                _log("  ✓ generation chain completed")

            update_job(job_id, status="done",
                       log="\n".join(log_lines[-200:]),
                       ended=datetime.now(timezone.utc).isoformat())
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            log_lines.append(f"[FAIL] {err}")
            if "ws" in locals() and "row_num" in locals() and row_num:
                try:
                    ws.update_cell(row_num, 11, failed_project_status)
                except Exception:
                    pass
            update_job(job_id, status="failed",
                       log="\n".join(log_lines[-200:]),
                       ended=datetime.now(timezone.utc).isoformat())
            # Capture the error so the endpoint can return it if setup failed
            _setup_error.append(err)
        finally:
            # Always signal — covers the case where setup itself raised
            # before we reached the post-cache-flush set() call.
            _setup_done.set()

    # Block the response until project SETUP is done (folder + sheet + master
    # row + cache flush). The slow generation chain (shotlist_gen → storyboards
    # → bibles) continues in the same thread after the setup signal fires.
    # Setup typically takes 15-40 sec. 90 sec timeout is the hard ceiling.
    _setup_done = threading.Event()
    _setup_error: list[str] = []

    threading.Thread(target=_run, daemon=True).start()

    if not _setup_done.wait(timeout=90):
        return jsonify({
            "ok": False,
            "error": "Project setup timed out after 90 seconds. Check /debug/jobs for details.",
            "job_id": job_id,
        }), 504
    if _setup_error:
        return jsonify({
            "ok": False,
            "error": f"Setup failed: {_setup_error[0]}",
            "job_id": job_id,
        }), 500

    return jsonify({
        "ok": True,
        "slug": slug,
        "gallery_slug": gallery_slug,
        "job_id": job_id,
        "redirect_url": redirect_url,
        "message": f"Project '{slug}' created. Generation continuing in background.",
    })


@server.route("/api/project-cover/<slug>", methods=["POST"])
def _api_project_cover(slug):
    """Upload a cover image for one project to its show's Drive folder.
    The cover is detected by name (cover.{jpg,png,webp,jpeg}) in read_projects(),
    so we just upload + overwrite + flush the projects cache.

    Body (multipart/form-data):
      file — image file (jpg / png / webp)

    Returns: {ok, cover_url, message}
    """
    from flask import request, jsonify
    import io
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "no file uploaded"}), 400

    # Look up the project's Drive folder from the master sheet
    data = read_projects(force=True)
    proj = next((p for p in data["projects"] if p["slug"] == slug), None)
    if not proj:
        return jsonify({"ok": False, "error": f"unknown project '{slug}'"}), 404
    folder_id = proj.get("drive_folder_id", "")
    if not folder_id:
        return jsonify({"ok": False, "error": f"project '{slug}' has no drive_folder_id"}), 400

    # File extension from upload (jpg, png, webp, jpeg only)
    from pathlib import Path as _P
    ext = (_P(f.filename).suffix or ".jpg").lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext not in {"jpg", "png", "webp"}:
        return jsonify({"ok": False, "error": f"unsupported image type .{ext} (jpg/png/webp only)"}), 400

    file_bytes = f.read()
    mimetype = f.mimetype or f"image/{ext}"

    try:
        from auth import get_credentials
        from googleapiclient.discovery import build as _drive_build
        from googleapiclient.http import MediaIoBaseUpload
        creds = get_credentials()
        drive = _drive_build("drive", "v3", credentials=creds)

        # Trash any existing cover.* in the folder before uploading new one.
        existing = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false "
              f"and (name='cover.jpg' or name='cover.png' or name='cover.webp')",
            fields="files(id,name)",
        ).execute().get("files", [])
        for old in existing:
            try:
                drive.files().update(fileId=old["id"], body={"trashed": True}).execute()
            except Exception:
                pass

        # Upload the new cover
        target_name = f"cover.{ext}"
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype, resumable=False)
        new_file = drive.files().create(
            body={"name": target_name, "parents": [folder_id]},
            media_body=media,
            fields="id,webViewLink",
        ).execute()
        drive.permissions().create(
            fileId=new_file["id"],
            body={"role": "reader", "type": "anyone"},
            fields="id",
        ).execute()
        cover_url = f"https://lh3.googleusercontent.com/d/{new_file['id']}=w800"

        # Flush projects cache so the cover shows up on next /projects load
        cache_del(_PROJECTS_KEY)

        return jsonify({
            "ok": True,
            "cover_url": cover_url,
            "drive_id": new_file["id"],
            "message": f"Cover uploaded ({len(file_bytes)//1024}KB) for {slug}",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


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
    _debug_guard()
    from flask import jsonify
    br.invalidate_all_caches()
    return jsonify({"ok": True, "msg": "all bible_reader caches invalidated"})


@server.route("/debug/anthropic")
def _debug_anthropic():
    """Sanity-check: is the Anthropic atomizer wired up on this Render
    instance? Returns whether ANTHROPIC_API_KEY is set, the anthropic
    package imports, and (if both) a 1-token ping to validate the key
    actually works. Use this before debugging why shotlist_gen.py fell
    back to the heuristic."""
    _debug_guard()
    from flask import jsonify
    out: dict = {}
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    out["key_set"] = bool(key)
    out["key_chars"] = len(key)
    out["model"] = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    try:
        import anthropic
        out["package_importable"] = True
        out["package_version"] = getattr(anthropic, "__version__", "?")
    except Exception as e:
        out["package_importable"] = False
        out["import_error"] = f"{type(e).__name__}: {e}"
        return jsonify(out)
    if not key:
        out["ping"] = "skipped (no key)"
        return jsonify(out)
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=out["model"],
            max_tokens=8,
            messages=[{"role": "user", "content": "say OK"}],
        )
        out["ping"] = "ok"
        out["ping_text"] = (msg.content[0].text if msg.content else "")[:40]
        out["ping_input_tokens"] = msg.usage.input_tokens
        out["ping_output_tokens"] = msg.usage.output_tokens
    except Exception as e:
        out["ping"] = "failed"
        out["ping_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return jsonify(out)


@server.route("/debug/higgs")
def _debug_higgs():
    """Run `higgs auth token` and `higgs version` and report exit codes +
    output. Use this to figure out why the CLI auth check fails for
    storyboard / bible regen subprocesses even when credentials.json
    is on disk."""
    _debug_guard()
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
    _debug_guard()
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
<html lang="en"><head>
<title>{%title%}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script>
  // Dark/light mode — shared with the COVEN/WHF galleries via the same
  // localStorage key ('gallery_dark_mode'), so the theme follows the user
  // across /projects, the galleries, and this dashboard.
  function applyDarkMode(on) {
    document.documentElement.setAttribute('data-theme', on ? 'dark' : 'light');
    var btn = document.getElementById('dark-toggle');
    if (btn) { btn.textContent = on ? '\\u2600' : '\\u{1F319}'; }
  }
  function toggleDarkMode() {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    applyDarkMode(!isDark);
    try { localStorage.setItem('gallery_dark_mode', !isDark ? '1' : '0'); } catch (e) {}
  }
  // Pre-paint: apply saved pref (or OS preference) before first render to avoid a flash.
  (function() {
    var saved = null;
    try { saved = localStorage.getItem('gallery_dark_mode'); } catch (e) {}
    var on;
    if (saved === '1') on = true;
    else if (saved === '0') on = false;
    else on = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyDarkMode(on);
    // Re-sync the toggle icon once the button exists (it's rendered after this script).
    window.addEventListener('DOMContentLoaded', function() {
      applyDarkMode(document.documentElement.getAttribute('data-theme') === 'dark');
    });
  })();
</script>
{%favicon%}{%css%}
</head><body>
<button id="dark-toggle" type="button" onclick="toggleDarkMode()"
        title="Toggle dark / light mode (saved in your browser)"
        aria-label="Toggle dark mode">&#127769;</button>
{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""


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


def video_cell(embed_url: str, label: str = "", aspect: str = "1/1"):
    """Inline iframe tile for a Drive-hosted video. Uses Drive's HTML5 player
    via /preview — plays in place, no lightbox. Used by bible cards where
    the ref is a video (e.g., character refs that ARE motion clips).

    Defaults to 1:1 because character ref clips are typically square; locations
    are still wide. Override via `aspect` if needed."""
    if not embed_url:
        return html.Div(className="img-cell", style={"aspectRatio": aspect}, children=[
            html.Div("(no video)", style={"color": "#a0a0a0", "fontStyle": "italic",
                                            "display": "flex", "alignItems": "center",
                                            "justifyContent": "center", "height": "100%"})
        ])
    return html.Div(className="img-cell",
                    style={"aspectRatio": aspect, "position": "relative",
                           "overflow": "hidden", "borderRadius": "8px",
                           "background": "#000"},
                    children=[
        html.Iframe(src=embed_url, style={
            "width": "100%", "height": "100%", "border": "0", "display": "block",
        }, allow="autoplay"),
        html.Div(label, style={
            "position": "absolute", "left": "8px", "bottom": "8px",
            "background": "#1a1a1a", "color": "#fff",
            "fontSize": "9px", "letterSpacing": "0.4px",
            "textTransform": "uppercase", "fontWeight": 600,
            "padding": "3px 8px", "borderRadius": "6px",
            "pointerEvents": "none",
        }) if label else None,
    ])


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
    # Pick aspect ratio from the iter kind so video tiles stay square (matches
    # the cut clips) and image tiles stay wide. If mixed, default to 16/9.
    kinds = {it.get("kind", "image") for it in iters}
    aspect = "1/1" if kinds == {"video"} else "16/9"

    def _cell(it):
        if it.get("kind") == "video" and it.get("embed"):
            return video_cell(it["embed"], it.get("label", ""), aspect=aspect)
        return img_cell(it.get("thumb", ""), it.get("label", ""), it.get("view", ""), aspect=aspect)

    grid = html.Div(style={"display": "grid", "gridTemplateColumns": cols, "gap": "4px",
                           "background": "#e3e3e3"},
                    children=[_cell(it) for it in iters]) if iters else \
            html.Div(style={"aspectRatio": "16/9", "background": "#e3e3e3",
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
            dcc.Tab(label="Master Shots", value="storyboards",
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
            html.Button("⚡ Generate all pending master shots",
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
                   "--sheet", sheet_id, "--set", str(set_n), "--force", "--style", "master"]
            label = f"sb-gen set{set_n}"
            kind_tag = "storyboard"
        else:
            cmd = [PYTHON_BIN, "byteplus_vidgen.py",
                   "--sheet", sheet_id, "--set", str(set_n), "--slot", str(slot),
                   "--resolution", "480p", "--duration", "15", "--aspect", "9:16"]
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
                "Generate Master Shot",
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
    cmd = [PYTHON_BIN, "storyboard_generate.py", "--sheet", sheet_id, "--set", str(set_n), "--force", "--style", "master"]
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
               "--resolution", "480p", "--duration", "15", "--aspect", "9:16"]
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


# --- Boot-time gallery cache primer -------------------------------------
# Render's first request after a cold start eats the full Sheets API tax
# (read_projects + every bible + every gallery build) — usually ~30s, the
# pain point the team complains about. This primer fires on a daemon
# thread at app boot, walks each gallery in the master Projects sheet,
# and pre-warms _projects_cache + _bible_cache + _gallery_cache so the
# first user lands on already-baked HTML.
#
# Idempotency: guarded by a module-level flag so multiple gunicorn
# workers don't fan out duplicate priming work. Failures are swallowed
# and logged — a partial prime is still better than zero, and the
# user-driven path will refill anything we missed on demand.
_cache_primer_started = False
_cache_primer_lock = threading.Lock()


def _prime_gallery_caches():
    """Walk the master Projects sheet and pre-build every gallery's HTML.

    Order: read_projects() first (single Sheets call) → per-gallery
    build_html() (each call hits the episode sheet + bible sheet, but
    the bible sheet read is shared across episodes of the same series
    via _bible_cache, so siblings reuse one another's reads)."""
    import time as _t
    try:
        # Brief delay so Render's Procfile boot sequence finishes before
        # we start hammering Google APIs from the worker.
        _t.sleep(3.0)
    except Exception:
        pass

    try:
        projects_data = read_projects()
    except Exception as e:
        print(f"[cache-primer] read_projects failed: {e}")
        return

    registry = projects_data.get("registry") or {}
    if not registry:
        print(f"[cache-primer] no galleries in master registry, skipping")
        return

    # The projects index is now warm — that's what /projects (the landing) needs,
    # and it's the slow cold-read we care about. Pre-building EVERY gallery's HTML
    # on boot hammers Sheets (N episode + bible reads → 429 backoffs that slow the
    # first user requests), so it's now OPT-IN. By default galleries build lazily
    # on first visit (30s-cached thereafter).
    if os.environ.get("DEARAI_PRIME_GALLERIES", "").strip().lower() not in ("1", "true", "yes"):
        print(f"[cache-primer] projects index warmed; skipping per-gallery pre-build "
              f"({len(registry)} galleries build lazily — set DEARAI_PRIME_GALLERIES=1 to pre-build)")
        return

    # Build each gallery in order. For a 6-ep series we make 1 bible-sheet
    # read (cached after the first build) + 6 episode-sheet reads. Total
    # wall time on a warm Sheets connection is ~10-15s for a full series.
    print(f"[cache-primer] priming {len(registry)} galleries…")
    try:
        from build_gallery import build_html as _build_html
    except Exception as e:
        print(f"[cache-primer] couldn't import build_gallery: {e}")
        return

    bible_for = projects_data.get("bible_for") or {}
    siblings_for = projects_data.get("siblings_for") or {}
    primed = 0
    failed = 0
    for slug, (sheet_id, show, episode) in registry.items():
        try:
            t0 = _t.time()
            html_doc = _build_html(
                sheet_id, show, episode,
                gallery_name=slug,
                bible_sheet_id=bible_for.get(slug),
                episodes=siblings_for.get(slug, []),
                verbose=False,
            )
            with _gallery_cache_lock:
                _gallery_cache[slug] = (_t.time(), html_doc)
            primed += 1
            print(f"[cache-primer] ✓ {slug} ({_t.time()-t0:.1f}s)")
        except Exception as e:
            failed += 1
            print(f"[cache-primer] ✗ {slug}: {e}")
    print(f"[cache-primer] done — {primed} primed, {failed} failed")


def _start_cache_primer():
    global _cache_primer_started
    with _cache_primer_lock:
        if _cache_primer_started:
            return
        _cache_primer_started = True
    threading.Thread(target=_prime_gallery_caches,
                     name="gallery-cache-primer",
                     daemon=True).start()


# Only prime in the Render / gunicorn path — local dev (run via __main__)
# leaves the cache cold so reloads pick up edits immediately. The
# DEARAI_PRIME_CACHE env var is the explicit override for either path.
_should_prime = (
    os.environ.get("DEARAI_PRIME_CACHE", "").strip().lower() in ("1", "true", "yes")
    or os.environ.get("RENDER", "").strip() != ""
    or os.environ.get("GUNICORN_CMD_ARGS", "").strip() != ""
)
if _should_prime:
    _start_cache_primer()


if __name__ == "__main__":
    # Local dev only. Render uses Procfile + gunicorn against `server` above.
    # PORT env honored either way (default 8050 locally; Render injects $PORT).
    port = int(os.environ.get("PORT", 8050))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"\n→ DearAI Production Dashboard: http://{host}:{port}\n")
    # threaded=True so the /api/asset-video streaming proxy (and any other
    # long-lived response) doesn't block the single-threaded dev server.
    app.run(debug=False, host=host, port=port, threaded=True)

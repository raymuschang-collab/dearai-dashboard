#!/usr/bin/env python3
"""smoke_test_dashboard.py — hermetic smoke test for the DearAI dashboard.

Boots the Flask/Dash app with AUTH off and a MOCK PROJECT injected (no network,
no Google creds), then exercises every surface via the Flask test client:

  • /projects renders the mock project card — crimson tokens, stat roll-up,
    hover-play vtile, the New-Project modal (6 global presets + the new
    text/bibles/masters depth), search box.
  • / (operational dashboard) shell — crimson theme.css, Inter (no Bebas Neue),
    dark-mode toggle; /_dash-layout carries the relabeled "Master Shots" tab.
  • /api/asset-video allowlist — unknown id 404s; an allowlisted id is served.
  • /api/edit-global — validation + a preset write (gspread mocked).
  • /debug/* gating — 404 when locked, 200 when DEARAI_DEBUG_OPEN=1.
  • global_presets — 6 cinematic presets load.

Run:  /tmp/dashvenv/bin/python smoke_test_dashboard.py   (needs dash installed)
Exit code 0 = all green.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dash_app"))

# --- hermetic env: auth OFF, dummy master sheet, debug locked, no cache primer ---
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)
os.environ.pop("DEARAI_DEBUG_OPEN", None)
os.environ.pop("RENDER", None)
os.environ.pop("GUNICORN_CMD_ARGS", None)
os.environ.pop("DEARAI_PRIME_CACHE", None)
os.environ["MASTER_PROJECTS_SHEET_ID"] = "mock-master-sheet"

# Neutralise the background cache warmer BEFORE app import (it would hit Sheets).
import bible_reader  # noqa: E402
bible_reader.start_background_refresh = lambda *a, **k: None
bible_reader.invalidate_all_caches = lambda *a, **k: None

import importlib  # noqa: E402
app_mod = importlib.import_module("dash_app.app")
flask_server = app_mod.server
client = flask_server.test_client()

# --- the MOCK PROJECT ---------------------------------------------------------
MOCK_HERO_ID = "MOCKVIDEOID123abc"
MOCK_PROJECT = {
    "slug": "mockshow", "title": "Mock Smoke Show", "type": "series",
    "status": "active", "owner_email": "tester@dearai.co",
    "created_at": "2026-06-21T00:00:00Z", "notes": "hermetic smoke test",
    "episodes": [{"gallery_slug": "mockshow_ep01"}], "cover_url": "",
    "hero_video": {"file_id": MOCK_HERO_ID,
                   "poster": f"https://drive.google.com/thumbnail?id={MOCK_HERO_ID}&sz=w800",
                   "kind": "character", "name": "MOCK HERO"},
    "n_characters": 5, "n_locations": 7, "n_assets": 30,
}
MOCK_DATA = {"projects": [MOCK_PROJECT], "registry": {}, "bible_for": {},
             "siblings_for": {}, "_ok": True}
app_mod.read_projects = lambda force=False: MOCK_DATA  # patch the data source

# ------------------------------------------------------------------------------
_results: list[tuple[bool, str]] = []


def check(name: str, cond: bool, extra: str = ""):
    _results.append((bool(cond), name + (f"  [{extra}]" if extra and not cond else "")))


# === /projects (CMS landing with the mock project) ============================
r = client.get("/projects")
body = r.get_data(as_text=True)
check("/projects 200", r.status_code == 200, f"status={r.status_code}")
check("/projects renders mock project", "Mock Smoke Show" in body)
check("/projects stat roll-up (char/loc)", ">5</b> char" in body and ">7</b> loc" in body)
check("/projects hover-play vtile", 'card-cover vtile' in body)
check("/projects asset-video src wired", f"/api/asset-video/{MOCK_HERO_ID}" in body)
check("/projects crimson token", "#c11647" in body)
check("/projects dark mode present", 'data-theme' in body and 'gallery_dark_mode' in body)
check("/projects search box", 'id="proj-search"' in body and 'id="proj-sort"' in body)
check("/projects 6 global presets", all(
    n in body for n in ["Prestige Drama", "Warm Cinematic", "Neo-Noir",
                         "Natural Daylight Realism", "Epic Large-Format", "Vintage 70s Film"]))
check("/projects depth = masters (no storyboards)",
      'data-value="masters"' in body and 'data-value="storyboards"' not in body)

# === / operational dashboard shell ============================================
r = client.get("/")
shell = r.get_data(as_text=True)
check("/ 200", r.status_code == 200, f"status={r.status_code}")
check("/ dark-mode toggle", 'id="dark-toggle"' in shell and 'toggleDarkMode' in shell)
check("/ Inter font, no Bebas Neue", "Inter:wght" in shell and "Bebas" not in shell)
check("/ theme.css linked", "theme.css" in shell)

r = client.get("/_dash-layout")
layout = r.get_data(as_text=True)
check("/_dash-layout 200", r.status_code == 200)
check("dashboard tab relabeled 'Master Shots'", "Master Shots" in layout and '"Storyboards"' not in layout)

# === /api/asset-video allowlist ===============================================
r = client.get("/api/asset-video/totally-unknown-id-xyz")
check("/api/asset-video unknown id → 404 (allowlist closed)", r.status_code == 404,
      f"status={r.status_code}")

# allowlisted id is served — mock the builder so we don't hit Drive
_tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
_tmp.write(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
_tmp.close()
app_mod._asset_video_path = lambda safe: Path(_tmp.name)
r = client.get(f"/api/asset-video/{MOCK_HERO_ID}")
check("/api/asset-video allowlisted id → served", r.status_code in (200, 206),
      f"status={r.status_code}")

# === /api/edit-global =========================================================
r = client.post("/api/edit-global", json={})
check("/api/edit-global no sheet_id → 400", r.status_code == 400, f"status={r.status_code}")
r = client.post("/api/edit-global", json={"sheet_id": "x"})
check("/api/edit-global no preset/text → 400", r.status_code == 400, f"status={r.status_code}")

# preset write — mock gspread + auth so no network
import auth as _auth  # noqa: E402
import gspread as _gspread  # noqa: E402
_auth.get_credentials = lambda *a, **k: object()
_mock_ws = MagicMock()
_mock_sh = MagicMock(); _mock_sh.worksheet.return_value = _mock_ws
_mock_gc = MagicMock(); _mock_gc.open_by_key.return_value = _mock_sh
_gspread.authorize = lambda *a, **k: _mock_gc
r = client.post("/api/edit-global", json={"sheet_id": "mock-ep-sheet", "preset": "neo-noir"})
j = r.get_json() or {}
check("/api/edit-global preset write → 200 ok", r.status_code == 200 and j.get("ok") is True,
      f"status={r.status_code} body={j}")
check("/api/edit-global wrote B1+B2", set(j.get("wrote", [])) >= {"B1", "B2"})
check("/api/edit-global called Video Prompts batch_update", _mock_ws.batch_update.called)

# === /debug/* gating ==========================================================
r = client.get("/debug/env")
check("/debug/env locked by default → 404", r.status_code == 404, f"status={r.status_code}")
os.environ["DEARAI_DEBUG_OPEN"] = "1"
r = client.get("/debug/env")
check("/debug/env opens with DEARAI_DEBUG_OPEN=1 → 200", r.status_code == 200,
      f"status={r.status_code}")
os.environ.pop("DEARAI_DEBUG_OPEN", None)

# === global_presets ===========================================================
from global_presets import GLOBAL_PRESETS  # noqa: E402
check("global_presets has 6 presets", len(GLOBAL_PRESETS) == 6, f"n={len(GLOBAL_PRESETS)}")

# === report ===================================================================
passed = sum(1 for ok, _ in _results if ok)
total = len(_results)
print("\n=== DearAI dashboard smoke test (mock project) ===")
for ok, name in _results:
    print(f"  {'✓' if ok else '✗ FAIL'}  {name}")
print(f"\n{passed}/{total} checks passed")
try:
    os.unlink(_tmp.name)
except Exception:
    pass
sys.exit(0 if passed == total else 1)

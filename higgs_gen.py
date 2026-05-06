"""Higgsfield CLI image-gen wrapper. Shared by storyboard_generate.py,
character_generate.py, bible_generate.py — anything that needs to fire
text-to-image via the user's Higgsfield subscription (no marginal cost).

Routing per the project's provider memory:
  - characters       → gpt_image_2 (rich bible reference sheet)
  - costume/props/fx → nano_banana_2
  - storyboards      → gpt_image_2 (5-panel sketch)
  - locations        → uses location_generate.py's Reve direct path (NOT this)

Auth: the higgs CLI must be authenticated (`higgs auth login`). The CLI
caches a token at ~/.config/higgsfield/credentials, persistent across runs.
"""
from __future__ import annotations

import builtins as _b
import json
import os
import shutil
import subprocess
import sys
import time

import requests


def resolve_higgs_bin() -> str:
    configured = os.environ.get("HIGGS_BIN")
    if configured:
        return shutil.which(configured) or os.path.expanduser(configured)
    return (
        shutil.which("higgs")
        or os.path.expanduser("~/.npm-global/bin/higgs")
    )


HIGGS_BIN = resolve_higgs_bin()

# Resilient print() — survives a Dash restart killing our stdout pipe mid-job.
_orig_print = _b.print


def _safe_print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    except BrokenPipeError:
        try:
            sys.stdout = open(os.devnull, "w")
            sys.stderr = open(os.devnull, "w")
        except Exception:
            pass


_b.print = _safe_print


def assert_authed():
    if not os.path.exists(HIGGS_BIN):
        sys.exit(f"higgs CLI not found at {HIGGS_BIN}. "
                 f"Install: npm install -g @higgsfield/cli")
    chk = subprocess.run([HIGGS_BIN, "auth", "token"],
                        capture_output=True, text=True, timeout=10)
    if chk.returncode != 0:
        sys.exit("higgs CLI not authenticated. Run: higgs auth login")


def generate(prompt: str, model: str = "gpt_image_2",
             aspect_ratio: str = "16:9",
             quality: str = "high", resolution: str = "1k",
             image_ref_path: str | None = None,
             timeout: int = 360) -> bytes:
    """Submit one image gen to Higgsfield, poll until completed, return PNG bytes.

    `quality` arg kept for backward compatibility but NOT passed to the CLI.
    `image_ref_path` (optional) — local path to a PNG/JPG. The higgs CLI auto-
    uploads it and threads it through as a media reference. Used by location_gen
    for the "wide → plan view" two-step pipeline.

    Raises RuntimeError on failure. CLI's `higgs generate get <id> --json`
    returns the result URL at the top-level key `result_url`.
    """
    cmd = [HIGGS_BIN, "generate", "create", model,
           "--prompt", prompt,
           "--aspect_ratio", aspect_ratio,
           "--resolution", resolution,
           "--json"]
    if image_ref_path:
        cmd.extend(["--image", image_ref_path])
    sub = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if sub.returncode != 0:
        raise RuntimeError(f"submit failed: {sub.stderr[:300]}")
    job_ids = json.loads(sub.stdout)
    if not job_ids:
        raise RuntimeError(f"no job id returned: {sub.stdout[:200]}")
    job_id = job_ids[0]

    deadline = time.time() + timeout
    while time.time() < deadline:
        get = subprocess.run([HIGGS_BIN, "generate", "get", job_id, "--json"],
                            capture_output=True, text=True, timeout=30)
        if get.returncode == 0:
            try:
                data = json.loads(get.stdout)
            except json.JSONDecodeError:
                data = {}
            status = data.get("status")
            if status == "completed":
                url = data.get("result_url") or data.get("rawUrl") or (
                    data.get("results", {}).get("rawUrl")
                    if isinstance(data.get("results"), dict) else None
                )
                if not url:
                    raise RuntimeError(f"no result_url in completed job: {json.dumps(data)[:300]}")
                resp = requests.get(url, timeout=180)
                resp.raise_for_status()
                return resp.content
            if status == "failed":
                raise RuntimeError(f"job {job_id} failed: {json.dumps(data)[:300]}")
        time.sleep(8)
    raise RuntimeError(f"job {job_id} timed out after {timeout}s")

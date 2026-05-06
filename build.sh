#!/usr/bin/env bash
# Render build hook — installs Python deps + Higgsfield CLI into a path
# that survives the build → runtime container handoff.
#
# Render's build phase and runtime phase run in DIFFERENT containers. Only
# files under /opt/render/project/src/ (the repo checkout) are preserved
# from build to runtime. Anything written to $HOME, /tmp, /opt/render/...
# during build is gone at runtime. So we install npm globals into a project-
# local prefix instead of the default $HOME/npm-global.
#
# Render also auto-installs Node into /opt/render/project/nodes/<ver>/bin
# and adds it to PATH. So we don't need to download our own Node — we just
# call `npm` from PATH.
#
# Runtime auth: a separate hook in dash_app/app.py (_bootstrap_higgs_credentials)
# writes ~/.config/higgsfield/credentials.json from HIGGSFIELD_CREDENTIALS_JSON
# at every gunicorn worker boot. That path IS persistent at runtime since
# $HOME exists in the runtime container, just not the build container.
#
# Required Render env vars beyond the standard set:
#   HIGGSFIELD_CREDENTIALS_JSON  — full ~/.config/higgsfield/credentials.json
#                                   contents (174 chars typical)
# (HIGGS_BIN is set by the Procfile; no need to set it as an env var.)

set -euo pipefail

echo "=== [build.sh] Python deps ==="
pip install -r requirements.txt

echo
echo "=== [build.sh] Higgsfield CLI (project-local prefix) ==="

# Project-local npm prefix — survives build → runtime container handoff.
# Render preserves the repo checkout (/opt/render/project/src/) but discards
# everything else, so $HOME/npm-global from earlier attempts vanished after
# build. Install here instead.
NPM_PREFIX="/opt/render/project/src/.npm-global"
mkdir -p "$NPM_PREFIX"

# Use whatever node/npm Render put on PATH (typically /opt/render/project/nodes/<ver>/bin).
if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not on PATH. Render usually auto-installs Node when it"
    echo "       detects npm-related files (package.json, etc). If that"
    echo "       hasn't happened, add a top-level package.json or set"
    echo "       NODE_VERSION in Render's env."
    exit 1
fi

echo "npm found at: $(command -v npm)"
echo "node version: $(node --version)"

if [ -x "$NPM_PREFIX/bin/higgs" ]; then
    echo "Higgsfield CLI already installed at $NPM_PREFIX/bin/higgs — skipping reinstall"
else
    echo "Installing @higgsfield/cli into $NPM_PREFIX…"
    npm install -g --prefix "$NPM_PREFIX" @higgsfield/cli
fi

# Sanity check (non-fatal — version flag isn't standard)
"$NPM_PREFIX/bin/higgs" version 2>/dev/null || true

echo
echo "=== [build.sh] DONE ==="
echo "  higgs binary: $NPM_PREFIX/bin/higgs"
ls -l "$NPM_PREFIX/bin/" 2>/dev/null || echo "  (bin dir empty — install may have failed)"

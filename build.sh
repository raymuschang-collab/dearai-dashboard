#!/usr/bin/env bash
# Render build hook — installs Python deps + Higgsfield CLI on the build host.
#
# Render's Python runtime is Ubuntu-based but does not include Node.js. The
# Higgsfield CLI is a Node binary, so we download Node into the persistent
# build cache (~/node) and install @higgsfield/cli into ~/npm-global. Both
# are non-root-writable paths, so this works without sudo.
#
# Runtime auth: a separate startup hook in dash_app/app.py writes
# ~/.config/higgsfield/credentials.json from the HIGGSFIELD_CREDENTIALS_JSON
# env var, since Render's filesystem is ephemeral and we cannot run
# `higgs auth login` interactively.
#
# Render env vars to set in addition to the ones already wired:
#   HIGGSFIELD_CREDENTIALS_JSON  — full contents of local
#                                  ~/.config/higgsfield/credentials.json
#   HIGGS_BIN                    — usually $HOME/npm-global/bin/higgs (also
#                                  resolved via PATH by higgs_gen.py /
#                                  storyboard_generate.py if unset)

set -euo pipefail

echo "=== [build.sh] Python deps ==="
pip install -r requirements.txt

echo
echo "=== [build.sh] Node + Higgsfield CLI ==="
NODE_VERSION="v20.18.0"
NODE_TAR="node-${NODE_VERSION}-linux-x64.tar.xz"
NODE_URL="https://nodejs.org/dist/${NODE_VERSION}/${NODE_TAR}"

NODE_DIR="$HOME/node"
NPM_PREFIX="$HOME/npm-global"

if [ -x "$NPM_PREFIX/bin/higgs" ]; then
    echo "Higgsfield CLI already installed at $NPM_PREFIX/bin/higgs — skipping"
else
    mkdir -p "$NODE_DIR"
    TMPDIR=$(mktemp -d)
    cd "$TMPDIR"
    echo "Downloading Node ${NODE_VERSION}…"
    curl -fsSL "$NODE_URL" -o "$NODE_TAR"
    tar -xf "$NODE_TAR" -C "$NODE_DIR" --strip-components=1
    rm "$NODE_TAR"
    cd -
    rm -rf "$TMPDIR"

    export PATH="$NODE_DIR/bin:$PATH"
    export NPM_CONFIG_PREFIX="$NPM_PREFIX"
    mkdir -p "$NPM_PREFIX"

    "$NODE_DIR/bin/npm" install -g @higgsfield/cli
fi

# Sanity check (non-fatal — version flag isn't standard)
"$NPM_PREFIX/bin/higgs" version 2>/dev/null || true

echo
echo "=== [build.sh] DONE ==="
echo "  node:  $NODE_DIR/bin/node"
echo "  higgs: $NPM_PREFIX/bin/higgs"
echo "  Set Render env: HIGGS_BIN=$NPM_PREFIX/bin/higgs"

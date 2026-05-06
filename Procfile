web: HIGGS_BIN=${HIGGS_BIN:-$HOME/npm-global/bin/higgs} PATH=$HOME/node/bin:$HOME/npm-global/bin:$PATH gunicorn dash_app.app:server --bind 0.0.0.0:$PORT --workers 2 --timeout 120

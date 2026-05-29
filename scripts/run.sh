#!/bin/bash
set -e

if [ -n "${VIRTUAL_ENV:-}" ] && [ -f "${VIRTUAL_ENV}/bin/activate" ]; then
    source "${VIRTUAL_ENV}/bin/activate"
else
    source .venv/bin/activate
fi

flask run --host=0.0.0.0 --port=5000 &
FLASK_PID=$!

node lyrics_searcher/index.js &
NODE_PID=$!

echo "Everything running!"

cleanup() {
    kill "$FLASK_PID" "$NODE_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait -n "$FLASK_PID" "$NODE_PID"

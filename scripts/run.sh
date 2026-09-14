#!/bin/bash
set -e

if [ -n "${VIRTUAL_ENV:-}" ] && [ -f "${VIRTUAL_ENV}/bin/activate" ]; then
    source "${VIRTUAL_ENV}/bin/activate"
else
    source .venv/bin/activate
fi

# Use the installed backend by default; an explicit CPU override remains valid.
if [ -z "${DOMEOKE_DEVICE:-}" ] && [ -f "${VIRTUAL_ENV}/domeoke-backend" ]; then
    DOMEOKE_DEVICE=$(cat "${VIRTUAL_ENV}/domeoke-backend")
fi
export DOMEOKE_DEVICE="${DOMEOKE_DEVICE:-auto}"
python -m audio_processing.device

# Bind mounts can hide processing directories created during the image build.
mkdir -p processing/sentence_level_srt

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

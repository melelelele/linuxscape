#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

PROJECT_ROOT="$(realpath ..)"
export LINUXSCAPE_STATE_DIR="$PROJECT_ROOT/runtime"
export PORT="${PORT:-5000}"

mkdir -p "$LINUXSCAPE_STATE_DIR"

if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

python game.py &
BACKEND_PID="$!"

cleanup() {
    kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

sleep 1

if command -v firefox >/dev/null 2>&1; then
    firefox \
        --new-window \
        "file://$(realpath index.html)" &
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open \
        "file://$(realpath index.html)" \
        >/dev/null 2>&1 &
else
    echo "Öffne diese Datei im Browser:"
    echo "file://$(realpath index.html)"
fi

wait "$BACKEND_PID"
BASH


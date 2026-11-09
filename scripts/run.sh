#!/usr/bin/env bash
# Start the API, the folder watcher and the worker pool.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8000}
exec backend/.venv/bin/python -m uvicorn app.main:app \
  --app-dir backend --host "$HOST" --port "$PORT" "$@"

#!/usr/bin/env bash
# Development mode: API with reload on :8000, Vite dev server on :5173.
set -euo pipefail
cd "$(dirname "$0")/.."

backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend \
  --host 127.0.0.1 --port 8000 --reload &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

(cd frontend && npm run dev)

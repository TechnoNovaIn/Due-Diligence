#!/usr/bin/env bash
# One-time setup: Python environment, dependencies, database, frontend build.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
echo "==> Creating the Python environment"
$PY -m venv backend/.venv
backend/.venv/bin/python -m pip install --quiet --upgrade pip setuptools wheel
echo "==> Installing backend dependencies"
backend/.venv/bin/python -m pip install --quiet -r backend/requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Wrote .env (edit it to change the data directory or enable an AI provider)"
fi

echo "==> Applying database migrations"
(cd backend && .venv/bin/python -m alembic upgrade head)

if command -v npm >/dev/null 2>&1; then
  echo "==> Building the dashboard"
  (cd frontend && npm install --silent && npm run build)
else
  echo "!! npm was not found - the dashboard will not be built."
  echo "   The API still works at http://127.0.0.1:8000/docs"
fi

echo "==> Checking OCR"
if command -v tesseract >/dev/null 2>&1; then
  echo "    Tesseract is installed and will be used."
elif backend/.venv/bin/python -c "import platform,sys; sys.exit(0 if platform.system()=='Darwin' else 1)"; then
  # macOS ships its own recognition engine; these bindings make it usable.
  backend/.venv/bin/python -m pip install --quiet "ocrmac>=1.0" || true
  if backend/.venv/bin/python -c "from ocrmac import ocrmac" 2>/dev/null; then
    echo "    Using the OCR engine built into macOS. Nothing else to install."
  else
    echo "!!  No OCR engine available. Scanned documents will be flagged for manual review."
    echo "    Install one with: brew install tesseract"
  fi
else
  echo "!!  Tesseract OCR is not installed."
  echo "    Scanned documents will be flagged for manual review instead of being read."
  echo "    Debian/Ubuntu: sudo apt-get install tesseract-ocr"
fi

echo
echo "Setup complete. Start the system with: ./scripts/run.sh"

#!/bin/bash
# ==========================================================
# Production start script.
# Uses Gunicorn to run multiple Uvicorn worker processes so
# the app can use all available CPU cores instead of just one
# — important for handling 100-200 concurrent registrations/
# prints without slowing down or crashing.
#
# Usage:
#   ./start_prod.sh
#
# Mirrors run.sh's behavior:
#   - Always calls ./venv/bin/... directly (never relies on
#     "gunicorn"/"python" resolving correctly on PATH, which is
#     what breaks under conda/venv conflicts).
#   - HTTPS auto-detected from ../certs/ (same certs run.sh uses)
#     — falls back to plain http:// if they don't exist.
#   - Host/port read from .env via config.py, not hardcoded.
# ==========================================================
set -e

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "[setup] No venv found — run ./run.sh once first to set it up."
  exit 1
fi

# Make sure gunicorn is actually installed (requirements.txt may
# have been updated after the venv was first created).
./venv/bin/python -m pip install --quiet -r requirements.txt

HOST=$(./venv/bin/python -c "from config import settings; print(settings.app_host)")
PORT=$(./venv/bin/python -c "from config import settings; print(settings.app_port)")

# Rule of thumb: (2 x CPU cores) + 1. Adjust WORKERS based on
# your actual deployment machine's core count.
WORKERS=${WORKERS:-4}

CERT_FILE="../certs/localhost.pem"
KEY_FILE="../certs/localhost-key.pem"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
  echo "[run] Certs found — starting PRODUCTION backend on https://localhost:${PORT} (${WORKERS} workers)..."
  ./venv/bin/gunicorn main:app \
    --workers "$WORKERS" \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind "${HOST}:${PORT}" \
    --certfile "$CERT_FILE" \
    --keyfile "$KEY_FILE" \
    --timeout 30 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
else
  echo "[run] No certs found (run ../generate-certs.sh once to enable HTTPS)"
  echo "[run] Starting PRODUCTION backend on http://localhost:${PORT} (${WORKERS} workers)..."
  ./venv/bin/gunicorn main:app \
    --workers "$WORKERS" \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind "${HOST}:${PORT}" \
    --timeout 30 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
fi
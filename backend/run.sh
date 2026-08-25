#!/bin/bash
# ==========================================================
# One-command backend runner.
#
# Usage (every time, no matter what):
#   ./run.sh
#
# This script never relies on "python" or "pip" resolving to
# the right place (which is what caused the conda-vs-venv mixup
# before) — it always calls ./venv/bin/python directly by path.
#
# HTTPS: if ../certs/localhost.pem + localhost-key.pem exist
# (created once via ../generate-certs.sh), the server starts
# on https:// automatically. If they don't exist, it falls
# back to plain http:// exactly like before — nothing breaks
# either way.
# ==========================================================
set -e

# Always run relative to THIS script's location, no matter
# which folder you were in when you called it.
cd "$(dirname "$0")"

# Create the venv only if it doesn't already exist.
if [ ! -d "venv" ]; then
  echo "[setup] No venv found — creating one..."
  python3 -m venv venv
fi

echo "[setup] Installing/updating dependencies..."
./venv/bin/python -m pip install --quiet --upgrade pip
./venv/bin/python -m pip install --quiet -r requirements.txt

# Create .env from the example on first run, if missing.
if [ ! -f ".env" ]; then
  echo "[setup] No .env found — copying from .env.example..."
  cp .env.example .env
fi

# Read host/port from .env (via config.py) instead of hardcoding —
# so changing APP_HOST / APP_PORT in .env actually takes effect.
HOST=$(./venv/bin/python -c "from config import settings; print(settings.app_host)")
PORT=$(./venv/bin/python -c "from config import settings; print(settings.app_port)")

# ---------- HTTPS auto-detect ----------
CERT_FILE="../certs/localhost.pem"
KEY_FILE="../certs/localhost-key.pem"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
  echo "[run] Certs found — starting backend on https://localhost:${PORT} ..."
  ./venv/bin/python -m uvicorn main:app --reload --host "$HOST" --port "$PORT" \
    --ssl-certfile "$CERT_FILE" --ssl-keyfile "$KEY_FILE"
else
  echo "[run] No certs found (run ../generate-certs.sh once to enable HTTPS)"
  echo "[run] Starting backend on http://localhost:${PORT} ..."
  ./venv/bin/python -m uvicorn main:app --reload --host "$HOST" --port "$PORT"
fi
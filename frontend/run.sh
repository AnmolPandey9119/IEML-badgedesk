#!/bin/bash
# ==========================================================
# One-command frontend runner.
#
# Usage (every time):
#   ./run.sh
#
# Serves the frontend over http(s)://localhost:5500 instead of
# opening index.html directly (file://), which is required —
# printing breaks under file:// due to browser security rules.
#
# HTTPS: if ../certs/localhost.pem + localhost-key.pem exist
# (created once via ../generate-certs.sh), serve_https.py starts
# on https:// automatically. If they don't exist, it falls back
# to plain http:// exactly like before — nothing breaks either way.
# ==========================================================
set -e
cd "$(dirname "$0")"

PORT="${PORT:-5500}"
export PORT
python3 serve_https.py
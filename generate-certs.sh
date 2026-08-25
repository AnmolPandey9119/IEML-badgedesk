#!/bin/bash
# ==========================================================
# generate-certs.sh  (run from the project ROOT, once)
#
# Creates a locally-trusted HTTPS certificate (via mkcert) that
# both the frontend (run.sh) and backend (run.sh) auto-detect
# and use. Removes the browser's "Not Secure" warning.
#
# Safe to re-run any time — it just regenerates the cert.
# If mkcert isn't installed, this prints install instructions
# and exits WITHOUT touching anything else in the project —
# both run.sh scripts keep working over plain HTTP either way.
#
# Usage:
#   ./generate-certs.sh                  # localhost only
#   ./generate-certs.sh 192.168.1.10     # + this laptop's LAN IP
#                                         #   (needed if OTHER counter
#                                         #    laptops hit this one over
#                                         #    the LAN, not just localhost)
# ==========================================================
set -e
cd "$(dirname "$0")"

if ! command -v mkcert &> /dev/null; then
  echo "[error] mkcert is not installed."
  echo ""
  echo "Install it first, then re-run this script:"
  echo "  macOS:   brew install mkcert"
  echo "  Windows: choco install mkcert   (or scoop install mkcert)"
  echo "  Linux:   see https://github.com/FiloSottile/mkcert#installation"
  echo ""
  echo "Nothing has been changed — the app will keep running over"
  echo "plain HTTP (with the browser's Not Secure warning) until"
  echo "you install mkcert and re-run this script."
  exit 1
fi

echo "[setup] Installing local trusted root CA (one-time, may ask for your password)..."
mkcert -install

mkdir -p certs

HOSTS=(localhost 127.0.0.1 ::1)
if [ -n "$1" ]; then
  HOSTS+=("$1")
  echo "[setup] Including LAN IP: $1"
fi

echo "[setup] Generating certificate for: ${HOSTS[*]}"
mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem "${HOSTS[@]}"

echo ""
echo "[done] Certificate ready at ./certs/"
echo "[done] Now just run backend/run.sh and frontend/run.sh as usual —"
echo "[done] they'll detect the certs automatically and switch to https://."
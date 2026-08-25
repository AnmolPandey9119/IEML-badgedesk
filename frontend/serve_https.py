#!/usr/bin/env python3
"""
serve_https.py
Serves this frontend folder over HTTPS using the local mkcert
certificate (../certs/localhost.pem + localhost-key.pem).

If the certs don't exist yet, this automatically falls back to
plain HTTP on the same port — so the site NEVER breaks, HTTPS is
just an upgrade once ../generate-certs.sh has been run.

Called from run.sh — you shouldn't need to run this directly.
"""

import http.server
import os
import ssl

PORT = int(os.environ.get("PORT", 5500))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(SCRIPT_DIR, "..", "certs", "localhost.pem")
KEY_FILE = os.path.join(SCRIPT_DIR, "..", "certs", "localhost-key.pem")

handler = http.server.SimpleHTTPRequestHandler
httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler)

if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"[run] Certs found — starting frontend on https://localhost:{PORT} ...")
else:
    print(f"[run] No certs found (run ../generate-certs.sh once to enable HTTPS)")
    print(f"[run] Starting frontend on http://localhost:{PORT} ...")

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\n[run] Stopped.")
    httpd.server_close()
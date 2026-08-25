/* ==========================================================
   api.js (Entrance Scanner)
   Talks to the exact SAME FastAPI backend as the operator app and
   master console — no separate backend, no separate database.
   ========================================================== */

const API = (() => {

  if (!window.APP_CONFIG || !window.APP_CONFIG.API_BASE_URL) {
    console.error(
      "APP_CONFIG.API_BASE_URL is missing — make sure config.js is " +
      "loaded BEFORE api.js (copy config.example.js to config.js if you haven't yet)."
    );
  }

  const BASE_URL = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "";
  const LOGIN_PATH = "/api/auth/login";

  async function request(path, options = {}) {
    const url = `${BASE_URL}${path}`;

    const headers = { "Content-Type": "application/json" };
    const token = window.Auth && window.Auth.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const opts = { headers, ...options };

    try {
      const res = await fetch(url, opts);
      const data = await res.json().catch(() => ({}));

      if (res.status === 401 && window.Auth && path !== LOGIN_PATH) {
        window.Auth.logout(true);
        return { ok: false, error: "Session expired — please log in again" };
      }

      if (!res.ok) {
        throw new Error(data.detail || `Request failed (${res.status})`);
      }
      return { ok: true, data };
    } catch (err) {
      return { ok: false, error: err.message || "Network error" };
    }
  }

  return {
    /** Simple health check to show online/offline status in the topbar */
    checkHealth() {
      return request("/health", { method: "GET" });
    },

    /** Same shared login endpoint — scanner credentials get role="scanner" back */
    login(username, password) {
      return request(LOGIN_PATH, {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
    },

    /**
     * Called once per successful scan. Increments the visitor's
     * scan_count, logs one row tagged with this scanner/gate's
     * chosen name, and returns their full current details in the
     * same call — no separate lookup needed.
     */
    logScan(urn, scannerName) {
      return request(`/api/visitors/${encodeURIComponent(urn)}/scan-log`, {
        method: "POST",
        body: JSON.stringify({ scanner_name: scannerName }),
      });
    },
  };
})();
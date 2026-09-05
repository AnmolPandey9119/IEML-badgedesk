/* ==========================================================
   api.js — Mart Days Desk
   Same pattern as the "Other Events" desk's js/api.js, but every
   visitor-shaped endpoint points at /api/mart-desk/* instead of
   /api/visitors/* — a completely separate router/table on the same
   backend (see backend/routers/mart_desk.py). Login and health-check
   are shared endpoints (/api/auth/login, /health), same backend for
   both desks. No Sync Now / Excel export here — those are specific
   to the Google Sheet-backed "Other Events" desk and don't apply to
   Mart Days registrations.
   ========================================================== */

   const API = (() => {

    if (!window.APP_CONFIG || !window.APP_CONFIG.API_BASE_URL) {
      console.error(
        "APP_CONFIG.API_BASE_URL is missing — make sure config.js is " +
        "loaded BEFORE api.js in index.html."
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

      /** Logs in and returns { access_token, expires_in_hours, username, role } on success */
      login(username, password) {
        return request(LOGIN_PATH, {
          method: "POST",
          body: JSON.stringify({ username, password }),
        });
      },

      /**
       * Search a Mart Days registrant by URN / QR value / name /
       * mobile / company. Scoped to mart_days_registrations only —
       * see backend/routers/mart_desk.py.
       */
      searchVisitor(query) {
        const params = new URLSearchParams({ q: query });
        return request(`/api/mart-desk/search?${params.toString()}`, {
          method: "GET",
        });
      },

      /**
       * Registers a new Mart Days walk-in at this desk. `category`
       * must be one of the buyer types shown in the form.
       */
      registerVisitor(payload) {
        return request("/api/mart-desk/register", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      },

      /**
       * Edits an already-registered Mart Days registrant's details.
       * URN is never sent in the body — it's fixed, passed only in
       * the URL.
       */
      updateVisitor(urn, payload) {
        return request(`/api/mart-desk/${encodeURIComponent(urn)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      },

      /**
       * Called right after a browser print actually succeeds.
       * Increments this registrant's print_count in
       * mart_days_registrations.
       */
      logPrint(urn, deviceName) {
        return request(`/api/mart-desk/${encodeURIComponent(urn)}/print-log`, {
          method: "POST",
          body: JSON.stringify({ device_name: deviceName }),
        });
      },
    };
  })();
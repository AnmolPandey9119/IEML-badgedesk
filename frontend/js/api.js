/* ==========================================================
   api.js
   All communication with our FastAPI backend lives here.
   The FastAPI backend itself is responsible for talking to
   the organization's real server (realtime lookups + saving
   new onsite registrations / edits back to it).

   NOTE: BASE_URL comes from config.js (window.APP_CONFIG),
   NOT hardcoded here. Every counter/laptop on the LAN has its
   own config.js pointing to the same FastAPI backend so all
   data + print jobs go through one place.
   ========================================================== */

   const API = (() => {

    if (!window.APP_CONFIG || !window.APP_CONFIG.API_BASE_URL) {
      console.error(
        "APP_CONFIG.API_BASE_URL is missing — make sure config.js is " +
        "loaded BEFORE api.js in index.html, and that it's set up " +
        "(copy config.example.js to config.js if you haven't yet)."
      );
    }
  
    const BASE_URL = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "";
    const LOGIN_PATH = "/api/auth/login";
  
    async function request(path, options = {}) {
      const url = `${BASE_URL}${path}`;
  
      const headers = { "Content-Type": "application/json" };
      // Attach the login token to every request except /login itself.
      // window.Auth comes from auth.js, which must load before api.js.
      const token = window.Auth && window.Auth.getToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
  
      const opts = { headers, ...options };
  
      try {
        const res = await fetch(url, opts);
        const data = await res.json().catch(() => ({}));
  
        // A 401 on the LOGIN endpoint itself just means "wrong
        // username/password" — that's a normal login failure, NOT
        // an expired session, so it must NOT trigger the auto-logout
        // redirect below (that redirect target IS login.html, so
        // doing it here would bounce the page and swallow the error
        // message before the person ever sees "Incorrect username
        // or password").
        if (res.status === 401 && window.Auth && path !== LOGIN_PATH) {
          // Session expired or invalid — send the operator back to login
          // rather than showing a confusing generic error.
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
  
      /** Logs in and returns { access_token, expires_in_hours, username } on success */
      login(username, password) {
        return request(LOGIN_PATH, {
          method: "POST",
          body: JSON.stringify({ username, password }),
        });
      },
  
      /**
       * Search a visitor on the organization's real server (realtime)
       * by URN / QR value / name / mobile number. A QR scanner just
       * types the scanned value into the search box and "presses"
       * Enter, so a scan lands here exactly the same way manual
       * typing does — no separate scanner integration needed.
       *
       * Always includes the current event mode (Other Events / Mart
       * Days) from window.Auth.getEvent() — set once at login, not
       * chosen in-app anymore — so search only ever looks in the
       * right table. This is just a courtesy/default now: the
       * backend independently trusts the login token's own event
       * claim over this param (see routers/registration.py), so a
       * badge desk operator can never actually search the wrong
       * event's data even if this value were ever wrong or tampered.
       */
      searchVisitor(query) {
        const event = (window.Auth && window.Auth.getEvent()) || "other";
        const params = new URLSearchParams({ q: query, event });
        return request(`/api/visitors/search?${params.toString()}`, {
          method: "GET",
        });
      },
  
      /**
       * Register a new onsite visitor for any event OTHER than Mart
       * Days. This gets saved on the organization's real server
       * through the backend, and the backend returns the assigned
       * URN + visitor record back.
       */
      registerVisitor(payload) {
        return request("/api/visitors/register", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      },

      /**
       * Register a new onsite Mart Days visitor — used only when the
       * counter is in Mart Days mode. Writes ONLY to
       * mart_days_registrations on the backend (see
       * routers/registration.py's /register-mart-days), never to the
       * regular visitors table.
       */
      registerMartDaysVisitor(payload) {
        return request("/api/visitors/register-mart-days", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      },

      /**
       * Checks the extra Mart Days gate password (on top of the
       * already-logged-in staff token) that unlocks Mart Days mode
       * in this counter app. See routers/auth.py's
       * /verify-mart-days-access.
       */
      verifyMartDaysAccess(password) {
        return request("/api/auth/verify-mart-days-access", {
          method: "POST",
          body: JSON.stringify({ password }),
        });
      },
  
      /**
       * Edits an already-registered visitor's details (name, org,
       * designation, mobile, email, category). URN is NEVER sent in
       * the body — it's fixed, passed only in the URL, since it's
       * the permanent identifier already used as the badge's QR value.
       */
      updateVisitor(urn, payload) {
        return request(`/api/visitors/${encodeURIComponent(urn)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      },

      /**
       * Triggers an on-demand sync: backend fetches the Google Sheet
       * right now, saves any new registrants into the master store
       * with a fresh URN, and returns { enabled, fetched, new, skipped }.
       * Same function the background auto-sync loop uses, so manual
       * and automatic sync always behave identically.
       */
      runSync() {
        return request("/api/sync/run", { method: "POST" });
      },

      /**
       * Called right after a browser print actually succeeds. Increments
       * this visitor's print_count and logs one row tagged with the
       * device name — this is what the master console's print stats
       * and "Printed Badges" list are built from.
       */
      logPrint(urn, deviceName) {
        return request(`/api/visitors/${encodeURIComponent(urn)}/print-log`, {
          method: "POST",
          body: JSON.stringify({ device_name: deviceName }),
        });
      },

      /**
       * Downloads the URN-first master Excel file (every visitor
       * currently in the master store — sheet-synced + onsite). Not
       * a plain <a href> link because the route needs the admin
       * token attached, so this fetches the file as a blob and
       * triggers the browser download manually.
       */
      async exportExcel() {
        const token = window.Auth && window.Auth.getToken();
        const headers = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;

        try {
          const res = await fetch(`${BASE_URL}/api/export/excel`, { headers });

          if (res.status === 401 && window.Auth) {
            window.Auth.logout(true);
            return { ok: false, error: "Session expired — please log in again" };
          }

          if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || `Export failed (${res.status})`);
          }

          const blob = await res.blob();

          // Filename comes from the backend's Content-Disposition
          // header (e.g. "ieml-visitors-2026-08-18-1432.xlsx") so
          // repeated exports never overwrite each other.
          const disposition = res.headers.get("Content-Disposition") || "";
          const match = disposition.match(/filename="?([^"]+)"?/);
          const filename = match ? match[1] : "ieml-visitors.xlsx";

          const blobUrl = window.URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = blobUrl;
          link.download = filename;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.URL.revokeObjectURL(blobUrl);

          return { ok: true, filename };
        } catch (err) {
          return { ok: false, error: err.message || "Network error" };
        }
      },
    };
  })();
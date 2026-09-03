/* ==========================================================
   api.js (Master Console)
   Talks to the exact SAME FastAPI backend as the counter app —
   no separate backend, no separate database. The only difference
   is which token gets attached (master token from this app's
   own Auth, see js/auth.js) and which endpoints get called
   (the /api/master/* read endpoints, plus the shared
   register/update/delete endpoints the operator app also uses).
   ========================================================== */

   const API = (() => {

    if (!window.APP_CONFIG || !window.APP_CONFIG.API_BASE_URL) {
      console.error(
        "APP_CONFIG.API_BASE_URL is missing — make sure config.js is " +
        "loaded BEFORE api.js, and that it's set up (copy config.example.js to config.js if you haven't yet)."
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
  
      /** Same login endpoint the operator app uses — master credentials get role="master" back */
      login(username, password) {
        return request(LOGIN_PATH, {
          method: "POST",
          body: JSON.stringify({ username, password }),
        });
      },
  
      /**
       * Finds a visitor by URN, name, mobile, or organization — same
       * search the operator counter uses. Includes sheet-synced AND
       * onsite people, so the master console can print for anyone,
       * not just the ones in the Onsite Registrations table.
       */
      searchVisitor(query) {
        const params = new URLSearchParams({ q: query });
        return request(`/api/visitors/search?${params.toString()}`, {
          method: "GET",
        });
      },
  
      /**
       * Called right after a browser print actually succeeds, same as
       * the operator counter. Tagged with device_name "Master Console"
       * so it's clearly distinguishable in the per-device print stats.
       */
      logPrint(urn) {
        return request(`/api/visitors/${encodeURIComponent(urn)}/print-log`, {
          method: "POST",
          body: JSON.stringify({ device_name: "Master Console" }),
        });
      },
  
      /** Every visitor on file, full details + print_count. Master-only endpoint. */
      listAllVisitors() {
        return request("/api/master/visitors", { method: "GET" });
      },
  
      /** Overall print total + per-device breakdown. Master-only endpoint. */
      getPrintStats() {
        return request("/api/master/print-stats", { method: "GET" });
      },

      /** Overall scan total + per-scanner breakdown. Master-only endpoint. */
      getScanStats() {
        return request("/api/master/scan-stats", { method: "GET" });
      },

      /** Most recent entrance-gate scans, newest first, with visitor details. Master-only endpoint. */
      getRecentScans(limit = 100) {
        const params = new URLSearchParams({ limit: String(limit) });
        return request(`/api/master/recent-scans?${params.toString()}`, { method: "GET" });
      },

      /**
       * NEW. Visitors whose badge has been printed at least once but
       * who were never scanned at any entrance gate. Master-only
       * endpoint. Powers the "Unscanned Entries" tab.
       */
      getUnscannedEntries(limit = 5000) {
        const params = new URLSearchParams({ limit: String(limit) });
        return request(`/api/master/unscanned?${params.toString()}`, { method: "GET" });
      },

      /**
       * NEW. End-of-event reset — clears print/scan history and
       * counts (never touches visitor names/URNs/org details) so the
       * system is ready for the next event. Master-only endpoint.
       * Returns { visitors_reset, print_logs_cleared, scan_logs_cleared }.
       */
      clearHistory() {
        return request("/api/master/clear-history", { method: "POST" });
      },

      /**
       * Full database wipe — every visitor, every print/scan log,
       * gone. Requires the exact confirm phrase server-side too (see
       * routers/master.py) even though the UI already gates this
       * behind a hidden unlock + typed confirmation before this is
       * ever called.
       */
      purgeAll(confirmPhrase) {
        return request("/api/master/purge-all", {
          method: "POST",
          body: JSON.stringify({ confirm_phrase: confirmPhrase }),
        });
      },
  
      /**
       * NEW — Mart Days search, scoped to mart_days_registrations via
       * ?event=mart_days. Same /api/visitors/search endpoint the
       * counter app's Mart Days mode uses; searchVisitor() above is
       * untouched and keeps defaulting to "other" for Other Events.
       */
      searchMartDaysVisitor(query) {
        const params = new URLSearchParams({ q: query, event: "mart_days" });
        return request(`/api/visitors/search?${params.toString()}`, {
          method: "GET",
        });
      },

      /** NEW — new Mart Days registration, same endpoint the counter app's Mart Days mode uses. */
      registerMartDaysVisitor(payload) {
        return request("/api/visitors/register-mart-days", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      },

      /** NEW — every Mart Days registrant on file, full details + print_count. Master-only endpoint. */
      listMartDaysVisitors() {
        return request("/api/master/mart-days/visitors", { method: "GET" });
      },

      /** NEW — { total_registered, total_prints } for the Mart Days Home tab's stat cards. Master-only endpoint. */
      getMartDaysStats() {
        return request("/api/master/mart-days/stats", { method: "GET" });
      },

      /** New registration — same endpoint the counter app uses. */
      registerVisitor(payload) {
        return request("/api/visitors/register", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      },
  
      /** Edit an existing visitor's details — same endpoint the counter app uses. */
      updateVisitor(urn, payload) {
        return request(`/api/visitors/${encodeURIComponent(urn)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      },
  
      /** Permanently delete a visitor record. Master-only endpoint. */
      deleteVisitor(urn) {
        return request(`/api/visitors/${encodeURIComponent(urn)}`, {
          method: "DELETE",
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
       * Downloads the URN-first master Excel file (every visitor
       * currently in the master store — sheet-synced + onsite).
       * Master-only endpoint. Not a plain <a href> link because the
       * route needs the master token attached, so this fetches the
       * file as a blob and triggers the browser download manually.
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
/* ==========================================================
   config.js — Mart Days Desk
   Same backend as the "Other Events" desk (frontend/config.js) —
   this is one FastAPI app serving both desks through different
   routers/prefixes (/api/visitors vs /api/mart-desk). Update
   API_HOST here if you move the backend; keep it in sync with
   frontend/config.js's API_HOST since they must point at the SAME
   server.
   ========================================================== */

   window.APP_CONFIG = {
    // Host[:port] ONLY — no "http://" or "https://" here.
    API_HOST: "ieml-badgedesk.onrender.com",

    // How often (ms) the dashboard pings /health to show
    // online/offline status in the top bar.
    HEALTH_CHECK_INTERVAL_MS: 15000,
  };

  window.APP_CONFIG.API_BASE_URL = `${window.location.protocol}//${window.APP_CONFIG.API_HOST}`;
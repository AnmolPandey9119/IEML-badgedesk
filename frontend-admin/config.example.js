/* ==========================================================
   config.example.js  (Master Console)
   Copy this to config.js and fill in the real backend host.
   SAME backend as the main counter app — the master console is
   just a different frontend calling the exact same FastAPI API,
   only with master credentials instead of operator credentials.
   ========================================================== */

   window.APP_CONFIG = {
    // Host[:port] ONLY — no "http://" or "https://" here.
    // Same backend host the main app (frontend/config.js) uses.
    API_HOST: "ieml-badgedesk.onrender.com",
  
    HEALTH_CHECK_INTERVAL_MS: 15000,
  };
  
  window.APP_CONFIG.API_BASE_URL = `${window.location.protocol}//${window.APP_CONFIG.API_HOST}`;
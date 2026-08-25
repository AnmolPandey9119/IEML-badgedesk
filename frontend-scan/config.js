/* ==========================================================
   config.example.js  (Entrance Scanner)
   Copy this to config.js and fill in the real backend host.
   SAME backend as the operator app and master console — this is
   just a third frontend calling the exact same FastAPI API, with
   scanner credentials instead of operator/master ones.
   ========================================================== */

   window.APP_CONFIG = {
    // Host[:port] ONLY — no "http://" or "https://" here.
    // Same backend host frontend/config.js and frontend-admin/config.js use.
    API_HOST: "ieml-badgedesk.onrender.com",
  
    HEALTH_CHECK_INTERVAL_MS: 15000,
  };
  
  window.APP_CONFIG.API_BASE_URL = `${window.location.protocol}//${window.APP_CONFIG.API_HOST}`;
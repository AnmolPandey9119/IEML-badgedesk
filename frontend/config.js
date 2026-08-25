/* ==========================================================
   config.js
   Central runtime config for this laptop/counter.
   THIS FILE IS MACHINE-SPECIFIC — every laptop running the
   registration dashboard should have its own config.js
   pointing to the FastAPI backend's LAN address.

   This file is intentionally NOT hardcoded inside api.js.
   It should be excluded from git (see .gitignore) and
   copied/edited per machine from config.example.js.
   ========================================================== */

   window.APP_CONFIG = {
    // Host[:port] ONLY — no "http://" or "https://" here.
    // LAN address of the FastAPI backend server running this event.
    // Example on another laptop: "192.168.1.10:8000"
    API_HOST: "ieml-badgedesk.onrender.com",
  
    // How often (ms) the dashboard pings /health to show
    // online/offline status in the top bar.
    HEALTH_CHECK_INTERVAL_MS: 15000,
  };
  
  // ----------------------------------------------------------------
  // Auto-build the full API_BASE_URL using the SAME protocol this
  // page itself was loaded with (http or https). This is what
  // removes the "Not Secure" warning safely: once ../generate-certs.sh
  // has been run and both run.sh scripts pick up the cert, this page
  // loads over https:// and this line automatically calls the backend
  // over https:// too — matching protocols, so the browser never
  // blocks the request as "mixed content". Before certs are set up,
  // both sides are still http:// and everything works exactly as
  // before. You never need to hand-edit this part.
  // ----------------------------------------------------------------
  window.APP_CONFIG.API_BASE_URL = `${window.location.protocol}//${window.APP_CONFIG.API_HOST}`;

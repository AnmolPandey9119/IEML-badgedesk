/* ==========================================================
   config.js
   Unlike the counter/admin apps' config.js (which is per-machine
   and points at a LAN address), this is a public web deployment —
   one config, pointing straight at the live Render backend.

   IMPORTANT: after you deploy this, add this site's Vercel URL to
   ALLOWED_ORIGINS in the backend's .env on Render (comma-separated
   alongside the existing 3 frontend URLs), otherwise the browser
   will block the request with a CORS error.
   ========================================================== */

   window.APP_CONFIG = {
    // Same Render backend the rest of the platform already uses.
    API_BASE_URL: "https://ieml-badgedesk.onrender.com",
  };
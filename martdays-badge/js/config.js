/* ==========================================================
   config.js
   Standalone e-badge download platform — separate Vercel project
   from the registration form (frontend-martdays), same pattern as
   frontend-admin/frontend-scan being separate from frontend. One
   config, pointing straight at the live Render backend.

   IMPORTANT: after you deploy this, add this site's Vercel URL to
   ALLOWED_ORIGINS in the backend's .env on Render (comma-separated
   alongside the existing frontend URLs), otherwise the browser
   will block the request with a CORS error.
   ========================================================== */

   window.APP_CONFIG = {
    // Same Render backend the rest of the platform already uses.
    API_BASE_URL: "https://ieml-badgedesk.onrender.com",
  };
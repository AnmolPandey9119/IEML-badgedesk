/* ==========================================================
   theme.js
   Light/dark theme toggle. Preference is saved in localStorage
   so it persists across reloads and future visits on this
   browser/laptop.

   IMPORTANT: the very first block below runs immediately
   (not inside DOMContentLoaded) and must be loaded in <head>,
   BEFORE the CSS finishes rendering — this prevents a "flash"
   of the wrong theme on page load.
   ========================================================== */

   (function () {
    const STORAGE_KEY = "ieml_theme";
    const saved = localStorage.getItem(STORAGE_KEY);
    const theme = saved === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", theme);
  })();
  
  document.addEventListener("DOMContentLoaded", () => {
    const STORAGE_KEY = "ieml_theme";
    const toggleBtn = document.getElementById("theme-toggle-btn");
    if (!toggleBtn) return;
  
    function applyButtonLabel(theme) {
      toggleBtn.textContent = theme === "dark" ? "☀️ Light" : "🌙 Dark";
    }
  
    applyButtonLabel(document.documentElement.getAttribute("data-theme") || "light");
  
    toggleBtn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem(STORAGE_KEY, next);
      applyButtonLabel(next);
    });
  });
/* ==========================================================
   auth.js
   Two responsibilities:
   1) Shared token helpers (window.Auth) used by api.js (attach
      token to requests) and app.js (guard the dashboard page).
      Token lives in sessionStorage — cleared automatically
      when the browser/tab closes, so a shared counter laptop
      doesn't stay logged in overnight.
   2) Login FORM handling — only runs if #login-form exists on
      the current page (i.e. we're on login.html).

   REVERTED (Mart Days removed): this file used to also remember
   which of two events (event="other" / "mart_days") a badge desk
   login was scoped to (there were two separate operator logins —
   ADMIN_USERNAME and ADMIN_MARTDAYS_USERNAME — see backend/routers/
   auth.py). Mart Days now runs on its own separate portal, so
   there's only the one badge desk login again and no event concept
   to track here.
   ========================================================== */

   const Auth = (() => {
    const TOKEN_KEY = "ieml_badge_token";
  
    return {
      getToken() {
        return sessionStorage.getItem(TOKEN_KEY);
      },
      setToken(token) {
        sessionStorage.setItem(TOKEN_KEY, token);
      },
      clearToken() {
        sessionStorage.removeItem(TOKEN_KEY);
      },
      isLoggedIn() {
        return !!this.getToken();
      },
      /** Call when the backend returns 401 anywhere — session is dead. */
      logout(redirect = true) {
        this.clearToken();
        if (redirect) {
          window.location.href = "login.html";
        }
      },
    };
  })();
  
  window.Auth = Auth;
  
  /* ---------------- Login form (only on login.html) ---------------- */
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("login-form");
    if (!form) return; // not on the login page
  
    // Already logged in with a valid-looking token? Skip straight to the dashboard.
    if (Auth.isLoggedIn()) {
      window.location.href = "index.html";
      return;
    }
  
    const errorBox = document.getElementById("login-error");
    const loginBtn = document.getElementById("login-btn");
  
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errorBox.classList.add("hidden");
  
      const username = document.getElementById("login-username").value.trim();
      const password = document.getElementById("login-password").value;
  
      loginBtn.disabled = true;
      loginBtn.textContent = "Logging in...";
  
      const result = await API.login(username, password);
  
      loginBtn.disabled = false;
      loginBtn.textContent = "Login";
  
      if (!result.ok) {
        errorBox.textContent = result.error || "Login failed";
        errorBox.classList.remove("hidden");
        return;
      }
  
      Auth.setToken(result.data.access_token);
      window.location.href = "index.html";
    });
  });
/* ==========================================================
   auth.js (Master Console)
   Same pattern as the main app's auth.js, but with its OWN
   sessionStorage key ("ieml_master_token" instead of
   "ieml_badge_token") — so a manager who's logged into both the
   counter app and the master console in the same browser doesn't
   clobber one session with the other.
   ========================================================== */

   const Auth = (() => {
    const TOKEN_KEY = "ieml_master_token";
  
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
          window.location.href = "master-login.html";
        }
      },
    };
  })();
  
  window.Auth = Auth;
  
  /* ---------------- Login form (only on master-login.html) ---------------- */
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("login-form");
    if (!form) return; // not on the login page
  
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
  
      // Extra guard: this login endpoint is shared with the operator
      // app. If someone types operator credentials into the MASTER
      // login page, the backend happily returns a valid token, but
      // role will be "operator" — the master API routes (visitors,
      // print-stats, delete) would then just 403 everywhere. Catch
      // it here instead, with a clear message, before that happens.
      if (result.data.role !== "master") {
        errorBox.textContent = "This account doesn't have master console access.";
        errorBox.classList.remove("hidden");
        return;
      }
  
      Auth.setToken(result.data.access_token);
      window.location.href = "index.html";
    });
  });
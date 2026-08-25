/* ==========================================================
   auth.js (Entrance Scanner)
   Same pattern as the master console's auth.js, own token key
   ("ieml_scanner_token") so a phone/browser that's ever also
   logged into the operator or master apps doesn't clash sessions.
   ========================================================== */

   const Auth = (() => {
    const TOKEN_KEY = "ieml_scanner_token";
  
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
      logout(redirect = true) {
        this.clearToken();
        if (redirect) {
          window.location.href = "scan-login.html";
        }
      },
    };
  })();
  
  window.Auth = Auth;
  
  /* ---------------- Login form (only on scan-login.html) ---------------- */
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("login-form");
    if (!form) return;
  
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
  
      // Same shared-login-endpoint guard as master-login.html: someone
      // typing operator/master credentials here would get a valid
      // token, just not role="scanner" — catch it with a clear message
      // instead of letting them into a scanner UI that then 403s.
      if (result.data.role !== "scanner") {
        errorBox.textContent = "This account doesn't have scanner access.";
        errorBox.classList.remove("hidden");
        return;
      }
  
      Auth.setToken(result.data.access_token);
      window.location.href = "index.html";
    });
  });
/* ==========================================================
   event-gate.js
   Shown once per login session, right after the dashboard loads:
   an overlay asking the operator to pick "Other Events" or
   "Mart Days". "Other Events" unlocks immediately. "Mart Days"
   asks for the extra gate password (POST /api/auth/verify-mart-
   days-access) before unlocking.

   The choice is remembered in sessionStorage (cleared when the
   tab/browser closes, same lifetime as the login token) so it
   survives a page refresh but always asks again after a fresh
   login. Everything else in the app (api.js, app.js) reads the
   current choice through window.EventGate.getCurrentEvent().
   ========================================================== */

   const EventGate = (() => {
    const EVENT_KEY = "ieml_current_event"; // "other" | "mart_days"
  
    return {
      getCurrentEvent() {
        return sessionStorage.getItem(EVENT_KEY);
      },
      isMartDays() {
        return this.getCurrentEvent() === "mart_days";
      },
      _setCurrentEvent(value) {
        sessionStorage.setItem(EVENT_KEY, value);
      },
      _clearCurrentEvent() {
        sessionStorage.removeItem(EVENT_KEY);
      },
    };
  })();
  
  window.EventGate = EventGate;
  
  document.addEventListener("DOMContentLoaded", () => {
    const overlay = document.getElementById("event-gate-overlay");
    if (!overlay) return; // not on index.html
  
    const els = {
      overlay,
      choiceScreen: document.getElementById("event-gate-choice"),
      passwordScreen: document.getElementById("event-gate-password"),
      otherBtn: document.getElementById("event-gate-other-btn"),
      martDaysBtn: document.getElementById("event-gate-martdays-btn"),
      passwordInput: document.getElementById("event-gate-password-input"),
      passwordSubmitBtn: document.getElementById("event-gate-password-submit-btn"),
      passwordBackBtn: document.getElementById("event-gate-password-back-btn"),
      passwordError: document.getElementById("event-gate-password-error"),
  
      otherEventsSections: document.querySelectorAll("[data-event-scope='other']"),
      martDaysSections: document.querySelectorAll("[data-event-scope='mart_days']"),
    };
  
    function applyModeToUI(event) {
      const isMartDays = event === "mart_days";
      els.otherEventsSections.forEach((el) => el.classList.toggle("hidden", isMartDays));
      els.martDaysSections.forEach((el) => el.classList.toggle("hidden", !isMartDays));
    }
  
    function unlock(event) {
      EventGate._setCurrentEvent(event);
      applyModeToUI(event);
      els.overlay.classList.add("hidden");
    }
  
    function showChoiceScreen() {
      els.passwordScreen.classList.add("hidden");
      els.choiceScreen.classList.remove("hidden");
      els.passwordInput.value = "";
      els.passwordError.classList.add("hidden");
    }
  
    function showPasswordScreen() {
      els.choiceScreen.classList.add("hidden");
      els.passwordScreen.classList.remove("hidden");
      els.passwordInput.focus();
    }
  
    // "Other Events" needs no extra password — same as before this feature existed.
    els.otherBtn.addEventListener("click", () => unlock("other"));
  
    els.martDaysBtn.addEventListener("click", showPasswordScreen);
    els.passwordBackBtn.addEventListener("click", showChoiceScreen);
  
    async function submitMartDaysPassword() {
      const password = els.passwordInput.value;
      if (!password) return;
  
      els.passwordSubmitBtn.disabled = true;
      els.passwordSubmitBtn.textContent = "Checking...";
      els.passwordError.classList.add("hidden");
  
      const result = await API.verifyMartDaysAccess(password);
  
      els.passwordSubmitBtn.disabled = false;
      els.passwordSubmitBtn.textContent = "Unlock";
  
      if (!result.ok) {
        els.passwordError.textContent = result.error || "Incorrect password";
        els.passwordError.classList.remove("hidden");
        els.passwordInput.value = "";
        els.passwordInput.focus();
        return;
      }
  
      unlock("mart_days");
    }
  
    els.passwordSubmitBtn.addEventListener("click", submitMartDaysPassword);
    els.passwordInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submitMartDaysPassword();
      }
    });
  
    // On load: if a choice was already made this session (e.g. the
    // operator refreshed the page), skip straight past the overlay.
    const existing = EventGate.getCurrentEvent();
    if (existing) {
      applyModeToUI(existing);
      els.overlay.classList.add("hidden");
    } else {
      showChoiceScreen();
    }
  });
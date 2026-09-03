/* ==========================================================
   app.js
   Main dashboard logic: search, registration form, edit.
   Actual "print" execution lives in print.js — this file calls
   window.BadgePrint.printVisitor(visitor) when needed.
   ========================================================== */

   document.addEventListener("DOMContentLoaded", () => {

    const els = {
      eventName: document.getElementById("event-name"),
      connectionStatus: document.getElementById("connection-status"),
      syncNowBtn: document.getElementById("sync-now-btn"),
      exportPrintLogBtn: document.getElementById("export-print-log-btn"),
      logoutBtn: document.getElementById("logout-btn"),
  
      searchInput: document.getElementById("search-input"),
      searchBtn: document.getElementById("search-btn"),
      searchResults: document.getElementById("search-results"),
  
      visitorSection: document.getElementById("visitor-details-section"),
      vName: document.getElementById("v-name"),
      vOrg: document.getElementById("v-org"),
      vUrn: document.getElementById("v-urn"),
      vDesignation: document.getElementById("v-designation"),
      vMobile: document.getElementById("v-mobile"),
      vEmail: document.getElementById("v-email"),
      vCategory: document.getElementById("v-category"),

      vNameInput: document.getElementById("v-name-input"),
      vOrgInput: document.getElementById("v-org-input"),
      vDesignationInput: document.getElementById("v-designation-input"),
      vMobileInput: document.getElementById("v-mobile-input"),
      vEmailInput: document.getElementById("v-email-input"),
      vCategoryInput: document.getElementById("v-category-input"),

      printBadgeBtn: document.getElementById("print-badge-btn"),
      editVisitorBtn: document.getElementById("edit-visitor-btn"),
      cancelVisitorBtn: document.getElementById("cancel-visitor-btn"),

      visitorViewActions: document.getElementById("visitor-view-actions"),
      visitorEditActions: document.getElementById("visitor-edit-actions"),
      saveVisitorBtn: document.getElementById("save-visitor-btn"),
      cancelEditBtn: document.getElementById("cancel-edit-btn"),
  
      toggleRegistrationBtn: document.getElementById("toggle-registration-btn"),
      registrationFormWrapper: document.getElementById("registration-form-wrapper"),
      registrationFormOther: document.getElementById("registration-form-other"),
      registrationFormMartDays: document.getElementById("registration-form-martdays"),
      cancelRegistrationBtns: document.querySelectorAll(".cancel-registration-btn"),
  
      printQueueStatus: document.getElementById("print-queue-status"),
      printCount: document.getElementById("print-count"),
      activityLogBody: document.getElementById("activity-log-body"),
      clearHistoryBtn: document.getElementById("clear-history-btn"),
    };
  
    let currentVisitor = null;
    let printQueueCount = 0;

    /* ---------------- Event Mode (Other Events / Mart Days) ----------------
       FIXED: this used to be an in-app overlay (js/event-gate.js) asking
       the operator to choose, with a second password for Mart Days.
       Now the event is decided at LOGIN (two separate badge desk
       accounts — see js/auth.js) and applied once here, on page load:
       sections tagged data-event-scope="other" / "mart_days" in
       index.html are shown/hidden to match, same as before, just
       driven by Auth.getEvent() instead of a runtime choice. */
    (function applyEventMode() {
      const isMartDays = window.Auth && window.Auth.isMartDays && window.Auth.isMartDays();
      document.querySelectorAll("[data-event-scope='other']").forEach((el) => el.classList.toggle("hidden", isMartDays));
      document.querySelectorAll("[data-event-scope='mart_days']").forEach((el) => el.classList.toggle("hidden", !isMartDays));

      // Mart Days always shows this fixed label on the topbar — it
      // never comes from the backend. "Other Events" keeps showing
      // whatever settings.event_name currently is (set per-event in
      // the backend .env), which checkConnection() below refreshes
      // on its own poll.
      if (isMartDays) {
        const eventNameEl = document.getElementById("event-name");
        if (eventNameEl) eventNameEl.textContent = "IEML Mart Days";
      }
    })();

    /* ---------------- Recent Activity + Print Count ----------------
       Both persist across page refreshes/reopens via localStorage
       (per-browser, this counter's own running total) — so a reload
       never wipes what happened, and the print count keeps climbing
       across the whole event, not just this session.
       This is NOT the platform's real data store — that's still the
       org server / master_store — this is just a local operator-
       facing convenience log/counter. */
    const MAX_ACTIVITY_ROWS = 30;
    const ACTIVITY_STORAGE_KEY = "ieml_badgedesk_activity_log";
    const PRINT_COUNT_STORAGE_KEY = "ieml_badgedesk_print_count";
    const DEVICE_NAME_STORAGE_KEY = "ieml_badgedesk_device_name";
    let activityLog = loadActivityLog();
    let printsCount = loadPrintCount();

    /* ---------------- Device name (for master console's per-device print stats) ----------------
       Asked once per browser/laptop, then remembered in localStorage.
       Purely a label sent alongside each print-log call — doesn't
       affect anything else this app does. */
    function getDeviceName() {
      let name = localStorage.getItem(DEVICE_NAME_STORAGE_KEY);
      if (!name) {
        name = (window.prompt("Name this counter/laptop (e.g. \"Counter 1\", \"Reception Laptop\"):", "") || "").trim();
        if (!name) name = "Unnamed device";
        try {
          localStorage.setItem(DEVICE_NAME_STORAGE_KEY, name);
        } catch {
          // Storage unavailable — we'll just ask again next print, harmless.
        }
      }
      return name;
    }

    function loadActivityLog() {
      try {
        const raw = localStorage.getItem(ACTIVITY_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    }

    function saveActivityLog() {
      try {
        localStorage.setItem(ACTIVITY_STORAGE_KEY, JSON.stringify(activityLog));
      } catch {
        // Storage full/unavailable — activity log just stays in-memory for this tab.
      }
    }

    function loadPrintCount() {
      try {
        const raw = localStorage.getItem(PRINT_COUNT_STORAGE_KEY);
        const n = raw ? parseInt(raw, 10) : 0;
        return Number.isFinite(n) && n >= 0 ? n : 0;
      } catch {
        return 0;
      }
    }

    function savePrintCount() {
      try {
        localStorage.setItem(PRINT_COUNT_STORAGE_KEY, String(printsCount));
      } catch {
        // Storage full/unavailable — count just stays in-memory for this tab.
      }
    }

    function updatePrintCount() {
      els.printCount.textContent = `🖨️ Prints: ${printsCount}`;
    }

    /* ---------------- Print Log (for "Export Print Log") ----------------
       Separate from `activityLog` (which is capped at MAX_ACTIVITY_ROWS
       for the on-screen table, and mixes searches/syncs/exports/prints
       together) — this is the FULL, uncapped record of every successful
       print only, so the export always has everyone who actually got a
       badge, however many other actions happened around it. */
    const PRINT_LOG_STORAGE_KEY = "ieml_badgedesk_print_log";
    let printLog = loadPrintLog();

    function loadPrintLog() {
      try {
        const raw = localStorage.getItem(PRINT_LOG_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    }

    function savePrintLog() {
      try {
        localStorage.setItem(PRINT_LOG_STORAGE_KEY, JSON.stringify(printLog));
      } catch {
        // Storage full/unavailable — print log just stays in-memory for this tab.
      }
    }

    function recordPrint(visitor) {
      printLog.push({
        time: new Date().toLocaleString([], { dateStyle: "short", timeStyle: "medium" }),
        name: visitor.name || "--",
        urn: visitor.urn || "--",
        org: visitor.organization || "",
        designation: visitor.designation || "",
        mobile: visitor.mobile || "",
        email: visitor.email || "",
        city: visitor.city || "",
        category: visitor.category || "",
        status: visitor.status || "",
      });
      savePrintLog();
    }

    function downloadPrintLogExcel() {
      if (printLog.length === 0) {
        alert("No prints recorded yet on this laptop.");
        return;
      }
      const header = [
        "Time", "URN", "Name", "Organization", "Designation",
        "Mobile", "Email", "City", "Category", "Status",
      ];
      const rows = printLog.map((p) => [
        p.time, p.urn, p.name, p.org, p.designation || "",
        p.mobile || "", p.email || "", p.city || "", p.category || "", p.status || "",
      ]);
      const worksheet = XLSX.utils.aoa_to_sheet([header, ...rows]);
      // Reasonable column widths so it's readable without manual resizing.
      worksheet["!cols"] = [
        { wch: 18 }, { wch: 10 }, { wch: 22 }, { wch: 22 }, { wch: 16 },
        { wch: 14 }, { wch: 26 }, { wch: 16 }, { wch: 16 }, { wch: 12 },
      ];
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Print Log");
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      XLSX.writeFile(workbook, `ieml-print-log-${stamp}.xlsx`);
    }

    els.exportPrintLogBtn.addEventListener("click", downloadPrintLogExcel);

    function addActivity({ name, urn, action, status }) {
      activityLog.unshift({
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        name: name || "--",
        urn: urn || "--",
        action,
        status, // "success" | "failed" | "pending"
      });
      if (activityLog.length > MAX_ACTIVITY_ROWS) {
        activityLog.length = MAX_ACTIVITY_ROWS;
      }
      saveActivityLog();
      renderActivity();
    }

    function renderActivity() {
      if (activityLog.length === 0) {
        els.activityLogBody.innerHTML =
          `<tr><td colspan="5" class="search-empty">No activity yet this session.</td></tr>`;
        return;
      }
      els.activityLogBody.innerHTML = activityLog
        .map((entry) => {
          const statusClass =
            entry.status === "success" ? "activity-status-success" : "activity-status-failed";
          const statusLabel = entry.status === "success" ? "Success" : "Failed";
          return `
            <tr>
              <td>${escapeHtml(entry.time)}</td>
              <td>${escapeHtml(entry.name)}</td>
              <td>${escapeHtml(entry.urn)}</td>
              <td>${escapeHtml(entry.action)}</td>
              <td><span class="activity-status ${statusClass}">${statusLabel}</span></td>
            </tr>`;
        })
        .join("");
    }

    renderActivity(); // show "No activity yet" placeholder on load

    /* ---------------- Clear History ----------------
       Wipes the Prints counter, the on-screen Activity table, AND
       the full Print Log (used by "Export Print Log") — but ONLY on
       THIS laptop's browser, since all three live in localStorage,
       never on the backend/master store. Each counter/laptop used
       at the event has to do this separately for a fresh start. */
    els.clearHistoryBtn.addEventListener("click", () => {
      const confirmed = confirm(
        "Clear Prints count, Recent Activity, and Print Log on THIS laptop?\n\n" +
        "This does NOT touch any visitor data or URNs — only this " +
        "laptop's local counters/history reset to zero."
      );
      if (!confirmed) return;

      activityLog = [];
      saveActivityLog();
      renderActivity();

      printsCount = 0;
      savePrintCount();
      updatePrintCount();

      printLog = [];
      savePrintLog();
    });
  
    /* ---------------- Logout ---------------- */
    els.logoutBtn.addEventListener("click", () => {
      window.Auth.logout(true);
    });
  
    /* ---------------- Connection Status ---------------- */
    async function checkConnection() {
      const result = await API.checkHealth();
      if (result.ok) {
        els.connectionStatus.textContent = "Online";
        els.connectionStatus.className = "status status-online";
        // Mart Days always shows a fixed label, regardless of
        // whatever settings.event_name the backend is currently set
        // to — that backend value is "Other Events" only from here on.
        // See applyEventMode() above for the at-load version of this
        // same check.
        const isMartDays = window.Auth && window.Auth.isMartDays && window.Auth.isMartDays();
        if (isMartDays) {
          els.eventName.textContent = "IEML Mart Days";
        } else if (result.data.event) {
          els.eventName.textContent = result.data.event;
        }
      } else {
        els.connectionStatus.textContent = "Offline";
        els.connectionStatus.className = "status status-offline";
      }
    }
  
    checkConnection();
    updatePrintCount();
    const healthCheckInterval =
      (window.APP_CONFIG && window.APP_CONFIG.HEALTH_CHECK_INTERVAL_MS) || 15000;
    setInterval(checkConnection, healthCheckInterval);

    /* ---------------- Sync Now ----------------
       Manual trigger for the same sheet-sync the backend already runs
       automatically in the background. Fetches the Google Sheet right
       now, saves any new registrants into the master store with a
       fresh URN. */
    els.syncNowBtn.addEventListener("click", async () => {
      els.syncNowBtn.disabled = true;
      els.syncNowBtn.textContent = "Syncing...";

      const result = await API.runSync();

      els.syncNowBtn.disabled = false;
      els.syncNowBtn.textContent = "🔄 Sync Now";

      if (!result.ok) {
        alert(`Sync failed: ${result.error}`);
        return;
      }

      const { new: newCount = 0, updated = 0, unchanged = 0, blank = 0, no_name: noName = 0, fetched = 0 } = result.data;
      addActivity({
        name: "--",
        urn: "--",
        action: `Sync (${newCount} new, ${updated} updated)`,
        status: "success",
      });

      let msg = `Sync done — ${newCount} new, ${updated} updated, ${unchanged} unchanged (${fetched} rows checked).`;
      if (blank > 0) {
        msg += `\n\n⚠️ ${blank} completely blank row(s) skipped.`;
      }
      if (noName > 0) {
        msg += `\n\nℹ️ ${noName} row(s) had no Full Name — registered anyway with a fallback name (their email/mobile/org).`;
      }
      alert(msg);
    });
  
    /* ---------------- Search ---------------- */
    // Also what a QR scan resolves through: the scanner types the
    // scanned URN into this box and "presses" Enter, exactly like
    // manual typing, so no separate scanner-handling code is needed.
    // We just make sure the box is focused and ready to receive it.
    function focusSearchInput() {
      els.searchInput.focus();
    }
    focusSearchInput();

    async function runSearch() {
      const query = els.searchInput.value.trim();
      if (!query) return;
  
      els.searchResults.innerHTML = `<div class="search-empty">Searching...</div>`;
  
      const result = await API.searchVisitor(query);
  
      if (!result.ok) {
        els.searchResults.innerHTML = `<div class="search-empty">Error: ${escapeHtml(result.error)}</div>`;
        return;
      }
  
      const matches = result.data.results || [];
  
      if (matches.length === 0) {
        els.searchResults.innerHTML = `<div class="search-empty">No visitor found for "${escapeHtml(query)}". You can register them below.</div>`;
        return;
      }
  
      // Exact single match -> go straight to visitor details
      if (matches.length === 1) {
        showVisitorDetails(matches[0]);
        els.searchResults.innerHTML = "";
        return;
      }
  
      // Multiple matches -> let operator pick
      els.searchResults.innerHTML = "";
      matches.forEach((visitor) => {
        const row = document.createElement("div");
        row.className = "search-result-item";
        row.innerHTML = `
          <div>
            <strong>${escapeHtml(visitor.name)}</strong> — ${escapeHtml(visitor.organization || "")}
          </div>
          <div>${escapeHtml(visitor.urn || "")}</div>
        `;
        row.addEventListener("click", () => {
          showVisitorDetails(visitor);
          els.searchResults.innerHTML = "";
        });
        els.searchResults.appendChild(row);
      });
    }
  
    els.searchBtn.addEventListener("click", runSearch);
    els.searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        runSearch();
      }
    });
  
    /* ---------------- Visitor Details (view mode) ---------------- */
    function showVisitorDetails(visitor) {
      currentVisitor = visitor;
      renderViewMode();
      exitEditMode(); // always open in view mode, never mid-edit
      els.visitorSection.classList.remove("hidden");
      els.visitorSection.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function renderViewMode() {
      els.vName.textContent = currentVisitor.name || "--";
      els.vOrg.textContent = currentVisitor.organization || "--";
      els.vUrn.textContent = currentVisitor.urn || "--";
      els.vDesignation.textContent = currentVisitor.designation || "--";
      els.vMobile.textContent = currentVisitor.mobile || "--";
      els.vEmail.textContent = currentVisitor.email || "--";
      els.vCategory.textContent = currentVisitor.category || "--";
    }
  
    els.cancelVisitorBtn.addEventListener("click", () => {
      currentVisitor = null;
      els.visitorSection.classList.add("hidden");
      els.searchInput.value = "";
      focusSearchInput();
    });
  
    els.printBadgeBtn.addEventListener("click", () => {
      if (!currentVisitor) return;
      triggerPrint(currentVisitor);
    });

    /* ---------------- Visitor Details (edit mode) ---------------- */
    function enterEditMode() {
      if (!currentVisitor) return;

      // Pre-fill inputs with the current (possibly just-searched) values.
      els.vNameInput.value = currentVisitor.name || "";
      els.vOrgInput.value = currentVisitor.organization || "";
      els.vDesignationInput.value = currentVisitor.designation || "";
      els.vMobileInput.value = currentVisitor.mobile || "";
      els.vEmailInput.value = currentVisitor.email || "";
      els.vCategoryInput.value = currentVisitor.category || "visitor";

      // Swap each field's <p> for its <input>/<select>.
      els.vName.classList.add("hidden");
      els.vNameInput.classList.remove("hidden");
      els.vOrg.classList.add("hidden");
      els.vOrgInput.classList.remove("hidden");
      els.vDesignation.classList.add("hidden");
      els.vDesignationInput.classList.remove("hidden");
      els.vMobile.classList.add("hidden");
      els.vMobileInput.classList.remove("hidden");
      els.vEmail.classList.add("hidden");
      els.vEmailInput.classList.remove("hidden");
      els.vCategory.classList.add("hidden");
      els.vCategoryInput.classList.remove("hidden");

      els.visitorViewActions.classList.add("hidden");
      els.visitorEditActions.classList.remove("hidden");

      els.vNameInput.focus();
    }

    function exitEditMode() {
      els.vName.classList.remove("hidden");
      els.vNameInput.classList.add("hidden");
      els.vOrg.classList.remove("hidden");
      els.vOrgInput.classList.add("hidden");
      els.vDesignation.classList.remove("hidden");
      els.vDesignationInput.classList.add("hidden");
      els.vMobile.classList.remove("hidden");
      els.vMobileInput.classList.add("hidden");
      els.vEmail.classList.remove("hidden");
      els.vEmailInput.classList.add("hidden");
      els.vCategory.classList.remove("hidden");
      els.vCategoryInput.classList.add("hidden");

      els.visitorViewActions.classList.remove("hidden");
      els.visitorEditActions.classList.add("hidden");
    }

    els.editVisitorBtn.addEventListener("click", enterEditMode);

    els.cancelEditBtn.addEventListener("click", () => {
      exitEditMode(); // just discard input values, currentVisitor is untouched
    });

    els.saveVisitorBtn.addEventListener("click", async () => {
      if (!currentVisitor) return;

      const payload = {
        name: els.vNameInput.value.trim(),
        organization: els.vOrgInput.value.trim(),
        designation: els.vDesignationInput.value.trim(),
        mobile: els.vMobileInput.value.trim(),
        email: els.vEmailInput.value.trim(),
        category: els.vCategoryInput.value,
      };

      if (!payload.name || !payload.organization || !payload.mobile) {
        alert("Name, Organization, and Mobile No. are required.");
        return;
      }

      els.saveVisitorBtn.disabled = true;
      els.saveVisitorBtn.textContent = "Saving...";

      const result = await API.updateVisitor(currentVisitor.urn, payload);

      els.saveVisitorBtn.disabled = false;
      els.saveVisitorBtn.textContent = "Save Changes";

      if (!result.ok) {
        addActivity({ name: payload.name, urn: currentVisitor.urn, action: "Update Details", status: "failed" });
        alert(`Update failed: ${result.error}`);
        return;
      }

      currentVisitor = result.data.visitor;
      renderViewMode();
      exitEditMode();
      addActivity({ name: currentVisitor.name, urn: currentVisitor.urn, action: "Update Details", status: "success" });
    });

    /* ---------------- Registration Form ----------------
       Two separate <form> elements share this section — which one
       is visible is controlled by applyEventMode() above (data-event-
       scope toggling based on Other Events / Mart Days login). Both
       share the same "+ New Registration" toggle and Cancel buttons. */
    els.toggleRegistrationBtn.addEventListener("click", () => {
      els.registrationFormWrapper.classList.toggle("hidden");
    });

    els.cancelRegistrationBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        els.registrationFormOther.reset();
        els.registrationFormMartDays.reset();
        els.registrationFormWrapper.classList.add("hidden");
        focusSearchInput();
      });
    });

    async function submitRegistration(form, apiCall) {
      const formData = new FormData(form);
      const payload = Object.fromEntries(formData.entries());

      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = "Registering...";

      const result = await apiCall(payload);

      submitBtn.disabled = false;
      submitBtn.textContent = "Register & Print";

      if (!result.ok) {
        addActivity({ name: payload.name || payload.full_name, urn: "--", action: "New Registration", status: "failed" });
        alert(`Registration failed: ${result.error}`);
        return;
      }

      const newVisitor = result.data.visitor;

      addActivity({ name: newVisitor.name, urn: newVisitor.urn, action: "New Registration", status: "success" });

      form.reset();
      els.registrationFormWrapper.classList.add("hidden");

      // Immediately move to print
      triggerPrint(newVisitor);
    }

    els.registrationFormOther.addEventListener("submit", (e) => {
      e.preventDefault();
      submitRegistration(els.registrationFormOther, API.registerVisitor);
    });

    els.registrationFormMartDays.addEventListener("submit", (e) => {
      e.preventDefault();
      submitRegistration(els.registrationFormMartDays, API.registerMartDaysVisitor);
    });
  
    /* ---------------- Print Trigger ---------------- */
    function triggerPrint(visitor) {
      printQueueCount++;
      updateQueueStatus();
      els.printBadgeBtn.disabled = true;
  
      window.BadgePrint.printVisitor(visitor, (success) => {
        printQueueCount = Math.max(0, printQueueCount - 1);
        updateQueueStatus();
        els.printBadgeBtn.disabled = false;

        addActivity({
          name: visitor.name,
          urn: visitor.urn,
          action: "Print Badge",
          status: success ? "success" : "failed",
        });

        if (success) {
          printsCount++;
          savePrintCount();
          updatePrintCount();
          recordPrint(visitor);

          // Tell the backend a print happened — this is what feeds the
          // master console's print stats + "Printed Badges" list. If it
          // fails (offline counter, etc.), the print itself already
          // succeeded and the local log above already has it, so we
          // just log a warning and move on — never alert/block on this.
          API.logPrint(visitor.urn, getDeviceName()).then((result) => {
            if (!result.ok) {
              console.warn("Print happened but wasn't logged to the master console:", result.error);
            }
          });
        } else {
          alert(`Print failed for ${visitor.name}. Please retry.`);
        }
      });
    }
  
    function updateQueueStatus() {
      els.printQueueStatus.textContent = `Queue: ${printQueueCount}`;
    }
  
    /* ---------------- Utils ---------------- */
    function escapeHtml(str) {
      if (str === undefined || str === null) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }
  
  });
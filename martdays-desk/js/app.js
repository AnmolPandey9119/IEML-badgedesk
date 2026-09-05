/* ==========================================================
   app.js — Mart Days Desk
   Same structure as the "Other Events" desk's app.js. Differences:
   - No Sync Now button/handler (no Google Sheet feeds this desk).
   - localStorage keys are namespaced "martdays" so this desk's local
     activity/print history never mixes with the other desk's, even
     if someone ever runs both against the same browser profile.
   - "Organization" -> "Company Name" and "Visitor Category" ->
     "Buyer Type" throughout, to match index.html's labels/options.
   ========================================================== */

   document.addEventListener("DOMContentLoaded", () => {

    const els = {
      eventName: document.getElementById("event-name"),
      connectionStatus: document.getElementById("connection-status"),
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
      cancelRegistrationBtns: document.querySelectorAll(".cancel-registration-btn"),

      printQueueStatus: document.getElementById("print-queue-status"),
      printCount: document.getElementById("print-count"),
      activityLogBody: document.getElementById("activity-log-body"),
      clearHistoryBtn: document.getElementById("clear-history-btn"),
    };

    let currentVisitor = null;
    let printQueueCount = 0;

    const MAX_ACTIVITY_ROWS = 30;
    const ACTIVITY_STORAGE_KEY = "ieml_martdays_desk_activity_log";
    const PRINT_COUNT_STORAGE_KEY = "ieml_martdays_desk_print_count";
    const DEVICE_NAME_STORAGE_KEY = "ieml_martdays_desk_device_name";
    const PRINT_LOG_STORAGE_KEY = "ieml_martdays_desk_print_log";
    let activityLog = loadActivityLog();
    let printsCount = loadPrintCount();
    let printLog = loadPrintLog();

    function getDeviceName() {
      let name = localStorage.getItem(DEVICE_NAME_STORAGE_KEY);
      if (!name) {
        name = (window.prompt("Name this counter/laptop (e.g. \"Mart Days Counter 1\"):", "") || "").trim();
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
        category: visitor.category || "",
      });
      savePrintLog();
    }

    function downloadPrintLogExcel() {
      if (printLog.length === 0) {
        alert("No prints recorded yet on this laptop.");
        return;
      }
      const header = ["Time", "URN", "Name", "Company Name", "Designation", "Mobile", "Email", "Buyer Type"];
      const rows = printLog.map((p) => [
        p.time, p.urn, p.name, p.org, p.designation || "", p.mobile || "", p.email || "", p.category || "",
      ]);
      const worksheet = XLSX.utils.aoa_to_sheet([header, ...rows]);
      worksheet["!cols"] = [
        { wch: 18 }, { wch: 10 }, { wch: 22 }, { wch: 22 }, { wch: 16 }, { wch: 14 }, { wch: 26 }, { wch: 22 },
      ];
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Print Log");
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      XLSX.writeFile(workbook, `ieml-martdays-print-log-${stamp}.xlsx`);
    }

    els.exportPrintLogBtn.addEventListener("click", downloadPrintLogExcel);

    function addActivity({ name, urn, action, status }) {
      activityLog.unshift({
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        name: name || "--",
        urn: urn || "--",
        action,
        status,
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

    renderActivity();

    els.clearHistoryBtn.addEventListener("click", () => {
      const confirmed = confirm(
        "Clear Prints count, Recent Activity, and Print Log on THIS laptop?\n\n" +
        "This does NOT touch any registrant data or URNs — only this " +
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

    els.logoutBtn.addEventListener("click", () => {
      window.Auth.logout(true);
    });

    async function checkConnection() {
      const result = await API.checkHealth();
      if (result.ok) {
        els.connectionStatus.textContent = "Online";
        els.connectionStatus.className = "status status-online";
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

    /* ---------------- Search ---------------- */
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
        els.searchResults.innerHTML = `<div class="search-empty">No Mart Days registrant found for "${escapeHtml(query)}". You can register them below.</div>`;
        return;
      }

      if (matches.length === 1) {
        showVisitorDetails(matches[0]);
        els.searchResults.innerHTML = "";
        return;
      }

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
      exitEditMode();
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

      els.vNameInput.value = currentVisitor.name || "";
      els.vOrgInput.value = currentVisitor.organization || "";
      els.vDesignationInput.value = currentVisitor.designation || "";
      els.vMobileInput.value = currentVisitor.mobile || "";
      els.vEmailInput.value = currentVisitor.email || "";
      els.vCategoryInput.value = currentVisitor.category || "";

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
      exitEditMode();
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

      if (!payload.name || !payload.organization || !payload.mobile || !payload.category) {
        alert("Full Name, Company Name, Mobile No., and Buyer Type are required.");
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

    /* ---------------- Registration Form ---------------- */
    els.toggleRegistrationBtn.addEventListener("click", () => {
      els.registrationFormWrapper.classList.toggle("hidden");
    });

    els.cancelRegistrationBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        els.registrationFormOther.reset();
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
        addActivity({ name: payload.name, urn: "--", action: "New Registration", status: "failed" });
        alert(`Registration failed: ${result.error}`);
        return;
      }

      const newVisitor = result.data.visitor;

      addActivity({ name: newVisitor.name, urn: newVisitor.urn, action: "New Registration", status: "success" });

      form.reset();
      els.registrationFormWrapper.classList.add("hidden");

      triggerPrint(newVisitor);
    }

    els.registrationFormOther.addEventListener("submit", (e) => {
      e.preventDefault();
      submitRegistration(els.registrationFormOther, API.registerVisitor);
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

          API.logPrint(visitor.urn, getDeviceName()).then((result) => {
            if (!result.ok) {
              console.warn("Print happened but wasn't logged to the backend:", result.error);
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
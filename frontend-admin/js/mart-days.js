/* ==========================================================
   mart-days.js (Master Console)

   Two jobs:
   1) The "Choose Event" gate shown once per master-login session
      (Other Events vs Mart Days) — no password step, unlike the
      counter app's version, since this is already behind master
      login. Reopenable any time via the topbar's "🔁 Switch Event"
      button. Choice remembered in sessionStorage under a DIFFERENT
      key than the counter app uses, so the two apps never interfere
      with each other even if somehow open in related tabs.
   2) A self-contained "Mart Days Home" panel — its own state, own
      DOM ids (all prefixed md-), own render/search/add/edit/delete/
      print functions. Deliberately NOT sharing app.js's allVisitors/
      panelMode/activeUrn state or its functions — this keeps the
      existing Other Events console (app.js) completely untouched,
      zero risk of a Mart Days bug ever affecting the live, already-
      working Other Events flow.

   Mart Days has no Print Count / Scan Monitoring / Unscanned Entries
   tabs on purpose: it doesn't track per-device print breakdown or
   any entrance scanning at all (see backend services/master_store.py
   — mart_days_registrations has no print_log/scan_log of its own,
   just a running print_count). So its Home tab is just: how many
   registered so far, how many badges printed, find & print, and the
   full registrant list.

   Editing is deliberately limited to Full Name / Company Name /
   Designation / Email / Phone — NOT Buyer Type / Address / District /
   State / Country / Pincode. This isn't a new restriction introduced
   here — the backend's update_mart_days_visitor() has always only
   supported updating those five fields (see routers/registration.py's
   PUT /api/visitors/{urn}), same as the counter app's own edit form.
   ========================================================== */

   let allMartDaysVisitors = [];
   let mdPanelMode = "closed"; // "closed" | "add" | "view" | "edit"
   let mdActiveUrn = null;
   
   const MASTER_EVENT_KEY = "ieml_master_current_event"; // "other" | "mart_days"
   
   // Exposed so app.js's startHealthCheck() can check the current mode
   // before writing the backend's settings.event_name into the topbar
   // label — Mart Days always shows a fixed label instead, never the
   // backend value. Same pattern as the counter app's window.EventGate.
   window.MasterEventGate = {
     isMartDays() {
       return sessionStorage.getItem(MASTER_EVENT_KEY) === "mart_days";
     },
   };
   
   document.addEventListener("DOMContentLoaded", () => {
     wireEventGate();
     wireSwitchEventBtn();
     wireMartDaysAddToggle();
     wireMartDaysForm();
     wireMartDaysViewActions();
     wireMartDaysTableRowClicks();
     wireMartDaysSearch();
     wireMartDaysFindAndPrint();
     wireMartDaysExport();
     wireMdClearHistory();
     wireMdPurgeAll();
   
     const existing = sessionStorage.getItem(MASTER_EVENT_KEY);
     if (existing) {
       applyMasterMode(existing);
     } else {
       showEventGate();
     }
   });
   
   /* ---------------- Event Gate ---------------- */
   
   function showEventGate() {
     document.getElementById("event-gate-overlay").classList.remove("hidden");
   }
   
   function wireEventGate() {
     document.getElementById("event-gate-other-btn").addEventListener("click", () => chooseMode("other"));
     document.getElementById("event-gate-martdays-btn").addEventListener("click", () => chooseMode("mart_days"));
   }
   
   function chooseMode(mode) {
     sessionStorage.setItem(MASTER_EVENT_KEY, mode);
     applyMasterMode(mode);
     document.getElementById("event-gate-overlay").classList.add("hidden");
   }
   
   function wireSwitchEventBtn() {
     const btn = document.getElementById("switch-event-btn");
     if (!btn) return;
     btn.addEventListener("click", showEventGate);
   }
   
   /* Shows/hides the existing Other Events tabs+panels (app.js — left
      completely alone) vs the new Mart Days panel, and updates the
      topbar mode badge + a couple of Other-Events-only topbar buttons
      that don't apply to Mart Days (Sync Now / full-DB Export Excel,
      both scoped to the `visitors` table only). */
   function applyMasterMode(mode) {
     const isMartDays = mode === "mart_days";
   
     const tabsNav = document.querySelector(".tabs-nav");
     if (tabsNav) tabsNav.classList.toggle("hidden", isMartDays);
   
     document.getElementById("panel-home").classList.toggle("hidden", isMartDays);
     const mdPanel = document.getElementById("panel-martdays-home");
     if (mdPanel) mdPanel.classList.toggle("hidden", !isMartDays);
   
     if (!isMartDays) {
       // Back to Other Events — land on Home tab, not wherever the nav
       // was last left (e.g. mid Scan Monitoring tab from before).
       if (typeof window.switchTab === "function") window.switchTab("home");
     } else {
       // Leaving Other Events — close its detail panel if it happened
       // to be open, so it's not sitting hidden-but-open underneath.
       document.getElementById("panel-print-count").classList.add("hidden");
       document.getElementById("panel-scan").classList.add("hidden");
       document.getElementById("panel-unscanned").classList.add("hidden");
     }
   
     const syncBtn = document.getElementById("sync-now-btn");
     const exportBtn = document.getElementById("export-excel-btn");
     if (syncBtn) syncBtn.classList.toggle("hidden", isMartDays);
     if (exportBtn) exportBtn.classList.toggle("hidden", isMartDays);
   
     const badge = document.getElementById("master-mode-badge");
     if (badge) {
       badge.textContent = isMartDays ? "Mart Days" : "Other Events";
       badge.classList.remove("hidden");
     }
   
     // Instant feedback on switch — app.js's startHealthCheck() then
     // keeps this correct on every subsequent poll (see the
     // MasterEventGate.isMartDays() check added there).
     const eventNameEl = document.getElementById("event-name");
     if (eventNameEl && isMartDays) {
       eventNameEl.textContent = "IEML Mart Days";
     }
   
     if (isMartDays) {
       loadMartDaysStats();
       loadMartDaysVisitors();
     }
   }
   
   /* ---------------- Stats ---------------- */
   
   async function loadMartDaysStats() {
     const registeredEl = document.getElementById("md-home-registered-total");
     const printEl = document.getElementById("md-home-print-total");
   
     const result = await API.getMartDaysStats();
     if (!result.ok) {
       if (registeredEl) registeredEl.textContent = "—";
       if (printEl) printEl.textContent = "—";
       return;
     }
   
     if (registeredEl) registeredEl.textContent = result.data.total_registered;
     if (printEl) printEl.textContent = result.data.total_prints;
   }
   
   /* ---------------- Visitors: fetch + render + filter ---------------- */
   
   async function loadMartDaysVisitors() {
     const bodyEl = document.getElementById("md-visitors-table-body");
     const result = await API.listMartDaysVisitors();
     if (!result.ok) {
       bodyEl.innerHTML = `<tr><td colspan="7" class="search-empty">${mdEscapeHtml(result.error || "Failed to load")}</td></tr>`;
       return;
     }
     allMartDaysVisitors = result.data.visitors || [];
     renderMartDaysTable(mdCurrentFiltered());
     loadMartDaysStats();
   }
   
   function mdMatchesQuery(v, q) {
     return (
       (v.urn || "").toLowerCase().includes(q) ||
       (v.full_name || "").toLowerCase().includes(q) ||
       (v.phone_number || "").toLowerCase().includes(q) ||
       (v.company_name || "").toLowerCase().includes(q) ||
       (v.email || "").toLowerCase().includes(q)
     );
   }
   
   function mdCurrentFiltered() {
     const input = document.getElementById("md-visitors-search");
     const q = input ? input.value.trim().toLowerCase() : "";
     return q ? allMartDaysVisitors.filter((v) => mdMatchesQuery(v, q)) : allMartDaysVisitors;
   }
   
   function wireMartDaysSearch() {
     const input = document.getElementById("md-visitors-search");
     if (!input) return;
     input.addEventListener("input", () => renderMartDaysTable(mdCurrentFiltered()));
   }
   
   function renderMartDaysTable(visitors) {
     const bodyEl = document.getElementById("md-visitors-table-body");
     const totalEl = document.getElementById("md-visitors-total");
     if (!bodyEl) return;
   
     if (totalEl) totalEl.textContent = `${visitors.length} total`;
   
     if (visitors.length === 0) {
       bodyEl.innerHTML = `<tr><td colspan="7" class="search-empty">No Mart Days registrations yet</td></tr>`;
       return;
     }
   
     bodyEl.innerHTML = visitors
       .map(
         (v) => `
         <tr data-urn="${mdEscapeHtml(v.urn)}" class="${v.urn === mdActiveUrn ? "row-active" : ""}">
           <td>${mdEscapeHtml(v.urn)}</td>
           <td>${mdEscapeHtml(v.full_name)}</td>
           <td>${mdEscapeHtml(v.buyer_type || "")}</td>
           <td>${mdEscapeHtml(v.company_name || "")}</td>
           <td>${mdEscapeHtml(v.phone_number || "")}</td>
           <td>${mdEscapeHtml(v.email || "")}</td>
           <td><span class="print-count-pill">${v.print_count || 0}</span></td>
         </tr>`
       )
       .join("");
   }
   
   function wireMartDaysTableRowClicks() {
     const body = document.getElementById("md-visitors-table-body");
     if (!body) return;
     body.addEventListener("click", (e) => {
       const row = e.target.closest("tr[data-urn]");
       if (!row) return;
       mdOpenViewMode(row.dataset.urn);
     });
   }
   
   /* ================================================================
      ONE PANEL, THREE STATES: add | view | edit
      ================================================================ */
   
   const mdEls = {
     panel: () => document.getElementById("md-detail-panel-section"),
     form: () => document.getElementById("md-registration-form"),
     title: () => document.getElementById("md-panel-form-title"),
     metaRow: () => document.getElementById("md-form-meta-row"),
     metaUrn: () => document.getElementById("md-meta-urn"),
     metaPrintCount: () => document.getElementById("md-meta-print-count"),
     submitActions: () => document.getElementById("md-submit-actions"),
     viewActions: () => document.getElementById("md-view-actions"),
     submitBtn: () => document.getElementById("md-form-submit-btn"),
     cancelBtn: () => document.getElementById("md-cancel-edit-btn"),
     editLimitNote: () => document.getElementById("md-edit-limit-note"),
     // Editable in BOTH add and edit mode.
     editableFields: () =>
       ["md-form-full-name", "md-form-company-name", "md-form-designation", "md-form-email", "md-form-phone"].map((id) =>
         document.getElementById(id)
       ),
     // Only ever editable at registration time (add mode) — the backend
     // has no update path for these on an existing Mart Days registrant.
     addOnlyFields: () =>
       ["md-form-buyer-type", "md-form-address", "md-form-district", "md-form-state", "md-form-country", "md-form-pincode"].map(
         (id) => document.getElementById(id)
       ),
   };
   
   function mdFillFields(visitor) {
     document.getElementById("md-form-urn").value = visitor.urn;
     document.getElementById("md-form-buyer-type").value = visitor.buyer_type || "Overseas buyers";
     document.getElementById("md-form-full-name").value = visitor.full_name || "";
     document.getElementById("md-form-company-name").value = visitor.company_name || "";
     document.getElementById("md-form-designation").value = visitor.designation || "";
     document.getElementById("md-form-email").value = visitor.email || "";
     document.getElementById("md-form-phone").value = visitor.phone_number || "";
     document.getElementById("md-form-address").value = visitor.address || "";
     document.getElementById("md-form-district").value = visitor.district || "";
     document.getElementById("md-form-state").value = visitor.state || "";
     document.getElementById("md-form-country").value = visitor.country || "";
     document.getElementById("md-form-pincode").value = visitor.pincode || "";
   }
   
   function mdOpenAddMode() {
     if (mdPanelMode === "add") {
       mdClosePanel();
       return;
     }
   
     mdPanelMode = "add";
     mdActiveUrn = null;
   
     mdEls.form().reset();
     document.getElementById("md-form-urn").value = "";
     mdEls.editableFields().forEach((f) => { f.disabled = false; });
     mdEls.addOnlyFields().forEach((f) => { f.disabled = false; });
     mdEls.editLimitNote().classList.add("hidden");
     mdEls.title().textContent = "Add New Mart Days Registration";
     mdEls.metaRow().classList.add("hidden");
     mdEls.submitActions().classList.remove("hidden");
     mdEls.viewActions().classList.add("hidden");
     mdEls.submitBtn().textContent = "Add Registration";
     mdEls.cancelBtn().classList.add("hidden");
     document.getElementById("md-form-error").classList.add("hidden");
   
     mdEls.panel().classList.remove("hidden");
     document.getElementById("md-toggle-add-form-btn").textContent = "Cancel";
     renderMartDaysTable(mdCurrentFiltered());
     document.getElementById("md-form-full-name").focus();
   }
   
   function mdOpenViewModeForVisitor(visitor) {
     const idx = allMartDaysVisitors.findIndex((v) => v.urn === visitor.urn);
     if (idx >= 0) {
       allMartDaysVisitors[idx] = { ...allMartDaysVisitors[idx], ...visitor };
     } else {
       allMartDaysVisitors.push(visitor);
     }
     mdOpenViewMode(visitor.urn);
   }
   
   function mdOpenViewMode(urn) {
     if (mdPanelMode === "view" && mdActiveUrn === urn) {
       mdClosePanel();
       return;
     }
   
     const visitor = allMartDaysVisitors.find((v) => v.urn === urn);
     if (!visitor) return;
   
     mdPanelMode = "view";
     mdActiveUrn = urn;
   
     mdFillFields(visitor);
     mdEls.editableFields().forEach((f) => { f.disabled = true; });
     mdEls.addOnlyFields().forEach((f) => { f.disabled = true; });
     mdEls.editLimitNote().classList.add("hidden");
     mdEls.title().textContent = visitor.full_name;
     mdEls.metaUrn().textContent = visitor.urn;
     mdEls.metaPrintCount().textContent = visitor.print_count || 0;
     mdEls.metaRow().classList.remove("hidden");
     mdEls.submitActions().classList.add("hidden");
     mdEls.viewActions().classList.remove("hidden");
     document.getElementById("md-form-error").classList.add("hidden");
   
     mdEls.panel().classList.remove("hidden");
     document.getElementById("md-toggle-add-form-btn").textContent = "+ Add Registration";
     renderMartDaysTable(mdCurrentFiltered());
     mdEls.panel().scrollIntoView({ behavior: "smooth", block: "start" });
   }
   
   function mdOpenEditMode() {
     if (!mdActiveUrn) return;
     mdPanelMode = "edit";
   
     // Only the 5 backend-supported fields become editable — Buyer Type/
     // Address/District/State/Country/Pincode stay disabled (visible,
     // read-only) since there's no update path for them once registered.
     mdEls.editableFields().forEach((f) => { f.disabled = false; });
     mdEls.addOnlyFields().forEach((f) => { f.disabled = true; });
     mdEls.editLimitNote().classList.remove("hidden");
     mdEls.title().textContent = `Edit — ${mdActiveUrn}`;
     mdEls.viewActions().classList.add("hidden");
     mdEls.submitActions().classList.remove("hidden");
     mdEls.submitBtn().textContent = "Save Changes";
     mdEls.cancelBtn().classList.remove("hidden");
     document.getElementById("md-form-full-name").focus();
   }
   
   function mdClosePanel() {
     mdPanelMode = "closed";
     mdActiveUrn = null;
     mdEls.panel().classList.add("hidden");
     mdEls.form().reset();
     document.getElementById("md-form-urn").value = "";
     document.getElementById("md-form-error").classList.add("hidden");
     document.getElementById("md-toggle-add-form-btn").textContent = "+ Add Registration";
     renderMartDaysTable(mdCurrentFiltered());
   }
   
   /* ---------------- Wiring ---------------- */
   
   function wireMartDaysAddToggle() {
     const btn = document.getElementById("md-toggle-add-form-btn");
     if (!btn) return;
     btn.addEventListener("click", mdOpenAddMode);
   }
   
   function wireMartDaysViewActions() {
     const editBtn = document.getElementById("md-view-edit-btn");
     const cancelBtn = document.getElementById("md-view-cancel-btn");
     const printBtn = document.getElementById("md-view-print-btn");
     const deleteBtn = document.getElementById("md-view-delete-btn");
     if (!editBtn) return;
   
     editBtn.addEventListener("click", mdOpenEditMode);
     cancelBtn.addEventListener("click", mdClosePanel);
   
     printBtn.addEventListener("click", (e) => {
       const visitor = allMartDaysVisitors.find((v) => v.urn === mdActiveUrn);
       if (visitor) mdPrintBadge(visitor, e.currentTarget);
     });
   
     deleteBtn.addEventListener("click", async () => {
       if (mdActiveUrn) await mdHandleDelete(mdActiveUrn);
     });
   }
   
   async function mdHandleDelete(urn) {
     const visitor = allMartDaysVisitors.find((v) => v.urn === urn);
     const label = visitor ? `${visitor.full_name} (${urn})` : urn;
   
     const confirmed = window.confirm(`Permanently delete ${label}? This cannot be undone.`);
     if (!confirmed) return;
   
     const result = await API.deleteVisitor(urn);
     if (!result.ok) {
       alert(result.error || "Delete failed");
       return;
     }
   
     allMartDaysVisitors = allMartDaysVisitors.filter((v) => v.urn !== urn);
     if (mdActiveUrn === urn) {
       mdClosePanel();
     } else {
       renderMartDaysTable(mdCurrentFiltered());
     }
     loadMartDaysStats();
   }
   
   function wireMartDaysForm() {
     const form = mdEls.form();
     if (!form) return;
   
     mdEls.cancelBtn().addEventListener("click", () => {
       if (mdPanelMode === "edit" && mdActiveUrn) {
         mdOpenViewMode(mdActiveUrn); // back to read-only view, discard changes
       } else {
         mdClosePanel();
       }
     });
   
     form.addEventListener("submit", async (e) => {
       e.preventDefault();
       const errorBox = document.getElementById("md-form-error");
       errorBox.classList.add("hidden");
   
       const isEdit = mdPanelMode === "edit";
       mdEls.submitBtn().disabled = true;
       mdEls.submitBtn().textContent = isEdit ? "Saving..." : "Adding...";
   
       let result;
       if (isEdit) {
         // Edit only ever sends the 5 backend-supported fields — see
         // update_mart_days_visitor() in services/master_store.py.
         const payload = {
           name: document.getElementById("md-form-full-name").value.trim(),
           organization: document.getElementById("md-form-company-name").value.trim(),
           designation: document.getElementById("md-form-designation").value.trim() || null,
           mobile: document.getElementById("md-form-phone").value.trim(),
           email: document.getElementById("md-form-email").value.trim() || null,
           category: "visitor",
         };
         result = await API.updateVisitor(mdActiveUrn, payload);
       } else {
         const payload = {
           buyer_type: document.getElementById("md-form-buyer-type").value,
           full_name: document.getElementById("md-form-full-name").value.trim(),
           company_name: document.getElementById("md-form-company-name").value.trim(),
           designation: document.getElementById("md-form-designation").value.trim() || null,
           email: document.getElementById("md-form-email").value.trim(),
           phone_number: document.getElementById("md-form-phone").value.trim(),
           address: document.getElementById("md-form-address").value.trim() || null,
           district: document.getElementById("md-form-district").value.trim() || null,
           state: document.getElementById("md-form-state").value.trim() || null,
           country: document.getElementById("md-form-country").value.trim() || null,
           pincode: document.getElementById("md-form-pincode").value.trim() || null,
         };
         result = await API.registerMartDaysVisitor(payload);
       }
   
       mdEls.submitBtn().disabled = false;
   
       if (!result.ok) {
         errorBox.textContent = result.error || "Something went wrong";
         errorBox.classList.remove("hidden");
         mdEls.submitBtn().textContent = isEdit ? "Save Changes" : "Add Registration";
         return;
       }
   
       const savedVisitor = result.data.visitor;
       const idx = allMartDaysVisitors.findIndex((v) => v.urn === savedVisitor.urn);
       if (idx >= 0) {
         allMartDaysVisitors[idx] = { ...allMartDaysVisitors[idx], ...savedVisitor };
       } else {
         allMartDaysVisitors.unshift(savedVisitor);
       }
   
       document.getElementById("md-visitors-search").value = "";
       loadMartDaysStats();
       mdClosePanel();
     });
   }
   
   /* ---------------- Print (shared by the view panel's Print button and Find & Print) ---------------- */
   
   function mdPrintBadge(visitor, triggerBtn) {
     const originalLabel = triggerBtn ? triggerBtn.textContent : "";
     if (triggerBtn) {
       triggerBtn.disabled = true;
       triggerBtn.textContent = "Printing...";
     }
   
     // BadgePrint (js/print.js) is generic — just wants name/organization/
     // urn/mobile/email, so a Mart Days registrant's full_name/company_name/
     // phone_number map onto that shape here.
     const badgeVisitor = {
       name: visitor.full_name,
       organization: visitor.company_name,
       urn: visitor.urn,
       mobile: visitor.phone_number,
       email: visitor.email,
     };
   
     window.BadgePrint.printVisitor(badgeVisitor, async (success) => {
       if (triggerBtn) {
         triggerBtn.disabled = false;
         triggerBtn.textContent = originalLabel;
       }
   
       if (!success) {
         alert(`Print failed for ${visitor.full_name}. Please retry.`);
         return;
       }
   
       const result = await API.logPrint(visitor.urn);
       if (!result.ok) {
         console.warn("Print happened but wasn't logged to print stats:", result.error);
         return;
       }
   
       const idx = allMartDaysVisitors.findIndex((v) => v.urn === visitor.urn);
       if (idx >= 0) {
         allMartDaysVisitors[idx].print_count = (allMartDaysVisitors[idx].print_count || 0) + 1;
       }
   
       if (mdActiveUrn === visitor.urn) {
         mdEls.metaPrintCount().textContent = allMartDaysVisitors.find((v) => v.urn === visitor.urn).print_count;
       }
       renderMartDaysTable(mdCurrentFiltered());
       loadMartDaysStats();
     });
   }
   
   /* ---------------- Find & Print (search anyone in mart_days_registrations) ---------------- */
   
   function wireMartDaysFindAndPrint() {
     const input = document.getElementById("md-print-search-input");
     const btn = document.getElementById("md-print-search-btn");
     const resultsEl = document.getElementById("md-print-search-results");
     if (!input) return;
   
     async function runSearch() {
       const q = input.value.trim();
       if (!q) {
         resultsEl.innerHTML = "";
         return;
       }
   
       resultsEl.innerHTML = `<div class="search-empty">Searching...</div>`;
       const result = await API.searchMartDaysVisitor(q);
   
       if (!result.ok) {
         resultsEl.innerHTML = `<div class="search-empty">${mdEscapeHtml(result.error || "Search failed")}</div>`;
         return;
       }
   
       const matches = result.data.results || [];
   
       if (matches.length === 0) {
         resultsEl.innerHTML = `<div class="search-empty">No matching registrations found.</div>`;
         return;
       }
   
       // The shared /api/visitors/search endpoint returns results in the
       // generic Visitor shape (name/organization) even for Mart Days —
       // map back to full_name/company_name before touching our state.
       const mdMatches = matches.map((m) => ({
         ...m,
         full_name: m.name,
         company_name: m.organization,
         phone_number: m.mobile,
       }));
   
       if (mdMatches.length === 1) {
         mdOpenViewModeForVisitor(mdMatches[0]);
         resultsEl.innerHTML = "";
         input.value = "";
         return;
       }
   
       resultsEl.innerHTML = "";
       mdMatches.forEach((visitor) => {
         const row = document.createElement("div");
         row.className = "search-result-item";
         row.innerHTML = `
           <div><strong>${mdEscapeHtml(visitor.full_name)}</strong> — ${mdEscapeHtml(visitor.company_name || "")}</div>
           <div>${mdEscapeHtml(visitor.urn || "")}</div>
         `;
         row.addEventListener("click", () => {
           mdOpenViewModeForVisitor(visitor);
           resultsEl.innerHTML = "";
           input.value = "";
         });
         resultsEl.appendChild(row);
       });
     }
   
     btn.addEventListener("click", runSearch);
     input.addEventListener("keydown", (e) => {
       if (e.key === "Enter") {
         e.preventDefault();
         runSearch();
       }
     });
   }
   
   /* ---------------- Excel export (client-side, same library app.js uses) ---------------- */
   
   function wireMartDaysExport() {
     const btn = document.getElementById("md-export-btn");
     if (!btn) return;
     btn.addEventListener("click", () => {
       const visitors = mdCurrentFiltered();
       if (visitors.length === 0) {
         alert("No Mart Days registrations to export yet.");
         return;
       }
   
       const header = ["URN", "Full Name", "Buyer Type", "Company", "Designation", "Phone", "Email", "Address", "District", "State", "Country", "Pincode", "Prints"];
       const rows = visitors.map((v) => [
         v.urn || "", v.full_name || "", v.buyer_type || "", v.company_name || "", v.designation || "",
         v.phone_number || "", v.email || "", v.address || "", v.district || "", v.state || "",
         v.country || "", v.pincode || "", v.print_count || 0,
       ]);
   
       const worksheet = XLSX.utils.aoa_to_sheet([header, ...rows]);
       const workbook = XLSX.utils.book_new();
       XLSX.utils.book_append_sheet(workbook, worksheet, "Sheet1");
   
       const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
       XLSX.writeFile(workbook, `ieml-mart-days-registrations-${stamp}.xlsx`);
     });
   }
   
   /* ---------------- Clear History (Mart Days end-of-edition reset) ----------------
      Mirrors app.js's wireClearHistory(), scoped to "mart_days".
      Mart Days has no print_log/scan_log of its own (see
      backend services/master_store.py), so this only resets the
      print_count/scan_count/last_scanned_at columns on
      mart_days_registrations — registrant name/URN/company/etc. are
      never touched. Same double-confirm pattern as Other Events. */
   function wireMdClearHistory() {
     const btn = document.getElementById("md-clear-history-btn");
     if (!btn) return;
     btn.addEventListener("click", async () => {
       const firstOk = window.confirm(
         "This will clear the print count for every Mart Days " +
         "registrant, ready for the next edition.\n\n" +
         "Registrant names, URNs, and company details will NOT be " +
         "deleted — only print counts.\n\n" +
         "This cannot be undone. Continue?"
       );
       if (!firstOk) return;

       const typed = window.prompt('Type CONFIRM (in capitals) to proceed:');
       if (typed !== "CONFIRM") {
         if (typed !== null) alert("Clear History cancelled — text didn't match.");
         return;
       }

       btn.disabled = true;
       btn.textContent = "Clearing...";

       const result = await API.clearHistory("mart_days");

       btn.disabled = false;
       btn.textContent = "Clear Print History";

       if (!result.ok) {
         alert(`Clear History failed: ${result.error}`);
         return;
       }

       const { mart_days_reset = 0 } = result.data || {};
       alert(`Done — ${mart_days_reset} Mart Days registrant(s) reset.`);

       loadMartDaysStats();
       loadMartDaysVisitors();
     });
   }

   /* ---------------- Delete All Mart Days Data (full mart_days_registrations wipe) ----------------
      Mirrors app.js's wirePurgeAll(), scoped to "mart_days". Section
      itself starts hidden and is revealed by the SAME secret-unlock
      gesture as the Other Events one (see wireSecretPurgeUnlock() in
      app.js) — this function only wires the typed-confirm + click
      handling once the section is visible. Server-side (routers/
      master.py) checks the exact phrase again independently, same
      as the Other Events endpoint. */
   function wireMdPurgeAll() {
     const input = document.getElementById("md-purge-confirm-input");
     const btn = document.getElementById("md-purge-all-btn");
     if (!input || !btn) return;

     const PHRASE = "DELETE EVERYTHING";

     input.addEventListener("input", () => {
       btn.disabled = input.value !== PHRASE;
     });

     btn.addEventListener("click", async () => {
       if (input.value !== PHRASE) return;

       const confirmed = window.confirm(
         "This permanently deletes EVERY Mart Days registrant and their " +
         "print count. Other Events data is untouched.\n\n" +
         "There is NO undo. Only do this when starting a brand new Mart " +
         "Days edition from a completely blank slate.\n\n" +
         "Continue?"
       );
       if (!confirmed) return;

       btn.disabled = true;
       btn.textContent = "Deleting...";

       const result = await API.purgeAll(input.value, "mart_days");

       btn.textContent = "Delete All Mart Days Data";
       input.value = "";

       if (!result.ok) {
         btn.disabled = true; // stays disabled until phrase is retyped
         alert(`Delete All Mart Days Data failed: ${result.error}`);
         return;
       }

       const { mart_days_deleted = 0 } = result.data || {};
       alert(`Done — ${mart_days_deleted} Mart Days registrant(s) permanently deleted.`);

       document.getElementById("md-purge-all-section").classList.add("hidden");
       loadMartDaysStats();
       loadMartDaysVisitors();
     });
   }

   /* ---------------- Small helper (own copy — app.js's escapeHtml is
      already global, but this file is meant to stand alone) ---------------- */
   function mdEscapeHtml(str) {
     if (str === null || str === undefined) return "";
     return String(str)
       .replace(/&/g, "&amp;")
       .replace(/</g, "&lt;")
       .replace(/>/g, "&gt;")
       .replace(/"/g, "&quot;")
       .replace(/'/g, "&#39;");
   }
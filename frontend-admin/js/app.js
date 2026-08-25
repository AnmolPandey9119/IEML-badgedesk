/* ==========================================================
   app.js (Master Console)
   Onsite Registrations table rows are clickable — clicking one
   opens a read-only "view" panel (name/org/etc. + URN + print
   count), with Edit / Print / Delete buttons. Clicking Edit turns
   the same panel into an editable form. The "+ Add Registration"
   button opens the same panel empty, in add mode.
   No dropdown menus — one panel, three states: add | view | edit.
   ========================================================== */

   let allVisitors = [];
   let panelMode = "closed"; // "closed" | "add" | "view" | "edit"
   let activeUrn = null;     // which visitor the panel is currently showing (view/edit)
   
   document.addEventListener("DOMContentLoaded", () => {
     wireTabs();
     wireLogout();
     startHealthCheck();
     loadPrintStats();
     loadVisitors();
     wireForm();
     wireAddToggle();
     wireViewActions();
     wireSearch();
     wirePrintedSearch();
     wireTableRowClicks();
     wireFindAndPrint();
     wireExports();
   });
   
   /* ---------------- Tabs ---------------- */
   function wireTabs() {
     document.querySelectorAll(".tab-btn").forEach((btn) => {
       btn.addEventListener("click", () => switchTab(btn.dataset.tab));
     });
     document.querySelectorAll("[data-goto]").forEach((el) => {
       el.addEventListener("click", () => switchTab(el.dataset.goto));
     });
   }
   
   function switchTab(tabName) {
     document.querySelectorAll(".tab-btn").forEach((btn) => {
       btn.classList.toggle("active", btn.dataset.tab === tabName);
     });
     document.querySelectorAll(".tab-panel").forEach((panel) => {
       panel.classList.toggle("hidden", panel.id !== `panel-${tabName}`);
     });
   }
   
   /* ---------------- Logout ---------------- */
   function wireLogout() {
     const btn = document.getElementById("logout-btn");
     if (!btn) return;
     btn.addEventListener("click", () => window.Auth.logout(true));
   }
   
   /* ---------------- Connection status + event name ---------------- */
   function startHealthCheck() {
     const statusEl = document.getElementById("connection-status");
     const eventEl = document.getElementById("event-name");
   
     async function check() {
       const result = await API.checkHealth();
       if (result.ok) {
         statusEl.textContent = "Online";
         statusEl.className = "status status-online";
         if (eventEl) eventEl.textContent = result.data.event || "";
       } else {
         statusEl.textContent = "Offline";
         statusEl.className = "status status-offline";
       }
     }
   
     check();
     const intervalMs = (window.APP_CONFIG && window.APP_CONFIG.HEALTH_CHECK_INTERVAL_MS) || 15000;
     setInterval(check, intervalMs);
   }
   
   /* ---------------- Print stats ---------------- */
   async function loadPrintStats() {
     const totalEl = document.getElementById("overall-print-total");
     const homeTotalEl = document.getElementById("home-print-total");
     const bodyEl = document.getElementById("device-stats-body");
   
     const result = await API.getPrintStats();
     if (!result.ok) {
       bodyEl.innerHTML = `<tr><td colspan="2" class="search-empty">${escapeHtml(result.error || "Failed to load")}</td></tr>`;
       return;
     }
   
     totalEl.textContent = result.data.overall_total;
     if (homeTotalEl) homeTotalEl.textContent = result.data.overall_total;
   
     const byDevice = result.data.by_device || [];
     if (byDevice.length === 0) {
       bodyEl.innerHTML = `<tr><td colspan="2" class="search-empty">No prints logged yet</td></tr>`;
       return;
     }
   
     bodyEl.innerHTML = byDevice
       .map((d) => `<tr><td>${escapeHtml(d.device_name)}</td><td>${d.count}</td></tr>`)
       .join("");
   }
   
   /* ---------------- Visitors: fetch once, render two filtered views ---------------- */
   async function loadVisitors() {
     const visitorsBody = document.getElementById("visitors-table-body");
     const printedBody = document.getElementById("printed-table-body");
   
     const result = await API.listAllVisitors();
     if (!result.ok) {
       const msg = `<tr><td colspan="8" class="search-empty">${escapeHtml(result.error || "Failed to load")}</td></tr>`;
       visitorsBody.innerHTML = msg;
       printedBody.innerHTML = `<tr><td colspan="8" class="search-empty">${escapeHtml(result.error || "Failed to load")}</td></tr>`;
       return;
     }
   
     allVisitors = result.data.visitors || [];
     renderOnsiteTable(onlyOnsite(allVisitors));
     renderPrintedTable(onlyPrinted(allVisitors));
   }
   
   function onlyOnsite(list) {
     return list.filter((v) => v.source === "onsite");
   }
   
   function onlyPrinted(list) {
     return list
       .filter((v) => (v.print_count || 0) > 0)
       .sort((a, b) => (b.print_count || 0) - (a.print_count || 0));
   }
   
   function renderOnsiteTable(visitors) {
     const bodyEl = document.getElementById("visitors-table-body");
     const totalEl = document.getElementById("visitors-total");
     const homeTotalEl = document.getElementById("home-onsite-total");
   
     totalEl.textContent = `${visitors.length} total`;
     if (homeTotalEl) homeTotalEl.textContent = visitors.length;
   
     if (visitors.length === 0) {
       bodyEl.innerHTML = `<tr><td colspan="8" class="search-empty">No onsite registrations yet</td></tr>`;
       return;
     }
   
     bodyEl.innerHTML = visitors
       .map(
         (v) => `
         <tr data-urn="${escapeHtml(v.urn)}" class="${v.urn === activeUrn ? "row-active" : ""}">
           <td>${escapeHtml(v.urn)}</td>
           <td>${escapeHtml(v.name)}</td>
           <td>${escapeHtml(v.organization || "")}</td>
           <td>${escapeHtml(v.designation || "")}</td>
           <td>${escapeHtml(v.mobile || "")}</td>
           <td>${escapeHtml(v.email || "")}</td>
           <td>${escapeHtml(v.category || "")}</td>
           <td><span class="print-count-pill">${v.print_count || 0}</span></td>
         </tr>`
       )
       .join("");
   }
   
   function renderPrintedTable(visitors) {
     const bodyEl = document.getElementById("printed-table-body");
     document.getElementById("printed-total").textContent = `${visitors.length} total`;
   
     if (visitors.length === 0) {
       bodyEl.innerHTML = `<tr><td colspan="8" class="search-empty">No badges printed yet</td></tr>`;
       return;
     }
   
     bodyEl.innerHTML = visitors
       .map(
         (v) => `
         <tr>
           <td>${escapeHtml(v.urn)}</td>
           <td>${escapeHtml(v.name)}</td>
           <td>${escapeHtml(v.organization || "")}</td>
           <td>${escapeHtml(v.designation || "")}</td>
           <td>${escapeHtml(v.mobile || "")}</td>
           <td>${escapeHtml(v.email || "")}</td>
           <td>${escapeHtml(v.category || "")}</td>
           <td><span class="print-count-pill">${v.print_count || 0}</span></td>
         </tr>`
       )
       .join("");
   }
   
   /* ---------------- Client-side filters ---------------- */
   function matchesQuery(v, q) {
     return (
       (v.urn || "").toLowerCase().includes(q) ||
       (v.name || "").toLowerCase().includes(q) ||
       (v.mobile || "").toLowerCase().includes(q) ||
       (v.organization || "").toLowerCase().includes(q) ||
       (v.email || "").toLowerCase().includes(q)
     );
   }
   
   function wireSearch() {
     const input = document.getElementById("visitors-search");
     input.addEventListener("input", () => {
       const q = input.value.trim().toLowerCase();
       const base = onlyOnsite(allVisitors);
       renderOnsiteTable(q ? base.filter((v) => matchesQuery(v, q)) : base);
     });
   }
   
   function wirePrintedSearch() {
     const input = document.getElementById("printed-search");
     input.addEventListener("input", () => {
       const q = input.value.trim().toLowerCase();
       const base = onlyPrinted(allVisitors);
       renderPrintedTable(q ? base.filter((v) => matchesQuery(v, q)) : base);
     });
   }
   
   /* ================================================================
      ONE PANEL, THREE STATES: add | view | edit
      ================================================================ */
   
   const els = {
     panel: () => document.getElementById("detail-panel-section"),
     form: () => document.getElementById("registration-form"),
     title: () => document.getElementById("panel-form-title"),
     metaRow: () => document.getElementById("form-meta-row"),
     metaUrn: () => document.getElementById("meta-urn"),
     metaPrintCount: () => document.getElementById("meta-print-count"),
     submitActions: () => document.getElementById("submit-actions"),
     viewActions: () => document.getElementById("view-actions"),
     submitBtn: () => document.getElementById("form-submit-btn"),
     cancelBtn: () => document.getElementById("cancel-edit-btn"),
     fields: () => ["form-name", "form-organization", "form-designation", "form-mobile", "form-email", "form-category"].map((id) => document.getElementById(id)),
   };
   
   function setFieldsDisabled(disabled) {
     els.fields().forEach((f) => { f.disabled = disabled; });
   }
   
   function fillFields(visitor) {
     document.getElementById("form-urn").value = visitor.urn;
     document.getElementById("form-name").value = visitor.name || "";
     document.getElementById("form-organization").value = visitor.organization || "";
     document.getElementById("form-designation").value = visitor.designation || "";
     document.getElementById("form-mobile").value = visitor.mobile || "";
     document.getElementById("form-email").value = visitor.email || "";
     document.getElementById("form-category").value = visitor.category || "visitor";
   }
   
   function openAddMode() {
     if (panelMode === "add") {
       closePanel();
       return;
     }
   
     panelMode = "add";
     activeUrn = null;
   
     els.form().reset();
     document.getElementById("form-urn").value = "";
     setFieldsDisabled(false);
     els.title().textContent = "Add New Registration";
     els.metaRow().classList.add("hidden");
     els.submitActions().classList.remove("hidden");
     els.viewActions().classList.add("hidden");
     els.submitBtn().textContent = "Add Registration";
     els.cancelBtn().classList.add("hidden");
     document.getElementById("form-error").classList.add("hidden");
   
     els.panel().classList.remove("hidden");
     document.getElementById("toggle-add-form-btn").textContent = "Cancel";
     renderOnsiteTable(currentOnsiteFiltered());
     document.getElementById("form-name").focus();
   }
   
   function openViewModeForVisitor(visitor) {
     const idx = allVisitors.findIndex((v) => v.urn === visitor.urn);
     if (idx >= 0) {
       allVisitors[idx] = { ...allVisitors[idx], ...visitor };
     } else {
       // Found via search but not in our locally cached list yet (e.g.
       // someone else's sheet sync landed after this page loaded) —
       // seed it in so the view panel and print-count updates work.
       allVisitors.push(visitor);
     }
     openViewMode(visitor.urn);
   }
   
   function openViewMode(urn) {
     if (panelMode === "view" && activeUrn === urn) {
       closePanel();
       return;
     }
   
     const visitor = allVisitors.find((v) => v.urn === urn);
     if (!visitor) return;
   
     panelMode = "view";
     activeUrn = urn;
   
     fillFields(visitor);
     setFieldsDisabled(true);
     els.title().textContent = visitor.name;
     els.metaUrn().textContent = visitor.urn;
     els.metaPrintCount().textContent = visitor.print_count || 0;
     els.metaRow().classList.remove("hidden");
     els.submitActions().classList.add("hidden");
     els.viewActions().classList.remove("hidden");
     document.getElementById("form-error").classList.add("hidden");
   
     els.panel().classList.remove("hidden");
     document.getElementById("toggle-add-form-btn").textContent = "+ Add Registration";
     renderOnsiteTable(currentOnsiteFiltered());
     els.panel().scrollIntoView({ behavior: "smooth", block: "start" });
   }
   
   function openEditMode() {
     if (!activeUrn) return;
     panelMode = "edit";
   
     setFieldsDisabled(false);
     els.title().textContent = `Edit — ${activeUrn}`;
     els.viewActions().classList.add("hidden");
     els.submitActions().classList.remove("hidden");
     els.submitBtn().textContent = "Save Changes";
     els.cancelBtn().classList.remove("hidden");
     document.getElementById("form-name").focus();
   }
   
   function closePanel() {
     panelMode = "closed";
     activeUrn = null;
     els.panel().classList.add("hidden");
     els.form().reset();
     document.getElementById("form-urn").value = "";
     document.getElementById("form-error").classList.add("hidden");
     document.getElementById("toggle-add-form-btn").textContent = "+ Add Registration";
     renderOnsiteTable(currentOnsiteFiltered());
   }
   
   function currentOnsiteFiltered() {
     const q = document.getElementById("visitors-search").value.trim().toLowerCase();
     const base = onlyOnsite(allVisitors);
     return q ? base.filter((v) => matchesQuery(v, q)) : base;
   }
   
   /* ---------------- Wiring ---------------- */
   function wireAddToggle() {
     document.getElementById("toggle-add-form-btn").addEventListener("click", openAddMode);
   }
   
   function wireTableRowClicks() {
     document.getElementById("visitors-table-body").addEventListener("click", (e) => {
       const row = e.target.closest("tr[data-urn]");
       if (!row) return;
       openViewMode(row.dataset.urn);
     });
   }
   
   function wireViewActions() {
     document.getElementById("view-edit-btn").addEventListener("click", openEditMode);
     document.getElementById("view-cancel-btn").addEventListener("click", closePanel);
   
     document.getElementById("view-print-btn").addEventListener("click", (e) => {
       const visitor = allVisitors.find((v) => v.urn === activeUrn);
       if (visitor) printBadge(visitor, e.currentTarget);
     });
   
     document.getElementById("view-delete-btn").addEventListener("click", async () => {
       if (activeUrn) await handleDelete(activeUrn);
     });
   }
   
   /* ---------------- Delete ---------------- */
   async function handleDelete(urn) {
     const visitor = allVisitors.find((v) => v.urn === urn);
     const label = visitor ? `${visitor.name} (${urn})` : urn;
   
     const confirmed = window.confirm(`Permanently delete ${label}? This also removes their print history and cannot be undone.`);
     if (!confirmed) return;
   
     const result = await API.deleteVisitor(urn);
     if (!result.ok) {
       alert(result.error || "Delete failed");
       return;
     }
   
     allVisitors = allVisitors.filter((v) => v.urn !== urn);
     renderPrintedTable(onlyPrinted(allVisitors));
   
     if (activeUrn === urn) {
       closePanel();
     } else {
       renderOnsiteTable(currentOnsiteFiltered());
     }
   }
   
   /* ---------------- Add / Edit form submit ---------------- */
   function wireForm() {
     const form = els.form();
   
     els.cancelBtn().addEventListener("click", () => {
       if (panelMode === "edit" && activeUrn) {
         openViewMode(activeUrn); // back to read-only view, discard changes
       } else {
         closePanel();
       }
     });
   
     form.addEventListener("submit", async (e) => {
       e.preventDefault();
       const errorBox = document.getElementById("form-error");
       errorBox.classList.add("hidden");
   
       const payload = {
         name: document.getElementById("form-name").value.trim(),
         organization: document.getElementById("form-organization").value.trim(),
         designation: document.getElementById("form-designation").value.trim() || null,
         mobile: document.getElementById("form-mobile").value.trim(),
         email: document.getElementById("form-email").value.trim() || null,
         category: document.getElementById("form-category").value,
       };
   
       const isEdit = panelMode === "edit";
       els.submitBtn().disabled = true;
       els.submitBtn().textContent = isEdit ? "Saving..." : "Adding...";
   
       const result = isEdit
         ? await API.updateVisitor(activeUrn, payload)
         : await API.registerVisitor(payload);
   
       els.submitBtn().disabled = false;
   
       if (!result.ok) {
         errorBox.textContent = result.error || "Something went wrong";
         errorBox.classList.remove("hidden");
         els.submitBtn().textContent = isEdit ? "Save Changes" : "Add Registration";
         return;
       }
   
       const savedVisitor = result.data.visitor;
       const idx = allVisitors.findIndex((v) => v.urn === savedVisitor.urn);
       if (idx >= 0) {
         allVisitors[idx] = { ...allVisitors[idx], ...savedVisitor };
       } else {
         allVisitors.unshift({ ...savedVisitor, source: "onsite", print_count: savedVisitor.print_count || 0 });
       }
   
       renderPrintedTable(onlyPrinted(allVisitors));
       document.getElementById("visitors-search").value = "";
   
       // NOTE: intentionally no print/QR screen here — adding or saving
       // a registration in the master console just saves it. Printing
       // is a separate, explicit action (the Print button / Find & Print).
       closePanel();
     });
   }
   
   /* ---------------- Print (shared by the view panel's Print button and Find & Print) ---------------- */
   function printBadge(visitor, triggerBtn) {
     const originalLabel = triggerBtn ? triggerBtn.textContent : "";
     if (triggerBtn) {
       triggerBtn.disabled = true;
       triggerBtn.textContent = "Printing...";
     }
   
     window.BadgePrint.printVisitor(visitor, async (success) => {
       if (triggerBtn) {
         triggerBtn.disabled = false;
         triggerBtn.textContent = originalLabel;
       }
   
       if (!success) {
         alert(`Print failed for ${visitor.name}. Please retry.`);
         return;
       }
   
       const result = await API.logPrint(visitor.urn);
       if (!result.ok) {
         console.warn("Print happened but wasn't logged to print stats:", result.error);
         return;
       }
   
       const idx = allVisitors.findIndex((v) => v.urn === visitor.urn);
       if (idx >= 0) {
         allVisitors[idx].print_count = (allVisitors[idx].print_count || 0) + 1;
       } else {
         allVisitors.push({ ...visitor, print_count: 1 });
       }
   
       if (activeUrn === visitor.urn) {
         els.metaPrintCount().textContent = allVisitors.find((v) => v.urn === visitor.urn).print_count;
       }
       renderOnsiteTable(currentOnsiteFiltered());
       renderPrintedTable(onlyPrinted(allVisitors));
       loadPrintStats();
     });
   }
   
   /* ---------------- Find & Print (search anyone — onsite or sheet-synced — same behavior as the operator app's search) ---------------- */
   function wireFindAndPrint() {
     const input = document.getElementById("print-search-input");
     const btn = document.getElementById("print-search-btn");
     const resultsEl = document.getElementById("print-search-results");
   
     async function runSearch() {
       const q = input.value.trim();
       if (!q) {
         resultsEl.innerHTML = "";
         return;
       }
   
       resultsEl.innerHTML = `<div class="search-empty">Searching...</div>`;
       const result = await API.searchVisitor(q);
   
       if (!result.ok) {
         resultsEl.innerHTML = `<div class="search-empty">${escapeHtml(result.error || "Search failed")}</div>`;
         return;
       }
   
       const matches = result.data.results || [];
   
       if (matches.length === 0) {
         resultsEl.innerHTML = `<div class="search-empty">No matching registrations found.</div>`;
         return;
       }
   
       // Exact single match — open its full details directly, same as the operator app.
       if (matches.length === 1) {
         openViewModeForVisitor(matches[0]);
         resultsEl.innerHTML = "";
         input.value = "";
         return;
       }
   
       // Multiple matches — compact clickable list, click one to open its details.
       resultsEl.innerHTML = "";
       matches.forEach((visitor) => {
         const row = document.createElement("div");
         row.className = "search-result-item";
         row.innerHTML = `
           <div><strong>${escapeHtml(visitor.name)}</strong> — ${escapeHtml(visitor.organization || "")}</div>
           <div>${escapeHtml(visitor.urn || "")}</div>
         `;
         row.addEventListener("click", () => {
           openViewModeForVisitor(visitor);
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
   
   /* ---------------- Excel export (client-side, same library the operator app uses) ---------------- */
   function exportToExcel(visitors, filenamePrefix, emptyMessage) {
     if (visitors.length === 0) {
       alert(emptyMessage);
       return;
     }
   
     const header = ["URN", "Name", "Organization", "Designation", "Mobile", "Email", "Category", "Prints"];
     const rows = visitors.map((v) => [
       v.urn || "", v.name || "", v.organization || "", v.designation || "",
       v.mobile || "", v.email || "", v.category || "", v.print_count || 0,
     ]);
   
     const worksheet = XLSX.utils.aoa_to_sheet([header, ...rows]);
     worksheet["!cols"] = [
       { wch: 10 }, { wch: 22 }, { wch: 22 }, { wch: 16 },
       { wch: 14 }, { wch: 26 }, { wch: 16 }, { wch: 8 },
     ];
   
     const workbook = XLSX.utils.book_new();
     XLSX.utils.book_append_sheet(workbook, worksheet, "Sheet1");
   
     const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
     XLSX.writeFile(workbook, `${filenamePrefix}-${stamp}.xlsx`);
   }
   
   function wireExports() {
     document.getElementById("export-onsite-btn").addEventListener("click", () => {
       exportToExcel(currentOnsiteFiltered(), "ieml-onsite-registrations", "No onsite registrations to export yet.");
     });
   
     document.getElementById("export-printed-btn").addEventListener("click", () => {
       const q = document.getElementById("printed-search").value.trim().toLowerCase();
       const base = onlyPrinted(allVisitors);
       const list = q ? base.filter((v) => matchesQuery(v, q)) : base;
       exportToExcel(list, "ieml-printed-badges", "No printed badges to export yet.");
     });
   }
   
   /* ---------------- Small helper ---------------- */
   function escapeHtml(str) {
     if (str === null || str === undefined) return "";
     return String(str)
       .replace(/&/g, "&amp;")
       .replace(/</g, "&lt;")
       .replace(/>/g, "&gt;")
       .replace(/"/g, "&quot;")
       .replace(/'/g, "&#39;");
   }
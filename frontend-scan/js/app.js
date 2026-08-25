/* ==========================================================
   app.js (Entrance Scanner)
   Continuous camera-based QR scanning — the camera NEVER pauses
   and there is no manual "next" step. Every successful decode:
     1. extracts the URN from the decoded text (works with both
        the new multi-line QR format and old bare-URN badges)
     2. if it's the SAME urn as the last one within a short cooldown
        window, ignores it (the badge is just still sitting in
        frame, e.g. someone's hand hasn't moved yet) — this is the
        only thing that stops one badge from firing the API
        repeatedly, not a pause/click
     3. calls POST /{urn}/scan-log in the background — this both
        logs the scan AND returns the visitor's full current
        details in one call
     4. shows a brief, glanceable confirmation toast that fades on
        its own — camera keeps reading the whole time, so the next
        person's badge is picked up immediately, even mid-toast
     5. bumps the local "Entries" counter on this device/gate
   ========================================================== */

   const SCANNER_NAME_KEY = "ieml_scanner_name";
   // Ignore a repeat scan of the exact same QR within this window —
   // stops one badge held in front of the camera (or a shaky hand)
   // from firing the API over and over. Deliberately short: real
   // re-entries (same person leaving and coming back later) are
   // always well past this gap.
   const SAME_BADGE_COOLDOWN_MS = 4000;
   // How long a result toast stays up before auto-clearing.
   const TOAST_DURATION_MS = 1800;
   
   let html5QrCode = null;
   let lastScannedUrn = null;
   let lastScannedAt = 0;
   let toastTimeoutId = null;
   let gateEntryCount = 0;
   
   document.addEventListener("DOMContentLoaded", () => {
     wireLogout();
     startHealthCheck();
     setupScannerName();
     startCamera();
   });
   
   /* ---------------- Logout ---------------- */
   function wireLogout() {
     document.getElementById("logout-btn").addEventListener("click", () => {
       if (html5QrCode) {
         html5QrCode.stop().catch(() => {});
       }
       window.Auth.logout(true);
     });
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
   
   /* ---------------- Scanner / gate name ---------------- */
   function setupScannerName() {
     const chip = document.getElementById("scanner-name-chip");
   
     function getName() {
       return localStorage.getItem(SCANNER_NAME_KEY);
     }
   
     function promptForName() {
       const current = getName() || "";
       const name = (window.prompt("Name this scanner/gate (e.g. \"Gate 1\", \"Main Entrance\"):", current) || "").trim();
       if (name) {
         localStorage.setItem(SCANNER_NAME_KEY, name);
         chip.textContent = name;
       }
     }
   
     if (!getName()) {
       promptForName();
     } else {
       chip.textContent = getName();
     }
   
     document.getElementById("change-scanner-name-btn").addEventListener("click", promptForName);
   }
   
   function getScannerName() {
     return localStorage.getItem(SCANNER_NAME_KEY) || "Unnamed scanner";
   }
   
   /* ---------------- Gate entry counter (local, resets on page load) ---------------- */
   function bumpGateCounter() {
     gateEntryCount += 1;
     const el = document.getElementById("gate-counter-value");
     if (el) el.textContent = gateEntryCount;
   }
   
   /* ---------------- Camera / QR scanning ---------------- */
   function startCamera() {
     // eslint-disable-next-line no-undef
     html5QrCode = new Html5Qrcode("qr-reader", {
       // eslint-disable-next-line no-undef
       formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
       verbose: false,
     });
   
     html5QrCode
       .start(
         { facingMode: "environment" },
         { fps: 10, qrbox: { width: 250, height: 250 } },
         onScanSuccess,
         () => {} // decode-failure callback fires continuously while aiming — ignore
       )
       .catch((err) => {
         document.getElementById("scan-hint").textContent =
           "Couldn't access the camera — check camera permission for this site and reload.";
         console.error("Camera start failed:", err);
       });
   }
   
   function onScanSuccess(decodedText) {
     // Camera is never paused, so this fires continuously while a QR is
     // in frame — the cooldown below is what stops duplicate API calls
     // for the SAME badge, not a pause/click.
     const urn = extractUrn(decodedText);
     const now = Date.now();
   
     if (urn === lastScannedUrn && now - lastScannedAt < SAME_BADGE_COOLDOWN_MS) {
       return;
     }
   
     lastScannedUrn = urn;
     lastScannedAt = now;
     handleScan(urn);
   }
   
   /**
    * Pulls the URN out of the scanned text. Handles both:
    *  - the new multi-line format: "URN: XXXXXX\nName: ...\n..."
    *  - old badges printed before that change: just the bare URN
    */
   function extractUrn(decodedText) {
     const firstLine = decodedText.split("\n")[0].trim();
     const match = firstLine.match(/^URN:\s*(.+)$/i);
     return (match ? match[1] : firstLine).trim();
   }
   
   /* ---------------- Handle a scan: log it, show a toast — camera keeps running ---------------- */
   async function handleScan(urn) {
     showLoadingToast();
   
     const result = await API.logScan(urn, getScannerName());
   
     if (!result.ok) {
       showErrorToast(result.error || "Something went wrong");
       return;
     }
   
     bumpGateCounter();
     showSuccessToast(result.data.visitor);
   }
   
   /* ---------------- Toast rendering (auto-clears, never blocks the camera) ---------------- */
   function clearToastTimer() {
     clearTimeout(toastTimeoutId);
   }
   
   function scheduleToastClear() {
     clearToastTimer();
     toastTimeoutId = setTimeout(() => {
       document.getElementById("result-area").innerHTML = "";
     }, TOAST_DURATION_MS);
   }
   
   function showLoadingToast() {
     clearToastTimer();
     document.getElementById("result-area").innerHTML = `
       <div class="result-card">
         <div class="result-header success">Looking up...</div>
       </div>
     `;
   }
   
   function showSuccessToast(visitor) {
     document.getElementById("result-area").innerHTML = `
       <div class="result-card">
         <div class="result-header success">✅ Entry Confirmed</div>
         <div class="result-body">
           <div class="result-name">${escapeHtml(visitor.name)}</div>
           <div class="result-org">${escapeHtml(visitor.organization || "")}</div>
           <div class="result-grid">
             <div>
               <div class="result-field-label">URN</div>
               <div class="result-field-value">${escapeHtml(visitor.urn)}</div>
             </div>
             <div>
               <div class="result-field-label">Category</div>
               <div class="result-field-value">${escapeHtml(visitor.category || "")}</div>
             </div>
             <div>
               <div class="result-field-label">Mobile</div>
               <div class="result-field-value">${escapeHtml(visitor.mobile || "—")}</div>
             </div>
             <div>
               <div class="result-field-label">Email</div>
               <div class="result-field-value">${escapeHtml(visitor.email || "—")}</div>
             </div>
           </div>
           <span class="entry-count-badge">🔁 Entry #${visitor.scan_count || 1}</span>
         </div>
       </div>
     `;
     scheduleToastClear();
   }
   
   function showErrorToast(message) {
     document.getElementById("result-area").innerHTML = `
       <div class="result-card">
         <div class="result-header error">❌ Not Found</div>
         <div class="result-body">
           <p class="error-text">${escapeHtml(message)}</p>
         </div>
       </div>
     `;
     scheduleToastClear();
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
/* ==========================================================
   app.js (Entrance Scanner)
   Continuous camera-based QR scanning. Every successful decode:
     1. pauses the camera
     2. extracts the URN from the decoded text (works with both
        the new multi-line QR format and old bare-URN badges)
     3. calls POST /{urn}/scan-log — this both logs the scan AND
        returns the visitor's full current details in one call
     4. shows a big, glanceable result card
     5. auto-resumes scanning after a short pause (or on tap)
   ========================================================== */

const SCANNER_NAME_KEY = "ieml_scanner_name";
let html5QrCode = null;
let isPaused = false;
let resumeTimeoutId = null;

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
  if (isPaused) return; // ignore any stray callbacks while a result is showing
  isPaused = true;

  html5QrCode.pause(true);
  document.getElementById("scan-hint").classList.add("hidden");

  const urn = extractUrn(decodedText);
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

/* ---------------- Handle a scan: log it, show the result ---------------- */
async function handleScan(urn) {
  renderLoading();

  const result = await API.logScan(urn, getScannerName());

  if (!result.ok) {
    renderError(result.error || "Something went wrong");
    scheduleResume();
    return;
  }

  renderSuccess(result.data.visitor);
  scheduleResume();
}

function scheduleResume() {
  clearTimeout(resumeTimeoutId);
  resumeTimeoutId = setTimeout(resumeScanning, 3000);
}

function resumeScanning() {
  clearTimeout(resumeTimeoutId);
  document.getElementById("result-area").innerHTML = "";
  document.getElementById("scan-hint").classList.remove("hidden");
  isPaused = false;
  if (html5QrCode) {
    html5QrCode.resume();
  }
}

/* ---------------- Result rendering ---------------- */
function renderLoading() {
  document.getElementById("result-area").innerHTML = `
    <div class="result-card">
      <div class="result-header success">Looking up...</div>
    </div>
  `;
}

function renderSuccess(visitor) {
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
        <button class="scan-next-btn" onclick="resumeScanning()">Scan Next</button>
      </div>
    </div>
  `;
}

function renderError(message) {
  document.getElementById("result-area").innerHTML = `
    <div class="result-card">
      <div class="result-header error">❌ Not Found</div>
      <div class="result-body">
        <p class="error-text">${escapeHtml(message)}</p>
        <button class="scan-next-btn" onclick="resumeScanning()">Scan Next</button>
      </div>
    </div>
  `;
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
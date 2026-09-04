/* ==========================================================
   badge-download.js
   Self-service e-badge download: takes URN/email/phone, calls
   GET /api/mart-days/badge-download?value=..., and either
     - triggers a real file download of the returned PNG, or
     - shows the backend's error message (not found / server error)
   No login/token involved anywhere in this file — same public,
   no-auth pattern as js/app.js's registration flow.
   ========================================================== */

   (function () {
    const lookupForm = document.getElementById("lookup-form");
    const lookupInput = document.getElementById("lookup-value");
    const lookupBtn = document.getElementById("lookup-btn");
    const btnLabel = lookupBtn.querySelector(".btn-label");
    const btnSpinner = lookupBtn.querySelector(".btn-spinner");
    const errorBox = document.getElementById("lookup-error");
  
    const lookupSection = document.getElementById("lookup-section");
    const successSection = document.getElementById("success-section");
    const successUrn = document.getElementById("success-urn");
    const previewImg = document.getElementById("badge-preview-img");
  
    const downloadAgainBtn = document.getElementById("download-again-btn");
    const searchAgainBtn = document.getElementById("search-again-btn");
  
    let lastBlobUrl = null;
    let lastFilename = "IEML-MartDays-Badge.png";
  
    function setLoading(isLoading) {
      lookupBtn.disabled = isLoading;
      btnLabel.classList.toggle("hidden", isLoading);
      btnSpinner.classList.toggle("hidden", !isLoading);
    }
  
    function showError(message) {
      errorBox.textContent = message;
      errorBox.classList.remove("hidden");
    }
  
    function clearError() {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
    }
  
    // Pulls the URN back out of "IEML-MartDays-Badge-<URN>.png" so the
    // success screen can show it without the backend needing to send
    // any JSON metadata alongside the image bytes.
    function extractUrnFromFilename(filename) {
      const match = /IEML-MartDays-Badge-([A-Z0-9]+)\.png/i.exec(filename || "");
      return match ? match[1].toUpperCase() : "";
    }
  
    function extractFilename(response, fallback) {
      const header = response.headers.get("Content-Disposition") || "";
      const match = /filename="?([^"]+)"?/i.exec(header);
      return match ? match[1] : fallback;
    }
  
    function triggerDownload(blobUrl, filename) {
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
  
    async function fetchBadge(value) {
      const base = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "";
      const url = base + "/api/mart-days/badge-download?value=" + encodeURIComponent(value);
  
      const response = await fetch(url, { method: "GET" });
  
      if (!response.ok) {
        let detail = "We couldn't find a Mart Days registration for that URN, email, or phone number.";
        try {
          const data = await response.json();
          if (data && data.detail) detail = data.detail;
        } catch (_) {
          // response wasn't JSON — keep the generic message above
        }
        throw new Error(detail);
      }
  
      const blob = await response.blob();
      const filename = extractFilename(response, lastFilename);
      return { blob, filename };
    }
  
    function showSuccess(blob, filename) {
      if (lastBlobUrl) URL.revokeObjectURL(lastBlobUrl);
      lastBlobUrl = URL.createObjectURL(blob);
      lastFilename = filename;
  
      previewImg.src = lastBlobUrl;
      successUrn.textContent = extractUrnFromFilename(filename) || "—";
  
      triggerDownload(lastBlobUrl, filename);
  
      lookupSection.classList.add("hidden");
      successSection.classList.remove("hidden");
    }
  
    lookupForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      clearError();
  
      const value = lookupInput.value.trim();
      if (!value) {
        showError("Please enter your URN, email, or phone number.");
        return;
      }
  
      setLoading(true);
      try {
        const { blob, filename } = await fetchBadge(value);
        showSuccess(blob, filename);
      } catch (err) {
        showError(err.message || "Something went wrong. Please try again.");
      } finally {
        setLoading(false);
      }
    });
  
    downloadAgainBtn.addEventListener("click", function () {
      if (lastBlobUrl) triggerDownload(lastBlobUrl, lastFilename);
    });
  
    searchAgainBtn.addEventListener("click", function () {
      successSection.classList.add("hidden");
      lookupSection.classList.remove("hidden");
      lookupInput.value = "";
      clearError();
      lookupInput.focus();
    });
  })();
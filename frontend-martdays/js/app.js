/* ==========================================================
   app.js
   Handles the Mart Days registration form: collect fields,
   POST to the public backend endpoint, show URN on success.
   No login/token involved anywhere in this file — intentional.
   ========================================================== */

   (function () {
    const form = document.getElementById("register-form");
    const submitBtn = document.getElementById("submit-btn");
    const errorBox = document.getElementById("form-error");
    const formSection = document.getElementById("form-section");
    const successSection = document.getElementById("success-section");
  
    function showError(message) {
      errorBox.textContent = message;
      errorBox.classList.remove("hidden");
    }
  
    function clearError() {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
    }
  
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      clearError();
  
      const payload = {
        buyer_type: document.getElementById("buyer_type").value,
        full_name: document.getElementById("full_name").value.trim(),
        company_name: document.getElementById("company_name").value.trim(),
        designation: document.getElementById("designation").value.trim() || null,
        email: document.getElementById("email").value.trim(),
        phone_number: document.getElementById("phone_number").value.trim(),
        address: document.getElementById("address").value.trim() || null,
        district: document.getElementById("district").value.trim() || null,
        state: document.getElementById("state").value.trim() || null,
        country: document.getElementById("country").value.trim() || null,
        pincode: document.getElementById("pincode").value.trim() || null,
      };
  
      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting...";
  
      try {
        const res = await fetch(`${window.APP_CONFIG.API_BASE_URL}/api/mart-days/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
  
        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          const detail = errBody.detail;
          const message =
            typeof detail === "string"
              ? detail
              : "Please check the form — some details look invalid.";
          throw new Error(message);
        }
  
        const data = await res.json();
  
        document.getElementById("success-name").textContent = data.full_name;
        document.getElementById("success-urn").textContent = data.urn;
        document.getElementById("success-email").textContent = data.email;
  
        formSection.classList.add("hidden");
        successSection.classList.remove("hidden");
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (err) {
        showError(err.message || "Something went wrong. Please try again.");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Register";
      }
    });
  })();
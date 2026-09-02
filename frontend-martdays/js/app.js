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
  
    const countryEl = document.getElementById("country");
    const stateSelect = document.getElementById("state-select");
    const stateText = document.getElementById("state-text");
    const districtSelect = document.getElementById("district-select");
    const districtText = document.getElementById("district-text");
  
    const stateSelectLabel = document.querySelector('label[for="state-select"]');
    const stateTextLabel = document.querySelector('label[for="state-text"]');
    const districtSelectLabel = document.querySelector('label[for="district-select"]');
    const districtTextLabel = document.querySelector('label[for="district-text"]');
  
    // ------------------------------------------------------------
    // Country dropdown: populated once from location-data.js.
    // ------------------------------------------------------------
    (window.COUNTRIES || []).forEach(function (name) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      countryEl.appendChild(opt);
    });
  
    function showIndiaFields() {
      stateSelect.classList.remove("hidden");
      stateSelectLabel.classList.remove("hidden");
      stateSelect.disabled = false;
      stateText.classList.add("hidden");
      stateTextLabel.classList.add("hidden");
      stateText.value = "";
    }
  
    function showOtherCountryFields() {
      stateSelect.classList.add("hidden");
      stateSelectLabel.classList.add("hidden");
      stateSelect.disabled = true;
      stateSelect.innerHTML = '<option value="" selected>Select state</option>';
      stateText.classList.remove("hidden");
      stateTextLabel.classList.remove("hidden");
      hideDistrictSelect();
      districtText.classList.remove("hidden");
      districtTextLabel.classList.remove("hidden");
      districtText.value = "";
    }
  
    function hideDistrictSelect() {
      districtSelect.classList.add("hidden");
      districtSelectLabel.classList.add("hidden");
      districtSelect.disabled = true;
      districtSelect.innerHTML = '<option value="" selected>Select district</option>';
    }
  
    function resetLocationFields() {
      stateSelect.classList.add("hidden");
      stateSelectLabel.classList.add("hidden");
      stateSelect.disabled = true;
      stateSelect.innerHTML = '<option value="" selected>Select state</option>';
      stateText.classList.add("hidden");
      stateTextLabel.classList.add("hidden");
      stateText.value = "";
      districtText.classList.add("hidden");
      districtTextLabel.classList.add("hidden");
      districtText.value = "";
      hideDistrictSelect();
    }
  
    // Country changes -> reset State/District, then show the right
    // field type (real dropdown for India, free text for everyone
    // else — we don't have district-level data for every country).
    countryEl.addEventListener("change", function () {
      resetLocationFields();
      if (countryEl.value === "India") {
        showIndiaFields();
        Object.keys(window.INDIA_LOCATIONS || {}).forEach(function (state) {
          const opt = document.createElement("option");
          opt.value = state;
          opt.textContent = state;
          stateSelect.appendChild(opt);
        });
      } else if (countryEl.value) {
        showOtherCountryFields();
      }
    });
  
    // State (India) changes -> populate District dropdown for that state.
    stateSelect.addEventListener("change", function () {
      hideDistrictSelect();
      const districts = (window.INDIA_LOCATIONS || {})[stateSelect.value] || [];
      if (districts.length) {
        districtSelect.classList.remove("hidden");
        districtSelectLabel.classList.remove("hidden");
        districtSelect.disabled = false;
        districts.forEach(function (d) {
          const opt = document.createElement("option");
          opt.value = d;
          opt.textContent = d;
          districtSelect.appendChild(opt);
        });
      }
    });
  
    // Reads whichever field (dropdown or text) is currently visible
    // for State/District — the form doesn't care which one was used,
    // only the final chosen value.
    function currentStateValue() {
      return countryEl.value === "India" ? stateSelect.value : stateText.value.trim();
    }
  
    function currentDistrictValue() {
      return countryEl.value === "India" ? districtSelect.value : districtText.value.trim();
    }
  
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
        district: currentDistrictValue() || null,
        state: currentStateValue() || null,
        country: countryEl.value || null,
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
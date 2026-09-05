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

    const buyerTypeRadios = document.querySelectorAll('input[name="buyer_type"]');
    const fieldsetOverseas = document.getElementById("fieldset-overseas");
    const fieldsetDomestic = document.getElementById("fieldset-domestic");
    const dialCodeEl = document.getElementById("phone_dial_code");

    // ------------------------------------------------------------
    // Phone country-code dropdown: populated from DIAL_CODES,
    // defaults to India (+91) since that's who most registrants will
    // be, and auto-follows the Country field below — but the person
    // can still change it manually afterwards (e.g. an overseas buyer
    // registering with an Indian rep's mobile, or vice versa).
    // ------------------------------------------------------------
    (function populateDialCodes() {
      const codes = window.DIAL_CODES || {};
      Object.keys(codes).forEach(function (name) {
        const opt = document.createElement("option");
        opt.value = codes[name];
        opt.textContent = codes[name] + " " + name;
        opt.dataset.country = name;
        if (name === "India") opt.selected = true;
        dialCodeEl.appendChild(opt);
      });
    })();

    // ------------------------------------------------------------
    // Buyer type toggle: shows/hides the section that only applies
    // to that buyer type. "Buying/Sourcing consultants" gets neither
    // extra section — matches the source form exactly.
    // ------------------------------------------------------------
    function currentBuyerType() {
      const checked = document.querySelector('input[name="buyer_type"]:checked');
      return checked ? checked.value : "";
    }

    function updateBuyerTypeSections() {
      const type = currentBuyerType();
      fieldsetOverseas.classList.toggle("hidden", type !== "Overseas buyers");
      fieldsetDomestic.classList.toggle("hidden", type !== "Domestic volume buyers");
    }

    buyerTypeRadios.forEach(function (radio) {
      radio.addEventListener("change", updateBuyerTypeSections);
    });
    updateBuyerTypeSections();

    // Reads every checked checkbox inside a .check-grid group and
    // returns their values as an array — used for every checkbox-tile
    // field (nature of business, known-through, products of interest).
    function checkedValues(groupEl) {
      if (!groupEl) return [];
      return Array.from(groupEl.querySelectorAll('input[type="checkbox"]:checked')).map(function (el) {
        return el.value;
      });
    }
  
    // ------------------------------------------------------------
    // Country dropdown: populated once from location-data.js.
    // ------------------------------------------------------------
    (window.COUNTRIES || []).forEach(function (name) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      countryEl.appendChild(opt);
    });
  
    // State/District each have TWO elements sharing one label+slot
    // (a dropdown for India, a text field for everyone else) — only
    // one is ever visible at a time, so the field is NEVER a blank
    // gap: it's always either a locked/disabled placeholder, a real
    // dropdown, or an editable text box.
  
    function setStateMode(mode) {
      // 'locked'  -> disabled dropdown, "Select country first"
      // 'india'   -> enabled dropdown with real state options
      // 'text'    -> enabled free-text field (non-India country)
      if (mode === "india") {
        stateSelect.classList.remove("hidden");
        stateSelect.disabled = false;
        stateText.classList.add("hidden");
      } else if (mode === "text") {
        stateSelect.classList.add("hidden");
        stateText.classList.remove("hidden");
        stateText.disabled = false;
      } else {
        stateSelect.classList.remove("hidden");
        stateSelect.disabled = true;
        stateSelect.innerHTML = '<option value="" selected>Select country first</option>';
        stateText.classList.add("hidden");
        stateText.value = "";
      }
    }
  
    function setDistrictMode(mode) {
      // 'locked'  -> disabled dropdown, "Select state first"
      // 'india'   -> enabled dropdown with real district options
      // 'text'    -> enabled free-text field (non-India country)
      if (mode === "india") {
        districtSelect.classList.remove("hidden");
        districtSelect.disabled = false;
        districtText.classList.add("hidden");
      } else if (mode === "text") {
        districtSelect.classList.add("hidden");
        districtText.classList.remove("hidden");
        districtText.disabled = false;
      } else {
        districtSelect.classList.remove("hidden");
        districtSelect.disabled = true;
        districtSelect.innerHTML = '<option value="" selected>Select state first</option>';
        districtText.classList.add("hidden");
        districtText.value = "";
      }
    }
  
    // Country changes -> reset State/District, then unlock the right
    // mode (real dropdown chain for India, free text for everyone
    // else — we don't have district-level data for every country).
    countryEl.addEventListener("change", function () {
      if (countryEl.value === "India") {
        stateSelect.innerHTML = '<option value="" selected>Select state</option>';
        Object.keys(window.INDIA_LOCATIONS || {}).forEach(function (state) {
          const opt = document.createElement("option");
          opt.value = state;
          opt.textContent = state;
          stateSelect.appendChild(opt);
        });
        setStateMode("india");
        setDistrictMode("locked");
      } else if (countryEl.value) {
        setStateMode("text");
        setDistrictMode("text");
      } else {
        setStateMode("locked");
        setDistrictMode("locked");
      }

      // Auto-follow the dial code to whichever country was just
      // picked, when we actually have a code for it — still just a
      // starting point, the person can pick a different one after.
      const code = (window.DIAL_CODES || {})[countryEl.value];
      if (code) dialCodeEl.value = code;
    });
  
    // State (India) changes -> populate District dropdown for that state.
    stateSelect.addEventListener("change", function () {
      const districts = (window.INDIA_LOCATIONS || {})[stateSelect.value] || [];
      if (districts.length) {
        districtSelect.innerHTML = '<option value="" selected>Select district</option>';
        districts.forEach(function (d) {
          const opt = document.createElement("option");
          opt.value = d;
          opt.textContent = d;
          districtSelect.appendChild(opt);
        });
        setDistrictMode("india");
      } else {
        setDistrictMode("locked");
      }
    });
  
    // Reads whichever field (dropdown or text) is currently active
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

      const buyerType = currentBuyerType();
      if (!buyerType) {
        showError("Please select your buyer type at the top of the form.");
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }

      // Mandatory-field check — mirrors every field marked * on the
      // form: Full Name, Company Name, Designation, Email, Phone,
      // Country, State, Street, Zip/Post Code.
      const requiredChecks = [
        [document.getElementById("full_name").value.trim(), "Please enter your Full Name."],
        [document.getElementById("company_name").value.trim(), "Please enter your Company Name."],
        [document.getElementById("designation").value.trim(), "Please enter your Designation."],
        [document.getElementById("email").value.trim(), "Please enter your Email."],
        [document.getElementById("phone_number").value.trim(), "Please enter your Phone Number."],
        [countryEl.value, "Please select your Country."],
        [currentStateValue(), "Please enter/select your State."],
        [document.getElementById("street").value.trim(), "Please enter your Street address."],
        [document.getElementById("pincode").value.trim(), "Please enter your Zip/Post Code."],
      ];
      for (const [value, message] of requiredChecks) {
        if (!value) {
          showError(message);
          return;
        }
      }

      // Products of interest is common to every buyer type.
      const productsOfInterest = checkedValues(document.getElementById("products-of-interest"));
      if (!productsOfInterest.length) {
        showError("Please select at least one product of interest.");
        return;
      }

      const payload = {
        buyer_type: buyerType,
        full_name: document.getElementById("full_name").value.trim(),
        company_name: document.getElementById("company_name").value.trim(),
        designation: document.getElementById("designation").value.trim(),
        email: document.getElementById("email").value.trim(),
        phone_number: (dialCodeEl.value + " " + document.getElementById("phone_number").value.trim()).trim(),
        address: document.getElementById("street").value.trim(),
        district: currentDistrictValue() || null,
        state: currentStateValue(),
        country: countryEl.value,
        pincode: document.getElementById("pincode").value.trim(),
        nature_of_business: null,
        annual_turnover: null,
        known_through: null,
        online_seller: null,
        products_of_interest: productsOfInterest,
      };

      // Buyer-type-specific required fields — only validated for the
      // section that's actually visible for the selected buyer type.
      if (buyerType === "Overseas buyers") {
        const nob = checkedValues(document.getElementById("nob-overseas"));
        const turnover = document.getElementById("annual_turnover").value.trim();
        if (!nob.length) {
          showError("Please select at least one 'Nature of business' option.");
          return;
        }
        if (!turnover) {
          showError("Please enter your Annual Turnover in USD (2024).");
          return;
        }
        payload.nature_of_business = nob;
        payload.annual_turnover = turnover;
      } else if (buyerType === "Domestic volume buyers") {
        const known = checkedValues(document.getElementById("known-through"));
        const nob = checkedValues(document.getElementById("nob-domestic"));
        const onlineSellerEl = document.querySelector('input[name="online_seller"]:checked');
        if (!known.length) {
          showError("Please select how you came to know about the fair.");
          return;
        }
        if (!nob.length) {
          showError("Please select at least one 'Nature of business' option.");
          return;
        }
        if (!onlineSellerEl) {
          showError("Please tell us if you're an online seller on Ecommerce platforms.");
          return;
        }
        payload.known_through = known;
        payload.nature_of_business = nob;
        payload.online_seller = onlineSellerEl.value;
      }

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
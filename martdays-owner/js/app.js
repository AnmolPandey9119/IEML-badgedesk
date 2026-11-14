/* ==========================================================
   app.js — Mart Owner registration form.
   Posts to the SAME public backend endpoint the buyer form uses
   (/api/mart-days/register) — backend + database unchanged.
   Owner data is mapped onto the EXISTING mart_days_registrations
   columns, so no new table/column is needed:

     buyer_type          -> "Mart owners"
     full_name           -> First Name + Last Name
     company_name        -> Company Name
     designation         -> "Mart Owner"
     email / phone_number-> Email ID / "+91 " + Mobile Number
     address             -> "Mart No. <Mart No.>"
     country             -> "India"
     nature_of_business  -> ["Mart Owner"]
     known_through       -> ["Mart No: ..", "Open Mart during Mart Sourcing Days: Yes/No",
                             "Interested in Domestic Volume Buyers: ..."]
   ========================================================== */
   (function () {
    const form = document.getElementById("owner-form");
    const submitBtn = document.getElementById("submit-btn");
    const errorBox = document.getElementById("form-error");
    const formSection = document.getElementById("form-section");
    const successSection = document.getElementById("success-section");
  
    const val = (id) => document.getElementById(id).value.trim();
  
    function showError(msg) {
      errorBox.textContent = msg;
      errorBox.classList.remove("hidden");
    }
    function clearError() {
      errorBox.classList.add("hidden");
      errorBox.textContent = "";
    }
  
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      clearError();
  
      const openMartEl = document.querySelector('input[name="open_mart"]:checked');
      const phoneDigits = val("phone_number").replace(/[\s\-()]/g, "");
  
      const checks = [
        [val("mart_no"), "Please enter your Mart No."],
        [val("company_name"), "Please enter your Company Name."],
        [val("first_name"), "Please enter your First Name."],
        [val("last_name"), "Please enter your Last Name."],
        [phoneDigits, "Please enter your Mobile Number."],
        [val("email"), "Please enter your Email ID."],
        [openMartEl, "Please tell us if you are interested in opening your Mart during Mart Sourcing Days."],
        [val("domestic_interest"), "Please select if you are interested in Domestic Volume Buyers."],
      ];
      for (const [v, msg] of checks) {
        if (!v) { showError(msg); return; }
      }
      if (!/^\d{10}$/.test(phoneDigits)) {
        showError("Please enter a valid 10-digit Mobile Number.");
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val("email"))) {
        showError("Please enter a valid Email ID.");
        return;
      }
  
      // Mart No. is alphanumeric and may contain special characters (A-12, B/204, C12#...) — sent as-is.
      const martNo = val("mart_no");
      const payload = {
        buyer_type: "Mart owners",
        full_name: (val("first_name") + " " + val("last_name")).trim(),
        company_name: val("company_name"),
        designation: "Mart Owner",
        email: val("email").toLowerCase(),
        phone_number: "+91 " + phoneDigits,
        address: "Mart No. " + martNo,
        district: null,
        state: null,
        country: "India",
        pincode: null,
        nature_of_business: ["Mart Owner"],
        annual_turnover: null,
        known_through: [
          "Mart No: " + martNo,
          "Open Mart during Mart Sourcing Days: " + openMartEl.value,
          "Interested in Domestic Volume Buyers: " + val("domestic_interest"),
        ],
        online_seller: null,
        products_of_interest: null,
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
          const body = await res.json().catch(() => ({}));
          const d = body.detail;
          if (res.status === 409) {
            // Backend rejects a repeated email or mobile number (one entry per email / mobile).
            throw new Error(
              (typeof d === "string" && d) ||
              "This email or mobile number is already registered. Each email and mobile number can be used only once."
            );
          }
          throw new Error(typeof d === "string" ? d : "Please check the form — some details look invalid.");
        }
        const data = await res.json();
        document.getElementById("success-name").textContent = data.full_name;
        formSection.classList.add("hidden");
        successSection.classList.remove("hidden");
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (err) {
        showError(err.message || "Something went wrong. Please try again.");
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit";
      }
    });
  })();
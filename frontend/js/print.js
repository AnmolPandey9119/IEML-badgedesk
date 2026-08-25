/* ==========================================================
   print.js
   Dual-purpose file:
   1) On index.html -> exposes window.BadgePrint.printVisitor()
      which loads print.html inside a hidden iframe and triggers
      the browser print dialog for that iframe only.
   2) On print.html itself -> reads visitor data from the URL
      query params, fills in Name/Org/URN, renders the QR code,
      then signals back to the parent window that it's ready.
   ========================================================== */

   (function () {

    const isPrintPage = document.getElementById("badge-sheet") !== null;
  
    /* ==========================================================
       PART 1: Runs when THIS SCRIPT IS LOADED INSIDE print.html
       ========================================================== */
    if (isPrintPage) {
      const params = new URLSearchParams(window.location.search);
  
      const visitor = {
        name: params.get("name") || "",
        organization: params.get("org") || "",
        urn: params.get("urn") || "",
        mobile: params.get("mobile") || "",
        email: params.get("email") || "",
      };
  
      document.getElementById("field-name").textContent = visitor.name;
      document.getElementById("field-org").textContent = visitor.organization;
      document.getElementById("field-urn").textContent = visitor.urn;
  
      // QR content: URN is always the FIRST line — the entrance-scanning
      // app (built later) only needs to read that first line to identify
      // the visitor and look up fresh details from the backend. The rest
      // (name/mobile/email) is there so a plain phone camera / Google Lens
      // scan shows something human-readable too — handy for exhibitors
      // exchanging contact info at the event. Any field left blank is
      // simply skipped.
      const qrLines = [`URN: ${visitor.urn}`];
      if (visitor.name) qrLines.push(`Name: ${visitor.name}`);
      if (visitor.mobile) qrLines.push(`Mobile: ${visitor.mobile}`);
      if (visitor.email) qrLines.push(`Email: ${visitor.email}`);
      const qrText = qrLines.join("\n");
  
      const qrContainer = document.getElementById("qr-code");
      qrContainer.innerHTML = "";
      // eslint-disable-next-line no-undef
      new QRCode(qrContainer, {
        text: qrText,
        width: 115,   // px, roughly maps to the 1.2in box at print resolution
        height: 115,
        correctLevel: QRCode.CorrectLevel.M,
      });
  
      // Give the QR library a brief moment to finish drawing to
      // canvas/img before telling the parent we're ready to print.
      // 150ms is enough in practice; increase if QR sometimes
      // renders blank on slower machines.
      setTimeout(() => {
        if (window.parent && window.parent !== window) {
          window.parent.postMessage({ type: "badge-ready-to-print" }, "*");
        }
      }, 150);
  
      return;
    }
  
    /* ==========================================================
       PART 2: Runs when THIS SCRIPT IS LOADED INSIDE index.html
       Exposes window.BadgePrint.printVisitor(visitor, callback)
       ========================================================== */
  
    const printFrame = document.getElementById("print-frame");
    let pendingCallback = null;
    let printTimeoutId = null;
  
    window.addEventListener("message", (event) => {
      if (!event.data || event.data.type !== "badge-ready-to-print") return;
  
      clearTimeout(printTimeoutId);
  
      try {
        printFrame.contentWindow.focus();
        printFrame.contentWindow.print();
        finishPrint(true);
      } catch (err) {
        console.error("Print failed:", err);
        finishPrint(false);
      }
    });
  
    function finishPrint(success) {
      if (pendingCallback) {
        pendingCallback(success);
        pendingCallback = null;
      }
    }
  
    window.BadgePrint = {
      /**
       * Loads print.html with this visitor's data inside the hidden
       * iframe and triggers the browser print dialog for it.
       * callback(success: boolean) is called once print has been
       * triggered (or failed / timed out).
       */
      printVisitor(visitor, callback) {
        pendingCallback = callback || function () {};
  
        const url =
          `print.html?name=${encodeURIComponent(visitor.name || "")}` +
          `&org=${encodeURIComponent(visitor.organization || "")}` +
          `&urn=${encodeURIComponent(visitor.urn || "")}` +
          `&mobile=${encodeURIComponent(visitor.mobile || "")}` +
          `&email=${encodeURIComponent(visitor.email || "")}`;
  
        // Safety timeout: if print.html never signals ready
        // (e.g. QR library failed to load), don't leave the
        // operator stuck — mark it failed after 5s so they can retry.
        printTimeoutId = setTimeout(() => {
          console.warn("Print timed out waiting for badge-ready-to-print");
          finishPrint(false);
        }, 5000);
  
        printFrame.src = url;
      },
    };
  
  })();
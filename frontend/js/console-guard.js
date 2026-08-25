/**
 * console-guard.js
 * Purely a visual/social-engineering deterrent for the browser console.
 * IMPORTANT: this is NOT real security. Anyone who actually knows what
 * they're doing can still read Network/Sources tabs, inspect requests,
 * etc. Do not rely on this to protect sensitive data — that must be
 * enforced by the backend (auth, RBAC, rate limits) instead.
 */
(function () {
    "use strict";
  
    var stopCSS =
      "color:#ef4444;font-weight:900;font-size:60px;line-height:60px;" +
      "text-shadow:2px 2px 0 #7f1d1d;";
    var subCSS =
      "color:#f87171;font-weight:bold;font-size:15px;line-height:1.5;";
    var tipCSS = "color:#94a3b8;font-style:italic;font-size:13px;";
    var dimCSS = "color:#64748b;font-size:12px;";
  
    function printBanner() {
      console.log("%cSTOP!", stopCSS);
      console.log(
        "%cThis is a browser feature meant for developers. If someone told you to copy-paste something here to \"unlock\" a feature or fix an issue, it is a scam — pasting it can hand them access to this admin panel and everyone's data in it.",
        subCSS
      );
      console.log(" ");
      console.log("%cTip: This is admin panel. Don't do anything in console.", tipCSS);
    }
  
    // Fake boot-noise: mimics ordinary app logging so the console doesn't
    // read as "empty and suspicious" — same idea as the screenshot.
    function printNoise() {
      console.log("EventProvider initialized with user:", {});
      var n = 8;
      for (var i = 0; i < n; i++) {
        console.log("Email");
        console.log({});
      }
    }
  
    function printAll() {
      printBanner();
      printNoise();
    }
  
    // 1) Print once on page load (covers the case where devtools was
    //    already open before/while the page loaded).
    printAll();
  
    // 2) Detect devtools being opened AFTER load (the common real case:
    //    visitor opens the site normally, THEN opens console to paste
    //    something). Docked devtools shrink the window's inner size vs
    //    outer size — poll for that crossing from closed -> open.
    var wasOpen = false;
    var threshold = 160;
    setInterval(function () {
      var isOpen =
        window.outerWidth - window.innerWidth > threshold ||
        window.outerHeight - window.innerHeight > threshold;
      if (isOpen && !wasOpen) {
        printAll();
      }
      wasOpen = isOpen;
    }, 800);
  
    // 3) Fallback for undocked devtools windows (size-based detection
    //    above can't see those) — reprint periodically so the banner is
    //    never more than ~30s stale in the console.
    setInterval(printAll, 30000);
  })();
/* ==========================================================
   edition.js
   Fills the current Mart Days edition (edition number, dates, timing,
   venue, co-located show) into the page from the backend, so nothing
   here ever needs a code change when the month changes — the master
   edits it once in the admin page (martdays-admin) and every page
   picks it up.

   Usage in HTML:  <span data-edition="dates_short">22–23 Oct 2026</span>
   The text already in the tag is the FALLBACK shown instantly (and if
   the backend is unreachable); it is replaced once the live value
   arrives. Available keys: edition_label, dates_short, dates_long,
   timing, venue, co_located_with, badge_tag, event_name, badge_line.
   Add data-edition-prefix="Co-located with " to prepend text; elements
   whose live value is empty are hidden.
   ========================================================== */

   (function () {
    var base = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "";
    if (!base) return;
  
    function apply(ed) {
      ed.badge_line = ed.badge_tag ? ed.edition_label + " · " + ed.badge_tag : ed.edition_label;
      document.querySelectorAll("[data-edition]").forEach(function (el) {
        var value = ed[el.getAttribute("data-edition")];
        if (value === undefined) return;
        if (!value) { el.hidden = true; return; }
        el.hidden = false;
        el.textContent = (el.getAttribute("data-edition-prefix") || "") + value;
      });
      if (ed.event_name && document.body.hasAttribute("data-edition-title")) {
        document.title = document.body.getAttribute("data-edition-title").replace("{event}", ed.event_name);
      }
    }
  
    fetch(base + "/api/mart-edition")
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(apply)
      .catch(function () { /* keep the fallback text already in the page */ });
  })();
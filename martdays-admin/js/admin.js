/* admin.js — Mart Days edition settings (master login only). */
(function () {
    var BASE = window.APP_CONFIG.API_BASE_URL;
    var TOKEN_KEY = "martdays_admin_token";
    var $ = function (id) { return document.getElementById(id); };
    var MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
    var FIELDS = ["edition_number","event_name","start_date","end_date","timing","badge_tag","co_located_with","venue","email_note"];
  
    function getToken() { try { return sessionStorage.getItem(TOKEN_KEY); } catch (e) { return null; } }
    function setToken(t) { try { t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY); } catch (e) {} }
  
    function ordinal(n) {
      var v = n % 100;
      if (v >= 10 && v <= 20) return n + "th";
      return n + ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
    }
    function parse(s) { var p = (s || "").split("-"); return p.length === 3 ? { y: +p[0], m: +p[1], d: +p[2] } : null; }
    function fmtDates(a, b) {   // mirrors services/edition_store.format_dates (long form)
      if (!a || !b) return "";
      var ma = MONTHS[a.m - 1], mb = MONTHS[b.m - 1];
      if (a.y === b.y && a.m === b.m && a.d === b.d) return a.d + " " + mb + " " + b.y;
      if (a.y !== b.y) return a.d + " " + ma + " " + a.y + " – " + b.d + " " + mb + " " + b.y;
      if (a.m !== b.m) return a.d + " " + ma + " – " + b.d + " " + mb + " " + b.y;
      return a.d + "–" + b.d + " " + mb + " " + b.y;
    }
  
    function show(el, text, kind) {
      el.textContent = text; el.className = "msg " + (kind || ""); el.hidden = !text;
    }
  
    async function api(path, opts) {
      opts = opts || {};
      var headers = { "Content-Type": "application/json" };
      if (getToken()) headers.Authorization = "Bearer " + getToken();
      var res = await fetch(BASE + path, Object.assign({}, opts, { headers: headers }));
      var data = await res.json().catch(function () { return {}; });
      if (res.status === 401 && path !== "/api/auth/login") { logout(); throw new Error("Session expired — please sign in again."); }
      if (!res.ok) {
        var d = data.detail;
        if (Array.isArray(d)) d = d.map(function (x) { return (x.loc || []).slice(-1) + ": " + x.msg; }).join("; ");
        throw new Error(d || "Request failed (" + res.status + ")");
      }
      return data;
    }
  
    function fill(ed) {
      FIELDS.forEach(function (f) { $(f).value = ed[f] == null ? "" : ed[f]; });
      $("live-title").textContent = ed.edition_label + " · " + ed.event_name;
      $("live-sub").textContent = ed.dates_long + (ed.timing ? " · " + ed.timing : "");
      $("live-meta").textContent = (ed.co_located_with ? "Co-located with " + ed.co_located_with + " · " : "") + ed.venue +
        (ed.updated_by && ed.updated_by !== "seed" ? " · last saved by " + ed.updated_by : "");
      refreshPreview();
    }
  
    function refreshPreview() {
      var n = parseInt($("edition_number").value, 10);
      $("edition_hint").textContent = n > 0 ? "Shows as “" + ordinal(n) + " Edition”" : "";
      var s = fmtDates(parse($("start_date").value), parse($("end_date").value));
      $("dates_preview").textContent = s || "—";
    }
  
    async function load() {
      try { fill(await api("/api/mart-edition")); }
      catch (e) { show($("save-msg"), e.message, "error"); }
    }
  
    function showApp(username) {
      $("login-view").hidden = true; $("app-view").hidden = false; $("who").textContent = username || "";
      load();
    }
    function logout() { setToken(null); $("app-view").hidden = true; $("login-view").hidden = false; }
  
    $("login-form").addEventListener("submit", async function (e) {
      e.preventDefault();
      show($("login-error"), "");
      try {
        var data = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username: $("username").value, password: $("password").value }) });
        if (data.role !== "master") { show($("login-error"), "This account is not a master login.", "error"); return; }
        setToken(data.access_token); $("password").value = ""; showApp(data.username);
      } catch (err) { show($("login-error"), err.message, "error"); }
    });
    $("logout-btn").addEventListener("click", logout);
  
    ["edition_number", "start_date", "end_date"].forEach(function (id) { $(id).addEventListener("input", refreshPreview); });
  
    $("next-month-btn").addEventListener("click", function () {
      $("edition_number").value = (parseInt($("edition_number").value, 10) || 0) + 1;
      $("start_date").value = ""; $("end_date").value = ""; $("co_located_with").value = "";
      refreshPreview(); $("start_date").focus();
      show($("save-msg"), "Next edition started — pick the new dates and co-located show, then Save.", "");
    });
  
    $("edition-form").addEventListener("submit", async function (e) {
      e.preventDefault();
      var body = {};
      FIELDS.forEach(function (f) { body[f] = $(f).value; });
      body.edition_number = parseInt(body.edition_number, 10);
      if (!body.edition_number || !body.start_date || !body.end_date) { show($("save-msg"), "Edition number and both dates are required.", "error"); return; }
      $("save-btn").disabled = true;
      try {
        var saved = await api("/api/mart-edition", { method: "PUT", body: JSON.stringify(body) });
        fill(saved);
        show($("save-msg"), "Saved. Now live: " + saved.edition_label + ", " + saved.dates_long + ".", "ok");
      } catch (err) { show($("save-msg"), err.message, "error"); }
      finally { $("save-btn").disabled = false; }
    });
  
    $("preview-btn").addEventListener("click", async function () {
      show($("email-msg"), "");
      try {
        var p = await api("/api/mart-edition/email-preview");
        $("preview-subject").textContent = p.subject; $("preview-frame").srcdoc = p.html; $("preview-box").hidden = false;
      } catch (err) { show($("email-msg"), err.message, "error"); }
    });
  
    $("test-btn").addEventListener("click", async function () {
      var to = $("test-to").value.trim();
      if (!to) { show($("email-msg"), "Enter an email address to send the test to.", "error"); return; }
      $("test-btn").disabled = true; show($("email-msg"), "Sending…", "");
      try { await api("/api/mart-edition/test-email", { method: "POST", body: JSON.stringify({ to: to }) }); show($("email-msg"), "Test email sent to " + to + ".", "ok"); }
      catch (err) { show($("email-msg"), err.message, "error"); }
      finally { $("test-btn").disabled = false; }
    });
  
    if (getToken()) showApp(""); 
  })();
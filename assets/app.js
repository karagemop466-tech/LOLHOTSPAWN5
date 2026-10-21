/* Progressive enhancements: filters, search, local-time toggle. No dependencies. */
(function () {
  "use strict";

  /* ---------- tournament filter + search (picks page) ---------- */
  var chips = document.getElementById("chips");
  var q = document.getElementById("q");
  var countEl = document.getElementById("count");

  function apply() {
    var active = document.querySelector(".chip.is-on");
    var key = active ? active.getAttribute("data-filter") : "all";
    var term = (q && q.value || "").trim().toLowerCase();
    var shown = 0;
    document.querySelectorAll(".compblock").forEach(function (block) {
      var visibleInBlock = 0;
      block.querySelectorAll(".match").forEach(function (m) {
        var okT = key === "all" || m.getAttribute("data-t") === key;
        var okQ = !term || (m.getAttribute("data-q") || "").indexOf(term) !== -1;
        var show = okT && okQ;
        m.hidden = !show;
        if (show) visibleInBlock++;
      });
      block.hidden = visibleInBlock === 0;
      shown += visibleInBlock;
    });
    if (countEl) {
      countEl.textContent = shown + (shown === 1 ? " fixture shown" : " fixtures shown");
    }
  }

  if (chips) {
    chips.addEventListener("click", function (e) {
      var b = e.target.closest(".chip");
      if (!b) return;
      chips.querySelectorAll(".chip").forEach(function (c) { c.classList.remove("is-on"); });
      b.classList.add("is-on");
      apply();
    });
  }
  if (q) {
    var t;
    q.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(apply, 120);
    });
  }
  if (chips || q) apply();

  /* ---------- local time toggle ---------- */
  var btn = document.getElementById("tz");
  var KEY = "lolpick.tz";
  var mode = "utc";
  try { mode = localStorage.getItem(KEY) || "utc"; } catch (e) {}

  function render() {
    document.querySelectorAll("time[data-utc]").forEach(function (el) {
      var iso = el.getAttribute("data-utc");
      if (!iso) return;
      var d = new Date(iso);
      if (isNaN(d.getTime())) return;
      if (!el.getAttribute("data-utc-text")) el.setAttribute("data-utc-text", el.textContent);
      if (mode === "local") {
        el.textContent = d.toLocaleString(undefined, {
          weekday: "short", day: "2-digit", month: "short",
          hour: "2-digit", minute: "2-digit", timeZoneName: "short"
        });
      } else {
        el.textContent = el.getAttribute("data-utc-text");
      }
    });
    if (btn) {
      btn.textContent = mode === "local" ? "Times: your device" : "Times: UTC";
      btn.setAttribute("aria-pressed", mode === "local" ? "true" : "false");
    }
  }
  if (btn) {
    btn.addEventListener("click", function () {
      mode = mode === "local" ? "utc" : "local";
      try { localStorage.setItem(KEY, mode); } catch (e) {}
      render();
    });
  }
  render();
})();

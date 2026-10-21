/* ==========================================================================
   Hotspawn LoL Pick Desk — shared front-end
   Reads ./data/picks.json (regenerated every 6h by GitHub Actions) and renders
   mobile-first pick cards / tables. No build step, no dependencies.
   ========================================================================== */
(function () {
  "use strict";

  var DATA_URL = "data/picks.json";
  var cache = null;

  /* ------------------------------- utilities ------------------------------ */

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function pct(p) { return (p * 100).toFixed(1) + "%"; }

  function fmtTime(iso) {
    if (!iso) return { local: "Time TBC", utc: "" };
    var d = new Date(iso);
    if (isNaN(d.getTime())) return { local: String(iso), utc: "" };
    var local = d.toLocaleString(undefined, {
      weekday: "short", day: "numeric", month: "short",
      hour: "2-digit", minute: "2-digit"
    });
    var utc = iso.replace("T", " ").replace(/:\d{2}\+00:00$/, "") + " UTC";
    return { local: local, utc: utc };
  }

  function methodLabel(m) {
    return m === "MARKET" ? "Market line"
      : m === "MODEL" ? "Originated line"
      : "Unresolved";
  }
  function methodClass(m) {
    return m === "MARKET" ? "market" : m === "MODEL" ? "model" : "unresolved";
  }

  function tierLabel(t) {
    if (!t) return "Tier TBC";
    return "Tier " + String(t).toUpperCase();
  }

  function srcLinks(sources, limit) {
    if (!sources || !sources.length) return '<span class="dim">—</span>';
    var max = limit || 3;
    var shown = sources.slice(0, max);
    var out = shown.map(function (s) {
      return '<li><a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">' +
        esc(s.label) + "</a></li>";
    }).join("");
    if (sources.length > max) {
      out += '<li class="dim">+' + (sources.length - max) + " more</li>";
    }
    return '<ul class="srclist">' + out + "</ul>";
  }

  /* --------------------------------- data -------------------------------- */

  function load() {
    if (cache) return Promise.resolve(cache);
    return fetch(DATA_URL, { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (d) { cache = d; return d; });
  }

  /* ------------------------------- rendering ------------------------------ */

  function teamRow(team, p, isPicked, meta) {
    var cls = "prob-bar" + (p > 0.58 ? "" : " weak");
    return '' +
      '<div class="team' + (isPicked ? " picked" : "") + '">' +
        '<div>' +
          '<div class="team-name">' + esc(team) +
            (isPicked ? '<span class="tick">&#10003; PICK</span>' : "") +
          '</div>' +
          (meta ? '<div class="team-meta">' + esc(meta) + "</div>" : "") +
        "</div>" +
        '<div class="prob">' +
          '<div class="' + cls + '"><i style="width:' + Math.round(p * 100) + '%"></i></div>' +
          '<div class="prob-pct">' + pct(p) + "</div>" +
        "</div>" +
      "</div>";
  }

  function matchCard(m) {
    var t = fmtTime(m.start_utc);
    var meta1 = "Hotspawn crowd " + (m.crowd_pct_team1 == null ? "—" : m.crowd_pct_team1 + "%") +
      " (context only)";
    var meta2 = "Hotspawn crowd " + (m.crowd_pct_team2 == null ? "—" : m.crowd_pct_team2 + "%") +
      " (context only)";
    return '' +
      '<article class="match" data-id="' + esc(m.fixture_id) + '">' +
        '<div class="match-top">' +
          '<span class="tour">' + esc(m.tournament || "Tournament TBC") + "</span>" +
          '<span class="badge tier">' + esc(tierLabel(m.tier)) + "</span>" +
          (m.points != null ? '<span class="badge tier">' + esc(m.points) + " pts</span>" : "") +
          (m.open_for_picks ? "" : '<span class="badge closed">Pick window closed</span>') +
        "</div>" +
        '<div class="match-top" style="margin-top:-4px">' +
          '<span>' + esc(t.local) + "</span>" +
          (t.utc ? '<span class="dim">' + esc(t.utc) + "</span>" : "") +
        "</div>" +
        '<div class="match-teams">' +
          teamRow(m.team1, m.prob_team1, m.pick === m.team1, meta1) +
          teamRow(m.team2, m.prob_team2, m.pick === m.team2, meta2) +
        "</div>" +
        '<div class="match-foot">' +
          '<span class="pickline">PICK: ' + esc(m.pick) + " (" + pct(m.pick_prob) + ")</span>" +
          '<span class="badge ' + methodClass(m.method) + '">' + esc(methodLabel(m.method)) + "</span>" +
        "</div>" +
        '<div class="evidence"><b>How this line was produced:</b> ' + esc(m.evidence) + "</div>" +
        '<div class="evidence"><b>Confidence:</b> ' + esc(m.confidence) + "</div>" +
        '<div class="evidence"><b>Official sources:</b> ' + srcLinks(m.sources, 4) + "</div>" +
      "</article>";
  }

  function tableHTML(matches) {
    var rows = matches.map(function (m) {
      var t = fmtTime(m.start_utc);
      return "<tr>" +
        "<td>" + esc(t.local) + '<div class="small">' + esc(t.utc) + "</div></td>" +
        "<td>" + esc(m.tournament || "") +
          '<div class="small"><span class="badge tier">' + esc(tierLabel(m.tier)) + "</span></div></td>" +
        "<td>" + esc(m.team1) + "</td>" +
        "<td>" + esc(m.team2) + "</td>" +
        '<td class="num">' + pct(m.prob_team1) + "</td>" +
        '<td class="num">' + pct(m.prob_team2) + "</td>" +
        "<td><b>" + esc(m.pick) + '</b><div class="small">' + pct(m.pick_prob) + "</div></td>" +
        '<td><span class="badge ' + methodClass(m.method) + '">' + esc(methodLabel(m.method)) + "</span></td>" +
        "<td>" + srcLinks(m.sources, 2) + "</td>" +
        "</tr>";
    }).join("");
    return '<div class="tablewrap"><table class="data"><thead><tr>' +
      "<th>Start</th><th>Tournament</th><th>Team A</th><th>Team B</th>" +
      "<th>A win&nbsp;%</th><th>B win&nbsp;%</th><th>Pick</th><th>Line source</th><th>Sources</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function render(container, matches, view) {
    if (!matches.length) {
      container.innerHTML = '<div class="card muted">No matches match this filter.</div>';
      return;
    }
    if (view === "table") {
      container.innerHTML = tableHTML(matches);
    } else {
      container.innerHTML = '<div class="matchlist">' + matches.map(matchCard).join("") + "</div>";
    }
  }

  /* ------------------------------- filtering ------------------------------ */

  function applyFilters(all, container) {
    var q = ($("#search") && $("#search").value || "").toLowerCase().trim();
    var tour = $("#tournament-filter") ? $("#tournament-filter").value : "";
    var method = container.getAttribute("data-method") || "";
    var openOnly = container.getAttribute("data-open-only") === "1";
    var unresolvedOnly = container.getAttribute("data-unresolved-only") === "1";

    var out = all.filter(function (m) {
      if (method && m.method !== method) return false;
      if (openOnly && !m.open_for_picks) return false;
      if (unresolvedOnly && m.method !== "UNRESOLVED") return false;
      if (tour && m.tournament !== tour) return false;
      if (q) {
        var hay = (m.team1 + " " + m.team2 + " " + m.tournament + " " +
                   (m.pick || "") + " " + (m.evidence || "")).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    return out;
  }

  /* ------------------------------- page wiring ---------------------------- */

  function getView(defaultView) {
    try {
      var v = localStorage.getItem("hs-view");
      if (v === "table" || v === "cards") return v;
    } catch (e) { /* ignore */ }
    return defaultView || (window.matchMedia("(min-width: 900px)").matches ? "table" : "cards");
  }

  function setView(v, container, all) {
    try { localStorage.setItem("hs-view", v); } catch (e) { /* ignore */ }
    $$(".viewtoggle button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-view") === v ? "true" : "false");
    });
    render(container, applyFilters(all, container), v);
  }

  function initList() {
    var container = $("#list");
    if (!container) return;
    load().then(function (data) {
      var all = data.matches || [];

      // tournament filter options
      var sel = $("#tournament-filter");
      if (sel) {
        var tours = {};
        all.forEach(function (m) { if (m.tournament) tours[m.tournament] = 1; });
        Object.keys(tours).sort().forEach(function (t) {
          var o = document.createElement("option");
          o.value = t; o.textContent = t;
          sel.appendChild(o);
        });
      }

      var view = getView();
      $$(".viewtoggle button").forEach(function (b) {
        b.addEventListener("click", function () { setView(b.getAttribute("data-view"), container, all); });
      });
      ["#search", "#tournament-filter"].forEach(function (s) {
        var el = $(s);
        if (el) {
          el.addEventListener("input", function () { render(container, applyFilters(all, container), view); });
          el.addEventListener("change", function () { render(container, applyFilters(all, container), view); });
        }
      });

      setView(view, container, all);

      var countEl = $("#result-count");
      if (countEl) {
        var n = applyFilters(all, container).length;
        countEl.textContent = n + " of " + all.length + " fixtures";
      }
      var obs = new MutationObserver(function () {
        var c = $("#result-count");
        if (c) c.textContent = applyFilters(all, container).length + " of " + all.length + " fixtures";
      });
      obs.observe(container, { childList: true });
    }).catch(function (e) {
      container.innerHTML = '<div class="err">Could not load <code>data/picks.json</code> (' +
        esc(e.message) + "). The data file is regenerated every 6 hours — please reload shortly.</div>";
    });
  }

  function initSummary() {
    var el = $("#summary");
    if (!el) return;
    load().then(function (data) {
      var m = data.matches || [];
      var open = m.filter(function (x) { return x.open_for_picks; });
      var byMethod = { MARKET: 0, MODEL: 0, UNRESOLVED: 0 };
      m.forEach(function (x) { byMethod[x.method] = (byMethod[x.method] || 0) + 1; });

      var tiles = [
        { k: "Fixtures on board", v: m.length, n: "every scheduled LoL Pick'em on Hotspawn", c: "accent" },
        { k: "Open for picks", v: open.length, n: "lock time still in the future", c: "accent" },
        { k: "Priced by market", v: byMethod.MARKET || 0, n: "Pinnacle / Unibet / Polymarket", c: "good" },
        { k: "Originated lines", v: byMethod.MODEL || 0, n: "proprietary Leaguepedia model", c: "" },
        { k: "Unresolved", v: byMethod.UNRESOLVED || 0, n: "50/50 nominal pick, flagged", c: "warn" }
      ];
      el.innerHTML = '<div class="grid c2 c3">' + tiles.map(function (t) {
        return '<div class="stat ' + t.c + '">' +
          '<div class="stat-k">' + esc(t.k) + "</div>" +
          '<div class="stat-v">' + esc(t.v) + "</div>" +
          '<div class="stat-n">' + esc(t.n) + "</div></div>";
      }).join("") + "</div>";

      var stamp = $("#updated");
      if (stamp) stamp.textContent = (data.generated_at_human || data.generated_at || "—");

      $$("[data-count]").forEach(function (node) {
        var key = node.getAttribute("data-count");
        var val = {
          total: m.length,
          open: open.length,
          market: byMethod.MARKET || 0,
          model: byMethod.MODEL || 0,
          unresolved: byMethod.UNRESOLVED || 0
        }[key];
        if (val != null) node.textContent = String(val);
      });
    }).catch(function (e) {
      el.innerHTML = '<div class="err">Could not load <code>data/picks.json</code> (' +
        esc(e.message) + ").</div>";
    });
  }

  /* ------------------------- sources + flagged pages ---------------------- */

  function initSources() {
    var el = $("#sources-list");
    if (!el) return;
    fetch("data/sources.json", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) {
        var rows = (d.sources || []).map(function (s) {
          return '<div class="card">' +
            '<h3 style="margin-top:0"><a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">' +
            esc(s.name) + "</a> " +
            (s.verified
              ? '<span class="badge verified">Verified reachable</span>'
              : '<span class="badge unverified">Not reachable this run</span>') +
            "</h3>" +
            '<p style="margin:6px 0"><b>Role:</b> ' + esc(s.role) + "</p>" +
            '<p class="small" style="margin:6px 0"><b>Verification performed:</b> ' + esc(s.verification) + "</p>" +
            '<p class="small" style="margin:6px 0"><code>' + esc(s.url) + "</code></p>" +
            "</div>";
        }).join("");
        el.innerHTML = '<div class="stack">' + rows + "</div>" +
          '<p class="small muted">Verified at ' + esc(d.generated_at || "") + ".</p>";
      })
      .catch(function (e) {
        el.innerHTML = '<div class="err">Could not load <code>data/sources.json</code> (' +
          esc(e.message) + ").</div>";
      });
  }

  function initFlagged() {
    var el = $("#flagged-list");
    if (!el) return;
    fetch("data/flagged.json", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (d) {
        var items = d.items || [];
        if (!items.length) {
          el.innerHTML = '<div class="note good">No flagged items in the current run.</div>';
          return;
        }
        var sevClass = { high: "bad", medium: "warn", low: "" };
        var grouped = {};
        items.forEach(function (i) { (grouped[i.kind] = grouped[i.kind] || []).push(i); });
        var html = Object.keys(grouped).sort().map(function (kind) {
          var list = grouped[kind];
          return '<h3>' + esc(kind.replace(/-/g, " ")) +
            ' <span class="badge ' + (sevClass[list[0].severity] || "") + '">' +
            esc(list[0].severity) + '</span> <span class="small muted">' + list.length + " items</span></h3>" +
            list.map(function (i) {
              return '<div class="card">' +
                '<div style="font-weight:700">' + esc(i.title) + "</div>" +
                '<div class="small muted">' + esc(i.match || "") +
                (i.tournament ? " — " + esc(i.tournament) : "") +
                (i.start_utc ? " — " + esc(fmtTime(i.start_utc).utc) : "") + "</div>" +
                '<p class="small" style="margin:8px 0 4px">' + esc(i.detail) + "</p>" +
                srcLinks(i.sources, 4) +
                "</div>";
            }).join("");
        }).join("");
        el.innerHTML = '<p class="small muted">' + esc(String(d.count)) +
          " flagged items in this run.</p>" + html;
      })
      .catch(function (e) {
        el.innerHTML = '<div class="err">Could not load <code>data/flagged.json</code> (' +
          esc(e.message) + ").</div>";
      });
  }

  function initNavToggle() {
    var btn = $(".nav-toggle");
    var nav = $(".site-nav");
    if (!btn || !nav) return;
    nav.classList.add("collapsed");
    btn.setAttribute("aria-expanded", "false");
    btn.addEventListener("click", function () {
      var collapsed = nav.classList.toggle("collapsed");
      btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initNavToggle();
    initSummary();
    initList();
    initSources();
    initFlagged();
  });
})();

/* Client-side filtering for the picks list. No dependencies, works offline. */
(function () {
  "use strict";

  var search = document.getElementById("q");
  var conf = document.getElementById("conf");
  var tour = document.getElementById("tour");
  var count = document.getElementById("count");
  var rows = Array.prototype.slice.call(document.querySelectorAll("[data-pick]"));
  if (!rows.length) return;

  function apply() {
    var q = (search && search.value ? search.value : "").toLowerCase().trim();
    var c = conf ? conf.value : "";
    var t = tour ? tour.value : "";
    var shown = 0;
    rows.forEach(function (row) {
      var hay = row.getAttribute("data-pick") || "";
      var okQ = !q || hay.indexOf(q) !== -1;
      var okC = !c || row.getAttribute("data-conf") === c;
      var okT = !t || row.getAttribute("data-tour") === t;
      var show = okQ && okC && okT;
      row.classList.toggle("hidden", !show);
      if (show) shown++;
    });
    if (count) count.textContent = shown + " of " + rows.length + " matches";
  }

  if (search) search.addEventListener("input", apply);
  if (conf) conf.addEventListener("change", apply);
  if (tour) tour.addEventListener("change", apply);
  apply();

  // "open only" toggle on the landing page shortcuts
  var onlyOpen = document.getElementById("only-open");
  if (onlyOpen) {
    onlyOpen.addEventListener("change", function () {
      var target = document.getElementById("picks");
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
})();

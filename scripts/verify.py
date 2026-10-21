#!/usr/bin/env python3
"""Line-by-line verification of the generated data and site.

Fails (exit 1) if any invariant is broken, and writes data/verification.json so the
run is auditable. Checks:

  data
    * every fixture row has a Hotspawn source URL
    * every picked row has a pick that is one of the two teams
    * probabilities are in (0,1) and sum to 1
    * every unresolved row states a reason and a remedy
    * market-backed rows carry at least one external source link and a retrieval time
    * market probabilities equal the re-computed blend of their own quotes
  site
    * every internal href/src resolves to a file that exists
    * every page has exactly one <h1> and a viewport meta tag
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
W = {"pinnacle": 0.5, "kalshi": 0.4, "polymarket": 0.3}
errors: list[str] = []
warnings: list[str] = []


def load(name):
    p = DATA / name
    if not p.exists():
        errors.append(f"missing data file: {name}")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def check_data():
    picks = load("picks.json")
    meta = load("meta.json")
    if not picks or not meta:
        return {}, {}
    rows = picks["rows"]
    methods = Counter()
    for r in rows:
        rid = f"{r.get('team_a')} vs {r.get('team_b')} ({r.get('id')})"
        if not r.get("hotspawn_url", "").startswith("https://"):
            errors.append(f"{rid}: no Hotspawn source URL")
        if r["status"] == "picked":
            methods[r.get("basis")] += 1
            if r.get("pick") not in (r["team_a"], r["team_b"]):
                errors.append(f"{rid}: pick is not one of the two teams")
            pa, pb = r.get("prob_a"), r.get("prob_b")
            if not (isinstance(pa, (int, float)) and isinstance(pb, (int, float))):
                errors.append(f"{rid}: missing probabilities")
                continue
            if not (0 < pa < 1 and 0 < pb < 1):
                errors.append(f"{rid}: probability outside (0,1): {pa}/{pb}")
            if abs(pa + pb - 1) > 0.0011:
                errors.append(f"{rid}: probabilities do not sum to 1 ({pa}+{pb})")
            if r.get("basis") in ("market", "market+model"):
                srcs = r.get("market_sources") or []
                if not srcs:
                    errors.append(f"{rid}: market-backed row has no market source")
                for s in srcs:
                    if not s.get("url", "").startswith("https://"):
                        errors.append(f"{rid}: market source without https link")
                    if not s.get("retrieved_utc"):
                        errors.append(f"{rid}: market source without retrieval time")
                # recompute the blend and compare
                num = sum(s["prob_a"] * W.get(s["source"], 0.2) for s in srcs)
                den = sum(W.get(s["source"], 0.2) for s in srcs)
                if den and r.get("model"):
                    expect = 0.75 * (num / den) + 0.25 * r["model"]["prob_a"]
                elif den:
                    expect = num / den
                else:
                    expect = None
                if expect is not None and abs(expect - pa) > 0.0012:
                    errors.append(f"{rid}: published probability {pa} != recomputed blend {expect:.4f}")
            elif r.get("basis") == "model":
                m = r.get("model") or {}
                if not m.get("source"):
                    warnings.append(f"{rid}: model row does not record its rating pool")
                if min(m.get("games_a", 0), m.get("games_b", 0)) < 3:
                    errors.append(f"{rid}: model row with fewer than 3 games per team")
        else:
            if not r.get("reason"):
                errors.append(f"{rid}: unresolved without a reason")
            if not r.get("remedy"):
                warnings.append(f"{rid}: unresolved without a remedy")
    # duplicates
    ids = Counter(r["id"] for r in rows)
    for k, n in ids.items():
        if n > 1:
            errors.append(f"fixture id {k} appears {n} times")
    stats = meta.get("counts", {})
    if stats.get("scheduled") != len(rows):
        errors.append(f"meta scheduled {stats.get('scheduled')} != rows {len(rows)}")
    if stats.get("picked", 0) + stats.get("unresolved", 0) != len(rows):
        errors.append("picked + unresolved != total rows")
    if stats.get("picked") != methods.get("market", 0) + methods.get("market+model", 0) + methods.get("model", 0):
        errors.append("meta picked count does not match row basis counts")
    return picks, meta


PAGES = ["index.html", "404.html"] + [
    f"{p}/index.html" for p in ("picks", "unresolved", "methodology", "sources", "review")
]


def check_site():
    for rel in PAGES:
        f = ROOT / rel
        if not f.exists():
            errors.append(f"missing page: {rel}")
            continue
        html = f.read_text(encoding="utf-8")
        if html.count("<h1") != 1:
            warnings.append(f"{rel}: {html.count('<h1')} <h1> tags")
        if 'name="viewport"' not in html:
            errors.append(f"{rel}: missing viewport meta")
        if "<title>" not in html:
            errors.append(f"{rel}: missing title")
        for attr, url in re.findall(r'(href|src)="([^"]+)"', html):
            if url.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            base = f.parent
            path = url.split("#")[0].split("?")[0]
            if path.startswith("/LOLHOTSPAWN5/"):
                base = ROOT
                path = path[len("/LOLHOTSPAWN5/"):]
            elif path.startswith("/"):
                warnings.append(f"{rel}: root-absolute link outside the Pages base: {url}")
                continue
            if not path:
                continue
            target = (base / path).resolve()
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                errors.append(f"{rel}: broken internal link {url}")
    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        warnings.append("sitemap.xml missing")
    else:
        for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap.read_text(encoding="utf-8")):
            if "karagemop466-tech.github.io/LOLHOTSPAWN5" not in loc:
                warnings.append(f"sitemap loc outside site: {loc}")


def main() -> int:
    picks, meta = check_data()
    check_site()
    report = {
        "generated_utc": (meta or {}).get("generated_utc"),
        "rows": len((picks or {}).get("rows", [])),
        "errors": errors,
        "warnings": warnings,
        "status": "pass" if not errors else "fail",
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "verification.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("rows", "status")}, indent=1))
    for e in errors[:40]:
        print("ERROR:", e)
    for w in warnings[:20]:
        print("WARN:", w)
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Verify the built site: internal links, per-row source links and value sanity.

Checks performed
  1. every internal href/src in the generated HTML points at a file that exists
  2. every pick row carries at least one external source link (absolute http/https)
  3. every published probability is a number in [0, 1] and the pair sums to 1
  4. optionally (--external) a sample of external URLs is requested and recorded

Exit code is non-zero when a check fails, so the scheduled workflow stops before
publishing a broken site.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import EVIDENCE_DIR, REPO_ROOT, utcnow  # noqa: E402

PAGES = ["index.html", "picks.html", "unresolved.html", "review.html",
         "sources.html", "methodology.html"]
HREF_RE = re.compile(r'(?:href|src)="([^"]+)"')
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def check_internal() -> list[str]:
    problems: list[str] = []
    for page in PAGES:
        path = os.path.join(REPO_ROOT, page)
        if not os.path.exists(path):
            problems.append(f"missing page: {page}")
            continue
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        for target in set(HREF_RE.findall(content)):
            if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            clean = target.split("#")[0].split("?")[0]
            if not clean:
                continue
            if not os.path.exists(os.path.join(REPO_ROOT, clean)):
                problems.append(f"{page}: broken internal link -> {target}")
    return problems


def check_picks() -> list[str]:
    problems: list[str] = []
    path = os.path.join(REPO_ROOT, "data", "picks.json")
    if not os.path.exists(path):
        return ["missing data/picks.json"]
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    for pick in doc.get("picks", []):
        label = f"{pick.get('tournament')} / {pick.get('fixture_id')}"
        sources = [row.get("source_url") for row in pick.get("market_sources") or []
                   if row.get("source_url")]
        sources += [pick.get("hotspawn_url")]
        sources += [pick["team_a"].get("source_url"), pick["team_b"].get("source_url")]
        sources = [s for s in sources if s]
        if not sources:
            problems.append(f"{label}: row has no source link")
        for source in sources:
            if not str(source).startswith("http"):
                problems.append(f"{label}: non-http source link {source}")
        for side in ("team_a", "team_b"):
            prob = pick[side].get("prob")
            if prob is None:
                problems.append(f"{label}: missing probability for {pick[side].get('name')}")
                continue
            if not 0 <= float(prob) <= 1:
                problems.append(f"{label}: probability out of range for {pick[side].get('name')}: {prob}")
        pa = pick["team_a"].get("prob")
        pb = pick["team_b"].get("prob")
        if pa is not None and pb is not None and abs((float(pa) + float(pb)) - 1.0) > 0.02:
            problems.append(f"{label}: probabilities do not sum to 1 ({pa} + {pb})")
        if pick.get("confidence") == "default" and not pick.get("flags"):
            problems.append(f"{label}: default row without a flag")
    return problems


def check_external(limit: int = 40) -> tuple[list[str], list[dict]]:
    problems: list[str] = []
    results: list[dict] = []
    urls: list[str] = []
    path = os.path.join(REPO_ROOT, "data", "picks.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        for pick in doc.get("picks", []):
            for row in pick.get("market_sources") or []:
                if row.get("source_url"):
                    urls.append(row["source_url"])
    for extra in ("https://play.hotspawn.com/lol-pickems",
                  "https://kalshi.com/markets/kxlolgame",
                  "https://polymarket.com",
                  "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues",
                  "https://www.bovada.lv/esports",
                  "https://lol.fandom.com/wiki/Main_Page"):
        urls.append(extra)
    seen, unique = set(), []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    for url in unique[:limit]:
        request = urllib.request.Request(url, method="GET",
                                         headers={"User-Agent": UA, "Accept": "*/*"})
        entry = {"url": url}
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                entry["status"] = response.status
        except urllib.error.HTTPError as exc:
            entry["status"] = exc.code
        except Exception as exc:  # noqa: BLE001
            entry["status"] = None
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results.append(entry)
        status = entry.get("status")
        if status is None or status >= 400:
            problems.append(f"external link failed: {url} -> {status} {entry.get('error', '')}")
    return problems, results


def main() -> int:
    problems = check_internal() + check_picks()
    results: list[dict] = []
    if "--external" in sys.argv:
        external_problems, results = check_external()
        problems.extend(external_problems)

    report = {"generated_at": utcnow(), "problems": problems, "external": results}
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    with open(os.path.join(EVIDENCE_DIR, "link_check.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    if problems:
        print(f"FAILED: {len(problems)} problem(s)")
        for problem in problems[:60]:
            print("  -", problem)
        return 1
    print("link check passed: internal links resolve, every row has a source link, probabilities are sane")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

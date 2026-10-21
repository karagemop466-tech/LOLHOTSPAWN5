#!/usr/bin/env python3
"""Collect the HotSpawn League of Legends pick'em inventory.

HotSpawn is used ONLY to discover which matches exist, when they lock, what tier
and points they are worth, and the official permalink HotSpawn publishes for the
fixture. The crowd "X% picked" figures are deliberately NOT read into the output:
the project brief forbids using HotSpawn as a probability signal.

Sources (both are HotSpawn's own public surfaces):
  * https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1
  * https://play.hotspawn.com/lol-pickems   (Angular SSR - carries the permalink map)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import DATA_DIR, EVIDENCE_DIR, Http, epoch_ms_to_iso, utcnow, write_json  # noqa: E402

FIXTURES_API = ("https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures"
                "?sport_alias=lol&tenantId=1")
LOBBY_HTML = "https://play.hotspawn.com/lol-pickems"
PERMALINK_RE = re.compile(r'https://www\.hotspawn\.com/matches/[A-Za-z0-9\-]+')


def permalinks_from_lobby(html: str) -> dict[str, str]:
    """Read the ng-state permalink map out of the Angular SSR payload."""
    found: dict[str, str] = {}
    for match in re.finditer(r'"permalinks":\{(.*?)\}', html):
        for fid, url in re.findall(r'"(\d+)":"(https://www\.hotspawn\.com/matches/[^"]+)"',
                                   match.group(1)):
            found[fid] = url
    if not found:  # fallback: any permalink that embeds the fixture id
        for url in set(PERMALINK_RE.findall(html)):
            tail = url.rsplit("-", 1)[-1]
            if tail.isdigit():
                found[tail] = url
    return found


def main() -> int:
    http = Http(log_path=os.path.join(EVIDENCE_DIR, "source_health_hotspawn.json"), delay=0.3)

    fixtures, fx_meta = http.get_json(FIXTURES_API)
    if fixtures is None:
        previous = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "data", "hotspawn_matches.json")
        print("WARNING: could not read the HotSpawn fixtures API:", file=sys.stderr)
        print(json.dumps(fx_meta, indent=2), file=sys.stderr)
        if os.path.exists(previous):
            print("keeping the previous inventory (it will be published again)", file=sys.stderr)
            with open(previous, encoding="utf-8") as fh:
                old = json.load(fh)
            old.setdefault("sources", {})["fixtures_api"]["last_error"] = fx_meta
            old["stale"] = True
            write_json("data/hotspawn_matches.json", old)
            return 0
        print("FATAL: no previous inventory to fall back on", file=sys.stderr)
        return 2

    # The lobby HTML is CDN cached; a cache-buster query string forces a fresh render.
    lobby_html, lobby_meta = http.get(LOBBY_HTML + "?cb=" + str(int(utcnow_epoch())), timeout=90)
    permalinks = permalinks_from_lobby(lobby_html.decode("utf-8", "replace")) if lobby_html else {}

    matches = []
    for fx in fixtures:
        if fx.get("sport_alias") != "lol":
            continue
        fid = str(fx.get("id"))
        matches.append({
            "id": fid,
            "tournament": fx.get("competition_name"),
            "competition_id": fx.get("competition_id"),
            "tier": fx.get("tier"),
            "stage": fx.get("stage"),
            "status": fx.get("status"),
            "offered_points": fx.get("offered_points"),
            "base_points": fx.get("base_points"),
            "points_breakdown": fx.get("points_breakdown"),
            "best_of": fx.get("best_of"),
            "series_format": fx.get("series_format"),
            "lock_time": epoch_ms_to_iso(fx.get("lock_time")),
            "lock_time_ms": fx.get("lock_time"),
            "start_time": epoch_ms_to_iso(fx.get("scheduled_start_time")),
            "start_time_ms": fx.get("scheduled_start_time"),
            "teams": [
                {"id": fx.get("participants0_id"), "name": fx.get("participants0_name")},
                {"id": fx.get("participants1_id"), "name": fx.get("participants1_name")},
            ],
            "permalinks": permalinks.get(fid),
        })

    payload = {
        "generated_at": utcnow(),
        "sources": {
            "fixtures_api": {"url": FIXTURES_API, "meta": fx_meta},
            "lobby_html": {"url": LOBBY_HTML, "meta": lobby_meta,
                           "permalink_count": len(permalinks)},
        },
        "note": "HotSpawn is used for fixture identity, lock times, tiers and points only. "
                "Crowd pick percentages are not collected and are never used as a probability signal.",
        "counts": {
            "lol_fixtures_total": len(matches),
            "scheduled": sum(1 for m in matches if m["status"] == "scheduled"),
            "ended": sum(1 for m in matches if m["status"] == "ended"),
            "cancelled": sum(1 for m in matches if m["status"] == "cancelled"),
            "forfeited": sum(1 for m in matches if m["status"] == "forfeited"),
            "with_permalink": sum(1 for m in matches if m["permalinks"]),
        },
        "matches": matches,
    }
    path = write_json("data/hotspawn_matches.json", payload)
    print(f"wrote {path}: {len(matches)} LoL fixtures, "
          f"{payload['counts']['scheduled']} scheduled, {len(permalinks)} permalinks")
    return 0


def utcnow_epoch() -> int:
    import time
    return time.time()


if __name__ == "__main__":
    raise SystemExit(main())

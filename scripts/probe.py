#!/usr/bin/env python3
"""Capture raw payloads from every candidate source so the schema can be verified.

Run inside GitHub Actions (the runner has full internet). Writes one file per URL
under evidence/raw/ and a machine readable manifest at evidence/probe_manifest.json.

Nothing here is used as a probability signal on its own - the probe only records
what each source actually returns, so downstream code can be written against the
real schema instead of a guess.
"""
from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

OUT_DIR = os.path.join(os.path.dirname(__.path__), "evidence", "raw")
MAX_BYTES = 12 * 1024 * 1024
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# (name, url, headers) - headers is a dict of extra request headers
TARGETS: list[tuple[str, str, dict[str, str]]] = [
    # ---- HotSpawn (fixture inventory only, never a probability signal) -------
    ("hotspawn_fixtures_all",
     "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1", {}),
    ("hotspawn_fixtures_scheduled",
     "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&status=scheduled&tenantId=1", {}),
    ("hotspawn_lobby_lol",
     "https://play.hotspawn.com/lol-pickems", {}),
    ("hotspawn_lobby_root", "https://play.hotspawn.com/lobby", {}),
    ("hotspawn_competitions",
     "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/competitions?sport_alias=lol&tenantId=1", {}),
    ("hotspawn_teams",
     "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/teams?sport_alias=lol&tenantId=1", {}),

    # ---- Pinnacle (licensed bookmaker, public guest API) --------------------
    ("pinnacle_sports", "https://guest.api.arcadia.pinnacle.com/0.1/sports", {}),
    ("pinnacle_esports_leagues", "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues", {}),
    ("pinnacle_esports_matchups", "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups", {}),
    ("pinnacle_lol_worlds_matchups",
     "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues/9587/matchups", {}),
    ("pinnacle_lol_worlds_markets",
     "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues/9587/markets", {}),
    ("pinnacle_lol_emea_matchups",
     "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues/225201/matchups", {}),
    ("pinnacle_lol_emea_markets",
     "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues/225201/markets", {}),

    # ---- Bovada (licensed bookmaker) ---------------------------------------
    ("bovada_esports_events",
     "https://www.bovada.lv/services/sports/event/v2/events/A/description/esports", {}),

    # ---- Polymarket (prediction market) ------------------------------------
    ("polymarket_gamma_events",
     "https://gamma-api.polymarket.com/events?limit=200&closed=false", {}),
    ("polymarket_search_lol",
     "https://gamma-api.polymarket.com/public-search?q=league%20of%20legends&limit_per_type=20", {}),
    ("polymarket_series_lol",
     "https://gamma-api.polymarket.com/series?limit=100", {}),

    # ---- Kalshi (regulated prediction market) -------------------------------
    ("kalshi_series_esports",
     "https://api.elections.kalshi.com/trade-api/v2/series?category=Esports", {}),
    ("kalshi_markets_lol",
     "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXLOLGAME&limit=200", {}),

    # ---- Other esports books / lines ---------------------------------------
    ("matchbook_events", "https://api.matchbook.com/rest/events?status=open&limit=200", {}),
    ("matchbook_sports", "https://api.matchbook.com/rest/sports", {}),
    ("esportsbet_home", "https://www.esportsbet.com/", {}),
    ("betway_esports", "https://www.betway.com/api/sports/esports", {}),
    ("smarkets_events", "https://api.smarkets.com/v3/events?only_popular=true", {}),
    ("egamersworld_feed", "https://egamersworld.com/api/feed/", {}),
    ("lolepedia_api", "https://wiki.leaguepedia.com/api.php?action=query&meta=siteinfo&format=json", {}),

    # ---- Community / official LoL data -------------------------------------
    ("golgg_teams_list", "https://gol.gg/teams/list/", {}),
    ("golgg_tournament_list", "https://gol.gg/tournament/list/", {}),
    ("golgg_matchlist_lck", "https://gol.gg/tournament/tournamentmatchlist/LCK%20Season%202025/", {}),
    ("oracle_elixir_index", "https://oracleselixir.download/", {}),
    ("oracle_elixir_2026_csv",
     "https://oracleselixir.s3-us-west-2.amazonaws.com/2026_LoL_esports_match_data_from_OraclesElixir.csv", {}),
]


def fetch(name: str, url: str, extra_headers: dict[str, str]) -> dict:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    started = time.time()
    record: dict = {"name": name, "url": url, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            body = resp.read(MAX_BYTES)
            record.update({
                "status": resp.status,
                "content_type": resp.headers.get("Content-Type", ""),
                "bytes": len(body),
                "age": resp.headers.get("Age", ""),
                "x_cache": resp.headers.get("X-Cache", ""),
            })
            suffix = ".json" if "json" in record["content_type"].lower() else (
                ".csv" if "csv" in record["content_type"].lower() else ".html")
            path = os.path.join(OUT_DIR, name + suffix)
            with open(path, "wb") as fh:
                fh.write(body)
            record["file"] = os.path.relpath(path, os.path.dirname(os.path.dirname(OUT_DIR)))
            record["sample"] = body[:400].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(2000)
        record.update({"status": exc.code, "error": f"HTTPError {exc.code}",
                       "sample": body.decode("utf-8", "replace")[:400]})
    except Exception as exc:  # noqa: BLE001 - probe must never abort the run
        record.update({"status": None, "error": f"{type(exc).__name__}: {exc}"})
    record["elapsed_s"] = round(time.time() - started, 2)
    return record


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    records = []
    for name, url, hdrs in TARGETS:
        rec = fetch(name, url, hdrs)
        records.append(rec)
        print(f"{name:38s} status={rec.get('status')} bytes={rec.get('bytes', 0)} {rec.get('error', '')}")
        sys.stdout.flush()
        time.sleep(0.7)
    manifest = os.path.join(os.path.dirname(OUT_DIR), "probe_manifest.json")
    with open(manifest, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "targets": records},
                  fh, indent=2)
    print("wrote", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

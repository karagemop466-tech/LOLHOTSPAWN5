#!/usr/bin/env python3
"""Collect external League of Legends betting lines.

Four independent sources are read. Each quote records the exact URL it came from,
the retrieval time and whether the market is a *series* (match winner) or a *map*
(single game) price, because the two are not interchangeable.

  1. Kalshi      - CFTC-regulated prediction market, series KXLOLGAME (game scope)
  2. Polymarket  - prediction market, match-winner markets (series scope, BO in title)
  3. Pinnacle    - licensed bookmaker, public guest API (period 0 = series, period 1 = map)
  4. Bovada      - licensed bookmaker, public esports events feed (moneyline per period)

HotSpawn is NOT used here: crowd pick percentages are not a probability signal.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (DATA_DIR, EVIDENCE_DIR, Http, american_to_decimal, devig,  # noqa: E402
                    epoch_ms_to_iso, implied, utcnow, write_json)

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_SERIES = "KXLOLGAME"
POLY_GAMMA = "https://gamma-api.polymarket.com/events"
PINNACLE_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
BOVADA_EVENTS = "https://www.bovada.lv/services/sports/event/v2/events/A/description/esports"

BO_RE = re.compile(r"\(BO(\d)\)", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Kalshi
# --------------------------------------------------------------------------- #
def collect_kalshi(http: Http, quotes: list) -> dict:
    markets: list[dict] = []
    cursor = None
    pages = 0
    while pages < 12:
        url = f"{KALSHI_BASE}/markets?series_ticker={KALSHI_SERIES}&limit=1000"
        if cursor:
            url += f"&cursor={cursor}"
        data, meta = http.get_json(url)
        pages += 1
        if not data:
            break
        batch = data.get("markets", [])
        markets.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            break

    events: dict[str, dict] = {}
    cursor = None
    pages = 0
    while pages < 12:
        url = f"{KALSHI_BASE}/events?series_ticker={KALSHI_SERIES}&limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        data, meta = http.get_json(url)
        pages += 1
        if not data:
            break
        batch = data.get("events", [])
        for ev in batch:
            events[ev.get("event_ticker")] = ev
        cursor = data.get("cursor")
        if not cursor or not batch:
            break

    by_event: dict[str, list[dict]] = {}
    for market in markets:
        by_event.setdefault(market.get("event_ticker"), []).append(market)

    count = 0
    for ticker, event_markets in by_event.items():
        event = events.get(ticker, {})
        title = event.get("title") or ""
        parts = [p.strip() for p in re.split(r"\s+vs\.?\s+", title)] if title else []
        if len(parts) != 2:
            # fall back to the market titles ("<team> wins")
            names = [m.get("title", "")[:-5].strip() for m in event_markets
                     if (m.get("title") or "").endswith(" wins")]
            parts = names if len(names) == 2 else []
        if len(parts) != 2:
            continue

        team_a, team_b = parts[0], parts[1]
        price_a = mid_price(event_markets, team_a)
        price_b = mid_price(event_markets, team_b)
        if price_a is None or price_b is None:
            continue
        quotes.append({
            "source": "kalshi",
            "source_kind": "prediction market (CFTC-regulated)",
            "market_scope": "game",
            "source_url": f"{KALSHI_BASE}/events/{ticker}",
            "api_url": f"{KALSHI_BASE}/markets?series_ticker={KALSHI_SERIES}&limit=1000",
            "event_ticker": ticker,
            "event_title": title,
            "team_a": team_a,
            "team_b": team_b,
            "price_a": price_a,
            "price_b": price_b,
            "price_type": "probability",
            "start_time": event_markets[0].get("occurrence_datetime") or event_markets[0].get("open_time"),
            "retrieved_at": utcnow(),
            "raw": {
                "yes_bid": event_markets[0].get("yes_bid_dollars"),
                "yes_ask": event_markets[0].get("yes_ask_dollars"),
                "last": event_markets[0].get("last_price_dollars"),
                "volume": event_markets[0].get("volume_fp"),
                "close_time": event_markets[0].get("close_time"),
            },
        })
        count += 1
    return {"source": "kalshi", "api_url": f"{KALSHI_BASE}/markets?series_ticker={KALSHI_SERIES}",
            "events": len(events), "quotes": count}


def mid_price(event_markets: list[dict], team: str) -> float | None:
    """Mid of the yes bid/ask for "<team> wins"; falls back to last traded price."""
    wanted = norm(team)
    for market in event_markets:
        title = (market.get("title") or "")
        if not title.endswith(" wins"):
            continue
        name = norm(title[:-5].strip())
        if name != wanted:
            continue
        bid = to_float(market.get("yes_bid_dollars"))
        ask = to_float(market.get("yes_ask_dollars"))
        if bid is not None and ask is not None and ask >= bid:
            return round((bid + ask) / 2.0, 6)
        last = to_float(market.get("last_price_dollars"))
        if last is not None:
            return last
        return None
    return None


def to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


# --------------------------------------------------------------------------- #
# Polymarket
# --------------------------------------------------------------------------- #
def collect_polymarket(http: Http, quotes: list) -> dict:
    events: list[dict] = []
    offset = 0
    pages = 0
    while pages < 12:
        url = (f"{POLY_GAMMA}?tag_slug=league-of-legends&closed=false&limit=100&offset={offset}")
        data, meta = http.get_json(url)
        pages += 1
        if not data:
            break
        events.extend(data)
        if len(data) < 100:
            break
        offset += 100

    count = 0
    for event in events:
        markets = event.get("markets") or []
        for market in markets:
            question = market.get("question") or ""
            if not question.lower().startswith("lol:"):
                continue
            if not market.get("active") or market.get("closed"):
                continue
            outcomes = json.loads(market.get("outcomes") or "[]")
            prices = json.loads(market.get("outcomePrices") or "[]")
            if len(outcomes) != 2 or len(prices) != 2:
                continue
            # Polymarket quotes the match winner (series). The BO format is in the title.
            title = question.split(":", 1)[1].strip()
            bo_match = BO_RE.search(title)
            best_of = int(bo_match.group(1)) if bo_match else None
            team_a = outcomes[0].strip()
            team_b = outcomes[1].strip()
            p_a = to_float(prices[0])
            p_b = to_float(prices[1])
            if p_a is None or p_b is None:
                continue
            quotes.append({
                "source": "polymarket",
                "source_kind": "prediction market",
                "market_scope": "series",
                "best_of": best_of,
                "source_url": f"https://polymarket.com/event/{event.get('slug')}/{market.get('slug')}",
                "api_url": f"{POLY_GAMMA}?tag_slug=league-of-legends&closed=false",
                "event_title": title,
                "team_a": team_a,
                "team_b": team_b,
                "price_a": p_a,
                "price_b": p_b,
                "price_type": "probability",
                "start_time": market.get("gameStartTime") or market.get("startDate"),
                "retrieved_at": utcnow(),
                "raw": {
                    "best_bid": market.get("bestBid"),
                    "best_ask": market.get("bestAsk"),
                    "last_trade": market.get("lastTradePrice"),
                    "volume": market.get("volume"),
                    "liquidity": market.get("liquidity"),
                    "outcome_prices": prices,
                },
            })
            count += 1
    return {"source": "polymarket", "api_url": f"{POLY_GAMMA}?tag_slug=league-of-legends",
            "events": len(events), "quotes": count}


# --------------------------------------------------------------------------- #
# Pinnacle
# --------------------------------------------------------------------------- #
def collect_pinnacle(http: Http, quotes: list) -> dict:
    leagues, meta = http.get_json(f"{PINNACLE_BASE}/sports/12/leagues")
    if not leagues:
        return {"source": "pinnacle", "quotes": 0, "error": "league list unavailable"}
    lol_leagues = [lg for lg in leagues if str(lg.get("name", "")).startswith("League of Legends")]
    count = 0
    for league in lol_leagues:
        league_id = league.get("id")
        matchups, mmeta = http.get_json(f"{PINNACLE_BASE}/leagues/{league_id}/matchups")
        if not matchups:
            continue
        for matchup in matchups:
            if matchup.get("type") != "matchup":
                continue
            parts = matchup.get("participants") or []
            if len(parts) != 2:
                continue
            team_a, team_b = parts[0].get("name"), parts[1].get("name")
            markets_url = f"{PINNACLE_BASE}/matchups/{matchup.get('id')}/markets/related/straight"
            markets, kmeta = http.get_json(markets_url, retries=2)
            if not markets:
                continue
            for market in markets:
                if market.get("type") != "moneyline" or market.get("status") != "open":
                    continue
                period = market.get("period")
                scope = "series" if period == 0 else "game"
                prices = market.get("prices") or []
                if len(prices) != 2:
                    continue
                price_a = next((p.get("price") for p in prices if p.get("designation") == "home"), None)
                price_b = next((p.get("price") for p in prices if p.get("designation") == "away"), None)
                if price_a is None or price_b is None:
                    continue
                dec_a = american_to_decimal(float(price_a))
                dec_b = american_to_decimal(float(price_b))
                if not dec_a or not dec_b:
                    continue
                quotes.append({
                    "source": "pinnacle",
                    "source_kind": "licensed bookmaker",
                    "market_scope": scope,
                    "source_url": markets_url,
                    "api_url": markets_url,
                    "league": league.get("name"),
                    "team_a": team_a,
                    "team_b": team_b,
                    "decimal_a": dec_a,
                    "decimal_b": dec_b,
                    "price_a": implied(dec_a),
                    "price_b": implied(dec_b),
                    "price_type": "decimal_odds",
                    "start_time": matchup.get("startTime"),
                    "retrieved_at": utcnow(),
                    "raw": {"american": [price_a, price_b], "period": period,
                            "key": market.get("key"), "cutoff": market.get("cutoffAt")},
                })
                count += 1
    return {"source": "pinnacle", "api_url": f"{PINNACLE_BASE}/sports/12/leagues",
            "leagues": [lg.get("name") for lg in lol_leagues], "quotes": count}


# --------------------------------------------------------------------------- #
# Bovada
# --------------------------------------------------------------------------- #
def collect_bovada(http: Http, quotes: list) -> dict:
    payload, meta = http.get_json(BOVADA_EVENTS)
    if not payload:
        return {"source": "bovada", "quotes": 0, "error": "events feed unavailable"}
    count = 0
    for block in payload:
        path = block.get("path") or []
        is_lol = any("league-of-legends" in str(p.get("link", "")) for p in path)
        for event in block.get("events", []):
            if not is_lol:
                continue
            competitors = event.get("competitors") or []
            if len(competitors) != 2:
                continue
            team_a = competitors[0].get("name")
            team_b = competitors[1].get("name")
            event_url = "https://www.bovada.lv" + str(event.get("link", ""))
            for group in event.get("displayGroups", []):
                for market in group.get("markets", []):
                    if market.get("descriptionKey") != "Head To Head":
                        continue
                    outcomes = market.get("outcomes") or []
                    if len(outcomes) != 2:
                        continue
                    prices = []
                    for outcome in outcomes:
                        price = (outcome.get("price") or {}).get("decimal")
                        value = to_float(price)
                        prices.append(value)
                    if any(p is None for p in prices):
                        continue
                    period = (market.get("period") or {}).get("description")
                    scope = "series" if str(period).lower() in ("series", "match", "match winner") else "game"
                    quotes.append({
                        "source": "bovada",
                        "source_kind": "licensed bookmaker",
                        "market_scope": scope,
                        "market_period": period,
                        "source_url": event_url,
                        "api_url": BOVADA_EVENTS,
                        "team_a": team_a,
                        "team_b": team_b,
                        "decimal_a": prices[0],
                        "decimal_b": prices[1],
                        "price_a": implied(prices[0]),
                        "price_b": implied(prices[1]),
                        "price_type": "decimal_odds",
                        "start_time": epoch_ms_to_iso(event.get("startTime")),
                        "retrieved_at": utcnow(),
                        "raw": {"american": [(o.get("price") or {}).get("american") for o in outcomes],
                                "description": market.get("description"),
                                "status": market.get("status")},
                    })
                    count += 1
    return {"source": "bovada", "api_url": BOVADA_EVENTS, "quotes": count}


def main() -> int:
    http = Http(log_path=os.path.join(EVIDENCE_DIR, "source_health_odds.json"), delay=0.25)
    quotes: list[dict] = []
    summary = {}
    for name, fn in (("kalshi", collect_kalshi), ("polymarket", collect_polymarket),
                     ("pinnacle", collect_pinnacle), ("bovada", collect_bovada)):
        try:
            summary[name] = fn(http, quotes)
        except Exception as exc:  # noqa: BLE001 - one dead source must not kill the run
            summary[name] = {"source": name, "quotes": 0, "error": f"{type(exc).__name__}: {exc}"}
        print(f"{name}: {summary[name]}")

    # de-vig so every quote carries comparable probabilities
    for quote in quotes:
        pa, pb = quote.get("price_a"), quote.get("price_b")
        if pa and pb:
            dv_a, dv_b = devig(pa, pb)
            quote["prob_a"] = round(dv_a, 6)
            quote["prob_b"] = round(dv_b, 6)
            quote["overround"] = round(pa + pb, 6)

    payload = {
        "generated_at": utcnow(),
        "note": "External League of Legends lines only. HotSpawn crowd percentages are never used.",
        "sources": summary,
        "quotes": quotes,
    }
    path = write_json("data/odds.json", payload)
    print(f"wrote {path}: {len(quotes)} quotes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

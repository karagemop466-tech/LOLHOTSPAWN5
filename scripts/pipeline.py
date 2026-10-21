#!/usr/bin/env python3
"""Hotspawn LoL pick'em pipeline.

Collects the full Hotspawn LoL pick'em fixture inventory, joins independent
market prices (Kalshi exchange, Pinnacle bookmaker, Polymarket prediction
market) and computes our own win probabilities for every fixture.

Design rules (see METHODOLOGY.md):
  * Hotspawn's crowd "picked %" is NEVER used as a probability signal.
  * No value is inferred. If a match has neither a market quote nor enough
    independent form data, it is published as UNRESOLVED with the reason.
  * Every market figure keeps its source URL, book/exchange, and retrieval time.

Outputs: data/fixtures.json, data/markets.json, data/picks.json, data/meta.json
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = ROOT / "research" / "live"

UA = "ArenaResearchBot/1.0 (+https://github.com/karagemop466-tech/LOLHOTSPAWN5)"
HOTSPAWN_API = "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1"
HOTSPAWN_PAGE = "https://play.hotspawn.com/lol-pickems"
HOTSPAWN_MATCH = "https://www.hotspawn.com/matches/"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_GAME_SERIES = "KXLOLGAME"
PINNACLE = "https://guest.api.arcadia.pinnacle.com/0.1"
POLYMARKET = "https://gamma-api.polymarket.com"

NOW = datetime.now(timezone.utc)
STALE_AFTER = timedelta(hours=6)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def http_get(url: str, timeout: int = 45, tries: int = 3) -> tuple[int, bytes, str]:
    last = ""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), ""
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read()
            except Exception:  # noqa: BLE001
                pass
            if e.code in (429, 503) and attempt < tries - 1:
                time.sleep(5 * (attempt + 1))
                last = f"HTTP {e.code}"
                continue
            return e.code, body, f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
            if attempt < tries - 1:
                time.sleep(3 * (attempt + 1))
    return 0, b"", last


def http_json(url: str, **kw):
    for _ in range(kw.get("tries", 3)):
        status, body, err = http_get(url, **kw)
        if status == 200 and body:
            try:
                return json.loads(body), None
            except json.JSONDecodeError as e:
                return None, f"JSON error: {e}"
        if status not in (0, 429, 500, 502, 503, 504):
            return None, err or f"HTTP {status}"
        time.sleep(4)
    return None, err or "unavailable"


# --------------------------------------------------------------------------- #
# Normalisation helpers
# --------------------------------------------------------------------------- #
TRANSLIT = {
    "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "å": "a", "Å": "A", "œ": "oe",
    "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "þ": "th", "ß": "ss",
    "ı": "i", "ș": "s", "ț": "t", "ş": "s", "ğ": "g", "ç": "c", "ñ": "n",
}


def norm(name: str) -> str:
    if not name:
        return ""
    for a, b in TRANSLIT.items():
        name = name.replace(a, b)
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\b(esports?|e-sports?|gaming|gg|club|team)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


ALIASES = {
    # verified aliases only (market name -> Hotspawn name); seeded from the
    # join report after human review, never guessed.
    "movistar koi": "Movistar KOI",
    "koi": "Movistar KOI",
    "los": "LOS",
    "los ninos": "LOS NINOS",
    "hanwha life esports": "Hanwha Life Esports",
    "hle": "Hanwha Life Esports",
    "bilibili gaming": "Bilibili Gaming",
    "blg": "Bilibili Gaming",
    "anyones legend": "Anyone's Legend",
    "anyone s legend": "Anyone's Legend",
    "top esports": "Top Esports",
    "tes": "Top Esports",
    "ctbc flying oyster": "CTBC Flying Oyster",
    "cfo": "CTBC Flying Oyster",
    "team secret whales": "Team Secret Whales",
    "tsw": "Team Secret Whales",
    "karmine corp": "Karmine Corp",
    "kc": "Karmine Corp",
    "gen g": "Gen.G",
    "geng": "Gen.G",
    "t1": "T1",
    "dplus kia": "Dplus KIA",
    "dk": "Dplus KIA",
    "invictus gaming": "Invictus Gaming",
    "ig": "Invictus Gaming",
    "g2 esports": "G2 Esports",
    "g2": "G2 Esports",
    "movistar koi fenix": "Movistar KOI Fénix",
    "team liquid": "Team Liquid",
    "tl": "Team Liquid",
    "lyon": "LYON",
    "flyquest": "FlyQuest",
    "furia": "FURIA",
    "cloud9": "Cloud9",
    "c9": "Cloud9",
}


def team_key(name: str) -> str:
    return norm(name)


# --------------------------------------------------------------------------- #
# Collect: Hotspawn
# --------------------------------------------------------------------------- #
def ms_to_dt(ms) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def collect_hotspawn() -> dict:
    data, err = http_json(HOTSPAWN_API, tries=4)
    if not isinstance(data, list):
        return {"ok": False, "error": err or "unexpected payload", "fixtures": []}
    (RAW).mkdir(parents=True, exist_ok=True)
    (RAW / "hotspawn_fixtures.json").write_text(json.dumps(data), encoding="utf-8")
    fixtures = []
    for f in data:
        if f.get("sport_alias") != "lol":
            continue
        start = ms_to_dt(f.get("scheduled_start_time"))
        fixtures.append(
            {
                "id": str(f.get("id")),
                "competition": (f.get("competition_name") or "").strip(),
                "competition_id": str(f.get("competition_id") or ""),
                "status": f.get("status"),
                "start_utc": start.isoformat().replace("+00:00", "Z") if start else None,
                "start_ts": int(start.timestamp()) if start else None,
                "tier": f.get("tier") or "waiting for information",
                "stage": f.get("stage") or "",
                "best_of": f.get("best_of"),
                "points": f.get("offered_points"),
                "team_a": (f.get("participants0_name") or "").strip(),
                "team_b": (f.get("participants1_name") or "").strip(),
                "team_a_id": str(f.get("participants0_id") or ""),
                "team_b_id": str(f.get("participants1_id") or ""),
                "score_a": f.get("participants0_score"),
                "score_b": f.get("participants1_score"),
                # crowd percentage is captured for transparency only; it is
                # never an input to any probability in this pipeline.
                "crowd_pct_a": f.get("participants0_picked_percent"),
                "crowd_pct_b": f.get("participants1_picked_percent"),
                "hotspawn_url": (
                    HOTSPAWN_MATCH + f.get("competition_name", "").lower()
                    if False
                    else f"{HOTSPAWN_MATCH}"
                ),
            }
        )
    # match permalinks are not exposed by the fixtures API; we link the lobby.
    for fx in fixtures:
        fx["hotspawn_url"] = HOTSPAWN_PAGE
    return {"ok": True, "count": len(fixtures), "fixtures": fixtures, "error": None}


def collect_hotspawn_links() -> dict:
    """Verified per-match permalinks from the server-rendered LoL lobby.

    The fixtures API does not expose permalinks; the lobby HTML does. We only
    attach a link when the team pair matches exactly (after normalisation).
    """
    status, body, err = http_get(HOTSPAWN_PAGE)
    if status != 200 or not body:
        return {"ok": False, "error": err or f"HTTP {status}", "links": {}}
    html = body.decode("utf-8", "replace")
    (RAW).mkdir(parents=True, exist_ok=True)
    (RAW / "hotspawn_lol_page.html").write_text(html, encoding="utf-8")
    links = {}
    for seg in re.split(r'<div[^>]*class="vs-card vs-card--static"', html)[1:]:
        href = re.search(r'href="(https://www\.hotspawn\.com/matches/[^"]+)"', seg)
        names = re.findall(r'class="vs-card-team-name"[^>]*>\s*([^<]+?)\s*<', seg)
        if not href or len(names) != 2:
            continue
        key = tuple(sorted((norm(names[0]), norm(names[1]))))
        links[key] = href.group(1)
    return {"ok": True, "error": None, "links": links, "cards": len(links)}


# --------------------------------------------------------------------------- #
# Collect: Kalshi (regulated US exchange, binary event contracts)
# --------------------------------------------------------------------------- #
def american_to_decimal(p: float) -> float | None:
    try:
        p = float(p)
    except Exception:  # noqa: BLE001
        return None
    if p == 0:
        return None
    if p > 0:
        return round(1 + p / 100, 4) if p > 100 else round(p, 4)
    return round(1 + 100 / abs(p), 4) if abs(p) > 100 else round(p, 4)


def parse_kalshi_dt(ticker: str) -> datetime | None:
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})", ticker or "")
    if not m:
        return None
    months = {m_: i for i, m_ in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
    yy, mon, dd, hh, mm = m.groups()
    try:
        return datetime(2000 + int(yy), months[mon], int(dd), int(hh), int(mm), tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def collect_kalshi() -> dict:
    markets = []
    cursor = ""
    for _ in range(8):
        url = f"{KALSHI}/markets?series_ticker={KALSHI_GAME_SERIES}&status=open&limit=1000"
        if cursor:
            url += f"&cursor={cursor}"
        data, err = http_json(url)
        if not isinstance(data, dict) or "markets" not in data:
            return {"ok": False, "error": err or "unexpected payload", "quotes": []}
        markets.extend(data["markets"])
        cursor = data.get("cursor") or ""
        if not cursor:
            break
    (RAW).mkdir(parents=True, exist_ok=True)
    (RAW / "kalshi_markets.json").write_text(json.dumps(markets), encoding="utf-8")

    events: dict[str, dict] = {}
    for m in markets:
        ev = m.get("event_ticker") or ""
        row = {
            "team": (m.get("yes_sub_title") or "").replace(" wins", "").strip(),
            "price": m.get("last_price_dollars") or m.get("last_price"),
            "bid": m.get("yes_bid_dollars"),
            "ask": m.get("yes_ask_dollars"),
            "volume": m.get("volume") or m.get("volume_24h"),
            "status": m.get("status"),
        }
        if not row["team"]:
            continue
        events.setdefault(ev, {"ticker": ev, "start": parse_kalshi_dt(ev), "rows": []})["rows"].append(row)

    quotes = []
    for ev, e in events.items():
        if len(e["rows"]) != 2 or not e["start"]:
            continue  # only two-outcome match markets are usable
        prices = []
        for r in e["rows"]:
            bid, ask, last = to_float(r["bid"]), to_float(r["ask"]), to_float(r["price"])
            if bid is not None and ask is not None and ask > 0 and 0 < bid < 1 and ask <= 1:
                prices.append((bid + ask) / 2)
            elif last is not None:
                prices.append(last)
            else:
                prices.append(None)
        if None in prices:
            continue
        total = sum(prices)
        if total <= 0:
            continue
        quotes.append(
            {
                "source": "kalshi",
                "source_label": "Kalshi (CFTC-regulated exchange)",
                "event": ev,
                "start_utc": e["start"].isoformat().replace("+00:00", "Z"),
                "teams": [e["rows"][0]["team"], e["rows"][1]["team"]],
                "probs": [p / total for p in prices],
                "url": (f"{KALSHI}/markets?series_ticker={KALSHI_GAME_SERIES}"
                        f"&status=open&event_ticker={ev}"),
                "page_url": "https://kalshi.com/markets/kxlolgame",
                "retrieved_utc": NOW.isoformat().replace("+00:00", "Z"),
            }
        )
    return {"ok": True, "error": None, "quotes": quotes}


def to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Collect: Pinnacle (licensed bookmaker, sharp benchmark)
# --------------------------------------------------------------------------- #
def collect_pinnacle() -> dict:
    leagues, err = http_json(f"{PINNACLE}/sports/12/leagues")
    if not isinstance(leagues, list):
        return {"ok": False, "error": err or "leagues unavailable", "quotes": []}
    lol_leagues = [l for l in leagues if "league of legends" in (l.get("name") or "").lower()]
    matchups, err = http_json(f"{PINNACLE}/sports/12/matchups")
    if not isinstance(matchups, list):
        return {"ok": False, "error": err or "matchups unavailable", "quotes": []}
    (RAW).mkdir(parents=True, exist_ok=True)
    (RAW / "pinnacle_lol_matchups.json").write_text(
        json.dumps([m for m in matchups if (m.get("league") or {}).get("name", "").lower().startswith("league of legends")]),
        encoding="utf-8",
    )
    q = []
    for lg in lol_leagues:
        for m in matchups:
            if (m.get("league") or {}).get("id") != lg.get("id"):
                continue
            parent = m.get("parent") or {}
            parts = parent.get("participants") or []
            if len(parts) != 2:
                continue
            mkts, e2 = http_json(f"{PINNACLE}/matchups/{m.get('id')}/markets/related/straight")
            if not isinstance(mkts, list):
                continue
            ml = next((x for x in mkts if (x.get("type") == "moneyline" and x.get("period") == 0)), None)
            if not ml:
                continue
            prices = {p.get("designation"): to_float(p.get("price")) for p in ml.get("prices", [])}
            if "home" not in prices or "away" not in prices:
                continue
            dec = [american_to_decimal(prices["home"]), american_to_decimal(prices["away"])]
            if None in dec or min(dec) <= 1.0:
                continue
            raw = [1 / d for d in dec]
            total = sum(raw)
            start = parent.get("startTime")
            q.append(
                {
                    "source": "pinnacle",
                    "source_label": "Pinnacle (licensed bookmaker)",
                    "event": str(m.get("id")),
                    "start_utc": start,
                    "teams": [parts[0].get("name"), parts[1].get("name")],
                    "decimal": dec,
                    "probs": [r / total for r in raw],
                    "url": f"{PINNACLE}/matchups/{m.get('id')}/markets/related/straight",
                    "page_url": "https://www.pinnacle.com/en/esports/",
                    "retrieved_utc": NOW.isoformat().replace("+00:00", "Z"),
                }
            )
            time.sleep(0.2)
    return {"ok": True, "error": None, "quotes": q, "leagues": [l.get("name") for l in lol_leagues]}


# --------------------------------------------------------------------------- #
# Collect: Polymarket (prediction market)
# --------------------------------------------------------------------------- #
def collect_polymarket() -> dict:
    quotes = []
    seen = set()
    for tag in ("league-of-legends", "lol"):
        data, err = http_json(
            f"{POLYMARKET}/events?tag_slug={tag}&closed=false&limit=100&order=startDate&ascending=false"
        )
        if not isinstance(data, list):
            continue
        for ev in data:
            title = ev.get("title") or ""
            if not re.match(r"^LoL:\s", title):
                continue
            start = ev.get("startDate")
            if not start or ev.get("closed"):
                continue
            dt = None
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                pass
            if not dt or dt < NOW - timedelta(hours=12):
                continue
            mw = None
            for m in ev.get("markets", []):
                if (m.get("groupItemTitle") or "").lower() in ("match winner", "winner"):
                    mw = m
                    break
            if not mw or mw.get("closed"):
                continue
            try:
                outcomes = json.loads(mw.get("outcomes") or "[]")
                prices = [float(x) for x in json.loads(mw.get("outcomePrices") or "[]")]
            except Exception:  # noqa: BLE001
                continue
            if len(outcomes) != 2 or len(prices) != 2 or sum(prices) <= 0:
                continue
            if any(p <= 0.001 or p >= 0.999 for p in prices) and False:
                continue
            key = (outcomes[0], outcomes[1], start)
            if key in seen:
                continue
            seen.add(key)
            total = sum(prices)
            quotes.append(
                {
                    "source": "polymarket",
                    "source_label": "Polymarket (prediction market)",
                    "event": ev.get("slug") or ev.get("id"),
                    "start_utc": dt.isoformat().replace("+00:00", "Z"),
                    "teams": outcomes,
                    "probs": [p / total for p in prices],
                    "volume_usd": to_float(mw.get("volume")),
                    "url": f"https://polymarket.com/event/{ev.get('slug')}",
                    "retrieved_utc": NOW.isoformat().replace("+00:00", "Z"),
                }
            )
    (RAW).mkdir(parents=True, exist_ok=True)
    (RAW / "polymarket_quotes.json").write_text(json.dumps(quotes), encoding="utf-8")
    return {"ok": True, "error": None, "quotes": quotes}


# --------------------------------------------------------------------------- #
# Collect: Leaguepedia (independent results reference)
# --------------------------------------------------------------------------- #
LEAGUEPEDIA_EXPORT = "https://lol.fandom.com/wiki/Special:CargoExport"


def collect_leaguepedia(max_pages: int = 40, page_size: int = 500) -> dict:
    """Bulk completed-match history via CargoExport (the REST API is rate-limited)."""
    rows: list[dict] = []
    warning = None
    fields = "OverviewPage,Team1,Team2,Winner,DateTime_UTC,BestOf"
    for page in range(max_pages):
        url = (
            f"{LEAGUEPEDIA_EXPORT}?tables=MatchSchedule&fields={fields}"
            f"&where=DateTime_UTC%20%3E%3D%20%222024-10-01%22"
            f"&order_by=DateTime_UTC%20DESC&limit={page_size}&offset={page * page_size}&format=json"
        )
        status, body, err = http_get(url, timeout=90)
        if status != 200 or not body:
            warning = err or f"HTTP {status}"
            break
        try:
            chunk = json.loads(body.decode("utf-8", "replace").lstrip("\ufeff"))
        except json.JSONDecodeError as e:
            warning = f"json: {e}"
            break
        if not isinstance(chunk, list) or not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < page_size:
            break
        time.sleep(0.7)
    (RAW).mkdir(parents=True, exist_ok=True)
    (RAW / "leaguepedia_matches.json").write_text(json.dumps(rows), encoding="utf-8")
    parsed = []
    for r in rows:
        t1 = str(r.get("Team1") or "").strip()
        t2 = str(r.get("Team2") or "").strip()
        if not t1 or not t2 or t1.isdigit() or t2.isdigit() or "TBD" in (t1 + t2):
            continue
        w = r.get("Winner")
        try:
            w = int(w)
        except Exception:  # noqa: BLE001
            continue
        if w not in (1, 2):
            continue
        raw_dt = r.get("DateTime UTC") or r.get("DateTime_UTC")
        if not raw_dt:
            continue
        try:
            dt = datetime.strptime(raw_dt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            continue
        parsed.append(
            {"team_a": t1, "team_b": t2, "score_a": 1 if w == 1 else 0,
             "score_b": 1 if w == 2 else 0, "start_ts": int(dt.timestamp()),
             "tier": None, "best_of": r.get("BestOf"), "tournament": r.get("OverviewPage") or ""}
        )
    return {"ok": bool(parsed) or warning is None, "error": warning,
            "matches": parsed, "rows": len(rows)}


# --------------------------------------------------------------------------- #
# Model: Elo from completed fixtures
# --------------------------------------------------------------------------- #
def compute_elo(fixtures: list[dict], status_filter: str | None = "ended") -> dict:
    """Elo over completed matches (scores only).

    Weighting: recency decay (half-life 180 days) x tier weight.
    Crowd pick percentages are never read here.
    """
    hist = [
        f for f in fixtures
        if (status_filter is None or f.get("status") == status_filter)
        and isinstance(f.get("score_a"), (int, float))
        and isinstance(f.get("score_b"), (int, float))
        and f.get("start_ts")
    ]
    hist.sort(key=lambda x: x["start_ts"])
    rating = defaultdict(lambda: 1500.0)
    games = Counter()
    last_seen: dict[str, datetime] = {}
    tier_k = {"s": 32, "a": 28, "b": 24, "c": 20, "d": 16, "waiting for information": 16, None: 16}
    for f in hist:
        a, b = f["team_a"], f["team_b"]
        if not a or not b:
            continue
        sa, sb = f["score_a"], f["score_b"]
        if sa == sb:
            score = 0.5
        else:
            score = 1.0 if sa > sb else 0.0
        ra, rb = rating[a], rating[b]
        exp_a = 1 / (1 + 10 ** ((rb - ra) / 400))
        dt = datetime.fromtimestamp(f["start_ts"], timezone.utc)
        age_days = max(0.0, (NOW - dt).days)
        recency = 0.5 ** (age_days / 180.0)
        k = tier_k.get(f.get("tier"), 20) * recency
        rating[a] = ra + k * (score - exp_a)
        rating[b] = rb + k * ((1 - score) - (1 - exp_a))
        games[a] += 1
        games[b] += 1
        last_seen[a] = dt
        last_seen[b] = dt
    return {
        "ratings": dict(rating),
        "games": dict(games),
        "last_seen": {k: v.isoformat() for k, v in last_seen.items()},
        "history_matches": len(hist),
    }


def elo_probability(ra: float, rb: float) -> float:
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def series_probability(p_game: float, best_of: int | None) -> float:
    """Convert a single-game win probability to a series probability."""
    if not best_of or best_of < 2:
        return p_game
    m = (best_of - 1) // 2
    p = 0.0
    for k in range(m + 1):
        p += math.comb(m + k, k) * (p_game ** (m + 1)) * ((1 - p_game) ** k)
    return p


# --------------------------------------------------------------------------- #
# Verification: cross-check Hotspawn results against Leaguepedia
# --------------------------------------------------------------------------- #
def crosscheck_results(hs_fixtures: list[dict], lp_matches: list[dict]) -> dict:
    """Compare winners for the same fixture across the two feeds.

    Only unambiguous pairs are counted: exactly one Leaguepedia match with the
    same two teams within +/- 8 hours. Series rematches and same-day double
    fixtures are skipped rather than guessed.
    """
    idx = defaultdict(list)
    for m in lp_matches:
        idx[frozenset((norm(m["team_a"]), norm(m["team_b"])))].append(m)
    checked = agree = skipped = 0
    disagreements = []
    for f in hs_fixtures:
        if f.get("status") != "ended" or not isinstance(f.get("score_a"), (int, float)):
            continue
        cands = [m for m in idx.get(frozenset((norm(f["team_a"]), norm(f["team_b"]))), [])
                 if abs(m["start_ts"] - f["start_ts"]) <= 8 * 3600]
        if len(cands) != 1:
            if cands:
                skipped += 1
            continue
        m = cands[0]
        hs_win = f["team_a"] if f["score_a"] > f["score_b"] else f["team_b"]
        lp_win = m["team_a"] if m["score_a"] > m["score_b"] else m["team_b"]
        checked += 1
        if norm(hs_win) == norm(lp_win):
            agree += 1
        else:
            disagreements.append(
                {"fixture": f"{f['team_a']} vs {f['team_b']}", "start_utc": f["start_utc"],
                 "hotspawn_winner": hs_win, "leaguepedia_winner": lp_win}
            )
    return {"checked": checked, "agree": agree, "skipped_ambiguous": skipped,
            "disagreements": disagreements[:25]}


# --------------------------------------------------------------------------- #
# Join
# --------------------------------------------------------------------------- #
def quote_probability_for(q: dict, a: str, b: str) -> float | None:
    qa, qb = q["teams"]
    if norm(qa) == norm(a) and norm(qb) == norm(b):
        return q["probs"][0]
    if norm(qb) == norm(a) and norm(qa) == norm(b):
        return q["probs"][1]
    return None


def join_markets(fixtures: list[dict], quotes: list[dict]) -> tuple[dict, list]:
    """Attach market quotes. Requires exact normalised team names + time window."""
    by_fixture: dict[str, list] = defaultdict(list)
    used = set()
    unmatched = []
    for f in fixtures:
        if not f["team_a"] or not f["team_b"]:
            continue
        fdt = datetime.fromisoformat(f["start_utc"].replace("Z", "+00:00")) if f["start_utc"] else None
        for i, q in enumerate(quotes):
            if i in used:
                continue
            p = quote_probability_for(q, f["team_a"], f["team_b"])
            if p is None:
                continue
            qdt = None
            try:
                qdt = datetime.fromisoformat((q.get("start_utc") or "").replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                pass
            if fdt and qdt and abs((fdt - qdt).total_seconds()) > 36 * 3600:
                continue
            by_fixture[f["id"]].append({**q, "prob_a": p})
            used.add(i)
    for i, q in enumerate(quotes):
        if i not in used:
            unmatched.append(q)
    return by_fixture, unmatched


# --------------------------------------------------------------------------- #
# Build picks
# --------------------------------------------------------------------------- #
CONF_ORDER = {"high": 3, "medium": 2, "low": 1, "none": 0}


def shrink(rating: float, games: int) -> float:
    """Bayesian-style shrinkage so thin samples do not imply false precision."""
    return 1500 + (rating - 1500) * (games / (games + 8.0))


def build_picks(fixtures: list[dict], quotes: list[dict], elo: dict, links: dict | None = None,
                elo_lp: dict | None = None) -> dict:
    links = links or {}
    scheduled = [f for f in fixtures if f["status"] == "scheduled"]
    market_map, unmatched = join_markets(scheduled, quotes)
    rows = []
    for f in scheduled:
        start = datetime.fromisoformat(f["start_utc"].replace("Z", "+00:00")) if f["start_utc"] else None
        key = tuple(sorted((norm(f["team_a"]), norm(f["team_b"]))))
        row = {
            **{k: f[k] for k in (
                "id", "competition", "tier", "stage", "best_of", "points", "team_a", "team_b",
                "start_utc", "hotspawn_url", "crowd_pct_a", "crowd_pct_b",
            )},
            "hotspawn_url": links.get(key, HOTSPAWN_PAGE),
            "hotspawn_link_verified": key in links,
        }
        if not f["team_a"] or not f["team_b"] or "tbd" in (f["team_a"] + f["team_b"]).lower():
            row.update(status="unresolved", reason="Teams not announced (Hotspawn lists TBD).",
                       remedy="Re-check after Hotspawn publishes both participants.")
            rows.append(row)
            continue
        if start and start < NOW - STALE_AFTER:
            row.update(
                status="unresolved",
                reason=("Hotspawn still marks this fixture 'scheduled' but its start time has already passed; "
                        "it is excluded rather than guessed."),
                remedy="Wait for Hotspawn to publish the result and the next round of fixtures.",
            )
            rows.append(row)
            continue

        mk = market_map.get(f["id"], [])
        p_market = None
        if mk:
            w = {"pinnacle": 0.5, "kalshi": 0.4, "polymarket": 0.3}
            num = sum(q["prob_a"] * w.get(q["source"], 0.2) for q in mk)
            den = sum(w.get(q["source"], 0.2) for q in mk)
            p_market = num / den

        # choose the strongest available rating pool: Leaguepedia first
        # (independent of Hotspawn), Hotspawn results as fallback.
        pools = []
        if elo_lp:
            pools.append(("leaguepedia", elo_lp))
        pools.append(("hotspawn", elo))
        rating_source = None
        ra = rb = None
        games_a = games_b = 0
        p_model = None
        for label, pool in pools:
            ga = pool["games"].get(f["team_a"], 0)
            gb = pool["games"].get(f["team_b"], 0)
            if ga >= 3 and gb >= 3 and f["team_a"] in pool["ratings"] and f["team_b"] in pool["ratings"]:
                ra, rb = pool["ratings"][f["team_a"]], pool["ratings"][f["team_b"]]
                games_a, games_b = ga, gb
                rating_source = label
                p_model = series_probability(
                    elo_probability(shrink(ra, games_a), shrink(rb, games_b)), f.get("best_of")
                )
                break
        if p_model is None:
            games_a = elo["games"].get(f["team_a"], 0)
            games_b = elo["games"].get(f["team_b"], 0)

        if p_market is not None and p_model is not None:
            p, conf, basis = 0.75 * p_market + 0.25 * p_model, "high", "market+model"
        elif p_market is not None:
            p, conf, basis = p_market, "high", "market"
        elif p_model is not None:
            p = p_model
            conf = "medium" if min(games_a, games_b) >= 8 else "low"
            basis = "model"
        else:
            thin = [t for t, g in ((f["team_a"], games_a), (f["team_b"], games_b)) if 0 < g < 3]
            none = [t for t, g in ((f["team_a"], games_a), (f["team_b"], games_b)) if g == 0]
            bits = []
            if none:
                bits.append("no completed fixtures in the reference set for " + ", ".join(none))
            if thin:
                bits.append("fewer than 3 completed fixtures for " + ", ".join(thin))
            row.update(
                status="unresolved",
                reason=("No bookmaker, exchange or prediction-market line covers this match"
                        + ("; " + "; ".join(bits) + "." if bits else ".")),
                remedy=("Needs an external market line or at least 3 verified completed fixtures per team "
                        "before a probability can be defended."),
            )
            rows.append(row)
            continue

        p = min(max(p, 0.02), 0.98)
        pick_team = f["team_a"] if p >= 0.5 else f["team_b"]
        notes = []
        if basis == "market":
            notes.append(
                "No usable form sample for both teams; the line is the de-vigged market price only."
            )
        if basis == "model" and min(games_a, games_b) < 8:
            notes.append(f"Thin form sample ({games_a} / {games_b} completed fixtures in the reference set).")
        row.update(
            status="picked",
            basis=basis,
            confidence=conf,
            prob_a=round(p, 4),
            prob_b=round(1 - p, 4),
            pick=pick_team,
            pick_prob=round(max(p, 1 - p), 4),
            fair_decimal_a=round(1 / p, 2),
            fair_decimal_b=round(1 / (1 - p), 2),
            market_sources=[
                {"source": q["source"], "label": q["source_label"], "url": q["url"],
                 "prob_a": round(q["prob_a"], 4), "retrieved_utc": q["retrieved_utc"]}
                for q in mk
            ],
            model=({"source": rating_source, "prob_a": round(p_model, 4), "elo_a": round(ra),
                    "elo_b": round(rb), "games_a": games_a, "games_b": games_b}
                   if p_model is not None else None),
            notes=notes,
        )
        rows.append(row)

    rows.sort(key=lambda r: (r.get("start_utc") or "", r["competition"], r["team_a"]))
    stale = [r for r in rows if r["status"] == "unresolved" and "start time has already passed" in (r.get("reason") or "")]
    picked = [r for r in rows if r["status"] == "picked"]
    upcoming_unresolved = [r for r in rows if r["status"] == "unresolved" and r not in stale]
    stats = {
        "scheduled": len(rows),
        "stale": len(stale),
        "upcoming": len(rows) - len(stale),
        "picked": len(picked),
        "unresolved": len(rows) - len(picked),
        "unresolved_upcoming": len(upcoming_unresolved),
        "coverage_upcoming_pct": round(100 * len(picked) / max(1, len(rows) - len(stale)), 1),
    }
    return {"rows": rows, "unmatched_markets": unmatched, "stats": stats}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    DATA.mkdir(exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    hs = collect_hotspawn()
    links = collect_hotspawn_links()
    lp = collect_leaguepedia()
    kal = collect_kalshi()
    pin = collect_pinnacle()
    pm = collect_polymarket()
    quotes = (kal.get("quotes") or []) + (pin.get("quotes") or []) + (pm.get("quotes") or [])
    elo = compute_elo(hs["fixtures"])
    elo_lp = compute_elo(lp.get("matches") or [], status_filter=None) if lp.get("ok") else None
    built = build_picks(hs["fixtures"], quotes, elo, links.get("links"), elo_lp)

    scheduled = [f for f in hs["fixtures"] if f["status"] == "scheduled"]
    picked = [r for r in built["rows"] if r["status"] == "picked"]
    unresolved = [r for r in built["rows"] if r["status"] == "unresolved"]
    meta = {
        "generated_utc": NOW.isoformat().replace("+00:00", "Z"),
        "hotspawn": {"ok": hs["ok"], "error": hs["error"], "lobby": HOTSPAWN_PAGE,
                     "api": HOTSPAWN_API, "scheduled": len(scheduled),
                     "ended_in_reference": len([f for f in hs["fixtures"] if f["status"] == "ended"])},
        "sources": {
            "kalshi": {"ok": kal["ok"], "error": kal["error"], "quotes": len(kal.get("quotes") or [])},
            "pinnacle": {"ok": pin["ok"], "error": pin["error"], "quotes": len(pin.get("quotes") or []),
                          "leagues": pin.get("leagues") or []},
            "polymarket": {"ok": pm["ok"], "error": pm["error"], "quotes": len(pm.get("quotes") or [])},
        },
        "counts": {
            **built["stats"],
            "market_backed": len([r for r in picked if r["basis"] in ("market", "market+model")]),
            "model_only": len([r for r in picked if r["basis"] == "model"]),
        },
        "model": {
            "history_matches": elo["history_matches"], "teams_rated": len(elo["ratings"]),
            "leaguepedia": {
                "ok": lp.get("ok"), "error": lp.get("error"), "rows": lp.get("rows", 0),
                "matches": len(lp.get("matches") or []),
                "teams_rated": len(elo_lp["ratings"]) if elo_lp else 0,
            },
        },
        "hotspawn_links": {"ok": links.get("ok"), "error": links.get("error"),
                            "verified_links": links.get("cards", 0)},
        "unmatched_markets": len(built["unmatched_markets"]),
        "verification": crosscheck_results(hs["fixtures"], lp.get("matches") or [])
        if lp.get("ok") else {"checked": 0, "agree": 0, "disagreements": []},
    }
    (DATA / "fixtures.json").write_text(json.dumps(
        {"generated_utc": meta["generated_utc"], "fixtures": hs["fixtures"]}, indent=1), encoding="utf-8")
    (DATA / "markets.json").write_text(json.dumps(
        {"generated_utc": meta["generated_utc"], "quotes": quotes,
         "unmatched": built["unmatched_markets"]}, indent=1), encoding="utf-8")
    (DATA / "picks.json").write_text(json.dumps(
        {"generated_utc": meta["generated_utc"], "rows": built["rows"]}, indent=1), encoding="utf-8")
    (DATA / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta["counts"], indent=1))
    print("sources:", json.dumps(meta["sources"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        import traceback

        DATA.mkdir(exist_ok=True)
        tb = traceback.format_exc()
        (DATA / "error.json").write_text(json.dumps(
            {"generated_utc": datetime.now(timezone.utc).isoformat(), "traceback": tb}, indent=1),
            encoding="utf-8")
        print(tb)
        sys.exit(1)

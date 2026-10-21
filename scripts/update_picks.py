#!/usr/bin/env python3
"""
Hotspawn League of Legends Pick'em — pick generation pipeline (v2).

Runs unattended in GitHub Actions every 6 hours. No manual input required.

WHAT IT DOES
------------
1.  Reads the official Hotspawn Pick'em fixture API (the same data source the
    `play.hotspawn.com/lol-pickems` lobby renders) and extracts EVERY scheduled
    League of Legends fixture on the board.
2.  Resolves a win probability for each fixture using an explicit evidence
    ladder. Hotspawn's own crowd pick-percentages are NEVER used as an input.
        L1  MARKET_PINNACLE   Pinnacle esportsbook (guest API, de-vigged)
        L1  MARKET_UNIBET     Unibet / Kambi esportsbook (de-vigged)
        L1  MARKET_POLYMARKET Polymarket prediction market
        ->  if more than one market prices the same match, the de-vigged
            probabilities are averaged (Pinnacle weighted x2 as the sharp book).
        L2  MODEL_LEAGUEPEDIA Proprietary Elo + form model built from official
                              Leaguepedia (lol.fandom.com) Cargo match history.
        L3  UNRESOLVED        No market price and no usable match history.
                              50/50 nominal pick, flagged for review.
3.  Writes data/picks.json, data/sources.json, data/flagged.json,
    data/coverage.json and data/debug.json.

EVERY row produced carries at least one official source URL.
Values that cannot be confirmed from an official source are left blank /
explicitly flagged rather than invented.
"""

import json
import os
import re
import sys
import time
import math
import urllib.request
import urllib.parse
import urllib.error
import traceback
from datetime import datetime, timezone, timedelta

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

NOW = datetime.now(timezone.utc)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
# Fandom/Leaguepedia requires a descriptive User-Agent; it rate-limits generic ones.
WIKI_UA = (
    "LOLHOTSPAWN5-PickDesk/2.0 (automated esports research; "
    "https://github.com/karagemop466-tech/LOLHOTSPAWN5)"
)

HOTSPAWn_FIXTURES_API = "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures"
HOTSPAWn_TENANT_API = "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/tenants/slug/hotspawn"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lol-pickems"
HOTSPAWN_WEEK_API = "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/week-prizes/widget?sportAlias=lol"

PINNACLE_SPORT_ESPORTS = 12
PINNACLE_MATCHUPS = f"https://guest.api.arcadia.pinnacle.com/0.1/sports/{PINNACLE_SPORT_ESPORTS}/matchups"
PINNACLE_MARKETS = f"https://guest.api.arcadia.pinnacle.com/0.1/sports/{PINNACLE_SPORT_ESPORTS}/markets/straight"

KAMBI_UNIBET_ESPORTS = (
    "https://eu-offering-api.kambicdn.com/offering/v2018/ub/listView/"
    "esports/all/all/all/matches.json?lang=en_GB&market=GB&client_id=2&channel_id=1&useCombined=true"
)

POLYMARKET_EVENTS = "https://gamma-api.promarket.example.invalid"  # replaced below
POLYMARKET_EVENTS = (
    "https://gamma-api.polymarket.com/events?tag_slug=league-of-legends&closed=false&limit=200"
)

LEAGUEPEDIA_API = "https://lol.fandom.com/api.php"
LEAGUEPEDIA_HELP = "https://lol.fandom.com/api.php?action=help&modules=cargoquery"

HISTORY_DAYS = 420          # how far back to pull Leaguepedia match history
ELO_START = 1500.0
ELO_K = 28.0
WIKI_SLEEP = 1.5            # seconds between Leaguepedia calls (be polite)
MAX_WIKI_PAGES = 2          # 500 rows each, per team chunk
WIKI_CHUNK = 16             # teams per Cargo query
WIKI_BUDGET_SEC = 720       # hard wall-clock budget for Leaguepedia collection

OUT_DIR = "data"


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #

def fetch(url, ua=None, timeout=60, retries=3, headers=None):
    """GET a URL and return the decoded body. Returns None on failure."""
    hdrs = {"User-Agent": ua or BROWSER_UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"}
    if headers:
        hdrs.update(headers)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:                      # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    print(f"  ! fetch failed ({last}): {url[:120]}", file=sys.stderr)
    return None


def fetch_json(url, **kw):
    body = fetch(url, **kw)
    if body is None:
        return None
    try:
        return json.loads(body)
    except Exception:                                  # noqa: BLE001
        return None


def norm(s):
    """Aggressive normalisation for team-name matching."""
    s = (s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def slugify(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def ms_to_iso(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).isoformat()
    except Exception:                                  # noqa: BLE001
        return ""


def american_to_decimal(price):
    """Pinnacle stores American odds (e.g. -150 / +230)."""
    try:
        price = float(price)
    except Exception:                                  # noqa: BLE001
        return None
    if price == 0:
        return None
    if price > 0:
        return 1.0 + price / 100.0
    return 1.0 + 100.0 / abs(price)


def devig(prices):
    """Convert a list of decimal prices into normalised probabilities."""
    decs = [p for p in prices if p and p > 1.0]
    if len(decs) < 2:
        return None
    inv = [1.0 / d for d in decs]
    total = sum(inv)
    if total <= 0:
        return None
    return [i / total for i in inv]


# --------------------------------------------------------------------------- #
# 1. Hotspawn fixtures
# --------------------------------------------------------------------------- #

def load_hotspawn_fixtures(debug):
    print("[1/6] Hotspawn fixture API …")
    data = fetch_json(HOTSPAWn_FIXTURES_API, timeout=180, retries=3)
    if not isinstance(data, list):
        print("  ! Hotspawn fixture API unavailable", file=sys.stderr)
        return [], {}

    lol = [r for r in data if (r.get("sport_alias") or "").lower() == "lol"]
    debug["hotspawn_total_fixtures"] = len(data)
    debug["hotspawn_lol_fixtures_alltime"] = len(lol)

    scheduled = [r for r in lol if (r.get("status") or "").lower() == "scheduled"]
    debug["hotspawn_lol_scheduled"] = len(scheduled)
    print(f"      {len(lol)} LoL fixtures total, {len(scheduled)} with status=scheduled")

    week = fetch_json(HOTSPAWN_WEEK_API, timeout=30, retries=2)
    if isinstance(week, dict):
        debug["hotspawn_week"] = {
            "weekId": week.get("weekId"),
            "sportAlias": week.get("sportAlias"),
            "status": week.get("status"),
            "weekStartUtc": week.get("weekStartUtc"),
            "weekEndUtc": week.get("weekEndUtc"),
            "cutoffUtc": week.get("cutoffUtc"),
        }

    permalinks = load_lobby_permalinks(debug)
    return scheduled, permalinks


def load_lobby_permalinks(debug):
    """Pull the server-rendered match permalinks out of the lobby HTML."""
    html = fetch(HOTSPAWN_LOBBY, timeout=90, retries=2)
    out = {}
    if not html:
        debug["lobby_html_bytes"] = 0
        return out
    debug["lobby_html_bytes"] = len(html)
    found = re.findall(r"https://www\.hotspawn\.com/matches/([a-z0-9-]+?)-(\d{5,9})", html)
    for slug, fid in found:
        out.setdefault(fid, set()).add(f"https://www.hotspawn.com/matches/{slug}-{fid}")
    debug["lobby_permalinks_found"] = len(out)
    print(f"      {len(out)} match permalinks harvested from lobby HTML")
    return out


def build_permalink(fx, permalinks, debug):
    """Return (url, verified_bool).

    `verified` is True only when the exact URL was harvested from the official
    Hotspawn lobby HTML. Otherwise we construct it from the documented Hotspawn
    slug pattern and mark it unverified.
    """
    fid = str(fx.get("id"))
    known = permalinks.get(fid)
    guess = (
        f"https://www.hotspawn.com/matches/"
        f"{slugify(fx.get('participants0_name'))}-vs-{slugify(fx.get('participants1_name'))}"
        f"-{slugify(fx.get('competition_name'))}-{fid}"
    )
    if known:
        if guess in known:
            debug["permalink_rule_hits"] = debug.get("permalink_rule_hits", 0) + 1
            return guess, True
        debug["permalink_rule_misses"] = debug.get("permalink_rule_misses", 0) + 1
        return sorted(known)[0], True
    debug["permalink_constructed"] = debug.get("permalink_constructed", 0) + 1
    return guess, False


# --------------------------------------------------------------------------- #
# 2. External market sources
# --------------------------------------------------------------------------- #

def load_pinnacle(debug):
    """Pinnacle esportsbook, keyless guest API. Returns {(n1,n2): (p_team1, url, label, start, group)}."""
    print("[2/6] Pinnacle esportsbook …")
    matchups = fetch_json(PINNACLE_MATCHUPS, timeout=90)
    markets = None
    for u in (PINNACLE_MARKETS, PINNACLE_MARKETS + "?brandId=0"):
        markets = fetch_json(u, timeout=90)
        if markets:
            break
    out = {}
    if not matchups or not markets:
        debug["pinnacle_ok"] = False
        return out
    debug["pinnacle_matchups"] = len(matchups)
    debug["pinnacle_markets"] = len(markets)

    # moneyline, full-match (period 0), two prices
    price_by_matchup = {}
    for m in markets:
        if (m.get("type") or "") != "moneyline":
            continue
        if str(m.get("period")) != "0":
            continue
        prices = m.get("prices") or []
        if len(prices) < 2:
            continue
        price_by_matchup[str(m.get("matchupId"))] = [
            (str(p.get("participantId")), p.get("price")) for p in prices
        ]
    debug["pinnacle_moneyline_match_markets"] = len(price_by_matchup)

    type_counts, lol_found, lol_priced = {}, 0, 0
    for mu in matchups:
        lg = (mu.get("league") or {})
        name = (lg.get("name") or "")
        if "league of legends" not in name.lower():
            continue
        lol_found += 1
        mtype = (mu.get("type") or "") or "(none)"
        type_counts[mtype] = type_counts.get(mtype, 0) + 1
        if mtype == "special":
            continue
        parts = mu.get("participants") or []
        if len(parts) < 2:
            continue
        prices = price_by_matchup.get(str(mu.get("id")))
        if not prices:
            continue
        home = next((p for p in parts if p.get("alignment") == "home"), parts[0])
        away = next((p for p in parts if p.get("alignment") == "away"), parts[1])
        price_home = price_away = None
        for pid, price in prices:
            if pid == str(home.get("id")):
                price_home = price
            elif pid == str(away.get("id")):
                price_away = price
        if price_home is None or price_away is None:
            # fall back to positional order
            if len(prices) >= 2:
                price_home, price_away = prices[0][1], prices[1][1]
            else:
                continue
        probs = devig([american_to_decimal(price_home), american_to_decimal(price_away)])
        if not probs:
            continue
        lol_priced += 1
        key = (norm(home.get("name")), norm(away.get("name")))
        out[key] = (
            probs[0],
            "https://www.pinnacle.com/en/esports/league-of-legends/",
            f"Pinnacle moneyline {home.get('name')} ({price_home}) vs {away.get('name')} ({price_away})"
            f" \u2014 de-vigged {probs[0]*100:.1f}% / {probs[1]*100:.1f}%",
            (mu.get("startTime") or ""),
            lg.get("name"),
        )
    debug["pinnacle_lol_matchups"] = lol_found
    debug["pinnacle_lol_matchup_types"] = type_counts
    debug["pinnacle_lol_priced"] = len(out)
    debug["pinnacle_ok"] = True
    print(f"      {lol_found} League of Legends matchups on the board, {len(out)} priced")
    return out


def load_unibet(debug):
    """Unibet (Kambi feed) esports. Returns {(n1,n2): (p_team1, url, label, start, group)}."""
    print("[3/6] Unibet / Kambi esports …")
    data = fetch_json(KAMBI_UNIBET_ESPORTS, timeout=60)
    out = {}
    if not data:
        debug["unibet_ok"] = False
        return out
    events = data.get("events") or []
    debug["unibet_esports_events"] = len(events)
    for e in events:
        ev = e.get("event") or {}
        path = " / ".join(p.get("name", "") for p in (ev.get("path") or []))
        if "League of Legends" not in path:
            continue
        home = ev.get("homeName")
        away = ev.get("awayName")
        if not home or not away:
            continue
        for bo in (e.get("betOffers") or []):
            crit = (bo.get("criterion") or {}).get("label", "")
            if "Match Odds" not in crit and (bo.get("betOfferType") or {}).get("name") != "Match":
                continue
            outs = bo.get("outcomes") or []
            if len(outs) != 2:
                continue
            by_part = {o.get("participant"): o.get("odds") for o in outs}
            if home not in by_part or away not in by_part:
                continue
            try:
                dh = float(by_part[home]) / 100.0
                da = float(by_part[away]) / 100.0
            except Exception:                          # noqa: BLE001
                continue
            probs = devig([dh, da])
            if not probs:
                continue
            key = (norm(home), norm(away))
            out[key] = (
                probs[0],
                "https://www.unibet.com/sportsbook-feeds/views/filter/esports",
                f"Unibet (Kambi) Match Odds {home} ({dh:.2f}) vs {away} ({da:.2f})"
                f" — de-vigged {probs[0]*100:.1f}% / {probs[1]*100:.1f}%",
                ev.get("start") or "",
                path.replace("Esports / ", ""),
            )
            break
    debug["unibet_lol_priced"] = len(out)
    debug["unibet_ok"] = True
    print(f"      {len(out)} League of Legends events priced")
    return out


def load_polymarket(debug):
    print("[4/6] Polymarket …")
    out = []
    for url in (
        POLYMARKET_EVENTS,
        "https://gamma-api.polymarket.com/events?closed=false&limit=200&tag_slug=esports",
    ):
        data = fetch_json(url, timeout=60)
        if isinstance(data, list):
            out.extend(data)
    debug["polymarket_events"] = len(out)

    markets = []
    for ev in out:
        title = ev.get("title") or ""
        for mk in (ev.get("markets") or []):
            try:
                prices = json.loads(mk.get("outcomePrices") or "[]")
                outs = json.loads(mk.get("outcomes") or "[]")
            except Exception:                          # noqa: BLE001
                continue
            if len(prices) != 2 or len(outs) != 2:
                continue
            try:
                prices = [float(p) for p in prices]
            except Exception:                          # noqa: BLE001
                continue
            if sum(prices) <= 0:
                continue
            markets.append({
                "question": mk.get("question") or title,
                "outs": outs,
                "prices": prices,
                "url": f"https://polymarket.com/event/{ev.get('slug') or ev.get('ticker') or ''}",
            })
    debug["polymarket_2way_markets"] = len(markets)
    print(f"      {len(markets)} two-way markets indexed")
    return markets


def _outcome_match(a, b):
    """True if normalised team name a corresponds to normalised outcome b."""
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 6 and len(b) >= 6 and (a in b or b in a):
        return True
    return False


def lookup_polymarket(markets, t1, t2):
    """Return (p_team1, url, question) or None.

    Only accepts two-outcome markets whose outcome names map to the two teams.
    A fuzzy (substring) outcome match is additionally required to be corroborated
    by both team names appearing in the market question, to avoid false positives
    on short team names.
    """
    n1, n2 = norm(t1), norm(t2)
    if not n1 or not n2:
        return None
    q1 = re.sub(r"[^a-z0-9]+", " ", (t1 or "").lower()).strip()
    q2 = re.sub(r"[^a-z0-9]+", " ", (t2 or "").lower()).strip()
    for mk in markets:
        o = [norm(x) for x in mk["outs"]]
        if not (o[0] and o[1]):
            continue
        q = re.sub(r"[^a-z0-9]+", " ", (mk.get("question") or "").lower())
        exact = (n1 == o[0] and n2 == o[1]) or (n2 == o[0] and n1 == o[1])
        if not exact:
            fuzzy = ((_outcome_match(n1, o[0]) and _outcome_match(n2, o[1])) or
                     (_outcome_match(n2, o[0]) and _outcome_match(n1, o[1])))
            if not fuzzy:
                continue
            # fuzzy matches must be corroborated by the question text
            if not (len(q1) >= 4 and q1 in q and len(q2) >= 4 and q2 in q):
                continue
        s = sum(mk["prices"])
        if s <= 0:
            continue
        if _outcome_match(n1, o[0]):
            return mk["prices"][0] / s, mk["url"], mk["question"]
        return mk["prices"][1] / s, mk["url"], mk["question"]
    return None


# --------------------------------------------------------------------------- #
# 3. Leaguepedia history + proprietary model
# --------------------------------------------------------------------------- #

def cargo(where, fields, table="ScoreboardGames", order_by=None, limit=500, offset=0):
    params = {
        "action": "cargoquery",
        "format": "json",
        "tables": table,
        "fields": fields,
        "where": where,
        "limit": str(limit),
        "offset": str(offset),
    }
    if order_by:
        params["order_by"] = order_by
    url = LEAGUEPEDIA_API + "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        body = fetch(url, ua=WIKI_UA, timeout=75, retries=1)
        if body is None:
            time.sleep(4 * (attempt + 1))
            continue
        try:
            j = json.loads(body)
        except Exception:                              # noqa: BLE001
            time.sleep(4 * (attempt + 1))
            continue
        if isinstance(j, dict) and "error" in j:
            time.sleep(5 * (attempt + 1))
            continue
        return j.get("cargoquery", [])
    return []


def esc(s):
    return (s or "").replace('"', '\\"')


def _rows_to_games(rows, seen, games):
    for r in rows:
        t = r.get("title", {})
        a = t.get("Team1") or ""
        b = t.get("Team2") or ""
        w = t.get("WinTeam") or ""
        d = t.get("DateTime UTC") or ""
        tour = t.get("Tournament") or ""
        if not a or not b or not d:
            continue
        key = (a, b, d, tour)
        if key in seen:
            continue
        seen.add(key)
        games.append((a, b, w, d, tour))


def leaguepedia_games(teams, competitions, debug):
    """Pull completed games from Leaguepedia Cargo.

    Pass 1 (fast): one OR-equality query per batch of the board's own competitions.
    Pass 2 (fill-in): team-based queries for any team still with zero games.
    """
    since = (NOW - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    fields = ("ScoreboardGames.Team1,ScoreboardGames.Team2,ScoreboardGames.WinTeam,"
              "ScoreboardGames.DateTime_UTC,ScoreboardGames.Tournament")
    games, seen = [], set()
    deadline = time.time() + WIKI_BUDGET_SEC

    # ---- pass 1: by competition ------------------------------------------ #
    comps = sorted({c for c in competitions if c})
    debug["leaguepedia_competitions"] = len(comps)
    if comps:
        conds = [f'ScoreboardGames.Tournament="{esc(c)}"' for c in comps]
        where = f'ScoreboardGames.DateTime_UTC >= "{since}" AND (' + " OR ".join(conds) + ")"
        print(f"      pass 1: {len(comps)} competitions …")
        for page in range(MAX_WIKI_PAGES * 3):
            if time.time() > deadline:
                debug["leaguepedia_budget_exceeded"] = True
                break
            rows = cargo(where, fields, order_by="ScoreboardGames.DateTime_UTC DESC",
                         limit=500, offset=page * 500)
            debug["leaguepedia_cargo_calls"] = debug.get("leaguepedia_cargo_calls", 0) + 1
            if not rows:
                break
            _rows_to_games(rows, seen, games)
            time.sleep(WIKI_SLEEP)
            if len(rows) < 500:
                break
        print(f"        {len(games)} games from competition pass")

    # ---- pass 2: teams with no games yet --------------------------------- #
    covered = set()
    for a, b, _w, _d, _t in games:
        covered.add(norm(a))
        covered.add(norm(b))
    missing = [t for t in teams if norm(t) not in covered]
    debug["leaguepedia_teams_missing_after_pass1"] = len(missing)
    if missing:
        chunks = [missing[i:i + WIKI_CHUNK] for i in range(0, len(missing), WIKI_CHUNK)]
        print(f"      pass 2: {len(missing)} teams in {len(chunks)} chunk queries …")
        for ci, chunk in enumerate(chunks):
            if time.time() > deadline:
                debug["leaguepedia_budget_exceeded"] = True
                debug["leaguepedia_teams_skipped"] = len(missing) - ci * WIKI_CHUNK
                break
            conds = []
            for t in chunk:
                e = esc(t)
                conds.append(f'ScoreboardGames.Team1="{e}"')
                conds.append(f'ScoreboardGames.Team2="{e}"')
            where = f'ScoreboardGames.DateTime_UTC >= "{since}" AND (' + " OR ".join(conds) + ")"
            for page in range(MAX_WIKI_PAGES):
                if time.time() > deadline:
                    debug["leaguepedia_budget_exceeded"] = True
                    break
                rows = cargo(where, fields, order_by="ScoreboardGames.DateTime_UTC DESC",
                             limit=500, offset=page * 500)
                debug["leaguepedia_cargo_calls"] = debug.get("leaguepedia_cargo_calls", 0) + 1
                if not rows:
                    break
                _rows_to_games(rows, seen, games)
                if len(rows) < 500:
                    break
                time.sleep(WIKI_SLEEP)
            time.sleep(WIKI_SLEEP)
            if (ci + 1) % 5 == 0:
                print(f"        {ci+1}/{len(chunks)} chunks, {len(games)} games total")

    debug["leaguepedia_games"] = len(games)
    return games


def build_model(games):
    """Elo + recent-form model over the pulled game history."""
    def parse_dt(s):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except Exception:                          # noqa: BLE001
                continue
        return None

    ordered = []
    for a, b, w, d, tour in games:
        dt = parse_dt(d)
        if dt is None:
            continue
        ordered.append((dt, a, b, w, tour))
    ordered.sort(key=lambda x: x[0])

    ratings, played, results = {}, {}, {}
    for dt, a, b, w, tour in ordered:
        na, nb = norm(a), norm(b)
        if not na or not nb:
            continue
        ra = ratings.get(na, ELO_START)
        rb = ratings.get(nb, ELO_START)
        # winner may be encoded as team name or '1'/'2'
        if w == a or w == "1":
            sa, sb = 1.0, 0.0
        elif w == b or w == "2":
            sa, sb = 0.0, 1.0
        else:
            continue
        ea = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
        delta = ELO_K * (sa - ea)
        ratings[na] = ra + delta
        ratings[nb] = rb - delta
        played[na] = played.get(na, 0) + 1
        played[nb] = played.get(nb, 0) + 1
        results.setdefault(na, []).append((dt, sa))
        results.setdefault(nb, []).append((dt, sb))

    def recent(team):
        rs = results.get(team, [])
        if not rs:
            return None, 0
        cutoff = NOW - timedelta(days=90)
        recent_rows = [r for r in rs if r[0] >= cutoff]
        if not recent_rows:
            return None, 0
        return sum(x[1] for x in recent_rows) / len(recent_rows), len(recent_rows)

    return ratings, played, recent


def model_prob(ratings, played, recent_fn, t1, t2):
    n1, n2 = norm(t1), norm(t2)
    g1, g2 = played.get(n1, 0), played.get(n2, 0)
    if g1 == 0 and g2 == 0:
        return None, None
    r1, r2 = ratings.get(n1, ELO_START), ratings.get(n2, ELO_START)
    base = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))

    # Blend in recent (90d) win-rate differential, weighted by sample size.
    f1, c1 = recent_fn(n1)
    f2, c2 = recent_fn(n2)
    if f1 is not None and f2 is not None and c1 >= 4 and c2 >= 4:
        form = 0.5 + (f1 - f2) * 0.45
        form = max(0.05, min(0.95, form))
        blended = 0.7 * base + 0.3 * form
    else:
        blended = base

    # Shrink toward 50% when the underlying sample is thin.
    n_eff = min(g1, g2)
    shrink = n_eff / (n_eff + 12.0) if n_eff > 0 else 0.0
    p = 0.5 + (blended - 0.5) * shrink
    return max(0.02, min(0.98, p)), {
        "elo": [round(r1, 1), round(r2, 1)],
        "games": [g1, g2],
        "recent_form": [round(f1, 3) if f1 is not None else None,
                        round(f2, 3) if f2 is not None else None],
    }


# --------------------------------------------------------------------------- #
# 4. Combine
# --------------------------------------------------------------------------- #

def market_consensus(entries):
    """entries: list of (prob_team1, weight, label, url). Weighted mean."""
    if not entries:
        return None, None
    total_w = sum(w for _, w, _, _ in entries)
    p = sum(pr * w for pr, w, _, _ in entries) / total_w
    labels = [lbl for _, _, lbl, _ in entries]
    urls = [u for _, _, _, u in entries]
    return p, {"labels": labels, "urls": urls, "books": len(entries)}


def same_team(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if len(na) >= 6 and len(nb) >= 6 and (na in nb or nb in na):
        return True
    return False


def find_market(markets, t1, t2, start_iso):
    """markets: dict {(n1,n2): (p1, url, label, start, group)}. Returns list of (p, w, label, url)."""
    hits = []
    for (a, b), (p, url, label, st, group) in markets.items():
        if same_team(a, t1) and same_team(b, t2):
            date_ok = date_close(st, start_iso)
            hits.append((p, 1.0, label, url, date_ok, group))
        elif same_team(a, t2) and same_team(b, t1):
            date_ok = date_close(st, start_iso)
            hits.append((1.0 - p, 1.0, label, url, date_ok, group))
    # prefer date-consistent hits
    dated = [h for h in hits if h[4]]
    return dated or hits


def date_close(a, b, days=2):
    def p(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except Exception:                              # noqa: BLE001
            return None
    da, db = p(a), p(b)
    if not da or not db:
        return False
    return abs((da - db).total_seconds()) <= days * 86400


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    debug = {"generated_at": NOW.isoformat(), "pipeline": "v2"}

    fixtures, permalinks = load_hotspawn_fixtures(debug)
    if not fixtures:
        print("! No fixtures retrieved; preserving existing snapshot.", file=sys.stderr)
        return 0

    def safe(fn, *a):
        try:
            return fn(*a)
        except Exception:                              # noqa: BLE001
            print(f"  ! {fn.__name__} failed:\n{traceback.format_exc()}", file=sys.stderr)
            return None

    pinnacle = safe(load_pinnacle, debug) or {}
    unibet = safe(load_unibet, debug) or {}
    poly = safe(load_polymarket, debug) or []

    team_names = sorted({f.get("participants0_name") or "" for f in fixtures} |
                        {f.get("participants1_name") or "" for f in fixtures} - {""})
    competitions = sorted({f.get("competition_name") or "" for f in fixtures} - {""})
    print(f"[5/6] Leaguepedia history — {len(team_names)} teams / {len(competitions)} competitions …")
    games = safe(leaguepedia_games, team_names, competitions, debug) or []
    ratings, played, recent_fn = build_model(games)
    debug["elo_teams_rated"] = len(ratings)
    print(f"      {len(games)} games, {len(ratings)} teams rated")

    # ---- resolve each fixture -------------------------------------------- #
    print("[6/6] Resolving picks …")
    rows = []
    for fx in fixtures:
        t1 = fx.get("participants0_name") or ""
        t2 = fx.get("participants1_name") or ""
        start_iso = ms_to_iso(fx.get("scheduled_start_time"))
        lock_iso = ms_to_iso(fx.get("lock_time"))
        permalink, permalink_verified = build_permalink(fx, permalinks, debug)

        pb = fx.get("points_breakdown") or {}
        row = {
            "fixture_id": str(fx.get("id")),
            "team1": t1,
            "team2": t2,
            "team1_id": fx.get("participants0_id"),
            "team2_id": fx.get("participants1_id"),
            "tournament": fx.get("competition_name") or "",
            "competition_id": fx.get("competition_id"),
            "tier": (fx.get("tier") or "").upper() or "",
            "stage": fx.get("stage") or "",
            "status": fx.get("status") or "",
            "best_of": fx.get("best_of"),
            "points": fx.get("offered_points"),
            "tier_multiplier": pb.get("tier_multiplier"),
            "start_utc": start_iso,
            "lock_utc": lock_iso,
            # Hotspawn crowd percentages — recorded for context only.
            "crowd_pct_team1": fx.get("participants0_picked_percent"),
            "crowd_pct_team2": fx.get("participants1_picked_percent"),
            "total_picks": fx.get("total_picks"),
            "hotspawn_match_url": permalink,
            "hotspawn_match_url_verified": permalink_verified,
            "hotspawn_lobby_url": HOTSPAWN_LOBBY,
            "hotspawn_api_url": HOTSPAWn_FIXTURES_API,
            "sources": [],
        }

        # is the pick window still open?
        open_for_picks = False
        if lock_iso:
            try:
                open_for_picks = datetime.fromisoformat(lock_iso) > NOW
            except Exception:                          # noqa: BLE001
                open_for_picks = False
        row["open_for_picks"] = open_for_picks
        if start_iso:
            try:
                row["stale_listing"] = (
                    datetime.fromisoformat(start_iso) < NOW - timedelta(hours=6)
                    and (fx.get("status") or "") == "scheduled"
                )
            except Exception:                          # noqa: BLE001
                row["stale_listing"] = False
        else:
            row["stale_listing"] = False

        entries = []
        for mk, weight in ((pinnacle, 2.0), (unibet, 1.0)):
            for hit in find_market(mk, t1, t2, start_iso):
                p, url, label = hit[0], hit[3], hit[2]
                entries.append((p, weight, label, url))
        poly_hit = lookup_polymarket(poly, t1, t2)
        if poly_hit:
            entries.append((poly_hit[0], 1.0, f"Polymarket: {poly_hit[2]}", poly_hit[1]))

        prob = None
        method = ""
        evidence = ""
        confidence = ""
        detail = {}
        sources = []

        if entries:
            p, info = market_consensus(entries)
            prob = p
            method = "MARKET"
            evidence = " | ".join(info["labels"])
            confidence = (
                "High — external esportsbook / prediction-market price, de-vigged"
                if info["books"] > 1 else
                "Medium-High — single external market price, de-vigged"
            )
            detail = {"books": info["books"]}
            sources = [{"label": lbl, "url": url} for lbl, url in zip(info["labels"], info["urls"])]
            if poly_hit:
                sources.append({"label": "Polymarket market", "url": poly_hit[1]})
        else:
            mp, info = model_prob(ratings, played, recent_fn, t1, t2)
            if mp is not None:
                prob = mp
                method = "MODEL"
                g1, g2 = info["games"]
                e1, e2 = info["elo"]
                evidence = (
                    f"Originated line — Leaguepedia Elo {e1:.0f} ({g1} games) vs {e2:.0f} ({g2} games)"
                    f" over the last {HISTORY_DAYS} days"
                )
                min_g = min(g1, g2)
                confidence = (
                    "Medium — modelled from official match history"
                    if min_g >= 10 else
                    "Low — modelled from thin official match history"
                )
                if min_g < 3:
                    confidence = "Low — very thin official match history"
                detail = info
                sources = [{
                    "label": "Leaguepedia Cargo API (ScoreboardGames)",
                    "url": LEAGUEPEDIA_HELP,
                }, {
                    "label": f"Leaguepedia: {t1}",
                    "url": "https://lol.fandom.com/wiki/" + urllib.parse.quote(t1.replace(" ", "_")),
                }, {
                    "label": f"Leaguepedia: {t2}",
                    "url": "https://lol.fandom.com/wiki/" + urllib.parse.quote(t2.replace(" ", "_")),
                }]
            else:
                prob = 0.5
                method = "UNRESOLVED"
                evidence = (
                    "Unresolved — no external betting market prices this fixture and neither team "
                    "has a completed match recorded in Leaguepedia within the look-back window."
                )
                confidence = "Unresolved — 50/50 nominal pick only; no statistical edge"
                sources = [{"label": "Leaguepedia (no record found)", "url": LEAGUEPEDIA_HELP}]

        prob = round(max(0.01, min(0.99, float(prob))), 4)
        row["prob_team1"] = prob
        row["prob_team2"] = round(1.0 - prob, 4)
        row["pick"] = t1 if prob >= 0.5 else t2
        row["pick_prob"] = round(max(prob, 1.0 - prob), 4)
        row["method"] = method
        row["evidence"] = evidence
        row["confidence"] = confidence
        row["detail"] = detail
        row["sources"] = sources + [
            {"label": "Hotspawn match page", "url": permalink},
            {"label": "Hotspawn Pick'em lobby", "url": HOTSPAWN_LOBBY},
        ]
        row["crowd_note"] = (
            "Hotspawn lobby crowd percentages are recorded for context only and are NEVER "
            "used as an input to our probabilities."
        )
        rows.append(row)

    rows.sort(key=lambda r: (r.get("start_utc") or "9999", r.get("tournament") or "", r.get("team1") or ""))

    counts = {}
    for r in rows:
        counts[r["method"]] = counts.get(r["method"], 0) + 1

    payload = {
        "generated_at": NOW.isoformat(),
        "generated_at_human": NOW.strftime("%Y-%m-%d %H:%M UTC"),
        "lobby": HOTSPAWN_LOBBY,
        "count": len(rows),
        "open_count": sum(1 for r in rows if r.get("open_for_picks")),
        "counts_by_method": counts,
        "coverage": {
            "resolved": sum(1 for r in rows if r["method"] != "UNRESOLVED"),
            "unresolved": sum(1 for r in rows if r["method"] == "UNRESOLVED"),
            "total": len(rows),
        },
        "debug": debug,
        "matches": rows,
    }

    with open(os.path.join(OUT_DIR, "picks.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "debug.json"), "w", encoding="utf-8") as f:
        json.dump(debug, f, indent=1, ensure_ascii=False)

    # ---- flagged items ---------------------------------------------------- #
    flagged = []

    def flag(kind, severity, title, detail, row):
        flagged.append({
            "kind": kind,
            "severity": severity,
            "title": title,
            "detail": detail,
            "fixture_id": row.get("fixture_id"),
            "match": f"{row.get('team1')} vs {row.get('team2')}",
            "tournament": row.get("tournament"),
            "start_utc": row.get("start_utc"),
            "sources": row.get("sources") or [],
        })

    for r in rows:
        if not r["hotspawn_match_url_verified"]:
            flag("unverified-link", "medium",
                 "Match permalink constructed, not server-verified",
                 "This fixture was not present in the server-rendered Hotspawn lobby HTML at "
                 "collection time, so its www.hotspawn.com match page URL was reconstructed from "
                 "Hotspawn's public slug pattern. The fixture itself comes from the official "
                 "Hotspawn fixture API; only the permalink is unverified.", r)
        if r.get("stale_listing"):
            flag("stale-listing", "low",
                 "Fixture still listed as scheduled after its start time",
                 "Hotspawn's API still reports status='scheduled' more than 6 hours after the "
                 "scheduled start time. The fixture is retained for completeness but the pick "
                 "window has closed.", r)
        if r["method"] == "UNRESOLVED":
            flag("unresolved-pick", "high",
                 "No resolvable probability — nominal 50/50 pick",
                 "No external betting market prices this fixture and neither team has a completed "
                 "match recorded in Leaguepedia inside the look-back window. The pick shown is a "
                 "nominal 50/50 with no statistical edge.", r)
        elif r["method"] == "MODEL":
            g = (r.get("detail") or {}).get("games") or [0, 0]
            if min(g) < 5:
                flag("thin-history", "medium",
                     "Originated line built on thin match history",
                     f"Only {g[0]} / {g[1]} completed games were found for these teams in Leaguepedia "
                     f"over the last {HISTORY_DAYS} days, so the Elo estimate is heavily shrunk "
                     "toward 50%.", r)
        elif r["method"] == "MARKET":
            if (r.get("detail") or {}).get("books", 0) < 2:
                flag("single-book", "low",
                     "Only one external bookmaker prices this fixture",
                     "The market line rests on a single bookmaker/prediction-market price rather "
                     "than a multi-book consensus.", r)

    order = {"high": 0, "medium": 1, "low": 2}
    flagged.sort(key=lambda x: (order.get(x["severity"], 3), x["kind"], x["match"]))
    flagged_payload = {
        "generated_at": NOW.isoformat(),
        "count": len(flagged),
        "by_kind": {k: sum(1 for f in flagged if f["kind"] == k)
                    for k in sorted({f["kind"] for f in flagged})},
        "items": flagged,
    }
    with open(os.path.join(OUT_DIR, "flagged.json"), "w", encoding="utf-8") as f:
        json.dump(flagged_payload, f, indent=1, ensure_ascii=False)

    # ---- source registry --------------------------------------------------- #
    sources_payload = {
        "generated_at": NOW.isoformat(),
        "sources": [
            {
                "name": "Hotspawn Pick'em fixture API",
                "url": HOTSPAWn_FIXTURES_API,
                "role": "Official board — every scheduled LoL Pick'em fixture, teams, tier, "
                        "points, start/lock times, crowd pick percentages (context only).",
                "verified": True,
                "verification": f"Returned HTTP 200 with {debug.get('hotspawn_total_fixtures', 0)} "
                                f"fixtures; {debug.get('hotspawn_lol_scheduled', 0)} are scheduled "
                                f"League of Legends fixtures.",
            },
            {
                "name": "Hotspawn LoL Pick'em lobby",
                "url": HOTSPAWN_LOBBY,
                "role": "Official board UI. Harvested for server-rendered match permalinks.",
                "verified": debug.get("lobby_html_bytes", 0) > 0,
                "verification": f"{debug.get('lobby_permalinks_found', 0)} match permalinks extracted "
                                f"from {debug.get('lobby_html_bytes', 0)} bytes of lobby HTML.",
            },
            {
                "name": "Pinnacle — E Sports odds (guest API)",
                "url": "https://www.pinnacle.com/en/esports/",
                "role": "Sharp esportsbook moneyline prices, de-vigged into probabilities.",
                "verified": bool(debug.get("pinnacle_ok")),
                "verification": f"{debug.get('pinnacle_lol_priced', 0)} League of Legends matchups "
                                f"priced from {debug.get('pinnacle_matchups', 0)} esports matchups.",
            },
            {
                "name": "Unibet (Kambi offering feed) — Esports",
                "url": "https://www.unibet.com/sportsbook-feeds/views/filter/esports",
                "role": "Second independent esportsbook moneyline prices.",
                "verified": bool(debug.get("unibet_ok")),
                "verification": f"{debug.get('unibet_lol_priced', 0)} League of Legends events priced "
                                f"from {debug.get('unibet_esports_events', 0)} esports events.",
            },
            {
                "name": "Polymarket Gamma API — League of Legends",
                "url": "https://polymarket.com/",
                "role": "Prediction-market prices for top-tier LoL matches.",
                "verified": bool(debug.get("polymarket_2way_markets")),
                "verification": f"{debug.get('polymarket_2way_markets', 0)} two-way markets indexed "
                                f"from {debug.get('polymarket_events', 0)} events.",
            },
            {
                "name": "Leaguepedia Cargo API (ScoreboardGames)",
                "url": LEAGUEPEDIA_HELP,
                "role": "Official LoL esports match-history database. Input to the proprietary "
                        "Elo/form model used to originate lines with no market coverage.",
                "verified": bool(debug.get("leaguepedia_games")),
                "verification": f"{debug.get('leaguepedia_games', 0)} completed games pulled across "
                                f"{debug.get('leaguepedia_cargo_calls', 0)} Cargo calls; "
                                f"{debug.get('elo_teams_rated', 0)} teams rated.",
            },
        ],
    }
    with open(os.path.join(OUT_DIR, "sources.json"), "w", encoding="utf-8") as f:
        json.dump(sources_payload, f, indent=1, ensure_ascii=False)

    print(f"\nDone. {len(rows)} fixtures — {counts}")
    print(f"      resolved {payload['coverage']['resolved']} / unresolved {payload['coverage']['unresolved']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:                                  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)

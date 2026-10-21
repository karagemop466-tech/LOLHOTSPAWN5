#!/usr/bin/env python3
"""
Hotspawn LoL Pick'em Intelligence & Pick Generation Engine
- Reverse engineers and parses matches from play.hotspawn.com/lol-pickems & play.hotspawn.com/lobby
- Fetches external market lines: Polymarket public Gamma API, OddsPapi multi-bookmaker (Pinnacle, bet365)
- Originates proprietary Elo lines from official Leaguepedia Cargo match history (last 180 days)
- Handles low-tier / amateur unresolved matches with transparent 50/50 baselines and documented limitations
- Runs in GitHub Actions every 6 hours (no manual input required)
"""

import json
import os
import re
import sys
import math
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

UA = {
    "User-Agent": "Mozilla/5.0 (compatible; HotspawnLoLPicks/1.0; +https://github.com/karagemop466-tech/LOLHOTSPAWN5)"
}
LOBBIES = [
    "https://play.hotspawn.com/lol-pickems",
    "https://play.hotspawn.com/lobby"
]
NOW = datetime.now(timezone.utc)

def fetch_url(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace"), resp.status

def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

# ----------------- Hotspawn HTML / Token Stream Parser -----------------
class HotspawnHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self._href = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a":
            self._href = d.get("href")

    def handle_endtag(self, tag):
        if tag == "a":
            self._href = None

    def handle_data(self, data):
        clean = " ".join(data.split())
        if clean:
            self.items.append((clean, self._href))

DATE_RE = re.compile(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*\d{1,2}:\d{2}$')

def parse_lobby_content(html):
    matches = []
    # 1. Embedded Next.js / Inertia script blob
    for m in re.finditer(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S):
        try:
            blob = json.loads(m.group(1))
        except Exception:
            continue
        def walk(obj):
            if isinstance(obj, dict):
                keys = {k.lower() for k in obj}
                if any("team" in k for k in keys) and any("start" in k or "date" in k for k in keys):
                    matches.append(obj)
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    walk(v)
        walk(blob)

    if matches:
        out = []
        for o in matches:
            lo = {k.lower(): v for k, v in o.items()}
            t1 = lo.get("team1") or lo.get("home_team") or lo.get("participant1")
            t2 = lo.get("team2") or lo.get("away_team") or lo.get("participant2")
            if isinstance(t1, dict): t1 = t1.get("name")
            if isinstance(t2, dict): t2 = t2.get("name")
            if t1 and t2:
                out.append(dict(
                    team1=str(t1),
                    team2=str(t2),
                    tournament=str(lo.get("tournament") or lo.get("league") or ""),
                    start_raw=str(lo.get("scheduled_start") or lo.get("start_time") or lo.get("date") or ""),
                    tier=str(lo.get("tier") or ""),
                    points=str(lo.get("points") or ""),
                    hotspawn_url=str(lo.get("url") or ""),
                    crowd1=None,
                    crowd2=None
                ))
        if out:
            return out, "embedded-json"

    # 2. Token-stream parser over SSR HTML card components
    parser = HotspawnHTMLParser()
    parser.feed(html)
    items = parser.items
    out = []
    i = 0
    while i < len(items):
        txt = items[i][0]
        if DATE_RE.match(txt):
            start = txt
            window = items[i+1:i+40]
            texts = [w[0] for w in window]
            try:
                wi = texts.index("Who will win?")
            except ValueError:
                i += 1
                continue
            
            tournament = texts[0] if texts else ""
            tier = ""
            points = ""
            joined = " ".join(texts[:wi])
            tm = re.search(r'Tier\s*([A-Z]|WAITING FOR INFORMATION)', joined)
            if tm:
                tier = tm.group(1)
            tm2 = re.search(r'(\d+)\s*pts', joined)
            if tm2:
                points = tm2.group(1)

            # Team names follow "Who will win?"
            rest = texts[wi+1:wi+8]
            teams = []
            crowds = []
            for t in rest:
                pm = re.match(r'^(\d+)%\s*picked$', t)
                if pm:
                    crowds.append(int(pm.group(1)))
                elif t not in ("Sign in for streaks", "Locks in") and not re.match(r'^[\d:dhms ]+$', t) and len(teams) < 2:
                    teams.append(t)

            url = ""
            for w in window:
                if w[1] and "hotspawn.com/matches/" in w[1]:
                    url = w[1]
                    break

            if len(teams) == 2:
                out.append(dict(
                    team1=teams[0],
                    team2=teams[1],
                    tournament=tournament,
                    start_raw=start,
                    tier=tier or "WAITING FOR INFORMATION",
                    points=points,
                    hotspawn_url=url,
                    crowd1=crowds[0] if len(crowds) > 0 else None,
                    crowd2=crowds[1] if len(crowds) > 1 else None
                ))
            i += wi + 1
        else:
            i += 1

    # Deduplicate matches
    seen = set()
    deduped = []
    for m in out:
        key = (norm(m["team1"]), norm(m["team2"]), m["start_raw"], norm(m["tournament"]))
        if key not in seen:
            seen.add(key)
            deduped.append(m)

    return deduped, "html-token-stream"

def parse_start_date(raw):
    if not raw:
        return ""
    try:
        if str(raw).isdigit():
            return datetime.fromtimestamp(int(raw), timezone.utc).isoformat()
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        pass
    try:
        # Hotspawn format: "Oct 22, 12:00"
        dt = datetime.strptime(f"{raw} {NOW.year}", "%b %d, %H:%M %Y").replace(tzinfo=timezone.utc)
        if dt < NOW - timedelta(days=2):
            dt = dt.replace(year=NOW.year + 1)
        return dt.isoformat()
    except Exception:
        return ""

# ----------------- External Market 1: Polymarket Gamma API -----------------
def fetch_polymarket():
    events = []
    urls = [
        "https://gamma-api.polymarket.com/events?tag_slug=league-of-legends&active=true&closed=false&limit=100",
        "https://gamma-api.polymarket.com/events?search=league%20of%20legends&active=true&closed=false&limit=100",
        "https://gamma-api.polymarket.com/events?search=LoL&active=true&closed=false&limit=100"
    ]
    for url in urls:
        try:
            data, _ = fetch_url(url)
            parsed = json.loads(data)
            if isinstance(parsed, list):
                events.extend(parsed)
        except Exception as e:
            print(f"Polymarket fetch notice: {e}", file=sys.stderr)
    
    indexed = []
    for ev in events:
        for mk in ev.get("markets", []):
            q = mk.get("question", "")
            try:
                prices = json.loads(mk.get("outcomePrices") or "[]")
                outs = json.loads(mk.get("outcomes") or "[]")
            except Exception:
                continue
            if len(prices) == 2 and len(outs) == 2:
                indexed.append(dict(
                    question=q,
                    outs=outs,
                    prices=[float(x) for x in prices],
                    url="https://polymarket.com/event/" + str(ev.get("slug", ""))
                ))
    return indexed

def match_polymarket(indexed, t1, t2):
    n1, n2 = norm(t1), norm(t2)
    for m in indexed:
        o = [norm(x) for x in m["outs"]]
        if (n1 in o[0] or o[0] in n1) and (n2 in o[1] or o[1] in n2):
            return m["prices"][0], m["url"], m["question"]
        if (n2 in o[0] or o[0] in n2) and (n1 in o[1] or o[1] in n1):
            return m["prices"][1], m["url"], m["question"]
        q = norm(m["question"])
        if n1 in q and n2 in q and m["prices"]:
            return m["prices"][0], m["url"], m["question"]
    return None

# ----------------- External Market 2: OddsPapi (Esportsbooks) -----------------
def fetch_oddspapi():
    key = os.environ.get("ODDSPAPI_KEY")
    if not key:
        return []
    try:
        data, _ = fetch_url(f"https://api.oddspapi.io/v4/fixtures?sportId=18&apiKey={key}")
        fixtures = json.loads(data)
    except Exception as e:
        print(f"OddsPapi fixtures notice: {e}", file=sys.stderr)
        return []

    out = []
    for f in fixtures if isinstance(fixtures, list) else []:
        p1 = f.get("participant1Name") or ""
        p2 = f.get("participant2Name") or ""
        fid = f.get("fixtureId")
        if not (p1 and p2 and fid):
            continue
        try:
            data, _ = fetch_url(f"https://api.oddspapi.io/v4/odds?fixtureId={fid}&apiKey={key}")
            odds_data = json.loads(data)
            books = odds_data.get("bookmakers", {})
            probs = []
            for slug, book in books.items():
                mk = (book.get("markets") or {}).get("181")  # LoL series winner market
                if not mk:
                    continue
                outs = mk.get("outcomes") or {}
                vals = []
                for oid in ("181", "182"):
                    o = outs.get(oid) or {}
                    pr = (o.get("players") or {}).get("0") or o
                    price = pr.get("price")
                    if price:
                        vals.append(float(price))
                if len(vals) == 2 and all(v > 1 for v in vals):
                    inv = [1.0 / v for v in vals]
                    s = sum(inv)
                    probs.append((inv[0] / s, slug))
            if probs:
                probs.sort()
                med = probs[len(probs) // 2]
                out.append(dict(
                    team1=p1,
                    team2=p2,
                    p1=med[0],
                    source=f"OddsPapi median de-vigged ({len(probs)} books, incl. {med[1]})",
                    url="https://oddspapi.io/sports/esports/lol"
                ))
        except Exception as e:
            print(f"OddsPapi odds notice: {e}", file=sys.stderr)
    return out

# ----------------- Originated Lines: Leaguepedia Cargo API Elo -----------------
def build_elo_model():
    ratings = {}
    games = {}
    recent = {}
    since = (NOW - timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
    offset = 0
    for _ in range(12):  # up to 6000 games
        params = urllib.parse.urlencode({
            "action": "cargoquery",
            "format": "json",
            "tables": "ScoreboardGames=SG",
            "fields": "SG.Team1,SG.Team2,SG.Winner,SG.DateTime_UTC",
            "where": f"SG.DateTime_UTC >= '{since}' AND SG.Winner IS NOT NULL",
            "order_by": "SG.DateTime_UTC ASC",
            "limit": "500",
            "offset": str(offset)
        })
        try:
            data, _ = fetch_url("https://lol.fandom.com/api.php?" + params)
            rows = json.loads(data).get("cargoquery", [])
        except Exception as e:
            print(f"Leaguepedia Cargo notice: {e}", file=sys.stderr)
            break
        if not rows:
            break
        for r in rows:
            t = r.get("title", r)
            a, b, w = t.get("Team1", ""), t.get("Team2", ""), str(t.get("Winner", ""))
            if not a or not b:
                continue
            ra = ratings.get(norm(a), 1500)
            rb = ratings.get(norm(b), 1500)
            ea = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
            winner_a = (w == "1")
            delta = 32.0 * ((1.0 if winner_a else 0.0) - ea)
            ratings[norm(a)] = ra + delta
            ratings[norm(b)] = rb - delta
            for team, won in ((a, winner_a), (b, not winner_a)):
                games[norm(team)] = games.get(norm(team), 0) + 1
                recent.setdefault(norm(team), []).append(1 if won else 0)
        offset += 500
        if len(rows) < 500:
            break
    return ratings, games, recent

# ----------------- Main Orchestration Pipeline -----------------
def main():
    debug = {"generated_at": NOW.isoformat(), "lobbies": LOBBIES}
    html = ""
    st = None
    for lobby in LOBBIES:
        try:
            html, st = fetch_url(lobby)
            debug["lobby_http"] = st
            debug["lobby_bytes"] = len(html)
            debug["active_lobby"] = lobby
            break
        except Exception as e:
            print(f"Failed to fetch {lobby}: {e}", file=sys.stderr)

    if not html:
        print("Notice: Lobby fetch failed from current environment. Preserving existing data.", file=sys.stderr)
        if os.path.exists("docs/data/picks.json"):
            sys.exit(0)
        raise RuntimeError("No lobby HTML and no existing picks cache found.")

    matches, parser = parse_lobby_content(html)
    debug["parser"] = parser
    debug["matches_parsed"] = len(matches)
    if not matches:
        print("Notice: 0 matches parsed from lobby. Keeping existing data snapshot.", file=sys.stderr)
        sys.exit(0)

    polymarket_events = fetch_polymarket()
    debug["polymarket_markets"] = len(polymarket_events)

    bookmaker_lines = fetch_oddspapi()
    debug["oddspapi_fixtures_priced"] = len(bookmaker_lines)

    ratings, games, recent = build_elo_model()
    debug["elo_teams"] = len(ratings)

    rows = []
    for m in matches:
        n1, n2 = norm(m["team1"]), norm(m["team2"])
        row = dict(m)
        row["start_utc"] = parse_start_date(m["start_raw"])
        row["source_lobby"] = debug.get("active_lobby", LOBBIES[0])
        
        prob = None
        method = ""
        source = ""
        confidence = ""

        # 1. External Esportsbook median lines (OddsPapi Pinnacle / bet365 / etc)
        for b in bookmaker_lines:
            if {norm(b["team1"]), norm(b["team2"])} == {n1, n2}:
                prob = b["p1"] if norm(b["team1"]) == n1 else 1.0 - b["p1"]
                method = "MARKET_BOOKS"
                source = b["source"]
                confidence = "High — Established Esportsbook consensus line, de-vigged"
                row["market_url"] = b["url"]
                break

        # 2. Prediction Market Lines (Polymarket Gamma)
        if prob is None:
            hit = match_polymarket(polymarket_events, m["team1"], m["team2"])
            if hit:
                prob, url, q = hit
                method = "MARKET_POLYMARKET"
                source = f"Polymarket: {q}"
                confidence = "High — Prediction market external consensus (independent of Hotspawn)"
                row["market_url"] = url

        # 3. Originated Elo Model Lines (Leaguepedia Cargo API)
        if prob is None and (n1 in ratings or n2 in ratings):
            r1 = ratings.get(n1, 1500)
            r2 = ratings.get(n2, 1500)
            g1 = games.get(n1, 0)
            g2 = games.get(n2, 0)
            raw = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
            # Bayesian shrinkage toward 50% based on sample size
            shrink = min(g1, g2) / (min(g1, g2) + 10.0) if min(g1, g2) > 0 else 0.25
            prob = 0.5 + (raw - 0.5) * shrink
            method = "MODEL_ELO"
            source = f"Proprietary Elo (Leaguepedia ScoreboardGames, 180d): {m['team1']} {round(r1)} ({g1}g) vs {m['team2']} {round(r2)} ({g2}g)"
            confidence = "Medium — Official competitive match history" if min(g1, g2) >= 10 else "Low — Thin historical record in database"
            row["elo"] = [round(r1), round(r2)]
            row["games"] = [g1, g2]
            row["source_url"] = "https://lol.fandom.com/api.php?action=help&modules=cargoquery"

        # 4. Unresolved Lower-Tier Matches (No Market, No Database Match Record)
        if prob is None:
            prob = 0.50
            method = "UNRESOLVED"
            source = f"Unresolved: No external bookmaker coverage and no Leaguepedia match record found for Tier '{m.get('tier')}' circuit"
            confidence = "Unresolved — 50/50 baseline; nominal pick only (no statistical edge)"
            row["source_url"] = "https://lol.fandom.com/wiki/Leaguepedia:League_of_Legends_Esports_Wiki"

        prob = round(max(0.01, min(0.99, prob)), 4)
        row["prob_team1"] = prob
        row["prob_team2"] = round(1.0 - prob, 4)
        row["pick"] = m["team1"] if prob >= 0.5 else m["team2"]
        row["pick_prob"] = max(prob, round(1.0 - prob, 4))
        row["method"] = method
        row["evidence"] = source
        row["confidence"] = confidence
        row["crowd_note"] = "Hotspawn crowd % shown on lobby is context only and is NEVER used as an input to our probabilities."
        rows.append(row)

    rows.sort(key=lambda r: (r["start_utc"] or "9999", r["tournament"], r["team1"]))

    payload = {
        "generated_at": NOW.isoformat(),
        "lobby": debug.get("active_lobby", LOBBIES[0]),
        "count": len(rows),
        "counts_by_method": {
            k: sum(1 for r in rows if r["method"] == k)
            for k in ["MARKET_BOOKS", "MARKET_POLYMARKET", "MODEL_ELO", "UNRESOLVED"]
        },
        "debug": debug,
        "matches": rows
    }

    for path in ["docs/data/picks.json", "data/picks.json"]:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    with open("data/debug.json", "w", encoding="utf-8") as f:
        json.dump(debug, f, indent=2)

    print(f"Generated {len(rows)} picks: {payload['counts_by_method']}")

if __name__ == "__main__":
    main()

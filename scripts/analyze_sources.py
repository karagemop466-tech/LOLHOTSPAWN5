#!/usr/bin/env python3
"""Probe external LoL market sources from a runner with full internet.

Writes a compact report (research/market_report.json + .md) so the repo stays light.
No values are invented: anything not returned by a source is reported as missing.
"""
import json, os, re, sys, time, urllib.request, urllib.error

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
PIN_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
OUT = {}

def get(url, headers=None, timeout=45, raw=False):
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read()
            return r.status, (b if raw else b.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)

def jget(url, headers=None, timeout=45):
    c, t = get(url, headers, timeout)
    if c != 200:
        return c, None
    try:
        return c, json.loads(t)
    except Exception:
        return c, None

# ---------------------------------------------------------------- Pinnacle
def pinnacle():
    res = {"sport_list": [], "lol_leagues": [], "sample_matchups": []}
    c, sports = jget("https://guest.api.arcadia.pinnacle.com/0.1/sports",
                     {"X-API-Key": PIN_KEY, "X-Device-UUID": "0000"})
    res["sports_status"] = c
    if isinstance(sports, list):
        for s in sports:
            res["sport_list"].append({
                "id": s.get("id"), "name": s.get("name"), "slug": s.get("slug"),
                "matchupCount": s.get("matchupCount"),
                "leagueCount": s.get("leagueCount"),
            })
    esp = [s for s in res["sport_list"] if (s.get("slug") or "").lower() in
           ("esports", "e-sports", "esport") or "e-sport" in (s.get("name") or "").lower()
           or (s.get("name") or "").lower() == "esports"]
    res["esports_sport_ids"] = [s["id"] for s in esp]

    for sid in res["esports_sport_ids"] or [12]:
        c, leagues = jget(f"https://guest.api.arcadia.pinnacle.com/0.1/sports/{sid}/leagues",
                          {"X-API-Key": PIN_KEY, "X-Device-UUID": "0000"})
        if not isinstance(leagues, list):
            res.setdefault("league_errors", []).append({sid: c})
            continue
        for lg in leagues:
            nm = (lg.get("name") or "")
            res["lol_leagues"].append({
                "sportId": sid, "leagueId": lg.get("id"), "name": nm,
                "matchupCount": lg.get("matchupCount"), "homeTeamType": lg.get("homeTeamType"),
            })
    for lg in res["lol_leagues"]:
        m = re.search(r"(league of legends|\blol\b)", lg["name"], re.I)
        lg["is_lol"] = bool(m)
    res["lol_leagues"] = [l for l in res["lol_leagues"] if l["is_lol"] or l["matchupCount"]]

    # pull matchups for the LoL leagues
    for lg in [l for l in res["lol_leagues"] if l["is_lol"]][:4]:
        c, mus = jget(
            f"https://guest.api.arcadia.pinnacle.com/0.1/leagues/{lg['leagueId']}/matchups",
            {"X-API-Key": PIN_KEY, "X-Device-UUID": "0000"})
        if not isinstance(mus, list):
            res.setdefault("matchup_errors", []).append({str(lg["leagueId"]): c})
            continue
        for mu in mus[:6]:
            parts = mu.get("participants") or []
            names = [p.get("name") for p in parts]
            entry = {
                "league": lg["name"], "leagueId": lg["leagueId"],
                "matchupId": mu.get("id"), "startTime": mu.get("startTime"),
                "participants": names, "type": mu.get("type"),
                "parent": mu.get("parent"), "markets": [],
            }
            c2, mk = jget(
                f"https://guest.api.arcadia.pinnacle.com/0.1/matchups/{mu.get('id')}/markets/related/straight",
                {"X-API-Key": PIN_KEY, "X-Device-UUID": "0000"})
            if isinstance(mk, list):
                for m in mk:
                    if m.get("period") != 0:
                        continue
                    prices = []
                    for pr in m.get("prices") or []:
                        prices.append({"designation": pr.get("designation"),
                                       "price": pr.get("price"),
                                       "participantId": pr.get("participantId")})
                    entry["markets"].append({"type": m.get("type"),
                                             "cutoff": m.get("cutoffAt"),
                                             "prices": prices})
            res["sample_matchups"].append(entry)
    return res

# ---------------------------------------------------------------- Polymarket
def polymarket():
    res = {"status": None, "events": []}
    for url in ["https://gamma-api.polymarket.com/public-search?q=league%20of%20legends&limit_per_type=50",
                "https://gamma-api.polymarket.com/events?limit=100&closed=false&tag_slug=league-of-legends"]:
        c, data = jget(url)
        res["status"] = c
        if not data:
            continue
        evs = data.get("events", data) if isinstance(data, dict) else data
        if not isinstance(evs, list):
            continue
        for ev in evs:
            title = ev.get("title") or ""
            if not re.search(r"(league of legends|\blol\b|lck|lpl|lec|lcs)", title, re.I):
                continue
            mk = []
            for m in (ev.get("markets") or [])[:6]:
                mk.append({"question": m.get("question"),
                           "outcomes": m.get("outcomes"),
                           "prices": m.get("outcomePrices"),
                           "closed": m.get("closed"),
                           "volume": m.get("volume")})
            res["events"].append({"title": title, "slug": ev.get("slug"),
                                  "startDate": ev.get("startDate"),
                                  "markets": mk})
        if res["events"]:
            break
    return res

# ---------------------------------------------------------------- Kalshi
def kalshi():
    res = {}
    c, data = jget("https://api.elections.kalshi.com/trade-api/v2/events?limit=200&series_ticker=KXLOL&status=open")
    res["events_status"] = c
    evs = (data or {}).get("events", [])
    res["open_events"] = [{"ticker": e.get("event_ticker"), "title": e.get("title"),
                           "sub_title": e.get("sub_title")} for e in evs[:25]]
    if evs:
        c2, mk = jget(f"https://api.elections.kalshi.com/trade-api/v2/markets?limit=100&event_ticker={evs[0]['event_ticker']}")
        res["markets_status"] = c2
        res["sample_markets"] = [{"ticker": m.get("ticker"), "title": m.get("title"),
                                  "yes_bid": m.get("yes_bid"), "yes_ask": m.get("yes_ask"),
                                  "last_price": m.get("last_price"), "status": m.get("status")}
                                 for m in (mk or {}).get("markets", [])[:15]]
    return res

# ---------------------------------------------------------------- OddsPortal
def oddsportal():
    c, html = get("https://www.oddsportal.com/esports/league-of-legends/")
    res = {"status": c, "bytes": len(html or "")}
    if html:
        # only report what is literally present in the page
        res["has_json_payload"] = '"odds"' in html or "oddsData" in html
        m = re.findall(r'"home":"([^"]{2,40})","away":"([^"]{2,40})"', html)
        res["home_away_pairs"] = m[:15]
        res["match_links"] = re.findall(r'/esports/league-of-legends/([a-z0-9-]{6,60})/', html)[:15]
    return res

report = {}
for name, fn in [("pinnacle", pinnacle), ("polymarket", polymarket),
                 ("kalshi", kalshi), ("oddsportal", oddsportal)]:
    t0 = time.time()
    try:
        report[name] = fn()
    except Exception as e:
        report[name] = {"fatal": f"{type(e).__name__}: {e}"}
    report[name]["seconds"] = round(time.time() - t0, 1)
    print("done", name, file=sys.stderr)

os.makedirs("research", exist_ok=True)
with open("research/market_report.json", "w") as f:
    json.dump(report, f, indent=1)

# readable summary
lines = ["# External market source probe", ""]
p = report.get("pinnacle", {})
lines.append(f"## Pinnacle\n\n- sports list status: {p.get('sports_status')}")
lines.append(f"- esports sport ids: {p.get('esports_sport_ids')}")
lol = [l for l in p.get("lol_leagues", []) if l.get("is_lol")]
lines.append(f"- LoL leagues found: {len(lol)}")
for l in lol[:25]:
    lines.append(f"  - `{l['leagueId']}` {l['name']} (matchups={l['matchupCount']})")
lines.append(f"- sample matchups captured: {len(p.get('sample_matchups', []))}")
for s in p.get("sample_matchups", [])[:8]:
    lines.append(f"  - {s['participants']} @ {s.get('startTime')} markets={len(s['markets'])}")
    for m in s["markets"][:2]:
        lines.append(f"      {m['type']}: {[(x['designation'], x['price']) for x in m['prices']]}")
lines.append(f"\n## Polymarket\n\n- status: {report.get('polymarket', {}).get('status')}")
for e in report.get("polymarket", {}).get("events", [])[:12]:
    lines.append(f"  - {e['title']} (slug={e['slug']}) markets={len(e['markets'])}")
lines.append(f"\n## Kalshi\n")
k = report.get("kalshi", {})
lines.append(f"- events status: {k.get('events_status')}; open events: {len(k.get('open_events', []))}")
for e in k.get("open_events", [])[:10]:
    lines.append(f"  - {e['ticker']} {e['title']}")
lines.append(f"\n## OddsPortal\n\n- status: {report.get('oddsportal', {}).get('status')} bytes={report.get('oddsportal', {}).get('bytes')}")
lines.append(f"- pairs: {report.get('oddsportal', {}).get('home_away_pairs')}")
open("research/market_report.md", "w").write("\n".join(lines) + "\n")
print("wrote research/market_report.{json,md}")

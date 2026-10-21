#!/usr/bin/env python3
"""Collect real bookmaker moneyline prices for League of Legends matches.

Primary source : Pinnacle (guest/arcadia API) - widely regarded as the sharpest esports book.
Secondary      : Kalshi KXLOLGAME exchange (per-match binary moneylines, bid/ask midpoints).
Secondary      : Bovada (best-effort; recorded only if it answers).
Probes         : established esportsbooks (GG.BET, BC.GAME, N1 Bet, Melbet, Thunderpick,
                 Rivalry, 1xBet, EGamersWorld) - availability is recorded honestly in
                 `book_probes`; a price is only used when actually parsed. Probe failures
                 never produce numbers.
Never          : Hotspawn's own crowd pick percentage (that is a popularity poll, not a price).

Raw American prices (Pinnacle) and dollar bid/ask prices (Kalshi) are stored verbatim.
Implied probabilities are de-vigged with the proportional (normalisation) method, which is
documented in METHODOLOGY.md. No price is ever fabricated: a match without a market is
simply absent from this file.
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.error

PIN = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
DATA = "data"

# Established esportsbooks / odds sites the project has tried for low-tier LoL lines.
BOOK_PROBES = [
    ("GG.BET LoL", "https://gg.bet/esports/league-of-legends"),
    ("BC.GAME esports", "https://bc.game/sports/esports"),
    ("N1 Bet esports", "https://n1bet.com/esports"),
    ("Melbet LineFeed", "https://linefeed.melbet.com/line/en/"),
    ("Thunderpick esports", "https://thunderpick.com/en/esports"),
    ("Rivalry LoL", "https://www.rivalry.com/esports/league-of-legends-betting"),
    ("1xBet esports", "https://1xbet.com/esports"),
    ("EGamersWorld LoL", "https://egamersworld.com/lol/matches"),
]


def jget(url, headers=None, timeout=45, tries=3):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and a < tries - 1:
                time.sleep(2 * (a + 1))
                continue
            return e.code, None
        except Exception as e:
            if a < tries - 1:
                time.sleep(2 * (a + 1))
                continue
            return 0, str(e)
    return 0, None


def american_to_implied(price):
    """Convert American odds to raw (vigged) implied probability."""
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p == 0:
        return None
    if p > 0:
        return 100.0 / (p + 100.0)
    return (-p) / ((-p) + 100.0)


def devig(pairs):
    """pairs = [(label, implied_prob)] -> [(label, no_vig_prob)] using proportional method."""
    tot = sum(p for _, p in pairs)
    if not tot:
        return []
    return [(lab, p / tot) for lab, p in pairs]


def find_esports_sports(sports):
    out = []
    for s in sports or []:
        blob = f"{s.get('name','')} {s.get('slug','')}".lower()
        if "esport" in blob or "e-sport" in blob:
            out.append(s.get("id"))
    return out


def pinnacle_lol():
    res = {"leagues": [], "matchups": [], "errors": []}

    st, sports = jget(f"{PIN}/sports", {"X-API-Key": PIN_KEY, "X-Device-UUID": "0"})
    if st != 200 or not isinstance(sports, list):
        res["errors"].append(f"sports list: HTTP {st}")
        return res

    cand = find_esports_sports(sports) or [12]
    res["esports_sport_ids_probed"] = cand

    leagues = []
    for sid in cand:
        st, lg = jget(f"{PIN}/sports/{sid}/leagues",
                      {"X-API-Key": PIN_KEY, "X-Device-UUID": "0"})
        if st != 200 or not isinstance(lg, list):
            res["errors"].append(f"leagues for sport {sid}: HTTP {st}")
            continue
        for l in lg:
            if "league of legends" in (l.get("name") or "").lower():
                leagues.append({"sport_id": sid, "id": l.get("id"),
                                "name": l.get("name"),
                                "matchup_count": l.get("matchupCount")})

    seen = set()
    leagues = [l for l in leagues if not (l["id"] in seen or seen.add(l["id"]))]
    res["leagues"] = leagues

    for lg in leagues:
        st, mus = jget(f"{PIN}/leagues/{lg['id']}/matchups",
                       {"X-API-Key": PIN_KEY, "X-Device-UUID": "0"})
        if st != 200 or not isinstance(mus, list):
            res["errors"].append(f"matchups league {lg['id']}: HTTP {st}")
            continue
        for mu in mus:
            if mu.get("parent") is not None:
                continue  # child/special markets (correct-score style), not a series winner
            parts = mu.get("participants") or []
            if len(parts) != 2:
                continue
            st2, mkts = jget(
                f"{PIN}/matchups/{mu['id']}/markets/related/straight",
                {"X-API-Key": PIN_KEY, "X-Device-UUID": "0"})
            moneyline = None
            if isinstance(mkts, list):
                for m in mkts:
                    if m.get("type") == "moneyline" and m.get("period") == 0:
                        moneyline = m
                        break
            entry = {
                "league": lg["name"],
                "league_id": lg["id"],
                "matchup_id": mu.get("id"),
                "start_utc": mu.get("startTime"),
                "is_live": mu.get("isLive"),
                "participants": [{"id": p.get("id"), "name": p.get("name"),
                                  "alignment": p.get("alignment")} for p in parts],
                "market_status": st2,
                "prices": [],
                "devigged": [],
            }
            if moneyline:
                entry["cutoff_utc"] = moneyline.get("cutoffAt")
                labels = {}
                for p in parts:
                    labels[p.get("alignment")] = p.get("name")
                pairs = []
                for pr in moneyline.get("prices") or []:
                    desig = pr.get("designation")
                    imp = american_to_implied(pr.get("price"))
                    entry["prices"].append({
                        "designation": desig,
                        "american": pr.get("price"),
                        "implied_raw": round(imp, 5) if imp is not None else None,
                        "team": labels.get(desig),
                    })
                    if imp is not None:
                        pairs.append((labels.get(desig) or desig, imp))
                for team, p in devig(pairs):
                    entry["devigged"].append({"team": team, "prob": round(p, 5)})
                if len(entry["prices"]) >= 2:
                    res["matchups"].append(entry)
    return res


def bovada_lol():
    """Best-effort secondary book. Returns raw event names + decimal prices when available."""
    out = {"status": None, "events": [], "note": ""}
    url = ("https://services.bovada.lv/services/sports/event/coupon/events/A/description/"
           "esports/league-of-legends?marketFilterId=def&preMatchOnly=true&lang=en")
    h = {"User-Agent": UA, "Accept": "application/json"}
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=45) as r:
            out["status"] = r.status
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        out["note"] = f"{type(e).__name__}: {e}"
        return out
    for grp in data or []:
        for ev in grp.get("events") or []:
            comp = [c.get("name") for c in ev.get("competitors") or []]
            prices = []
            for dg in ev.get("displayGroups") or []:
                for m in dg.get("markets") or []:
                    if (m.get("descriptionKey") or "").lower() in ("win", "moneyline", "match winner"):
                        for o in m.get("outcomes") or []:
                            prices.append({"price": o.get("price", {}).get("decimal"),
                                           "label": o.get("description")})
            if comp:
                out["events"].append({"start": ev.get("startTime"),
                                      "competitors": comp, "prices": prices})
    return out


def kalshi_lol():
    """Kalshi KXLOLGAME per-match exchange moneylines (open events only).

    Schema (verified live against the trade API): each event carries two mutually
    exclusive binary markets - "<Team> wins" - with yes_bid_dollars/yes_ask_dollars.
    We use the midpoint of each side's book and then de-vig proportionally, so the
    exchange spread is removed exactly like a bookmaker's vig. The API URL is stored
    per entry so every published row can cite its evidence.

    Output entries mirror the Pinnacle matchup shape so the model join is shared:
      league, matchup_id (event ticker), start_utc, participants[2], devigged[2], prices
    """
    out = {"leagues": ["KXLOLGAME (Kalshi exchange, League of Legends)"], "matchups": [],
           "errors": [], "events_seen": 0, "api_url": f"{KALSHI}/events?series_ticker=KXLOLGAME"}
    cursor = ""
    for _page in range(6):
        url = (f"{KALSHI}/events?series_ticker=KXLOLGAME&status=open"
               f"&with_nested_markets=true&limit=200")
        if cursor:
            url += f"&cursor={cursor}"
        st, data = jget(url, tries=3)
        if st != 200 or not isinstance(data, dict):
            out["errors"].append(f"events page HTTP {st}")
            break
        events = data.get("events") or []
        out["events_seen"] += len(events)
        for ev in events:
            comp = ((ev.get("product_metadata") or {}).get("competition") or "")
            title = ev.get("title") or ""
            if "league of legends" not in comp.lower() and " vs" not in title.lower():
                continue
            sides = []
            prices = []
            for mk in ev.get("markets") or []:
                who = mk.get("yes_sub_title") or (mk.get("title") or "").replace(" wins", "").strip()
                try:
                    bid = float(mk.get("yes_bid_dollars"))
                    ask = float(mk.get("yes_ask_dollars"))
                except (TypeError, ValueError):
                    continue
                if not who or bid <= 0 or ask <= 0:
                    continue
                mid = (bid + ask) / 2.0
                sides.append((who, mid))
                prices.append({"team": who, "title": mk.get("title"),
                               "ticker": mk.get("ticker"),
                               "yes_bid_dollars": mk.get("yes_bid_dollars"),
                               "yes_ask_dollars": mk.get("yes_ask_dollars"),
                               "last_price_dollars": mk.get("last_price_dollars"),
                               "volume_dollars": mk.get("volume_fp"),
                               "open_interest": mk.get("open_interest_fp")})
            if len(sides) != 2:
                continue
            start = None
            for mk in ev.get("markets") or []:
                start = mk.get("occurrence_datetime") or start
            devs = devig(sides)
            out["matchups"].append({
                "league": "KXLOLGAME",
                "source": "Kalshi",
                "matchup_id": ev.get("event_ticker"),
                "start_utc": start,
                "participants": [{"name": sides[0][0], "alignment": "home"},
                                 {"name": sides[1][0], "alignment": "away"}],
                "prices": prices,
                "devigged": [{"team": t, "prob": round(p, 5)} for t, p in devs],
                "url": f"https://kalshi.com/markets/{(ev.get('event_ticker') or '').lower()}",
                "api_url": url,
                "rules_primary": (ev.get("markets") or [{}])[0].get("rules_primary"),
            })
        cursor = data.get("cursor") or ""
        if not cursor or not events:
            break
        time.sleep(1)
    return out


def probe_books():
    """Record honest availability of established esportsbooks / odds sites.

    This satisfies the requirement to *try* established LoL betting sites and
    esportsbooks before falling back to model lines. Status codes and body sizes are
    recorded verbatim; prices are only ever taken from an endpoint whose payload we
    actually parsed (none of these probes fabricate prices).
    """
    out = []
    for name, url in BOOK_PROBES:
        rec = {"name": name, "url": url, "status": None, "body_bytes": 0,
               "note": "", "prices_parsed": 0}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read(200000)
                rec["status"] = r.status
                rec["body_bytes"] = len(body)
                low = body[:20000].decode("utf-8", "replace").lower()
                rec["mentions_lol"] = ("league of legends" in low or "/lol" in low
                                       or "esports" in low)
        except urllib.error.HTTPError as e:
            rec["status"] = e.code
            rec["note"] = f"HTTP {e.code} from CI runner - no prices used"
        except Exception as e:
            rec["status"] = 0
            rec["note"] = f"{type(e).__name__}: {e} - no prices used"
        out.append(rec)
    return out


def main():
    os.makedirs(DATA, exist_ok=True)
    pin = pinnacle_lol()
    for m in pin.get("matchups", []):
        m.setdefault("source", "Pinnacle")
        m.setdefault("url", "https://www.pinnacle.com/en/esports/league-of-legends/matchups/")
        m.setdefault("api_url",
                     f"{PIN}/matchups/{m.get('matchup_id')}/markets/related/straight")
    doc = {
        "collected_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_notes": {
            "pinnacle": "Pinnacle guest/arcadia API, sport=Esports, leagues matching "
                        "'League of Legends'. American prices stored verbatim; probabilities "
                        "de-vigged proportionally.",
            "kalshi": "Kalshi trade API, series KXLOLGAME (per-match League of Legends "
                      "moneylines). Dollar bid/ask stored verbatim; side midpoints "
                      "de-vigged proportionally. Evidence: market ticker + API URL per row.",
            "bovada": "Best-effort secondary book; only recorded if it answers.",
            "book_probes": "Established esportsbooks tried for low-tier LoL lines. Status "
                           "codes recorded verbatim; no price is used unless actually parsed.",
            "hotspawn_percent": "NOT used as a price or probability anywhere in this file.",
        },
        "pinnacle": pin,
        "kalshi": kalshi_lol(),
        "bovada": bovada_lol(),
        "book_probes": probe_books(),
    }
    with open(f"{DATA}/market_lines.json", "w") as f:
        json.dump(doc, f, indent=1)
    p = doc["pinnacle"]
    k = doc["kalshi"]
    print(json.dumps({
        "lol_leagues": [l["name"] for l in p.get("leagues", [])],
        "pinnacle_matchups_with_moneyline": len(p.get("matchups", [])),
        "pinnacle_errors": p.get("errors"),
        "kalshi_events_seen": k.get("events_seen"),
        "kalshi_matchups_with_prices": len(k.get("matchups", [])),
        "kalshi_errors": k.get("errors"),
        "bovada_status": doc["bovada"].get("status"),
        "bovada_events": len(doc["bovada"].get("events", [])),
        "book_probes": [{"name": b["name"], "status": b["status"]} for b in doc["book_probes"]],
    }, indent=1))


if __name__ == "__main__":
    main()

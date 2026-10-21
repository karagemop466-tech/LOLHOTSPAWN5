#!/usr/bin/env python3
"""Collect real bookmaker moneyline prices for League of Legends matches.

Primary source : Pinnacle (guest/arcadia API) - widely regarded as the sharpest esports book.
Secondary      : Bovada (best-effort; recorded only if it answers).
Never          : Hotspawn's own crowd pick percentage (that is a popularity poll, not a price).

Raw American prices are stored verbatim. Implied probabilities are de-vigged with the
proportional (normalisation) method, which is documented in METHODOLOGY.md. No price is
ever fabricated: a match without a market is simply absent from this file.
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.error

PIN = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
DATA = "data"


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


def main():
    os.makedirs(DATA, exist_ok=True)
    doc = {
        "collected_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_notes": {
            "pinnacle": "Pinnacle guest/arcadia API, sport=Esports, leagues matching "
                        "'League of Legends'. American prices stored verbatim; probabilities "
                        "de-vigged proportionally.",
            "bovada": "Best-effort secondary book; only recorded if it answers.",
            "hotspawn_percent": "NOT used as a price or probability anywhere in this file.",
        },
        "pinnacle": pinnacle_lol(),
        "bovada": bovada_lol(),
    }
    with open(f"{DATA}/market_lines.json", "w") as f:
        json.dump(doc, f, indent=1)
    p = doc["pinnacle"]
    print(json.dumps({
        "lol_leagues": [l["name"] for l in p.get("leagues", [])],
        "matchups_with_moneyline": len(p.get("matchups", [])),
        "pinnacle_errors": p.get("errors"),
        "bovada_status": doc["bovada"].get("status"),
        "bovada_events": len(doc["bovada"].get("events", [])),
    }, indent=1))


if __name__ == "__main__":
    main()

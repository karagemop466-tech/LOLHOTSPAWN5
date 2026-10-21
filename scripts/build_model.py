#!/usr/bin/env python3
"""Build an independent win probability / pick for every Hotspawn LoL match.

Two independent, documented methods are combined:

  1. MARKET  - Pinnacle moneyline, de-vigged proportionally. Used ONLY when both teams of a
               Hotspawn fixture are matched to a Pinnacle matchup (name match + start time
               within TOLERANCE). This is the sharpest available external price.
  2. MODEL   - Our own Elo rating built from Leaguepedia historical results (last ~400 days),
               with inactivity decay and small-sample shrinkage. This is what lets us publish a
               real probability for low-tier fixtures that no sportsbook prices.

Hotspawn's own "picked %" is a crowd popularity share. It is carried through for transparency
and is NEVER used to set a probability.

A match is marked UNRESOLVED only when the model has no usable history for it; the reason is
recorded verbatim in the output so it can be published on the "Flagged for Review" page.
"""
import json, math, os, re, sys, datetime as dt

DATA = "data"
TOLERANCE_HOURS = 8.0
ELO_START = 1500.0
ELO_SCALE = 400.0
K_BASE = 24.0
K_BY_BEST_OF = {1: 20.0, 2: 24.0, 3: 28.0, 5: 36.0}
HALF_LIFE_DAYS = 365.0
SHRINK = 8.0            # pseudo-matches pulling a team back to the mean
MIN_MATCHES_RELIABLE = 3

# Explicit, auditable bridge between Pinnacle's short names and Hotspawn's display names.
ALIASES = {
    "g2": "g2 esports",
    "hanwha life": "hanwha life esports",
    "bilibili": "bilibili gaming",
    "secret whales": "team secret whales",
    "liquid": "team liquid",
    "invictus": "invictus gaming",
    "anyones legend": "anyones legend",
    "los": "los",
    "t1": "t1",
    "lyon": "lyon",
    "furia": "furia",
    "mvk": "mvk esports",
    "cloud9": "cloud9",
    "ctbc flying oyster": "ctbc flying oyster",
    "movistar koi": "movistar koi",
    "top esports": "top esports",
    "karmine corp": "karmine corp",
    "dplus kia": "dplus kia",
    "gen g": "geng",
    "solary": "solary",
    "galions": "galions",
}

DROPPED_TOKENS = {
    "esports", "esport", "e", "sports", "gaming", "gg", "team", "academy", "club",
    "the", "of", "and", "org", "organization", "official",
}


def norm(name):
    if not name:
        return ""
    s = name.strip().lower()
    s = (s.replace("ø", "o").replace("æ", "ae").replace("å", "a")
          .replace("ü", "u").replace("é", "e").replace("ñ", "n"))
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    key = " ".join(s.split())
    if key in ALIASES:
        return ALIASES[key]
    toks = [t for t in key.split() if t not in DROPPED_TOKENS]
    if not toks:
        toks = key.split()
    out = " ".join(toks)
    if out in ALIASES:
        return ALIASES[out]
    return out


def parse_iso(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(s[:19], fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def parse_lp_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s[:19] if len(s) > 10 else s,
                                        fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


# ------------------------------------------------------------------ Elo
def build_ratings(results):
    games = []
    for r in results:
        d = parse_lp_date(r.get("d"))
        t1, t2 = r.get("t1"), r.get("t2")
        w = r.get("w")
        if not (d and t1 and t2):
            continue
        if w == "1" or w == t1:
            s1 = 1.0
        elif w == "2" or w == t2:
            s1 = 0.0
        else:
            continue  # no recorded winner -> cannot be used for ratings
        bo = r.get("bo")
        try:
            bo = int(bo) if bo not in (None, "") else 2
        except (TypeError, ValueError):
            bo = 2
        games.append((d, t1, t2, s1, bo))

    games.sort(key=lambda g: g[0])
    rating, count, last = {}, {}, {}

    for d, t1, t2, s1, bo in games:
        a, b = norm(t1), norm(t2)
        if not a or not b or a == b:
            continue
        ra, rb = rating.get(a, ELO_START), rating.get(b, ELO_START)
        # inactivity decay toward the mean before the match is played
        for k, r, lastd in ((a, ra, last.get(a)), (b, rb, last.get(b))):
            if lastd:
                days = (d - lastd).total_seconds() / 86400.0
                if days > 0:
                    f = 0.5 ** (days / HALF_LIFE_DAYS)
                    if k == a:
                        ra = ELO_START + (ra - ELO_START) * f
                    else:
                        rb = ELO_START + (rb - ELO_START) * f
        ea = 1.0 / (1.0 + 10 ** ((rb - ra) / ELO_SCALE))
        k = K_BY_BEST_OF.get(bo, K_BASE)
        na, nb = count.get(a, 0), count.get(b, 0)
        # provisional players-move-faster: bigger K for teams with little history
        ka = k * (1.6 if na < 10 else 1.0)
        kb = k * (1.6 if nb < 10 else 1.0)
        rating[a] = ra + ka * (s1 - ea)
        rating[b] = rb + kb * ((1.0 - s1) - (1.0 - ea))
        count[a], count[b] = na + 1, nb + 1
        last[a] = last[b] = d

    return rating, count, last


def predict(ra, na, rb, nb):
    """Shrunk Elo win probability for team A."""
    rae = ELO_START + (ra - ELO_START) * (na / (na + SHRINK))
    rbe = ELO_START + (rb - ELO_START) * (nb / (nb + SHRINK))
    return 1.0 / (1.0 + 10 ** ((rbe - rae) / ELO_SCALE)), rae, rbe


def confidence(na, nb):
    lo = min(na, nb)
    if lo >= 20:
        return "high"
    if lo >= 8:
        return "medium"
    if lo >= MIN_MATCHES_RELIABLE:
        return "low"
    return "insufficient"


# ------------------------------------------------------------------ market join
def join_market(hs_matches, pinnacle):
    index = []
    for m in pinnacle.get("matchups", []):
        parts = m.get("participants") or []
        if len(parts) != 2:
            continue
        start = parse_iso(m.get("start_utc"))
        if not start:
            continue
        p = {}
        for d in m.get("devigged") or []:
            if d.get("team"):
                p[norm(d["team"])] = d["prob"]
        if len(p) != 2:
            continue
        index.append({
            "names": [norm(parts[0]["name"]), norm(parts[1]["name"])],
            "start": start,
            "probs": p,
            "raw": m,
        })

    matched, used = {}, set()
    for hm in hs_matches:
        h = norm(hm["home"]["name"])
        a = norm(hm["away"]["name"])
        t = parse_iso(hm.get("start_utc"))
        if not (t and h and a):
            continue
        for i, e in enumerate(index):
            if i in used:
                continue
            same_teams = set(e["names"]) == {h, a}
            if not same_teams:
                continue
            dt_h = abs((e["start"] - t).total_seconds()) / 3600.0
            if dt_h > TOLERANCE_HOURS:
                continue
            matched[hm["id"]] = {"entry": e, "hours_apart": round(dt_h, 2)}
            used.add(i)
            break
    return matched


def main():
    hs = json.load(open(f"{DATA}/hotspawn_matches.json"))
    try:
        res = json.load(open(f"{DATA}/match_results.json"))
    except Exception:
        res = {"results": [], "row_count": 0}
    try:
        lines = json.load(open(f"{DATA}/market_lines.json"))
    except Exception:
        lines = {"pinnacle": {"matchups": []}}

    rating, count, last = build_ratings(res.get("results", []))
    market = join_market(hs["matches"], lines.get("pinnacle", {}))

    now = dt.datetime.now(dt.timezone.utc)
    picks, unresolved = [], []

    for hm in hs["matches"]:
        home, away = hm["home"]["name"], hm["away"]["name"]
        h, a = norm(home), norm(away)
        ra, rb = rating.get(h, ELO_START), rating.get(a, ELO_START)
        na, nb = count.get(h, 0), count.get(a, 0)
        p_home_model, rae, rbe = predict(ra, na, rb, nb)
        conf = confidence(na, nb)

        start = parse_iso(hm.get("start_utc"))
        is_past = bool(start and start < now)

        rec = {
            "id": hm["id"],
            "competition": hm.get("competition"),
            "tier": hm.get("tier"),
            "stage": hm.get("stage"),
            "start_utc": hm.get("start_utc"),
            "lock_utc": hm.get("lock_utc"),
            "home": home,
            "away": away,
            "hotspawn_url": hm.get("hotspawn_url"),
            "hotspawn_pick_share_home": hm["home"].get("hotspawn_pick_share"),
            "hotspawn_pick_share_away": hm["away"].get("hotspawn_pick_share"),
            "home_rating": round(rae, 1),
            "away_rating": round(rbe, 1),
            "home_matches": na,
            "away_matches": nb,
            "model_prob_home": round(p_home_model, 4),
            "model_prob_away": round(1 - p_home_model, 4),
            "is_past_start": is_past,
            "has_hotspawn_page": bool(hm.get("hotspawn_url")),
        }

        mk = market.get(hm["id"])
        if mk:
            probs = mk["entry"]["probs"]
            ph = probs.get(h)
            if ph is None:
                ph = probs.get(a)
                ph = None if ph is None else 1 - ph
            if ph is not None:
                rec.update({
                    "method": "market",
                    "prob_home": round(ph, 4),
                    "prob_away": round(1 - ph, 4),
                    "pick": home if ph >= 0.5 else away,
                    "pick_prob": round(max(ph, 1 - ph), 4),
                    "confidence": "market-priced",
                    "market_source": "Pinnacle",
                    "market_url": "https://www.pinnacle.com/en/esports/league-of-legends/matchups/",
                    "market_league": mk["entry"]["raw"].get("league"),
                    "market_start_utc": mk["entry"]["raw"].get("start_utc"),
                    "market_hours_apart": mk["hours_apart"],
                    "market_american": [
                        {"team": p.get("team"), "american": p.get("american"),
                         "implied_raw": p.get("implied_raw")}
                        for p in mk["entry"]["raw"].get("prices", [])
                    ],
                    "model_prob_home": round(p_home_model, 4),
                    "model_vs_market_diff": round(p_home_model - ph, 4),
                })
                picks.append(rec)
                continue

        if conf == "insufficient" and na == 0 and nb == 0:
            rec.update({
                "method": "unresolved",
                "prob_home": None,
                "prob_away": None,
                "pick": None,
                "pick_prob": None,
                "confidence": "insufficient",
                "unresolved_reason": (
                    "No external bookmaker market prices this fixture and our Elo model has no "
                    "Leaguepedia results for either team, so no probability can be justified."),
            })
            unresolved.append(rec)
            picks.append(rec)
            continue

        rec.update({
            "method": "model",
            "prob_home": round(p_home_model, 4),
            "prob_away": round(1 - p_home_model, 4),
            "pick": home if p_home_model >= 0.5 else away,
            "pick_prob": round(max(p_home_model, 1 - p_home_model), 4),
            "confidence": conf,
            "market_source": None,
            "model_source": "Our Elo model (Leaguepedia MatchSchedule results, "
                            f"{res.get('row_count', 0)} rows)",
            "model_url": "https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule",
            "no_market_reason": (
                "No Pinnacle moneyline matched this fixture at collection time "
                f"(teams matched: {na} home / {nb} away historical results)."),
        })
        if is_past:
            rec["unresolved_reason"] = (
                "Fixture start time is already in the past but Hotspawn still lists it as "
                "scheduled; treated as a stale row.")
        picks.append(rec)

    picks.sort(key=lambda r: (r.get("start_utc") or "9999", r["id"]))
    live = [r for r in picks if not r["is_past_start"]]
    counts = {
        "market": sum(1 for r in picks if r["method"] == "market"),
        "model": sum(1 for r in picks if r["method"] == "model"),
        "unresolved": sum(1 for r in picks if r["method"] == "unresolved"),
    }
    doc = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inventory_source": hs.get("source"),
        "inventory_collected_utc": hs.get("collected_utc"),
        "results_source": res.get("source"),
        "results_collected_utc": res.get("collected_utc"),
        "results_rows": res.get("row_count", 0),
        "teams_rated": len(rating),
        "totals": {
            "matches": len(picks),
            "live_matches": len(live),
            "by_method": counts,
            "market_priced": counts["market"],
            "model_priced": counts["model"],
            "unresolved": counts["unresolved"],
            "with_a_pick": sum(1 for r in picks if r.get("pick")),
        },
        "methodology": {
            "elo_start": ELO_START, "elo_scale": ELO_SCALE,
            "shrink_pseudo_matches": SHRINK, "half_life_days": HALF_LIFE_DAYS,
            "k_by_best_of": K_BY_BEST_OF, "market_tolerance_hours": TOLERANCE_HOURS,
        },
        "picks": picks,
    }
    with open(f"{DATA}/picks.json", "w") as f:
        json.dump(doc, f, indent=1)

    print(json.dumps(doc["totals"], indent=1))
    print(f"teams_rated={len(rating)} results_rows={res.get('row_count',0)}",
          file=sys.stderr)


if __name__ == "__main__":
    main()

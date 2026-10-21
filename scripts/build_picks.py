#!/usr/bin/env python3
"""Join the HotSpawn inventory with external lines and our own line.

Produces data/picks.json: one row per HotSpawn League of Legends fixture with a
win probability for both teams, the pick, the source that backs it and any flags.

Priority for the headline probability:
  1. an external *series* market (Polymarket match market, Pinnacle period 0,
     Bovada series moneyline) - de-vigged;
  2. an external *map* market (Kalshi, Pinnacle period 1, Bovada game moneyline) -
     reported as-is and flagged, because a map price is not a series price;
  3. our own line (Elo over verified results);
  4. 50/50 default, flagged as unverified.

When several books cover the same fixture their de-vigged probabilities are
averaged into a consensus and every individual quote is kept for review.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import DATA_DIR, REPO_ROOT, norm_name, team_match_score, utcnow, write_json  # noqa: E402
from model import build_ratings, predict, series_from_map  # noqa: E402

MATCH_THRESHOLD = 0.8
SOURCE_RANK = {"pinnacle": 0, "bovada": 1, "polymarket": 2, "kalshi": 3}
SCOPE_RANK = {"series": 0, "game": 1}


def load(rel: str, default=None):
    path = os.path.join(REPO_ROOT, rel)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def pair_score(q: dict, team_a: str, team_b: str) -> float:
    """1.0 when the quote matches the fixture pair, 0.0 when it does not."""
    qa, qb = q.get("team_a", ""), q.get("team_b", "")
    direct = team_match_score(team_a, qa) * team_match_score(team_b, qb)
    swapped = team_match_score(team_a, qb) * team_match_score(team_b, qa)
    return max(direct, swapped)


def quote_orientation(q: dict, team_a: str, team_b: str) -> bool:
    """True when the quote's team_a corresponds to the fixture's team_a."""
    return (team_match_score(team_a, q.get("team_a", "")) >=
            team_match_score(team_a, q.get("team_b", "")))


def main() -> int:
    inventory = load("data/hotspawn_matches.json", {"matches": []})
    odds = load("data/odds.json", {"quotes": []})
    strength = load("data/team_strength.json", {"teams": {}})
    reference = load("data/reference_games.json", {"games": []})

    teams_strength = strength.get("teams", {})
    quotes = odds.get("quotes", [])

    fixtures = [m for m in inventory.get("matches", []) if m.get("status") == "scheduled"]
    if reference.get("games"):
        rebuilt = build_ratings(reference["games"])
        if rebuilt:
            teams_strength = {**teams_strength.get("_from_games", {}), **rebuilt}
        else:
            teams_strength = {**teams_strength, **rebuilt}

    picks = []
    for fixture in fixtures:
        team_a = fixture["teams"][0]["name"]
        team_b = fixture["teams"][1]["name"]
        flags = []

        matched = []
        for quote in quotes:
            score = pair_score(quote, team_a, team_b)
            if score >= MATCH_THRESHOLD:
                matched.append((score, quote))
        matched.sort(key=lambda item: -item[0])

        market_rows = []
        consensus_a = None
        best_of = None
        for score, quote in matched:
            flipped = not quote_orientation(quote, team_a, team_b)
            prob_a = quote.get("prob_a")
            prob_b = quote.get("prob_b")
            if prob_a is None or prob_b is None:
                continue
            if flipped:
                prob_a, prob_b = prob_b, prob_a
            market_rows.append({
                "source": quote.get("source"),
                "source_kind": quote.get("source_kind"),
                "scope": quote.get("market_scope"),
                "market_period": quote.get("market_period"),
                "source_url": quote.get("source_url"),
                "event_title": quote.get("event_title"),
                "league": quote.get("league"),
                "prob_a": round(prob_a, 4),
                "prob_b": round(prob_b, 4),
                "decimal_a": quote.get("decimal_a"),
                "decimal_b": quote.get("decimal_b"),
                "overround": quote.get("overround"),
                "best_of": quote.get("best_of"),
                "match_score": round(score, 3),
            })
            if quote.get("best_of"):
                best_of = quote["best_of"]
            if consensus_a is None:
                consensus_a = prob_a
            else:
                consensus_a = (consensus_a + prob_a) / 2

        market_rows.sort(key=lambda row: (SCOPE_RANK.get(row.get("scope"), 2),
                                         SOURCE_RANK.get(row.get("source"), 9)))
        primary = market_rows[0] if market_rows else None

        rating_a = teams_strength.get(team_a, {}).get("rating")
        rating_b = teams_strength.get(team_b, {}).get("rating")
        model_prob, model_reason = predict(rating_a, rating_b)
        if model_prob is None:
            model_prob, model_reason = 0.5, "no verified match history for at least one team"
            flags.append("no verified match history for at least one team")
        elif "clamped" in model_reason:
            flags.append("model probability clamped to its stated bounds")

        headline = None
        confidence = "default"
        basis = "default"
        if primary and primary["scope"] == "series":
            headline = primary["prob_a"]
            confidence = "market"
            basis = "external series line"
            if len(market_rows) > 1:
                consensus = consensus_a
                if consensus is not None and abs(consensus - headline) >= 0.02:
                    headline = consensus
                    flags.append("consensus of several external lines differs from the primary line by >=2 points")
        elif primary and primary["scope"] == "game":
            headline = primary["prob_a"]
            confidence = "market-map"
            basis = "external map (single game) line"
            flags.append("only a single-map price is published for this fixture")
            if best_of:
                adjusted = series_from_map(primary["prob_a"], best_of)
                flags.append(f"map price converted to a best-of-{best_of} series probability")
            else:
                flags.append("series format unverified - map price shown as-is")
        elif primary:
            headline = primary["prob_a"]
            confidence = "market-map"
            basis = "external map (single game) line"
            flags.append("only a single-map price is published for this fixture")
        else:
            headline = model_prob
            confidence = "model"
            basis = "our own line (Elo over verified results)"
            flags.append("no external betting line published for this fixture")

        prob_a = headline
        prob_b = round(1 - headline, 4)
        pick = team_a if prob_a >= prob_b else team_b
        pick_prob = max(prob_a, prob_b)

        strength_a = teams_strength.get(team_a, {})
        strength_b = teams_strength.get(team_b, {})
        if strength_a.get("source_url"):
            source_a = strength_a["source_url"]
        else:
            source_a = None
        if strength_b.get("source_url"):
            source_b = strength_b["source_url"]
        else:
            source_b = None

        lock_time = fixture.get("lock_time")
        picks.append({
            "fixture_id": fixture.get("id"),
            "tournament": fixture.get("tournament"),
            "tier": fixture.get("tier"),
            "stage": fixture.get("stage"),
            "offered_points": fixture.get("offered_points"),
            "lock_time": lock_time,
            "start_time": fixture.get("start_time"),
            "hotspawn_url": fixture.get("permalinks"),
            "hotspawn_lobby": "https://play.hotspawn.com/lol-pickems",
            "team_a": {"name": team_a, "prob": prob_a, "rating": strength_a.get("rating"),
                       "games": strength_a.get("games"), "source_url": source_a},
            "team_b": {"name": team_b, "prob": prob_b, "rating": strength_b.get("rating"),
                       "games": strength_b.get("games"), "source_url": source_b},
            "pick": pick,
            "pick_prob": pick_prob,
            "confidence": confidence,
            "basis": basis,
            "model": {"prob_a": model_prob, "reason": model_reason,
                      "rating_a": rating_a, "rating_b": rating_b},
            "market": primary,
            "market_sources": market_rows,
            "flags": flags,
            "unresolved": confidence in ("model", "default", "market-map"),
        })

    summary = {
        "fixtures": len(picks),
        "with_series_market": sum(1 for p in picks if p["confidence"] == "market"),
        "with_map_market_only": sum(1 for p in picks if p["confidence"] == "market-map"),
        "own_line": sum(1 for p in picks if p["confidence"] == "model"),
        "default_50_50": sum(1 for p in picks if p["confidence"] == "default"),
        "unresolved": sum(1 for p in picks if p["unresolved"]),
        "coverage_pct": round(100.0 * sum(1 for p in picks if p["confidence"] in ("market", "market-map"))
                              / max(1, len(picks)), 1),
    }
    payload = {
        "generated_at": utcnow(),
        "note": "HotSpawn supplies the fixture list only. Probabilities come from external "
                "betting lines (Kalshi, Polymarket, Pinnacle, Bovada) or from our own Elo line "
                "built on verified match results. HotSpawn crowd percentages are never used.",
        "summary": summary,
        "picks": picks,
    }
    path = write_json("data/picks.json", payload)
    print(f"wrote {path}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

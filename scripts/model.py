#!/usr/bin/env python3
"""Our own line: a transparent Elo-style model over verified match results.

The model is deliberately simple so every number on the site can be re-derived:

  * every team starts at 1500;
  * results are processed oldest -> newest, K = 32, no home advantage (LoL has none);
  * a team's published rating is shrunk toward 1500 when it has few games:
        r' = (r * n + 1500 * m0) / (n + m0),   m0 = 8
  * the series win probability for A vs B is the logistic of the rating gap:
        p(A) = 1 / (1 + 10 ** (-(rA - rB) / 400))

No HotSpawn crowd percentage is used anywhere in this module.
"""
from __future__ import annotations

START_RATING = 1500.0
K_FACTOR = 32.0
SHRINK_PRIOR = 8.0
MIN_PROB = 0.02
MAX_PROB = 0.98


def expected(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def build_ratings(games: list[dict]) -> dict[str, dict]:
    """games: list of {date, team_a, team_b, winner} (winner is team_a or team_b)."""
    ratings: dict[str, float] = {}
    counts: dict[str, int] = {}
    wins: dict[str, int] = {}
    history: dict[str, list[tuple[str, bool]]] = {}
    last_date: dict[str, str] = {}

    ordered = sorted(games, key=lambda g: (str(g.get("date") or ""), str(g.get("team_a") or "")))
    for game in ordered:
        team_a, team_b = game.get("team_a"), game.get("team_b")
        winner = game.get("winner")
        if not team_a or not team_b or winner not in (team_a, team_b):
            continue
        date = str(game.get("date") or "")
        for team in (team_a, team_b):
            ratings.setdefault(team, START_RATING)
            counts.setdefault(team, 0)
            wins.setdefault(team, 0)
            history.setdefault(team, [])
            if date:
                last_date[team] = max(last_date.get(team, ""), date)

        ra = ratings[team_a]
        rb = ratings[team_b]
        exp_a = expected(ra, rb)
        score_a = 1.0 if winner == team_a else 0.0
        delta = K_FACTOR * (score_a - exp_a)
        ratings[team_a] = ra + delta
        ratings[team_b] = rb - delta
        counts[team_a] += 1
        counts[team_b] += 1
        wins[team_a] += 1 if winner == team_a else 0
        wins[team_b] += 1 if winner == team_b else 0
        history[team_a].append((date, winner == team_a))
        history[team_b].append((date, winner == team_b))

    out: dict[str, dict] = {}
    for team, rating in ratings.items():
        n = counts[team]
        shrunk = (rating * n + START_RATING * SHRINK_PRIOR) / (n + SHRINK_PRIOR)
        recent = history[team][-10:]
        recent_wr = (sum(1 for _, won in recent if won) / len(recent)) if recent else None
        out[team] = {
            "raw_rating": round(rating, 2),
            "rating": round(shrunk, 2),
            "games": n,
            "wins": wins[team],
            "win_rate": round(wins[team] / n, 4) if n else None,
            "last10_win_rate": round(recent_wr, 4) if recent_wr is not None else None,
            "last_match": last_date.get(team) or None,
            "sample": "low" if n < 10 else ("medium" if n < 30 else "good"),
        }
    return out


def predict(rating_a: float | None, rating_b: float | None) -> tuple[float | None, str]:
    """Return (probability for A, reason). None means 'no verified data'."""
    if rating_a is None or rating_b is None:
        return None, "no verified match history for at least one team"
    prob = expected(rating_a, rating_b)
    clamped = False
    if prob < MIN_PROB:
        prob, clamped = MIN_PROB, True
    elif prob > MAX_PROB:
        prob, clamped = MAX_PROB, True
    reason = "elo" if not clamped else "elo (clamped to model bounds)"
    return round(prob, 4), reason


def series_from_map(p_map: float, best_of: int) -> float:
    """Convert a single-map win probability into a best-of-N series probability."""
    if not best_of or best_of <= 1:
        return p_map
    if best_of == 3:
        return p_map ** 3 + 3 * p_map ** 2 * (1 - p_map)
    if best_of == 5:
        return (p_map ** 5 + 5 * p_map ** 4 * (1 - p_map)
                + 10 * p_map ** 3 * (1 - p_map) ** 2)
    if best_of == 2:
        return p_map ** 2 + 2 * p_map * (1 - p_map)
    return p_map

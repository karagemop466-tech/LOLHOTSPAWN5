#!/usr/bin/env python3
"""Build verified reference data for our own line.

Leaguepedia (the League of Legends esports wiki) is read through its public
MediaWiki API:

  * search / titles  -> resolve a HotSpawn tournament or team to a wiki page
  * action=parse     -> the rendered page of a tournament (full match list) or of
                         a team's "Match History" subpage (their recent games)

Both are series-level results with dates, so the Elo model in scripts/model.py can
be fitted on them. Anything the wiki does not publish is simply absent - it is
never guessed.

Note: Cargo queries (action=cargoquery) are rate limited for anonymous callers and
are deliberately not used here.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (EVIDENCE_DIR, Http, REPO_ROOT, norm_name, team_match_score,  # noqa: E402
                    utcnow, write_json)
from model import build_ratings  # noqa: E402

API = "https://lol.fandom.com/api.php"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "application/json"}


def api_get(http: Http, **params) -> dict | None:
    params.setdefault("format", "json")
    url = API + "?" + urllib.parse.urlencode(params)
    data, _meta = http.get_json(url, headers=HEADERS, retries=3, timeout=90)
    return data


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def parse_matchlist(html: str) -> list[dict]:
    """Series results from a Leaguepedia tournament page matchlist table."""
    games: list[dict] = []
    for attrs, body in re.findall(r'<tr class="[^"]*ml-row[^"]*"([^>]*)>(.*?)</tr>', html, re.S):
        date_match = re.search(r'data-date="([^"]+)"', attrs)
        if not date_match:
            continue
        date = date_match.group(1)
        cells = re.findall(r"<td([^>]*)>(.*?)</td>", body, re.S)
        team_a = team_b = None
        score_a = score_b = None
        winner = None
        for cattr, cbody in cells:
            text = re.sub(r"<[^>]+>", "", cbody).strip()
            if "matchlist-team1" in cattr:
                m = re.search(r'data-teamhighlight="([^"]+)"', cattr)
                team_a = m.group(1) if m else None
            elif "matchlist-team2" in cattr:
                m = re.search(r'data-teamhighlight="([^"]+)"', cattr)
                team_b = m.group(1) if m else None
            elif "matchlist-score" in cattr:
                if score_a is None:
                    score_a = text
                    if "matchlist-winner-score" in cattr:
                        winner = "a"
                else:
                    score_b = text
                    if "matchlist-winner-score" in cattr:
                        winner = "b"
        if not team_a or not team_b or score_a is None or score_b is None:
            continue
        try:
            sa, sb = int(score_a), int(score_b)
        except ValueError:
            continue
        if sa == sb:
            continue
        games.append({
            "date": date,
            "team_a": team_a,
            "team_b": team_b,
            "winner": team_a if sa > sb else team_b,
            "score_a": sa,
            "score_b": sb,
            "best_of": max(sa, sb) + 1,
            "kind": "series",
        })
    return games


def parse_match_history(html: str) -> list[dict]:
    """Individual games from a team's Leaguepedia Match History subpage."""
    rows: list[dict] = []
    for row_attrs, body in re.findall(r'<tr class="(mhgame[^"]*)"[^>]*>(.*?)</tr>', html, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        if len(cells) < 6:
            continue
        date = re.sub(r"<[^>]+>", "", cells[0]).strip()
        tournament = ""
        m = re.search(r'title="([^"]+)"', cells[1])
        if m:
            tournament = m.group(1)
        result = re.sub(r"<[^>]+>", "", cells[3]).strip().lower()
        opponent = ""
        m = re.search(r'title="([^"]+)"', cells[5])
        if m:
            opponent = m.group(1)
        if not date or not opponent or result not in ("win", "loss"):
            continue
        rows.append({"date": date, "tournament": tournament, "opponent": opponent,
                     "won": result == "win"})
    return rows


def group_maps_into_series(rows: list[dict], team: str) -> list[dict]:
    """Rebuild series from a team's map-level match history."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (row["date"], row["tournament"], row["opponent"])
        groups.setdefault(key, []).append(row)
    games: list[dict] = []
    for (date, tournament, opponent), maps in groups.items():
        wins = sum(1 for m in maps if m["won"])
        losses = len(maps) - wins
        if wins == losses:
            continue
        winner = team if wins > losses else opponent
        games.append({
            "date": date,
            "team_a": team,
            "team_b": opponent,
            "winner": winner,
            "score_a": wins,
            "score_b": losses,
            "best_of": len(maps),
            "kind": "series",
            "tournament": tournament,
        })
    return games


# --------------------------------------------------------------------------- #
# resolution
# --------------------------------------------------------------------------- #
def resolve_titles(http: Http, names: list[str]) -> dict[str, str]:
    """Resolve exact wiki page titles (batched) for the given names."""
    resolved: dict[str, str] = {}
    unique = list(dict.fromkeys(names))
    for index in range(0, len(unique), 40):
        batch = unique[index:index + 40]
        data = api_get(http, action="query", titles="|".join(batch), redirects=1)
        if not data:
            continue
        pages = (data.get("query") or {}).get("pages") or {}
        normalized = {p.get("title"): p for p in pages.values() if p.get("title")}
        redirects = {r.get("from"): r.get("to") for r in
                     (data.get("query") or {}).get("redirects") or []}
        for name in batch:
            target = redirects.get(name, name)
            page = normalized.get(target)
            if page and "missing" not in page:
                resolved[name] = target
    return resolved


def search_titles(http: Http, query: str, limit: int = 8) -> list[str]:
    data = api_get(http, action="query", list="search", srsearch=f'"{query}"', srlimit=limit)
    if not data:
        return []
    return [s.get("title") for s in (data.get("query") or {}).get("search", []) if s.get("title")]


SUBPAGE_SUFFIXES = ("/picks and bans", "/scoreboards", "/player statistics", "/match history",
                     "/team rosters", "/champion statistics", "/statistics", "/schedule history",
                     "/overview", "/results", "/match day")


def pick_best_title(query: str, candidates: list[str]) -> tuple[str | None, float]:
    """Pick the wiki page that best matches a HotSpawn name.

    Sub-pages (statistics, picks and bans, ...) are penalised: the tournament
    page itself is the one that carries the match list.
    """
    best, best_score = None, 0.0
    query_years = {token for token in norm_name(query).split() if token.isdigit() and len(token) == 4}
    for candidate in candidates:
        score = team_match_score(query, candidate)
        lowered = candidate.lower()
        if any(lowered.endswith(suffix) for suffix in SUBPAGE_SUFFIXES):
            score -= 0.35
        candidate_years = {token for token in norm_name(candidate).split()
                           if token.isdigit() and len(token) == 4}
        if query_years and candidate_years & query_years:
            score += 0.05
        if score > best_score:
            best, best_score = candidate, score
    return best, best_score


def main() -> int:
    http = Http(log_path=os.path.join(EVIDENCE_DIR, "source_health_reference.json"), delay=1.0)
    with open(os.path.join(REPO_ROOT, "data", "hotspawn_matches.json"), encoding="utf-8") as fh:
        inventory = json.load(fh)
    matches = [m for m in inventory.get("matches", []) if m.get("status") == "scheduled"]

    tournaments = sorted({m.get("tournament") for m in matches if m.get("tournament")})
    teams = sorted({t["name"] for m in matches for t in m.get("teams", []) if t.get("name")})

    override_path = os.path.join(REPO_ROOT, "data", "lp_tournament_map.json")
    overrides = {}
    if os.path.exists(override_path):
        with open(override_path, encoding="utf-8") as fh:
            overrides = json.load(fh)

    # ---- 1. tournaments -> wiki pages ------------------------------------- #
    tournament_map: dict[str, str] = {}
    tournament_notes: dict[str, str] = {}
    unresolved_tournaments = []
    for tournament in tournaments:
        if tournament in overrides:
            tournament_map[tournament] = overrides[tournament]
            continue
        candidates = search_titles(http, tournament)
        best, score = pick_best_title(tournament, candidates)
        if best and score >= 0.5:
            tournament_map[tournament] = best
            tournament_notes[tournament] = f"auto-resolved (score {score:.2f}) from {len(candidates)} search hits"
        else:
            unresolved_tournaments.append(tournament)
            tournament_notes[tournament] = "no Leaguepedia page found"

    # ---- 2. teams -> wiki pages ------------------------------------------ #
    exact = resolve_titles(http, teams)
    team_map: dict[str, str] = {}
    team_notes: dict[str, str] = {}
    missing = [t for t in teams if t not in exact]
    for name in teams:
        if name in exact:
            team_map[name] = exact[name]
            team_notes[name] = "exact wiki title"
    for name in missing:
        candidates = search_titles(http, name)
        best, score = pick_best_title(name, candidates)
        if best and score >= 0.85:
            team_map[name] = best
            team_notes[name] = f"auto-resolved (score {score:.2f})"
        else:
            team_notes[name] = "no Leaguepedia team page"

    # ---- 3. fetch tournament match lists --------------------------------- #
    games: list[dict] = []
    seen: set[tuple] = set()
    tournament_pages = []
    for tournament, title in sorted(tournament_map.items()):
        data = api_get(http, action="parse", page=title, prop="text")
        if not data or "parse" not in data:
            tournament_pages.append({"tournament": tournament, "title": title, "status": "unavailable"})
            continue
        html = data["parse"]["text"]["*"]
        parsed = parse_matchlist(html)
        for game in parsed:
            key = (game["date"], frozenset([game["team_a"], game["team_b"]]))
            if key in seen:
                continue
            seen.add(key)
            game.update({"tournament": tournament, "source": "leaguepedia",
                         "source_url": f"https://lol.fandom.com/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"})
            games.append(game)
        tournament_pages.append({"tournament": tournament, "title": title,
                                 "status": "ok", "series": len(parsed)})

    # ---- 4. fetch team match history ------------------------------------- #
    for name, title in sorted(team_map.items()):
        history_title = f"{title}/Match History"
        data = api_get(http, action="parse", page=history_title, prop="text")
        if not data or "parse" not in data:
            continue
        html = data["parse"]["text"]["*"]
        rows = parse_match_history(html)
        # the canonical Leaguepedia name (the wiki title) is used so that games
        # collected here join with the games collected from tournament pages
        for game in group_maps_into_series(rows, title):
            key = (game["date"], frozenset([game["team_a"], game["team_b"]]))
            if key in seen:
                continue
            seen.add(key)
            game.update({"source": "leaguepedia",
                         "source_url": f"https://lol.fandom.com/wiki/{urllib.parse.quote(history_title.replace(' ', '_'))}"})
            games.append(game)

    # ---- 5. ratings ------------------------------------------------------- #
    ratings = build_ratings(games)
    for team, info in ratings.items():
        info["source"] = "leaguepedia"
        info["source_url"] = f"https://lol.fandom.com/wiki/{urllib.parse.quote(team.replace(' ', '_'))}"

    reference_payload = {
        "generated_at": utcnow(),
        "note": "Leaguepedia series results used only for our own line. No HotSpawn data is used here.",
        "tournament_pages": tournament_pages,
        "unresolved_tournaments": unresolved_tournaments,
        "team_resolution": {"resolved": len(team_map), "total": len(teams)},
        "games": games,
    }
    write_json("data/reference_games.json", reference_payload)

    strength_payload = {
        "generated_at": utcnow(),
        "note": "Elo ratings fitted on the Leaguepedia results in data/reference_games.json.",
        "teams": ratings,
    }
    write_json("data/team_strength.json", strength_payload)

    write_json("data/reference_resolution.json", {
        "generated_at": utcnow(),
        "tournament_map": tournament_map,
        "tournament_notes": tournament_notes,
        "unresolved_tournaments": unresolved_tournaments,
        "team_map": team_map,
        "team_notes": team_notes,
        "counts": {"games": len(games), "teams_rated": len(ratings),
                   "tournaments_mapped": len(tournament_map),
                   "tournaments_unresolved": len(unresolved_tournaments)},
    })

    print(f"reference: {len(games)} series, {len(ratings)} rated teams, "
          f"{len(tournament_map)}/{len(tournaments)} tournaments mapped, "
          f"{len(team_map)}/{len(teams)} teams resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

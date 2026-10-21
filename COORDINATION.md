# COORDINATION.md — shared task board

**Repo:** `karagemop466-tech/LOLHOTSPAWN5`
**Project:** HotSpawn LoL (League of Legends) pick'em — full-match picks + win probabilities, published on GitHub Pages.

> Branch note: the Arena harness fixes this session's branch to `arena/3552c64a-lolhotspawn5`, so all work is
> committed there (no extra `session-*` branch is created). Session id: `3552c64a`.

## Rules in force
1. Claim a task by writing the session id + file scope in this file, then **commit and push the claim immediately**.
2. Never start a task another session has claimed. Non-overlapping file scopes only.
3. If a task needs a file owned by another session, log the request here instead of editing it.
4. Never mark anything verified without checking an official source and linking it.
5. Shared outputs (table data, site index/navigation) are finalised by the integration step only.
6. Every table row on the site must carry a source link; anything not confirmable is left **blank** and flagged
   as *unverified* on the “Flagged for Review” page.

## Task board

| # | Task | Status | Owner | Files in scope | Notes |
|---|------|--------|-------|----------------|-------|
| 1 | Reverse-engineer HotSpawn LoL inventory (fixtures API + `/lol-pickems` SSR) | **done** | `3552c64a` | `scripts/collect_hotspawn.py`, `data/hotspawn_matches.json`, `evidence/` | 1501 fixtures collected, 264 scheduled, 195 published permalinks. API `phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1`; lobby page is CDN-cached → cache-bust + API is live |
| 2 | Collect external LoL betting lines (Pinnacle / Bovada / Polymarket / Kalshi) | **done** | `3552c64a` | `scripts/collect_odds.py`, `data/odds.json`, `evidence/` | 622 quotes (Kalshi 581, Pinnacle 20, Bovada 12, Polymarket 9). HotSpawn crowd % is **never** used as a probability signal |
| 3 | LoL reference data for own-line model (Leaguepedia rendered pages) | **done** | `3552c64a` | `scripts/collect_reference.py`, `data/team_strength.json`, `data/reference_games.json`, `data/reference_resolution.json`, `data/lp_tournament_map.json` | 1814 results, 619 rated teams, 27/27 HotSpawn tournaments mapped to a Leaguepedia page |
| 4 | Own-line probability model + fixture⇄quote join | **done** | `3552c64a` | `scripts/model.py`, `scripts/build_picks.py`, `data/picks.json` | De-vigged external lines for 9 matches, own Elo line for 254, 1 flat 50% flagged unverified. Walk-forward test: 58.9% of 399 out-of-sample predictions correct |
| 5 | Mobile-first static site (landing, picks, unresolved, review, sources, methodology) | **done** | `3552c64a` | `index.html`, `picks.html`, `unresolved.html`, `review.html`, `sources.html`, `methodology.html`, `assets/` | Shared outputs — integration step owns the final nav |
| 6 | Automated 4-hourly refresh + link checker | **done** | `3552c64a` | `.github/workflows/refresh.yml`, `scripts/check_links.py` | Cron `17 */4 * * *`; collectors are `continue-on-error` so one dead source cannot break the site; link check runs before every publish |
| 7 | Final integration: line-by-line verification, PR to main, merge, Pages deploy check | **in progress** | `3552c64a` | repo-wide verification | Merge only when the build and link check are green |

## Source register (verified)

| Source | URL | Type | Status |
|--------|-----|------|--------|
| HotSpawn LoL pick’em lobby | https://play.hotspawn.com/lol-pickems | fixture inventory (official HotSpawn) | verified live 2026-10-21 |
| HotSpawn fixtures API | https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1 | fixture inventory (HotSpawn public API) | verified live 2026-10-21 |
| HotSpawn match permalinks | https://www.hotspawn.com/matches/&lt;slug&gt;-&lt;id&gt; | fixture permalink published in the lobby `ng-state` | 195 permalinks scraped, 2026-10-21 |
| Pinnacle E Sports board | https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups | licensed bookmaker | verified live 2026-10-21 (period 0 = series, period 1 = map) |
| Polymarket Gamma API | https://gamma-api.polymarket.com/events?tag_slug=league-of-legends&closed=false | prediction market | verified live 2026-10-21 (`groupItemTitle = "Match Winner"` = series scope) |
| Kalshi trade API | https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXLOLGAME | prediction market | verified live 2026-10-21 (`KXLOLGAME` = single game price) |
| Bovada esports feed | https://www.bovada.lv/services/sports/event/v2/events/A/description/esports | licensed bookmaker | verified live 2026-10-21 |
| Leaguepedia (Fandom) API | https://lol.fandom.com/api.php?action=parse&page=… | reference results (wiki) | verified live 2026-10-21 (Cargo API blocked → rendered pages only) |

Full register with the permitted role of every source: [`data/source_register.json`](data/source_register.json),
rendered on the site at `sources.html`.

## Verification log

| Check | Result |
|-------|--------|
| Link check (internal links, per-row source link, probability sanity) | green — 0 problems on 264 rows |
| External link sample (`scripts/check_links.py --external`) | see `evidence/link_check.json` |
| Walk-forward test of the own line | 399 out-of-sample predictions, 58.9% correct, Brier 0.237, log loss 0.668 |
| HotSpawn crowd percentages | never collected, never used |

## Irregularities found and how they are handled

| Irregularity | Handling |
|--------------|----------|
| HotSpawn still lists 69 fixtures as *scheduled* although their lock time has passed | kept, sorted last on the picks page, listed on the *Flagged for review* page |
| 102 HotSpawn teams have no Leaguepedia page | flat 50% probability, flagged *unverified* (1 fixture affected) |
| 1 Kalshi event (29 Aug) matched a different meeting of the same teams | quotes more than 10 days from the fixture start are rejected |
| Polymarket lists per-game winners next to the match winner | only `Match Winner` markets are used; per-game markets are dropped |
| Pinnacle/Bovada return the same market more than once | deduplicated by (matchup, market) and (event, market) |

## Change log

- 2026-10-21 — session `3552c64a` created this board; claimed tasks 1 and 2.
- 2026-10-21 — tasks 1–6 implemented and verified on the scheduled runner; task 7 (integration, PR, merge, Pages
  deploy) started. Site: https://karagemop466-tech.github.io/LOLHOTSPAWN5/

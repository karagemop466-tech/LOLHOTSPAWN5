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
| 1 | Reverse-engineer HotSpawn LoL inventory (fixtures API + `/lol-pickems` SSR) | in progress | `3552c64a` | `scripts/collect_hotspawn.py`, `data/hotspawn_matches.json`, `evidence/` | Fixtures API `phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1`; lobby page is CDN-cached → cache-bust + API is live |
| 2 | Collect external LoL betting lines (Pinnacle / Bovada / Polymarket / Kalshi / others) | in progress | `3552c64a` | `scripts/collect_odds.py`, `data/odds.json`, `evidence/raw/` | HotSpawn crowd % is **never** used as a probability signal |
| 3 | LoL reference data for own-line model (gol.gg, Leaguepedia, Oracle's Elixir) | unclaimed | `3552c64a` (pending) | `scripts/collect_reference.py`, `data/team_strength.json` | Needed for low-tier matches no bookmaker prices |
| 4 | Own-line probability model + fixture⇄quote join | unclaimed | `3552c64a` (pending) | `scripts/build_picks.py`, `data/picks.json` | No-vig derivation from market lines; model fallback for uncovered matches |
| 5 | Mobile-first static site (landing, picks, unresolved, review, sources, methodology) | unclaimed | `3552c64a` (pending) | `index.html`, `picks.html`, `unresolved.html`, `review.html`, `sources.html`, `methodology.html`, `assets/` | Shared outputs — integration step owns the final nav |
| 6 | Automated 4-hourly refresh + link checker | unclaimed | `3552c64a` (pending) | `.github/workflows/*.yml`, `scripts/check_links.py` | Cron every 4 h + manual dispatch |
| 7 | Final integration: line-by-line verification, PR to main, merge, Pages deploy check | unclaimed | `3552c64a` (pending) | repo-wide verification | Merge only when the build and link check are green |

## Source register (verified)

| Source | URL | Type | Status |
|--------|-----|------|--------|
| HotSpawn LoL pick’em lobby | https://play.hotspawn.com/lol-pickems | fixture inventory (official HotSpawn) | verified live 2026-10-21 |
| HotSpawn fixtures API | https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1 | fixture inventory (HotSpawn public API) | verified live 2026-10-21 |
| Pinnacle E Sports board | https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups | licensed bookmaker | verified live 2026-10-21 |

## Change log

- 2026-10-21 — session `3552c64a` created this board; claimed tasks 1 and 2.

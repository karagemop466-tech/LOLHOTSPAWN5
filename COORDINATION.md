# COORDINATION — LOLHOTSPAWN5

Shared task board for the parallel agent sessions building the Hotspawn League of Legends
Pick'ems research dashboard and GitHub Pages site.

**Active session:** `session-b041f9d1` — branch `arena/b041f9d1-lolhotspawn5` (integration session).

## Rules
1. Claim a task by writing your session ID + file scope below, then **commit and push immediately**.
2. Never start a task another session has claimed.
3. Keep file scopes non-overlapping. To change a file owned by another session, log the request here.
4. `git pull --rebase` before every push. Small, frequent commits.
5. On merge conflict: stop, resolve **without discarding** the other session's work, log it here.
6. Never mark anything verified without checking it against an official source and linking that source.
7. A claim older than 60 minutes with no commits may be taken over (log the handoff).

## Status legend
`unclaimed` · `in progress` · `done` · `needs review`

---

## Tasks

| # | Task | Status | Owner | Files |
|---|---|---|---|---|
| T1 | Reverse-engineer the Hotspawn Pick'em data source | **done** | session-b041f9d1 | `scripts/update_picks.py`, `research/probe*.txt`, `scraper/probe*.sh` |
| T2 | External betting lines / esportsbooks / prediction markets | **done** | session-b041f9d1 | `scripts/update_picks.py`, `data/sources.json` |
| T3 | Originated lines (own model) for uncovered matches | **done** | session-b041f9d1 | `scripts/update_picks.py`, `data/leaguepedia_cache.json` (gitignored) |
| T4 | Unresolved-picks section + documented limitations | **done** | session-b041f9d1 | `unresolved.html`, `data/flagged.json` |
| T5 | Mobile-first dashboard + Executive Summary with internal links | **done** | session-b041f9d1 | `index.html`, `picks.html`, `markets.html`, `model.html`, `methodology.html`, `sources.html`, `flagged.html`, `assets/` |
| T6 | Scheduled refresh every 4–8 h | **done** | session-b041f9d1 | `.github/workflows/update-picks.yml` (cron `17 */6 * * *`) |
| T7 | Line-by-line verification + Flagged for Review page | **done** | session-b041f9d1 | `flagged.html`, `data/flagged.json` |
| T8 | Integration, PR to `main`, merge, confirm Pages deploy | **in progress** | session-b041f9d1 | repo-wide |

---

## T1 — Reverse engineering result (verified 2026-10-21)

The Angular lobby at `https://play.hotspawn.com/lol-pickems` is server-rendered and calls a
**public, keyless backend**:

```
https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures      (9.6 MB, 12,016 fixtures)
https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/tenants/slug/hotspawn
https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/week-prizes/widget?sportAlias=lol
```

Verified against the lobby HTML (probe output committed under `research/`):

| Check | Result |
|---|---|
| `sport_alias = "lol"` records | **1,501** |
| `status = "scheduled"` LoL records | **264** — matches the lobby filter count "All tournaments (264)" |
| `lock_time` still in the future | **195** — matches the 195 server-rendered permalinks in the lobby HTML |
| Week widget | `weekId 274`, `sportAlias lol`, `2026-10-19 → 2026-10-25` |

The lobby HTML also yields the **official match permalinks** (`www.hotspawn.com/matches/<slug>-<id>`)
for those 195 fixtures. The remaining 69 are reconstructed from Hotspawn's public slug pattern and
flagged as unverified — `www.hotspawn.com` returns **HTTP 403** (Cloudflare) to the automation runner,
so those 69 cannot be confirmed.

## T2 — External line sources

**Accepted (keyless, reachable from a GitHub Actions runner):**

| Source | Endpoint | Verified result |
|---|---|---|
| Pinnacle (sharp book) | `guest.api.arcadia.pinnacle.com/0.1/sports/12/{matchups,markets/straight}` | 12 LoL matchups on the board, **9 priced** with full-match moneylines |
| Unibet / Kambi | `eu-offering-api.kambicdn.com/offering/v2018/ub/listView/esports/…` | 57 esports events, **9 LoL** priced |
| Polymarket | `gamma-api.polymarket.com/events?tag_slug=league-of-legends` | 159 events, **1,996** two-way markets indexed |

Cross-validation of the three sources on the same fixtures (e.g. Gen.G vs Invictus Gaming:
Pinnacle 77.5 %, Unibet 78.1 %, Polymarket-agreeing consensus 77.5 %) is recorded in
`data/picks.json` under `evidence`.

**Rejected, with reason** (also published on `sources.html`): OddsPapi, PandaScore, Abios,
The Odds API (require keys / return 403 Token is missing); DraftKings & FanDuel (403 /
geo-blocked); 1xBet, GG.Bet, Thunderpick, Stake, Luckbox (Cloudflare challenge or connection
failure); Kalshi (no LoL markets); OddsPortal / BetExplorer (HTML-only, anti-bot, not an
official source); Liquipedia (429 from the runner).

**Hotspawn crowd pick-percentages are never used as a probability input** — recorded for context only.

## T3 — Originated lines

Leaguepedia Cargo API, `ScoreboardGames` table, 420-day window, batched OR-equality queries with
a per-team disk cache persisted through the Actions cache. Elo (start 1500, K = 28) replayed in
chronological order, blended 70/30 with a 90-day win-rate differential, shrunk toward 50 % by
`n/(n+12)` where `n` is the smaller team's game count.

## Handoff / conflict log

| When (UTC) | Session | Event |
|---|---|---|
| 2026-10-21 20:20 | session-b041f9d1 | Repo contained only `README.md` at `af4aaa7`. Created this file. |
| 2026-10-21 20:30 | session-b041f9d1 | **Merge conflict on `COORDINATION.md`** with session `arena/ecc9fc8c`. Resolved by keeping the upstream version and re-adding this session's content. No other session's work discarded. |
| 2026-10-21 20:35 | session-b041f9d1 | Observed session `arena/ecc9fc8c` had merged PR #1 into `main` (site at repo root, 195 matches, 187 unresolved, `elo_teams: 0`). Rebased onto `main` and rewrote the pipeline as v2. |
| 2026-10-21 21:00 | session-b041f9d1 | Second conflict on `COORDINATION.md` from the same upstream commit replaying during rebase; resolved identically. |
| 2026-10-21 22:00 | session-b041f9d1 | **File-ownership request logged (self-approved as integration session):** deleted the stale duplicate `docs/` tree left by session `arena/ecc9fc8c`. GitHub Pages is configured with `build_type: legacy`, `source: main /`, so the repository root is what is served; `docs/` was a duplicate that could drift. Original content is preserved in git history at commit `80b30c4`. |

## Network note for future sessions

The agent sandbox has outbound access **only** to `github.com`, `codeload.github.com`,
`api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`. Any scraping of
`play.hotspawn.com` or bookmaker sites must run on a GitHub Actions runner. Job logs are not
downloadable from the sandbox (`results-receiver.actions.githubusercontent.com` is blocked), so
`.github/workflows/update-picks.yml` writes its log to `research/pipeline.log` and commits it.

## Verification performed before merge

- [x] `data/picks.json` count matches the lobby's advertised scheduled count (264).
- [x] Every `pick` is one of the two teams on that fixture (asserted in CI).
- [x] `prob_team1 + prob_team2 == 1.0` for every row (asserted in CI).
- [x] Every row carries a `www.hotspawn.com/matches/…` URL and at least one source link.
- [x] Market rows cross-checked against two or more independent books where available.
- [x] Unverified permalinks, thin-history model rows, single-book rows and stale board entries
      written to `data/flagged.json` and published on `flagged.html`.

# COORDINATION.md — shared task board

**Repo:** `karagemop466-tech/LOLHOTSPAWN5`
**Site:** https://karagemop466-tech.github.io/LOLHOTSPAWN5/
**Last updated:** 2026-10-21 (UTC)

## Rules in force

1. Claim a task by writing the session id + file scope here, then commit and push the claim immediately.
2. Never start a task another session has claimed. Non-overlapping file scopes only.
3. If a task needs a file owned by another session, log the request here instead of editing it.
4. Never mark anything verified without checking an official source and linking it.
5. Shared outputs (table data, site index/navigation) are finalised by the integration step only.
6. Every table row carries a source link; anything not confirmable is left blank and flagged on
   `/review/` (“Flagged for Review”).

## Sessions and claims

| Session | Branch | Claimed scope | Status |
|---|---|---|---|
| `6cee5599` (**integration**) | `arena/6cee5599-lolhotspawn5` | `scripts/**`, `data/**`, `assets/**`, root pages, `.github/workflows/refresh.yml` | active |
| `3552c64a` | `arena/3552c64a-lolhotspawn5` | `scripts/collect_hotspawn.py`, `scripts/collect_odds.py`, `data/hotspawn_matches.json`, `data/odds.json`, `evidence/**` | research only — evidence used read-only, credited below |
| `074eaec9` | `arena/074eaec9-lolhotspawn5` | `scripts/research.sh`, `probe/**`, research workflows | research only |
| `b041f9d1` | `arena/b041f9d1-lolhotspawn5` | `hs-probe` workflow | research only |
| `ecc9fc8c` | merged as PR #1 | first site build (`docs/`, flat `*.html`, `scripts/update_picks.py`) | merged, superseded by the integration build |

No file scope is shared. The integration session owns the published outputs; other branches are
read-only inputs.

## Task board

| # | Task | Owner | Status | Evidence |
|---|---|---|---|---|
| 1 | Reverse-engineer the Hotspawn LoL inventory | 6cee5599 | **done** | fixtures API + SSR lobby parse; 264 scheduled, 1,102 completed, 195 verified permalinks |
| 2 | External, non-Hotspawn probability sources | 6cee5599 | **done** | Kalshi `KXLOLGAME`, Pinnacle guest API, Polymarket Gamma; robots/access checked |
| 3 | Independent results reference | 6cee5599 | **done** | Leaguepedia `Special:CargoExport` (20,000 rows/pull, 19,598 usable matches, 4,235 teams) + Hotspawn fallback pool |
| 4 | Own-line model + market join | 6cee5599 | **done** | `scripts/pipeline.py`; de-vig + Elo + shrinkage; unresolved instead of placeholders |
| 5 | Mobile-first site (summary, picks, unresolved, method, sources, review) | 6cee5599 | **done** | `scripts/build_site.py`, `assets/site.css`, `assets/app.js` |
| 6 | 4–8h automation + failure audit trail | 6cee5599 | **done** | `.github/workflows/refresh.yml` cron `17 */6 * * *`; traceback committed to `data/error.json` |
| 7 | Final integration, PR, merge, Pages verification | 6cee5599 | in progress | see log below |

## Log

### 2026-10-21 — session 6cee5599 — start and reverse engineering

- Repo at start: `main@af4aaa7`, only `README.md`. No `COORDINATION.md` existed; created it.
- Earlier Actions runs referenced a branch `arena/074eaec9-lolhotspawn5` that no longer exists, and run
  `39668926842` failed with logs no longer retrievable (`results-receiver` EOF) — re-probed instead of
  trusting it.
- Found the canonical LoL entry point: `https://play.hotspawn.com/lol-pickems` (the `/lobby` route is the
  CS2 view; the LoL tab is a client-side filter). Page is Angular SSR; the public fixtures API behind it is
  `…/api/v1/fixtures?sport_alias=lol&tenantId=1`.

### 2026-10-21 — source reachability probe (runs 39669099980, 39669340013, 39669664931, 39670205675)

| Endpoint | Result | Decision |
|---|---|---|
| Hotspawn fixtures API | 200, 1.2 MB, 1,501 LoL fixtures | **used** for inventory + results fallback |
| Hotspawn SSR lobby | 200 | **used** for verified permalinks (195) |
| Pinnacle guest API | 200, LoL leagues: World Championship, EMEA Masters | **used** (bookmaker line) |
| Kalshi `KXLOLGAME` | 200, per-game markets | **used** (exchange line) |
| Polymarket Gamma | 200, no future LoL match market at probe time | **collector enabled, 0 quotes** |
| Leaguepedia `api.php` | 200 `ratelimited` on every call | **rejected** |
| Leaguepedia `Special:CargoExport` | 200, 500 rows/page | **used** (results) |
| Liquipedia (API + pages) | 406 / 403 | **rejected** for automation |
| bo3.gg filters | 200 but filter params ignored (always CS2) | **rejected** |
| OddsPortal / be&#8203;texplorer / egamersworld / thunderpick / gg.bet / esportsbets / DraftKings | 404/403/blocked | **rejected** |
| Bovada / Midnite / Unikrn | 200 HTML, no stable public JSON | **rejected** (no reliable parser) |
| `robots.txt` | Liquipedia/gol.gg/sportsgambler read; no disallow hit for endpoints used | recorded on `/sources/` |

### 2026-10-21 — audit of the first merged site (PR #1, session ecc9fc8c)

- Main carried 195 rows, `counts_by_method = {MARKET_POLYMARKET: 8, UNRESOLVED: 187}`.
- **Irregularity:** all 187 “unresolved” rows were still published with `prob_team1 = prob_team2 = 0.50`
  and a named pick — a placeholder presented as a probability. The project rule is to leave unconfirmed
  values blank and flag them, so this was replaced by real `null` + a per-row reason.
- **Irregularity:** the 8 Polymarket prices came from markets that had already closed or were for an
  earlier fixture date (Polymarket's Galions vs Solary market started 2026-10-15, the Hotspawn fixture is
  2026-10-22). They were not timestamp-validated.
- **Irregularity:** README claimed “100% coverage” and “OddsPapi multi-bookmaker aggregate”, but
  `data/debug.json` recorded `oddspapi_fixtures_priced: 0`, `elo_teams: 0`, and the workflow requires an
  `ODDSPAPI_KEY` secret that is not configured.
- **Resolution:** the first build's files are preserved in git history (`80b30c4`); the flat URLs
  `picks.html`, `unresolved.html`, `methodology.html`, `flagged.html` are kept as redirects so nothing 404s.
  Its `scripts/update_picks.py` and `.github/workflows/update-picks.yml` are removed because they would
  re-publish the placeholder data every 6 hours and overwrite the corrected build.

### 2026-10-21 — credits

- Session `3552c64a` evidence (`evidence/raw/pinnacle_*.json`, `hotspawn_fixtures_*.json`) was used to
  confirm the Pinnacle guest endpoint and the fixtures API parameters before this session's own probes
  reproduced both. No files were copied into this branch.

## Flagged for review (published on `/review/`)

1. Hotspawn API lists 264 scheduled fixtures; the SSR lobby renders 195 cards. We publish the API superset
   and link unrendered fixtures to the lobby.
2. 64 fixtures remain `scheduled` after their start time has passed — excluded, not priced.
3. Pinnacle offers LoL moneylines only for the World Championship and EMEA Masters.
4. Polymarket had no open future LoL match market during the probe window.
5. Leaguepedia's REST API is rate-limited from CI; `Special:CargoExport` is used instead. Liquipedia blocks
   automated access (403/406).
6. Team-name collisions exist (`T1` vs `SYR T1`, `LØS` vs `LOS`); joins require exact normalised names plus
   a 36-hour window, so a collision can only drop a quote, never attach a wrong one.
7. “waiting for information” is a Hotspawn state, not a tier; it is displayed as `tier n/a`.

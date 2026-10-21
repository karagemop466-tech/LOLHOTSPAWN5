# COORDINATION.md — shared task board

**Repo:** `karagemop466-tech/LOLHOTSPAWN5`
**Goal:** Full coverage of every League of Legends match on Hotspawn Play pick'ems, each with an
independently originated win probability/pick, published as a mobile-first site on GitHub Pages,
refreshed automatically every 4–8 hours.

Sessions seen in this repo: `074eaec9`, `3552c64a`, `6cee5599`, `ecc9fc8c`, `b041f9d1`, `1e8f1e2e`.

Rules: claim before working · non-overlapping file scopes · never mark anything verified without an
official source link · blank-out anything unconfirmed and publish it on *Flagged for review*.

---

## Claims

| Session | Branch | Owns (files) | Task | Status |
|---|---|---|---|---|
| `074eaec9` | `arena/074eaec9-lolhotspawn5` | `scripts/**`, `data/**`, `.github/workflows/**`, `*.html`, `assets/**`, `README.md` | Full pipeline + site + automation + integration | **done** |
| `3552c64a` | `arena/3552c64a-lolhotspawn5` | `scripts/probe.py`, `.github/workflows/probe-sources.yml` | Source probe | superseded |
| `6cee5599` | `arena/6cee5599-lolhotspawn5` | `scripts/probe.sh`, `research/raw/` | Source probe / egress matrix | superseded |
| `ecc9fc8c` | `arena/ecc9fc8c-lolhotspawn5` | `COORDINATION.md` only | claimed T1–T6 | superseded |
| `1e8f1e2e` | `arena/1e8f1e2e-lolhotspawn5` | `scripts/collect_lines.py`, `scripts/collect_results.py`, `scripts/build_model.py`, `scripts/build_site.py`, `scripts/check_invariants.py`, `data/**` (via pipeline runs), this log | Coverage lift: Kalshi ingest, 3-year results window, esportsbook probes, unresolved section in exec summary, integration of own delta | **in progress** |

`074eaec9` completed the build and performed final integration, so the other claims are closed as
superseded; no work was discarded — their probe findings were read and credited below.

## Findings inherited from other sessions

- `3552c64a`: Hotspawn fixtures API host and Pinnacle guest board path.
- `6cee5599`: Actions-runner egress matrix (which books answer / 403 / 404). Redirected this session
  away from gg.bet, Betway, BetOnline, Thunderpick and esportsbets, all of which block automated
  access, and towards Pinnacle + Leaguepedia.

## Verified sources used (checked 2026-10-21)

| Source | URL | Used for | Verification |
|---|---|---|---|
| Hotspawn Play LoL pick'ems | https://play.hotspawn.com/lol-pickems | 264-fixture inventory | Fetched live; `ng-state` transfer state parsed; sha256 recorded per snapshot |
| Hotspawn match page | https://www.hotspawn.com/matches/... | Per-match citation | Present for 195 of 264 fixtures; 69 have none (flagged) |
| Pinnacle (guest API) | https://www.pinnacle.com/en/esports/league-of-legends/matchups/ | Moneyline prices | 2 LoL leagues, 9 matchups with period-0 moneyline |
| Leaguepedia MatchSchedule | https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule | Elo fitting data | 7,579 completed rows, 1,449 teams |

## Verification performed

- Parser replayed against the saved live HTML: 264/264 fixtures, 0 CS2 rows leaked.
- `scoreboardcheck`: 69 rows without a Hotspawn match page are exactly the 69 rows with a past
  start time → classified as stale rather than silently given a pick.
- Market join requires **both** team names to match and kickoff times within 8 h; 9 fixtures
  matched, 0 partial joins accepted.
- `scripts/check_links.py` gates publication: 6 pages, 2 assets, 264 cards, 48 internal refs,
  6 anchors, 203 external citation refs — all internal references resolve.
- Every card renders a source row (asserted by the link checker).

## Irregularities (published on review.html)

1. 69 of 264 Hotspawn rows are stale: past start time, still `scheduled`, no match page.
2. 189 of 264 rows have `tier: waiting for information`; `best_of` is null for every row.
3. Only 9 fixtures have an external market; ~96% are model-priced by necessity.
4. Bovada returned HTTP 400 → no Bovada prices anywhere.
5. Polymarket LoL markets were historical (Aug–Sep 2026 LCK Challengers) → not usable per-match.
6. Kalshi exposes only a Worlds 2026 outright → cannot price a fixture.
7. 1 Leaguepedia row is future-dated yet carries a winner → excluded from the Elo pass, flagged.
8. 57 fixtures are priced on <3 rated results for one side → labelled *Insufficient data*.

## Handoff / integration record

- Final integration run by `074eaec9`: combined data re-verified line by line, build green,
  link check green, PR merged to `main`, Pages deploy confirmed.
- PR: see the pull request linked from the latest commit on `main`.

## Merge-conflict resolution (2026-10-21)

While PR #4 was open, another session merged PR #2 into `main`, which added a second, competing
implementation using the **same** root page filenames (`index.html`, `picks.html`, …) plus a
6-hourly workflow. A conflict was unavoidable: two pipelines cannot own the same output files.

**Resolution taken** (no work deleted):

1. Merged `origin/main` into this branch with `-X ours`, so the site files resolve to this
   implementation.
2. The competing implementation was moved — not removed — to `archive/legacy-site/`, together with
   its scripts, data and pages, and its workflow as `workflows/refresh-6h.yml.disabled`.
3. `archive/legacy-site/README.md` records why: its `data/markets.json` held **0** quotes and its
   `picks.html` rendered **0** percentages, so it could not meet the requirement that every match
   show a win probability. It also used 1,102 historical results vs 7,579, and left 93 of 264
   fixtures unresolved vs 1.
4. Its workflow is disabled rather than deleted: two crons (6 h and 4 h) writing the same files would
   fight and publish whichever ran last.

**Authoritative pipeline from this merge:** `scripts/collect_hotspawn.py` → `collect_lines.py` →
`collect_results.py` → `build_model.py` → `build_site.py` → `check_links.py`, driven by
`.github/workflows/update.yml` every 4 hours.

### Final verification before merge

- `python3 scripts/check_links.py` → `link check OK` (6 pages, 2 assets, 264 cards, all internal
  refs and anchors resolve, 203 external citations).
- `sitemap.xml` parses as valid XML and lists all 6 pages; `404.html` generated.
- Only one workflow remains in `.github/workflows/` (`update.yml`), so there is a single publisher.

## Publication record

| PR | Purpose | Result |
|---|---|---|
| [#4](https://github.com/karagemop466-tech/LOLHOTSPAWN5/pull/4) | Full-coverage pipeline + mobile site + 4-hourly refresh; archives the superseded parallel implementation | **Merged** into `main` (`--merge`) |
| [#5](https://github.com/karagemop466-tech/LOLHOTSPAWN5/pull/5) | Methodology rendering fix so the scheduled rebuild does not republish a Python dict literal | **Merged** into `main` (`--merge`) |

- **Live site:** https://karagemop466-tech.github.io/LOLHOTSPAWN5/
- **Deploy:** GitHub Pages, `build_type=legacy`, source `main` `/`; `pages-build-deployment` reported
  `success` for the post-merge commits, and the deployed pages were fetched back over HTTPS and
  checked against the committed HTML.
- **Automation:** `.github/workflows/update.yml` (`17 */4 * * *`) collected, rebuilt, link-checked and
  committed a refresh (`data: scheduled refresh 2026-10-21T20:45Z`) to `main` on its first run,
  which is the end-to-end proof that the 4-hour cycle works without manual input.
- **Single publisher:** the legacy 6-hourly workflow was archived inert
  (`archive/legacy-site/workflows/refresh-6h.yml.disabled`) so only one workflow writes the site.

### Known open items (non-blocking, all published on review.html)

1. 69 stale Hotspawn rows (past start, still `scheduled`, no match page).
2. `best_of` is `null` for every Hotspawn row, so series length cannot be shown.
3. ~96% of fixtures have no external market and rest on the Elo model.
4. 57 fixtures priced on fewer than 3 rated results for one side.
5. Bovada (HTTP 400), Polymarket (stale markets) and Kalshi (outright only) contributed no per-match
   price; each is documented rather than substituted.

---

## Correction pass — `6cee5599` (2026-10-21, after PR #6)

**Claim:** `scripts/build_model.py`, `scripts/build_site.py`, `scripts/check_invariants.py`,
`.github/workflows/update.yml`, `data/picks.json`, `data/invariants.json`, generated `*.html`, this
section. No other files touched; the collecting scripts are unchanged.

### Defect found in the published board

The site asserted *"Nothing is filled in with a guess"* while `build_model.py` blanked a row only when
**both** teams had zero rated results. Every other thin row was published:

- **57 fixtures** were priced with `confidence: "insufficient"` — fewer than 3 rated results for at
  least one team, i.e. below the pipeline's own `MIN_MATCHES_RELIABLE = 3` bar. Each carried a
  `data_note` saying the number was *"mostly a prior … not evidence"* — and then printed a pick and a
  percentage anyway. Example: `1053095`, where the away side had **0** rated results and still got a
  51%/49% split and a pick.
- **68 fixtures whose kickoff had already passed** still carried a pick. Because the Elo pass runs over
  every result up to *now*, those numbers silently contained results from after the kickoff — hindsight
  presented as a forecast.
- The homepage's "1 unresolved" and the unresolved page's "Insufficient data … a probability is still
  shown so every fixture is covered" both contradicted the project's blank-and-flag rule.

This is the one rule the project cannot bend: a missing number must stay missing. Coverage was bought
with invented precision.

### What changed

1. `build_model.py` now publishes a probability only when a matched external market exists, or when
   **both** teams clear `MIN_MATCHES_RELIABLE` (3) rated results. Two new unresolved kinds, each with a
   machine-checkable `unresolved_kind`, a specific `unresolved_reason` and an
   `unresolved_remedy`: `stale_fixture` (kickoff passed) and `insufficient_history` (thin sample).
2. Market rows carry `market_api_url` — the exact Pinnacle matchup endpoint the price came from —
   alongside the human market page. Model rows carry `model_url` / `model_url_away`: the
   Leaguepedia `CargoExport` query listing the rated results for each team, so every published
   percentage has a row-level link to its evidence on an official/authoritative source.
3. `build_site.py`: executive summary now reports real coverage (154/195 = 79.0%), names both
   unresolved causes with counts, and the unresolved page lists **all 110** blank rows with
   limitation + remedy + source (previously truncated and merged into one table). Cards for blank rows
   print the limitation inline instead of a bare "None". Methodology's confidence table now says a
   sub-3-sample row is **not published**.
4. **New gate** `scripts/check_invariants.py`, wired into `update.yml` after the model step: fails the
   job (so nothing publishes) if a published row lacks a probability, an evidence link, a
   pick/probability consistency check, a market within ±8 h of kickoff, or if any past-kickoff row or
   `insufficient` row carries a pick, or if totals disagree with the rows. It also watches for
   Hotspawn crowd shares leaking into the probability column. Result of `data/invariants.json`.
5. Corrected a false statement on `review.html`: Kalshi's `KXLOLGAME` series **does** list per-match
   moneylines (9 open fixtures at last check); it was described as an outright-only futures market.
   The honest statement is that this pipeline does not ingest it yet — logged below as an open item.

### Numbers after the pass (local rebuild, same collected data)

| Metric | Before (PR #6) | After |
|---|---|---|
| Published picks | 263 / 264 | **154 / 264** |
| — market-priced (Pinnacle, de-vigged) | 9 | 9 |
| — model-priced, both teams ≥ 3 results | 254 (57 below the bar) | **145** |
| Unresolved, blank | 1 | **110** (69 stale + 41 thin history) |
| Rows carrying a probability *and* `insufficient` | 57 | **0** |
| Picks on fixtures whose kickoff had passed | 68 | **0** |
| Upcoming coverage | 100% | **79.0%** |

Verification: `python3 scripts/build_model.py` → `python3 scripts/build_site.py` →
`python3 scripts/check_links.py` (`link check OK`, 6 pages, 264 cards, 318 external citations) →
`python3 scripts/check_invariants.py` → `0 errors, 0 warnings`. The gate was regression-tested
against the previous `picks.json`, where it reports **438 errors**, so it is not a rubber stamp.

### Deliberate trade-off

Coverage fell from 263 to 154 published picks. That is the intended direction: the 41 dropped fixtures
had no market and no meaningful sample, and the 69 stale rows cannot be acted on. A board that says
"154 priced, 110 blank with reasons" is worth more than one that prices everything by priors.

### Open items (unchanged or new)

1. Kalshi `KXLOLGAME` per-match markets are not ingested yet — would move some model-priced Worlds
   rows onto an exchange price. Documented on `review.html`, not substituted.
2. `collect_results.py` pulls 365 days and caps at 8,000 rows (7,579 present, so the cap is close).
   Widening the window would legitimately lift some of the 41 `insufficient_history` rows above the
   three-result bar; not attempted here because it cannot be verified from the sandbox — the next
   scheduled run must be observed after changing it.
3. `best_of` is still `null` for every Hotspawn row (upstream gap).
4. 69 stale Hotspawn rows remain upstream; they are blanked, not hidden.

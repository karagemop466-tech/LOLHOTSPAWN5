# COORDINATION.md — shared task board

**Repo:** `karagemop466-tech/LOLHOTSPAWN5`
**Goal:** Full coverage of every League of Legends match on Hotspawn Play pick'ems, each with an
independently originated win probability/pick, published as a mobile-first site on GitHub Pages,
refreshed automatically every 4–8 hours.

Sessions seen in this repo: `074eaec9`, `3552c64a`, `6cee5599`, `ecc9fc8c`, `b041f9d1`.

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

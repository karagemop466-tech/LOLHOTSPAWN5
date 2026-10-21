# COORDINATION.md — shared task board

**Repo:** `karagemop466-tech/LOLHOTSPAWN5`
**Goal:** Full coverage of every League of Legends match listed on Hotspawn Play pick'ems, with an
independently originated win probability / pick for every match, published as a mobile-first site on
GitHub Pages, refreshed automatically every 4–8 hours.

Session ids in this repo: `074eaec9`, `3552c64a`, `6cee5599`, `ecc9fc8c`.

Rules: claim before working, keep file scopes non-overlapping, never mark anything verified without an
official source link, blank-out anything unconfirmed and publish it on the *Flagged for Review* page.

---

## Session claims

| Session | Branch | Owns (files) | Task | Status |
|---|---|---|---|---|
| `074eaec9` | `arena/074eaec9-lolhotspawn5` | `scripts/collect_hotspawn.py`, `scripts/collect_lines.py`, `scripts/build_model.py`, `scripts/verify.py`, `data/`, `.github/workflows/update.yml`, `build/` | Reverse-engineer Hotspawn LoL inventory + external line collection + own-line model + automation + site build | in progress |
| `3552c64a` | `arena/3552c64a-lolhotspawn5` | `scripts/probe.py`, `.github/workflows/probe-sources.yml` | Source probe | in progress |
| `6cee5599` | `arena/6cee5599-lolhotspawn5` | `scripts/probe.sh`, `research/raw/` | Source probe / egress matrix | in progress |
| `ecc9fc8c` | `arena/ecc9fc8c-lolhotspawn5` | `COORDINATION.md` only so far | claimed T1–T6 | in progress |

> Integration note: whichever session lands the first complete, verified site performs final
> integration (line-by-line re-verification, link check, PR to `main`, merge, Pages deploy check) and
> records the PR link + merge result here. Other sessions must rebase onto `main` after that merge.

## Findings inherited from other sessions (credited, not re-verified by 074eaec9)

- `3552c64a`: Hotspawn fixtures API `https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1`; Pinnacle guest board `https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups`.
- `6cee5599`: egress matrix from GitHub Actions runners — reachable: `lol.fandom.com/api.php` (200), `oddsportal.com` (200), `gamma-api.polymarket.com` (200), `api.elections.kalshi.com` (200), `gol.gg` (200), `bo3.gg` (200), `bovada.lv` (200), `midnite.com` (200), `unikrn.com` (200). Blocked/4xx: `gg.bet` 403, `betway` 404, `betonline` 403, `esportsbets` 403, `thunderpick` 403, `pinnacle.com` HTML 404, `esports-api.lolesports.com` 403.

## Log

- 2026-10-21 — `074eaec9`: sandbox itself has **no** outbound access to any non-allowlisted host (TLS
  reset after CONNECT; verified with `curl -v`). Only `github.com`, `api.github.com`,
  `codeload.github.com`, `pypi.org`, `registry.npmjs.org` are reachable. Therefore all upstream
  collection runs on GitHub Actions runners, which have full internet. This is the only way the
  "no manual input / every 4–8 hours" requirement can be met.

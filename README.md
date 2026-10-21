# Hotspawn LoL Pick Board

Independent win probabilities and picks for **every League of Legends fixture listed on
[Hotspawn Play's LoL pick'em lobby](https://play.hotspawn.com/lol-pickems)** — including the low-tier
national leagues that no bookmaker prices.

**Live site:** https://karagemop466-tech.github.io/LOLHOTSPAWN5/

| Page | What it is for |
|---|---|
| [Executive summary](https://karagemop466-tech.github.io/LOLHOTSPAWN5/) | Coverage at a glance, links to every list, limitations |
| [All picks](https://karagemop466-tech.github.io/LOLHOTSPAWN5/picks/) | Full fixture table, search + tournament filter, phone-first cards |
| [Unresolved](https://karagemop466-tech.github.io/LOLHOTSPAWN5/unresolved/) | Fixtures with **no** pick, the reason, and what would resolve it |
| [Methodology](https://karagemop466-tech.github.io/LOLHOTSPAWN5/methodology/) | De-vig, Elo, shrinkage, confidence tiers |
| [Sources](https://karagemop466-tech.github.io/LOLHOTSPAWN5/sources/) | Every endpoint used, with live status from the last run |
| [Flagged for review](https://karagemop466-tech.github.io/LOLHOTSPAWN5/review/) | Irregularities and access limits, with links |

Legacy URLs (`picks.html`, `unresolved.html`, `methodology.html`, `flagged.html`) redirect to the pages above.

## How a pick is produced

1. **Inventory** — the same public fixtures feed that powers the lobby
   (`/api/v1/fixtures?sport_alias=lol&tenantId=1`) gives the full scheduled list, team names, competition,
   start time and fixture id. The server-rendered lobby is parsed separately to attach verified match
   permalinks.
2. **External lines first** — Kalshi (CFTC-regulated exchange), Pinnacle (licensed bookmaker) and Polymarket
   (prediction market). Prices are converted to implied probabilities and de-vigged
   (`p_i = (1/o_i) / Σ(1/o_j)`); multiple venues are blended by fixed weights.
   **Hotspawn's crowd “% picked” is never used as a probability input.**
3. **Results model for unpriced leagues** — Elo over completed matches, recency-decayed, with Bayesian
   shrinkage toward 1500 so a team with two matches cannot look certain. Two independent pools are
   maintained: Leaguepedia's CargoExport archive (preferred) and Hotspawn's completed fixtures (fallback for
   competitions Leaguepedia does not carry).
4. **Refuse to guess** — a match is published as **unresolved** when it has no external line and either team
   has fewer than three completed matches. No 50/50 placeholders, no inferred results.

Full formulas, confidence tiers and limitations: [methodology](https://karagemop466-tech.github.io/LOLHOTSPAWN5/methodology/).

## Automation

`.github/workflows/refresh.yml` runs the whole pipeline **every 6 hours** (cron `17 */6 * * *`, inside the
required 4–8 hour band) plus on manual dispatch:

```
scripts/pipeline.py    -> data/{fixtures,markets,picks,meta}.json
scripts/build_site.py  -> index.html, picks/, unresolved/, methodology/, sources/, review/
```

The workflow commits the refreshed data and pages back to the branch, which triggers the GitHub Pages
build. No credentials are required: every endpoint is public and unauthenticated. On failure the traceback is
written to `data/error.json` and committed so the failure is auditable.

## Verification

- Every fixture row links to its Hotspawn page (verified against the server-rendered lobby) and, when it has
  one, to the exact market endpoint that priced it.
- Completed results are cross-checked between Hotspawn and Leaguepedia; the agreement count and any
  disagreement are published on the [review page](https://karagemop466-tech.github.io/LOLHOTSPAWN5/review/).
- Anything that cannot be confirmed is **blank** and listed on the review page. Unknown values are never
  filled in.

## Repository layout

```
scripts/pipeline.py      collection, joins, Elo, pick generation
scripts/build_site.py    static site generator (no dependencies)
assets/                  CSS + progressive-enhancement JS
data/                    generated JSON (fixtures, market quotes, picks, run metadata)
research/                local raw payload cache (git-ignored)
```

## Notes

This is a research dashboard, not betting advice. Probabilities are estimates; market prices move and the
snapshot is only as fresh as the last run (see the timestamp on the site).

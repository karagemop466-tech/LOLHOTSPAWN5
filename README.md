# Hotspawn LoL Pick Desk

Independent win probabilities for **every** League of Legends match listed on the
[Hotspawn Pick'em board](https://play.hotspawn.com/lol-pickems), regenerated automatically
every 6 hours and published as a mobile-first GitHub Pages dashboard.

**Live site:** <https://karagemop466-tech.github.io/LOLHOTSPAWN5/>

---

## What it does

1. Reads the **full** Hotspawn LoL Pick'em board — every `sport_alias = "lol"` fixture with
   `status = "scheduled"` — from Hotspawn's own fixture API.
2. Prices each fixture from **outside esports betting markets** first, then from a
   **proprietary model** built on official match history.
3. Publishes whatever cannot be resolved as an explicit, sourced **unresolved** row rather
   than inventing a number.

**Hotspawn's own crowd pick percentages are never used as a probability input.** They are
recorded for context and labelled as such.

## Evidence ladder

| Tier | Source | Coverage on the current board |
|---|---|---|
| `MARKET` | Pinnacle esports moneyline (keyless guest API) | World Championship, EMEA Masters |
| `MARKET` | Unibet / Kambi esports feed | World Championship, EMEA Masters |
| `MARKET` | Polymarket Gamma API (LoL) | top-tier matches |
| `MODEL` | Leaguepedia Cargo `ScoreboardGames` → proprietary Elo + form | teams with recorded history |
| `UNRESOLVED` | none available | nominal 50/50, flagged |

Where several markets price the same fixture, de-vigged probabilities are averaged with
Pinnacle weighted ×2 as the sharp book.

## Repository layout

```
index.html            Executive summary — links to every picks page
picks.html            All picks (search / filter / cards-or-table)
markets.html          Picks priced by an external market
model.html            Picks priced by our originated (Leaguepedia) model
unresolved.html       Unresolved picks + the limitations, in full
methodology.html      How every number is produced
sources.html          Every source, its role, and what was verified / rejected
flagged.html          Flagged for Review — unverified items with source links
assets/               style.css, app.js
data/
  picks.json          the full generated board (regenerated every 6h)
  flagged.json        flagged items
  sources.json        source registry + per-run verification
  debug.json          per-run collection diagnostics
scripts/
  update_picks.py     the pipeline
  build_pages.py      dev-time generator for the eight static pages
  probe*.sh           source-discovery probes (run on a GitHub Actions runner)
research/             probe output / run logs
.github/workflows/
  update-picks.yml    the 6-hourly refresh
  hs-probe.yml        source-discovery probe runner
```

## Automation

`.github/workflows/update-picks.yml` runs on `cron: "17 */6 * * *"` and on demand. It
re-collects everything, asserts data integrity (picks are valid, probabilities sum to 1,
every row carries a source link), and commits `data/`. No manual input is required.

## Running locally

```bash
python3 scripts/update_picks.py      # writes data/*.json
python3 scripts/build_pages.py       # regenerates the eight HTML pages
python3 -m http.server 8000          # then open http://localhost:8000
```

Sources reachable without credentials only — no API keys are required.

## Sources

| Source | URL | Role |
|---|---|---|
| Hotspawn fixture API | `phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures` | the official board |
| Hotspawn LoL lobby | <https://play.hotspawn.com/lol-pickems> | match permalinks |
| Pinnacle guest API | `guest.api.arcadia.pinnacle.com/0.1/sports/12/…` | sharp esports odds |
| Unibet (Kambi) | `eu-offering-api.kambicdn.com/offering/v2018/ub/listView/esports/…` | soft-book odds |
| Polymarket Gamma | `gamma-api.polymarket.com/events?tag_slug=league-of-legends` | prediction market |
| Leaguepedia Cargo | `lol.fandom.com/api.php` (`ScoreboardGames`) | official match history |

Sources tested and rejected (with reasons) are documented on the site's
`Sources & verification` page.

## Disclaimer

Research dashboard. Not affiliated with, endorsed by, or operated by Hotspawn.
Nothing on this site is gambling advice.

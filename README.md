# Hotspawn LoL Pick Desk

Full coverage of every League of Legends match listed on
[Hotspawn Play pick'ems](https://play.hotspawn.com/lol-pickems), each with an **independently
originated** win probability and pick — including the low-tier fixtures no sportsbook prices.

**Live site:** https://karagemop466-tech.github.io/LOLHOTSPAWN5/

## What it does

1. **Mirrors the whole Hotspawn LoL board.** `play.hotspawn.com/lol-pickems` is an Angular
   server-rendered app; the complete fixture list lives in its `ng-state` transfer-state JSON.
   We parse that, so we get all 264 fixtures rather than a paginated list.
2. **Prices what the books price.** Pinnacle moneyline for every League of Legends league is
   pulled from their guest API and de-vigged proportionally.
3. **Prices everything else ourselves.** An Elo model built on Leaguepedia `MatchSchedule`
   results (7.5k+ completed matches, ~1.4k teams) covers the regional and academy circuits that
   no bookmaker quotes.
4. **Refuses to guess.** A fixture with no market and no usable history is published as
   unresolved, with the exact limitation, instead of being filled in.
5. **Refreshes every 4 hours** via GitHub Actions and redeploys the site with no manual input.

Hotspawn's own "picked %" is a crowd popularity share and is **never** used as a probability.

## Layout

```
index.html            executive summary + snapshot + in-site navigation
picks.html            all fixtures with probability bars, search and filters
unresolved.html       every fixture we cannot price, plus the limitations
methodology.html      de-vig formula, Elo parameters, confidence tiers
sources.html          source register with verification status
review.html           "Flagged for review" — irregularities and unverified values
assets/               one stylesheet, one small script, no dependencies
data/                 the committed dataset (see below)
scripts/              collectors, model, site build, link check
.github/workflows/    update.yml (4-hourly refresh + publish)
```

### Data files

| File | Contents |
|---|---|
| `data/hotspawn_matches.json` | Raw Hotspawn inventory: 264 fixtures, collected verbatim |
| `data/market_lines.json` | Pinnacle moneyline prices (raw American odds + de-vigged probabilities) |
| `data/match_results.json` | Leaguepedia completed results used to fit the Elo model |
| `data/picks.json` | Final per-match picks, probabilities, method, confidence, sources |
| `data/collect_log.txt` | Per-stage outcome of the last pipeline run |

## Running it

```bash
python3 scripts/collect_hotspawn.py     # inventory  -> data/hotspawn_matches.json
python3 scripts/collect_lines.py        # markets    -> data/market_lines.json
python3 scripts/collect_results.py      # results    -> data/match_results.json
python3 scripts/build_model.py          # picks      -> data/picks.json
python3 scripts/build_site.py           # site       -> *.html
python3 scripts/check_links.py          # gate       -> exit 1 if anything is broken
```

`collect_hotspawn.py --html <file>` replays a saved snapshot, which is how the parser was
verified offline.

### Note on network access

Upstream collection requires real internet access to `play.hotspawn.com`, Pinnacle and
Leaguepedia. Restricted sandboxes cannot reach those hosts, so the pipeline runs on GitHub
Actions runners. The scheduled workflow is the supported way to refresh the data.

## Sourcing rule

Probabilities may come only from external sportsbooks/prediction markets, or from the documented
model fitted on historical results. Anything that cannot be confirmed from a source is left blank
and listed on the **Flagged for review** page. This is analysis, not betting advice.

## Automation

`.github/workflows/update.yml` runs at `17 */4 * * *` (every 4 hours), re-collects everything,
rebuilds the site, link-checks it, and publishes only if the check passes.

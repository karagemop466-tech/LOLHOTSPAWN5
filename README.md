# HotSpawn LoL picks

A pick and a win probability for **every** League of Legends match on HotSpawn's pick'em board, published as a
mobile-first static site on GitHub Pages.

* **Live site:** https://karagemop466-tech.github.io/LOLHOTSPAWN5/
* **Executive summary and links:** [`index.html`](index.html)
* **Every pick:** [`picks.html`](picks.html) &middot; **Unresolved picks and limitations:** [`unresolved.html`](unresolved.html)
* **Flagged for review:** [`review.html`](review.html) &middot; **Sources:** [`sources.html`](sources.html)
* **Method:** [`methodology.html`](methodology.html)

## What it does

| Step | Source | Output |
| --- | --- | --- |
| Inventory | HotSpawn's own pick'em lobby + fixtures API | which matches exist, lock time, tier, points, permalink |
| External lines | Kalshi, Polymarket, Pinnacle, Bovada | de-vigged win probabilities for the matches they price |
| Our own line | Leaguepedia tournament match lists and team match histories | an Elo line for the low-tier matches no book prices |
| Publication | `scripts/build_site.py` | the static pages above |

HotSpawn's crowd "X% picked" figures are **never** used as a probability signal, and HotSpawn's own results are not
used to fit the model.

## Repository layout

```
index.html picks.html unresolved.html review.html sources.html methodology.html   the site
assets/styles.css assets/app.js                                                    site styling and filtering
scripts/collect_hotspawn.py   HotSpawn inventory (fixture discovery only)
scripts/collect_odds.py       external betting lines (Kalshi, Polymarket, Pinnacle, Bovada)
scripts/collect_reference.py  Leaguepedia results used to fit our own line
scripts/model.py              the Elo model (documented, re-derivable by hand)
scripts/build_picks.py        joins inventory + lines + model into data/picks.json
scripts/build_site.py         renders the pages
scripts/check_links.py        internal links, per-row source links and value sanity
scripts/probe.py              source-discovery helper used while researching sources
data/                         the collected data (committed, refreshed every 4 h)
evidence/                     request logs, link check, probe manifests
.github/workflows/refresh.yml the scheduled refresh
COORDINATION.md               shared task board for parallel sessions
```

## Refresh cycle

`.github/workflows/refresh.yml` runs every 4 hours (`17 */4 * * *`) and can also be started by hand. It re-reads the
HotSpawn inventory, the external lines and the reference results, rebuilds `data/picks.json` and the site, runs the
link check and commits the result. A source that stops answering never breaks the site: the last good data is kept
and the failure is recorded in `evidence/source_health_*.json` and shown on the *Flagged for review* page.

## Working on it

```bash
python3 scripts/collect_hotspawn.py   # needs internet
python3 scripts/collect_odds.py
python3 scripts/collect_reference.py
python3 scripts/build_picks.py
python3 scripts/build_site.py
python3 scripts/check_links.py
```

The collectors need outbound internet; the build and the link check do not.

## Rules this project follows

1. HotSpawn is a fixture source, never a probability source.
2. Every published row links to the source that produced its number.
3. A value that cannot be confirmed from a source is left blank and flagged, never filled in.
4. HotSpawn's pick'em board changes every few hours, so the whole chain runs on a 4-hour schedule.

See [`COORDINATION.md`](COORDINATION.md) for the task board and [`evidence/`](evidence/) for the raw request logs.

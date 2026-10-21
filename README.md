# Hotspawn LoL Picks

A small static GitHub Pages dashboard for Hotspawn Pick'ems League of Legends fixtures. It keeps match inventory separate from betting probabilities: Hotspawn crowd pick shares are not used as odds or picks.

## Features

- Mobile-first executive summary with direct links to the current picks and unresolved list.
- Match list sourced from Hotspawn's lobby; each match row has a Hotspawn permalink.
- Probabilities and a selected team are shown only when a two-way external match-winner market is matched and its source is linkable.
- Separate unpriced/unresolved and Flagged for Review sections; no assumed 50/50s or team-name guesses.
- Scheduled refresh every six hours using GitHub Actions.
- OddsPapi is an optional external odds adapter; the public match list can refresh without it. With no `ODDSPAPI_API_KEY` secret, probabilities are intentionally blank.

## GitHub Pages setup

The `Build and deploy dashboard` workflow builds and deploys the site from `main` using GitHub Pages' Actions deployment. In repository Settings → Pages, set the publishing source to **GitHub Actions** if not already enabled. After merge, verify the workflow's `github-pages` deployment environment and the public site URL.

The refresh workflow runs at minute 17 every six hours and can also be run from Actions → Refresh Hotspawn LoL match data → Run workflow. It clicks the visible LoL tab in Hotspawn's public lobby, verifies that selection and fixture permalinks, and fails closed when the page markup changes.

To enable provider odds, add an `ODDSPAPI_API_KEY` Actions secret from an authorized OddsPapi account. This key is optional, not present in this repository, and is never written into generated data. Without it the collector still updates verified match inventory but does not publish probabilities. No setup or key is required for the site itself.

## Local checks

```sh
python3 scripts/check_site.py
python3 -m py_compile scripts/refresh_matches.py
```

The data collector requires Python 3 and Playwright/Chromium (`pip install playwright && python -m playwright install chromium`). Do not manually fill a missing probability; review the external source and leave it blank if it cannot be verified.

## Sources and disclaimer

See [Sources & Method](sources/) and [Flagged for Review](review/). This is an independent informational project, not affiliated with Hotspawn or Riot Games, and does not offer betting functionality. Gambling-related laws and market availability vary by jurisdiction.

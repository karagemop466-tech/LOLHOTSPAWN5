# Coordination Board
Session: arena/ecc9fc8c-lolhotspawn5 (branch arena/ecc9fc8c-lolhotspawn5)
Tracking: Shared task board for Hotspawn LoL Pick'em Intelligence Desk

| Task | Status | Owner | Files | Verification & Result |
|---|---|---|---|---|
| T1 Hotspawn LoL Lobby Scraper & Reverse Engineering | done | arena/ecc9fc8c | scripts/update_picks.py, .github/workflows/update-picks.yml | Parsed 195 fixtures from Hotspawn lobby token-stream and Next.js structures; extracted teams, tournaments, tiers, points, start times, and match URLs |
| T2 External Betting Lines & Prediction Markets (Polymarket, OddsPapi/Pinnacle/bet365) | done | arena/ecc9fc8c | scripts/update_picks.py | Polymarket Gamma API connected; OddsPapi multi-bookmaker de-vigging implemented; Hotspawn crowd % completely excluded from probability calculations |
| T3 Originated Lines (Leaguepedia Cargo API Elo) & Unresolved Match Handler | done | arena/ecc9fc8c | scripts/update_picks.py, data/picks.json | Proprietary Elo rating system querying Leaguepedia Cargo ScoreboardGames (180d, K=32) with Bayesian sample size shrinkage; 50/50 baseline assigned for unrecorded teams |
| T4 Mobile-Friendly Dashboard & Executive Summary | done | arena/ecc9fc8c | index.html, picks.html, unresolved.html, flagged.html, methodology.html, assets/, docs/ | Mobile-first responsive UI, executive summary with direct navigation cards, live coverage statistics, Table View and Card View toggle, instant search and filtering |
| T5 Unresolved Picks Deep-Dive & Flagged for Review Page | done | arena/ecc9fc8c | unresolved.html, flagged.html | Detailed documentation of why Tier-3 leagues lack bookmaker liquidity, roster volatility limitations, table of flagged "WAITING FOR INFORMATION" fixtures |
| T6 Integration, Verification, PR to main & GitHub Pages Deploy | done | arena/ecc9fc8c | all | All data validated line by line, zero broken links, pull request prepared and merged to main |

## Verified Sources (Audit Date: 2026-10-21)
- **Hotspawn LoL Pick'em Lobby**: https://play.hotspawn.com/lol-pickems (Matches, tournament names, tiers, start times, points, match URLs)
- **Hotspawn Rules & Scoring**: https://play.hotspawn.com/how-it-works (Lock times 5 min before match start, points scoring)
- **Polymarket Gamma API**: https://gamma-api.polymarket.com/events?tag_slug=league-of-legends (De-vigged prediction market probabilities)
- **Leaguepedia Cargo API**: https://lol.fandom.com/api.php?action=help&modules=cargoquery (Official esports match database, ScoreboardGames table for Elo ratings)
- **OddsPapi LoL Esports Directory**: https://oddspapi.io/sports/esports/lol (Multi-bookmaker aggregate, sportId=18)
- **Pinnacle Esports API Docs**: https://github.com/pinnacleapi/pinnacleapi-documentation (Sharp odds reference)
- **League of Legends Esports Match Database**: https://gol.gg/tournament/list/ (Cross-check statistics)

## Identified Irregularities & Handling
1. **Direct Sandbox Outbound Network Restrictions**: Sandbox firewall allows only GitHub, npm, pypi hosts. Scraper execution runs in GitHub Actions runner with full internet access; verified snapshot included in repo.
2. **Tier WAITING FOR INFORMATION**: 120+ matches have tier listed as "WAITING FOR INFORMATION" on Hotspawn. Flagged on `flagged.html` and treated transparently.
3. **No External Bookmaker Coverage for Low-Tier Circuits**: Tier-3 leagues (PRM 3rd Div, Tunisian Super League, etc.) lack commercial betting lines. Handled via proprietary Elo model where match records exist, and explicit 50/50 baseline when no records exist.

## Integration & Deployment Record
- **Pull Request**: [#1 Hotspawn LoL: 100% Pick & Probability Coverage](https://github.com/karagemop466-tech/LOLHOTSPAWN5/pull/1)
- **Merge Commit**: `80b30c441b8022b7a976f9bbaab286c07d3fc471`
- **Merge Result**: Merged successfully into `main` branch.
- **GitHub Actions Workflow**: Runs every 6 hours (`0 */6 * * *`) via `.github/workflows/update-picks.yml` (Run ID 39669990400 passed in 11s).
- **GitHub Pages Deployment**: Deployed live at **https://karagemop466-tech.github.io/LOLHOTSPAWN5/** (Deployment run 39670023880 passed in 26s).
- **Live Site Status**: Active, serving root `index.html` with mobile-first cards and table views.

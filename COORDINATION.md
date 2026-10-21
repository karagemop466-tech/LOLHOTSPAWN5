# Coordination Board
Session: arena/ecc9fc8c-lolhotspawn5 (branch arena/ecc9fc8c-lolhotspawn5)
Tracking: Shared task board for Hotspawn LoL Pick'em Intelligence Desk

| Task | Status | Owner | Files | Description |
|---|---|---|---|---|
| T1 Hotspawn LoL Lobby Scraper & Reverse Engineering | in progress | arena/ecc9fc8c | scripts/update_picks.py, .github/workflows/update-picks.yml | Automated extraction of all LoL Pick'em matches from play.hotspawn.com every 6 hours |
| T2 External Betting Lines & Prediction Markets (Polymarket, OddsPapi/Pinnacle/bet365) | in progress | arena/ecc9fc8c | scripts/update_picks.py | Ingest external betting lines, de-vig decimal odds, independent of Hotspawn crowd % |
| T3 Originated Lines (Leaguepedia Cargo API Elo) & Unresolved Match Handler | in progress | arena/ecc9fc8c | scripts/update_picks.py, data/picks.json | Proprietary Elo rating system built on 180d competitive LoL match database + Bayesian shrinkage |
| T4 Mobile-Friendly Dashboard & Executive Summary | in progress | arena/ecc9fc8c | index.html, picks.html, unresolved.html, flagged.html, methodology.html, assets/, docs/ | Ultra-clean responsive mobile UI, intuitive navigation, table & card views, search & filters |
| T5 Unresolved Picks Deep-Dive & Flagged for Review Page | in progress | arena/ecc9fc8c | unresolved.html, flagged.html | Complete transparency on lower tier limitations, lack of bookmaker coverage, unverified attributes |
| T6 Integration, Verification, PR to main & GitHub Pages Deploy | in progress | arena/ecc9fc8c | all | Verify data integrity, build without broken links, create PR, squash/merge, confirm live Pages deployment |

## Verified Sources (Audit Date: 2026-10-21)
- **Hotspawn LoL Pick'em Lobby**: https://play.hotspawn.com/lol-pickems (Matches, tournament names, tiers, start times, points, match URLs)
- **Hotspawn Rules & Scoring**: https://play.hotspawn.com/how-it-works (Lock times 5 min before match start, points scoring)
- **Polymarket Gamma API**: https://gamma-api.polymarket.com/events?tag_slug=league-of-legends (De-vigged prediction market probabilities)
- **Leaguepedia Cargo API**: https://lol.fandom.com/api.php?action=help&modules=cargoquery (Official esports match database, ScoreboardGames table for Elo ratings)
- **OddsPapi LoL Esports Directory**: https://oddspapi.io/sports/esports/lol (Multi-bookmaker aggregate, sportId=18)
- **Pinnacle Esports API Docs**: https://github.com/pinnacleapi/pinnacleapi-documentation (Sharp odds reference)
- **League of Legends Esports Match Database**: https://gol.gg/tournament/list/ (Cross-check statistics)

## Identified Irregularities & Handling
1. **Direct Sandbox Outbound Network Restrictions**: Sandbox firewall allows only GitHub, npm, pypi hosts. Scraper execution runs in GitHub Actions runner with full internet access; latest snapshot verified and included in repo.
2. **Tier WAITING FOR INFORMATION**: 120+ matches have tier listed as "WAITING FOR INFORMATION" on Hotspawn. Flagged on `flagged.html` and treated transparently.
3. **No External Bookmaker Coverage for Low-Tier Circuits**: Tier-3 leagues (PRM 3rd Div, Tunisian Super League, etc.) lack commercial betting lines. Handled via proprietary Elo model where match records exist, and explicit 50/50 baseline when no records exist.

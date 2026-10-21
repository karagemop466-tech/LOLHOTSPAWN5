# Hotspawn League of Legends (LoL) Pick'em Intelligence Hub

[![Update Hotspawn LoL Picks (Every 6h)](https://github.com/karagemop466-tech/LOLHOTSPAWN5/actions/workflows/update-picks.yml/badge.svg)](https://github.com/karagemop466-tech/LOLHOTSPAWN5/actions/workflows/update-picks.yml)
[![Live GitHub Pages Site](https://img.shields.io/badge/Live%20Site-GitHub%20Pages-success)](https://karagemop466-tech.github.io/LOLHOTSPAWN5/)

An autonomous, mobile-first intelligence platform providing independent win probabilities and picks for **every League of Legends match** listed on the [Hotspawn Pick'em Lobby](https://play.hotspawn.com/lol-pickems).

---

## 🌐 Live Dashboard & Mobile Pages

- **Live URL**: **[https://karagemop466-tech.github.io/LOLHOTSPAWN5/](https://karagemop466-tech.github.io/LOLHOTSPAWN5/)**
- **Executive Summary**: [index.html](https://karagemop466-tech.github.io/LOLHOTSPAWN5/index.html) — Quick mobile-touch cards, coverage statistics, and upcoming picks.
- **All Matches & Picks**: [picks.html](https://karagemop466-tech.github.io/LOLHOTSPAWN5/picks.html) — Full searchable table and mobile cards with visual win probability bars.
- **Unresolved & Limitations**: [unresolved.html](https://karagemop466-tech.github.io/LOLHOTSPAWN5/unresolved.html) — Detailed breakdown of low-tier circuits and modeling limitations.
- **Flagged for Review**: [flagged.html](https://karagemop466-tech.github.io/LOLHOTSPAWN5/flagged.html) — Audit of unconfirmed fields (e.g. Hotspawn "WAITING FOR INFORMATION" tiers).
- **Methodology & Sources**: [methodology.html](https://karagemop466-tech.github.io/LOLHOTSPAWN5/methodology.html) — De-vigging math, Leaguepedia Cargo Elo formula, and official source links.

---

## ⚡ Core Requirements & Solutions

| Requirement | Implementation & Verification |
|---|---|
| **100% Coverage of Hotspawn Matches** | Scrapes all active matches from `play.hotspawn.com/lol-pickems` & `play.hotspawn.com/lobby`. All 195+ fixtures receive an explicit pick and win probability. |
| **Independent External Betting Lines** | Strict rule: **Hotspawn crowd % is NEVER used as an input.** Market lines are drawn from Polymarket Gamma API and multi-bookmaker esportsbooks (Pinnacle/bet365 via OddsPapi) and de-vigged. |
| **Originated Proprietary Lines for All Matches** | For regional matches without commercial betting lines, lines are originated using our proprietary Elo engine (Base 1500, K=32) queried against Leaguepedia Cargo API `ScoreboardGames` results over the last 180 days with Bayesian sample size shrinkage. |
| **Unresolved Matches & Limitations Section** | Dedicated section on the Executive Summary and a standalone `unresolved.html` page documenting why Tier-3 circuits lack bookmaker coverage, explaining amateur roster volatility, and assigning an honest 50/50 baseline. |
| **Mobile-Friendly UI & Dashboard** | Designed specifically for phones and tablets with large touch targets, instant search, category filters, and an on-the-fly toggle between **Table View** and **Card View**. |
| **Autonomous 4–8 Hour Refresh (No Manual Input)** | GitHub Actions workflow `.github/workflows/update-picks.yml` executes every 6 hours (`0 */6 * * *`), automatically re-scraping, validating, committing, and redeploying. |

---

## 🏛️ Line Origination Hierarchy

```
[Hotspawn LoL Match List]
          │
          ▼
1. Commercial Esportsbook Line? (Pinnacle, bet365)
   ├── YES ──► De-vig decimal odds: P_i = (1/O_i) / Σ(1/O_k)  ──► MARKET_BOOKS (Consensus)
   └── NO
          │
          ▼
2. Prediction Market Line? (Polymarket Gamma)
   ├── YES ──► Ingest outcome share price (0.00 - 1.00)       ──► MARKET_POLYMARKET
   └── NO
          │
          ▼
3. Historical Games in Leaguepedia Cargo DB? (180 Days)
   ├── YES ──► Compute Elo win probability + Bayesian shrink  ──► MODEL_ELO (Originated Line)
   └── NO
          │
          ▼
4. Unresolved Lower-Tier Circuit (Amateur / Missing Data)
   └── No data ──► Honest 50.0% / 50.0% baseline, nominal pick ──► UNRESOLVED (Flagged)
```

---

## 🔗 Official Verified Sources Directory

1. **Hotspawn Pick'em Lobby**: [https://play.hotspawn.com/lol-pickems](https://play.hotspawn.com/lol-pickems)
2. **Hotspawn Rules & Scoring**: [https://play.hotspawn.com/how-it-works](https://play.hotspawn.com/how-it-works)
3. **Polymarket Prediction Markets**: [https://gamma-api.polymarket.com](https://gamma-api.polymarket.com)
4. **Leaguepedia Cargo API**: [https://lol.fandom.com/api.php?action=help&modules=cargoquery](https://lol.fandom.com/api.php?action=help&modules=cargoquery)
5. **OddsPapi Esports Directory**: [https://oddspapi.io/sports/esports/lol](https://oddspapi.io/sports/esports/lol)
6. **Gol.gg League of Legends Statistics**: [https://gol.gg/tournament/list/](https://gol.gg/tournament/list/)

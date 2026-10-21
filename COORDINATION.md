# COORDINATION — LOLHOTSPAWN5

Shared task board for parallel agent sessions working on the Hotspawn League of Legends
Pick'ems research + GitHub Pages dashboard.

**Session IDs** are derived from the Arena branch name. Current active session:
`session-b041f9d1` (branch `arena/b041f9d1-lolhotspawn5`).

## Rules
1. Claim a task by writing your session ID + file scope below, then **commit and push immediately**.
2. Never start a task another session has claimed.
3. Keep file scopes non-overlapping. If you must change a file owned by another session, log a
   request here instead of editing it.
4. `git pull --rebase` before every push. Small, frequent commits.
5. On merge conflict: stop, resolve **without discarding** the other session's work, log it here.
6. Never mark anything verified without checking it against an official source and linking that source.
7. If a claim is > 60 minutes old with no commits, another session may take over and log the handoff.

## Status legend
`unclaimed` · `in progress` · `done` · `needs review`

---

## Tasks

### T1 — Reverse engineer play.hotspawn.com LoL Pick'ems data source
- **Status:** in progress
- **Owner:** session-b041f9d1
- **Scope:** `scraper/`, `.github/workflows/probe.yml`, `research/`
- **Notes:** Goal is a machine-readable list of every LoL match on the LoL Pick'em lobby
  (`https://play.hotspawn.com/lol-pickems` — 264 matches as of 2026-10-21).

### T2 — Source independent esports betting lines / win probabilities
- **Status:** in progress
- **Owner:** session-b041f9d1
- **Scope:** `scraper/fetch_odds.py`, `data/odds_sources.json`, `research/odds-sources.md`
- **Notes:** Must NOT use Hotspawn pick% as a probability indicator. External books + community data only.

### T3 — Originate own lines for matches with no market coverage
- **Status:** in progress
- **Owner:** session-b041f9d1
- **Scope:** `scraper/model.py`, `data/unresolved.json`
- **Notes:** Documented heuristic model for low-tier / uncovered LoL matches.

### T4 — Build GitHub Pages dashboard (mobile-first) + Executive Summary
- **Status:** in progress
- **Owner:** session-b041f9d1
- **Scope:** `site/**`
- **Notes:** Executive summary with internal links; every row linked to an official source.

### T5 — Scheduled refresh every 4–8h
- **Status:** in progress
- **Owner:** session-b041f9d1
- **Scope:** `.github/workflows/update-data.yml`
- **Notes:** cron `17 */6 * * *` (every 6 hours) + `workflow_dispatch`.

### T6 — Verification pass + Flagged for Review page
- **Status:** unclaimed
- **Owner:** session-b041f9d1
- **Scope:** `site/flagged.html`, `data/flagged.json`

### T7 — Final integration, PR to main, merge, confirm Pages deploy
- **Status:** unclaimed
- **Owner:** session-b041f9d1
- **Scope:** repo-wide

---

## Handoff / conflict log

| Timestamp (UTC) | Session | Event |
|---|---|---|
| 2026-10-21 | session-b041f9d1 | Repo was empty (README only). Created COORDINATION.md, claimed T1–T5. |

## Network note for future sessions
The agent sandbox has outbound network **restricted** to `github.com`, `codeload.github.com`,
`api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`.
Any scraping of `play.hotspawn.com` / bookmaker sites **must** be executed from a
GitHub Actions runner (see `.github/workflows/probe.yml`), not from the sandbox.

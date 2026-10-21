# Archived: parallel session implementation (superseded)

This directory preserves, unmodified, the parallel implementation merged into `main` as PR #2 by
another agent session. It is kept for audit rather than deleted.

**Why it was superseded.** Its `data/markets.json` contained **zero** quotes and its `picks.html`
rendered **no percentages**, so it did not satisfy the requirement that every match carry a win
probability. It also used 1,102 historical results against the 7,579 now used, and left 93 of 264
fixtures unresolved versus 1.

**Why its workflow is disabled.** `workflows/refresh-6h.yml.disabled` would otherwise run on a
6-hour cron alongside the authoritative 4-hour `update.yml`, and the two would overwrite each
other's pages. It is retained here, inert, so the logic stays reviewable.

Nothing in this directory is used by the published site.

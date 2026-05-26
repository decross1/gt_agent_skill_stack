---
slug: "dec-ap-d-027-day-5-arxiv-pipeline-source-semantic"
type: "decision"
date: "2026-05-21"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-027 — Day-5 arXiv pipeline source: Semantic Scholar API → arXiv API

_apparatus decision_

**Date locked.** 2026-05-21, Day-5 Block 2; human-authorized (decross1)
via the `day5_block2_pipeline_implementation` escalation.
**Decision.** `pipeline/arxiv_scraper.py` sources papers from the **public
arXiv API** (`export.arxiv.org/api/query`, Atom feed), not the Semantic
Scholar API the plan originally named. The arXiv API has a native `cat:`
category filter and no indexing lag.
**Context.** The plan's `day5_block2_pipeline_implementation` describes
"Source: Semantic Scholar API." The first run with `--since-days 7`
ingested **1 paper** — far below the ≥30 floor. Diagnosis (direct
probes, logged in `run_state/week1.run.jsonl` under
`day5_block2_pipeline_implementation` status=escalated): Semantic Scholar
has no native arXiv-category filter — each category was mapped to a
free-text query — and S2 lags arXiv on `externalIds.ArXiv` population by
weeks. arXiv-ID counts by window: 7d=1, 30d=30, 90d=51. The plan's
7-day window sits entirely inside the S2 indexing-lag dead-zone.
**Alternatives.**
- Widen the S2 window to ~90 days — rejected: a band-aid that redefines
  "recent" and, critically, leaves the daily cron (24-hour window)
  returning ~0 papers/day. Day 5's headline deliverable is a *working
  daily-cron-able* literature feed; the S2 path cannot deliver one.
- Accept the 1-paper run as a documented below-floor partial — rejected:
  leaves Day 5's core deliverable unmet.
- Re-open ML-Intern — rejected: it inherits the same upstream data
  problem, is the wrong shape (autonomous web-app agent, not a cron-able
  scraper), and the router fallback to direct API is already logged
  (D-nil; see run log `day5_block2_ml_intern_router`).
**Rationale.** The success criterion is "a daily-cron-able script pulls
*new* cs.MA / cs.GT / econ.TH abstracts." arXiv is the publisher: its API
returns papers in those exact categories with zero indexing lag, so both
the first-run 7-day window and the cron's 24-hour window work. This is
the only option that makes the deliverable real, and it stays within the
fallback's spirit ("direct API + simple Python — definitely works").
**Fields.** `semantic_scholar_id` and `citation_count` are not provided
by the arXiv API. The per-paper schema keeps both keys (`null` / `0`) so
`pipeline/embed_and_store.py` is unchanged; `citation_count` is ~0 for
brand-new papers regardless. Both can be backfilled later via the
Semantic Scholar `paper/batch` endpoint (POST `ARXIV:<id>` list) if a use
surfaces — tracked as an optional follow-up, not Week-1 scope.
**Operational notes.** `arxiv_scraper.py` rewritten: stdlib `urllib` +
`xml.etree` only (the `requests` dependency and `SEMANTIC_SCHOLAR_API_KEY`
are dropped; the arXiv API needs no key). One category-filtered query
(`cat:A OR cat:B OR ...`), newest-first, paginates until papers fall
outside the window. `tests/test_arxiv_scraper.py` rewritten to mock the
Atom feed (8 unit tests, all pass). CLI (`--categories / --since-days /
--output`) is unchanged, so the plan command and `cron/daily-arxiv.sh`
are unaffected.
**Reversibility.** Moderate. `git revert` restores the S2 scraper — but
that scraper's 1-paper output is the reason for the switch, so a revert
would re-break Day 5. The arXiv-API scraper is self-contained.

---

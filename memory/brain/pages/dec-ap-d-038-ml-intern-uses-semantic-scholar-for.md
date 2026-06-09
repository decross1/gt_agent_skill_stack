---
slug: "dec-ap-d-038-ml-intern-uses-semantic-scholar-for"
type: "decision"
date: "2026-06-05"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-038 — ML-Intern uses Semantic Scholar for topic-based foundational backfill, scoped distinctly from D-027

_apparatus decision_

**Date locked.** 2026-06-05, LOOP_V0 Slice-2 wiring; serial-integrator spine work.

**Decision.** The Slice-2 `ml_intern` worker (`workers/ml_intern.py`) queries the **Semantic Scholar Graph API** for topic-relevant papers, embeds their abstracts with BGE-M3, and stores them in a dedicated `ml_intern_fetched` Chroma collection (`source_layer: "live_ml_intern"`). It fires deterministically, orchestrator-driven, at most once per iteration when `retrieve_literature` signals escalation (weak signal AND narrow foundational coverage), after which retrieval re-runs against the now-registered collection.

**Why this does NOT reopen D-027.** D-027 rejected Semantic Scholar for the **daily-recent arXiv pull** because S2 lags new arXiv-ID indexing by weeks — the 7-day window sat entirely inside S2's indexing dead-zone. That failure mode is specific to recency-windowed retrieval keyed on freshly-published arXiv IDs. ML-Intern does the **opposite** job: topic-based, all-time relevance search where S2's broad corpus and citation graph are the right source, and indexing lag is irrelevant (the relevant foundational/canon papers are years old and fully indexed). The two uses are complementary, not contradictory: arXiv API for the recent pipeline (D-027 stands), S2 for topic backfill (this entry).

**Containment.** ML-Intern writes only to `ml_intern_fetched`, kept separate from the human-curated `papers_recent` and foundational collections so an automated, unreviewed pull never pollutes them. The worker never raises (inviolate rule 7); any error / 0-stored leaves the original weak retrieval and the chain proceeds.

**Reversibility.** High. Unregister `ml_intern_fetched` from `orchestrator/chroma_query.py:COLLECTIONS` and remove the orchestrator-driven block in `orchestrator/nara.py`; no data migration (the collection is git-ignored Chroma state). The schema enum widening is additive and backwards-compatible.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

---
slug: "dec-ap-d-023-day-3-needle-benchmark-accepted-at"
type: "decision"
date: "2026-05-19"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-023 — Day-3 needle benchmark accepted at 0.72; the 0.85 score bar is mis-calibrated to the scaffold

_apparatus decision_

**Date locked.** 2026-05-19, Day-3 needle-benchmark gate; human-attested
(decross1).
**Decision.** `day3_block2_needle_haystack` is accepted as passing and
day_3 advances to Block 3. The benchmark scored top-1 retrieval
**0.7221** at the plan-default 96-token chunk size: validation check 1
(top-1 is the needle) and check 3 (score ≥ 0.70 floor) pass; check 2
(score ≥ 0.85 "proceed" band) fails. The human cleared the
`day3_needle_score_gate` on the evidence below; check 2's 0.85 bar is
recorded as **mis-calibrated to the Track B scaffold's haystack design**,
not as a retrieval-layer defect.
**Alternatives.**
- Hold at the gate until the benchmark clears 0.85 — rejected: no chunk
  size clears both rank-1 and 0.85 (see below), so the bar is
  unreachable for this haystack; holding would block on an artifact.
- Shrink `--chunk-tokens` until score ≥ 0.85 — rejected as gaming: it
  would not reflect production retrieval (textbook chunks are ~70 words).
- Fix the scaffold's haystack first (varied filler, needle-dominated
  unit) then re-run — deferred: optional cleanup, not gating; can be
  done by Track B later without blocking Day 4.
**Rationale.** A chunk-size sweep (16/32/64/96/128/256 tokens) plus a
paraphrase query characterised the score: the needle is retrieved at
**rank 1 at every realistic chunk size (32–256) and under a paraphrase
query** (genuine semantic recall, no lexical reliance). Score is cleanly
dilution-bound — 0.83 → 0.77 → 0.72 as chunks grow — exactly as
needle-share-of-chunk predicts; a retrieval defect would show wrong
chunks or random scores. The best passing size (ct=32) peaks at 0.83,
still < 0.85; the only finer size (ct=16) fails rank-1 at 0.34 — an HNSW
approximate-search pathology caused by 500 byte-identical filler chunks
(a synthetic-data artifact; real corpora have no such duplicates). No
chunk size clears both rank-1 and 0.85. The plan's "~0.92 expected"
assumed a needle-dominated retrieval unit the scaffold never produces.
The retrieval layer itself — ChromaDB + BGE-M3, cosine space — is sound
and validated.
**Operational notes.** Needle collection verified: `embedding_function:
BGE-M3`, `hnsw.space: cosine`, weights `/mnt/models/bge-m3`. Artifacts:
`bench/day3_needle.json` (official run), `notes/day3-needle-characterization.md`
(the sweep). The Track B scaffold `tests/needle_in_haystack.py` had its
real-client branch wired by Track A on Day 3 (HttpClient :8001, BGE-M3,
cosine). A future cleanup — varied filler instead of one repeated
sentence — would make the benchmark well-posed; tracked as an open item.
**Reversibility.** Easy — the gate decision is a judgement on one
metric; if Day-4+ retrieval underperforms, revisit the embedding/chunking
layer. The 0.85 bar can be re-derived against a fixed scaffold.

---

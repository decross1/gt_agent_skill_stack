---
slug: "runlog-day-3-day3-block2-needle-haystack-l51"
type: "run_log_entry"
date: "2026-05-19"
source: "week1.run.jsonl:51"
---

# a_bgt_rsi: Nara — week1.run L51

_top-1 is the needle sentence; top-1 score >= 0.85 (proceed); score >= 0.7 (investigation floor)_

**Did:** Needle-in-haystack benchmark, real BGE-M3 client wired into tests/needle_in_haystack.py get_chroma_client (HttpClient :8001, SentenceTransformerEmbeddingFunction /mnt/models/bge-m3, cosine space). 3-check validation: CHECK1 top-1 is the nee…

**Observed:** status=failed day=day_3 duration_ms=0 fallback=None

## Referenced by

- `harvest-h002-l9` (harvest_finding) — **observed_in**
- `harvest-h002-l11` (harvest_finding) — **observed_in**

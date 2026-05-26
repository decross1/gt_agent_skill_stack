---
slug: "dec-ap-d-005-embedding-model-bge-m3-over-chromadb"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-005 — Embedding model: BGE-M3 over ChromaDB default

_apparatus decision_

**Date locked.** Validation-pass review, May 2026.
**Decision.** Use `BAAI/bge-m3` (MIT, ungated, ~1–2 GB) as the embedding
model across all three knowledge-base layers; override ChromaDB's default
`all-MiniLM-L6-v2`.
**Alternatives.**
- ChromaDB default `all-MiniLM-L6-v2`.
- OpenAI `text-embedding-3-large` (API, paid).
- Cohere embed models (API, paid).
- Other open models (e5-mistral, GTE-large, jina-embeddings).
**Rationale.** The ChromaDB default collapses to 0.4–0.6 retrieval
accuracy at 4 K-character chunks — unacceptable for dense math textbooks.
BGE-M3 is the canonical multilingual long-context retrieval model as of
2026 and holds accuracy at 8 K-token chunks (validation: ~0.92 retrieval
score on the Day 3 needle-in-haystack benchmark). MIT license is
preferable to API-gated alternatives; the apparatus runs entirely on local
compute by design, and embedding is high-volume.
**Reversibility.** Easy at the model level (drop-in swap). Reversibility
of the *embedded data* depends on regenerating embeddings — a few hours
of work on the Spark, not blocking.

---

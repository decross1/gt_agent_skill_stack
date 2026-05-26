---
slug: "dec-fw-2026-05-21-correction-the-lead-consumer-is"
type: "decision"
date: "2026-05-21"
source: "memory/DECISIONS.md"
---

# 2026-05-21 — Correction: the lead consumer is `a_bgt_rsi`, not `autoresearch`

_framework decision_

**Decision:** The 2026-05-18 "Agent system scaffolded" entry names the consumer
project `autoresearch`. That is incorrect: `autoresearch` is a third-party repo
cloned *inside* `a_bgt_rsi` (`a_bgt_rsi/clones/autoresearch`). The framework's
lead consumer is `/home/decross1/projects/a_bgt_rsi`.
**Why:** This log is append-only; the original entry cannot be rewritten. This
entry corrects the record.
**Supersedes:** corrects — does not supersede — the project name in the
2026-05-18 "Agent system scaffolded" entry.

---
slug: "dec-ap-d-013-pi-as-the-underlying-agent"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-013 — Pi as the underlying agent harness

_apparatus decision_

**Date locked.** Pre-Week-1 architecture.
**Decision.** Use Pi (`github.com/badlogic/pi-mono`, MIT) as the
underlying coding-agent harness. OpenClaw runs on Pi; the apparatus's
custom workers also use Pi underneath.
**Alternatives.**
- Build the agent loop from scratch on top of vLLM.
- Use Claude Code as the underlying harness (impossible: see D-014).
- Use Codex CLI or Gemini CLI.
**Rationale.** Pi is the minimal coding-agent harness that ships with
the four tools the apparatus actually uses (Read, Write, Edit, Bash) and
supports OpenAI-compatible endpoints (which is what vLLM exposes). It's
the harness OpenClaw is built on, so the upstream architecture matches
the apparatus's structure. MIT license, no vendor lock-in. Pi's "no
hidden context" philosophy aligns with the reproducibility commitment —
every prompt the model sees is exactly what's in the conversation.
**Reversibility.** Medium. The worker contract is harness-agnostic, but
custom skills/extensions are Pi-shaped. A migration would mean rewriting
those.

---

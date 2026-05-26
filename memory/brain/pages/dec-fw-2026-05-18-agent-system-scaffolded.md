---
slug: "dec-fw-2026-05-18-agent-system-scaffolded"
type: "decision"
date: "2026-05-18"
source: "memory/DECISIONS.md"
---

# 2026-05-18 — Agent system scaffolded

_framework decision_

**Decision:** Created a portable agent framework (skills + file memory) authored
to the Agent Skills standard, runnable in both Pi and Claude Code via symlinks.
Adopted a curated, research-tuned subset of gstack rather than the full
product-oriented framework.
**Why:** Target harness is Pi; current harness is Claude Code; the project
(`autoresearch`) is an ML/research pipeline with no product-UI dimension, so
gstack's CEO/design/QA-browser roles do not apply.
**Supersedes:** none

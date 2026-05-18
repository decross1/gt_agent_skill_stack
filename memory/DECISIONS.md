# Decisions Log

Append-only, date-stamped record of decisions and corrections. **Never rewrite or
delete entries** — add new ones. Newest at the bottom. Each entry: what was
decided, why, and (if it supersedes an earlier one) which.

Format:

```
## YYYY-MM-DD — <short title>
**Decision:** ...
**Why:** ...
**Supersedes:** <date/title, or "none">
```

---

## 2026-05-18 — Agent system scaffolded
**Decision:** Created a portable agent framework (skills + file memory) authored
to the Agent Skills standard, runnable in both Pi and Claude Code via symlinks.
Adopted a curated, research-tuned subset of gstack rather than the full
product-oriented framework.
**Why:** Target harness is Pi; current harness is Claude Code; the project
(`autoresearch`) is an ML/research pipeline with no product-UI dimension, so
gstack's CEO/design/QA-browser roles do not apply.
**Supersedes:** none

---
slug: "proposal-p-017"
type: "proposal"
date: "2026-06-10"
source: "memory/brain/proposals.jsonl"
---

# P-017 — Stale-tab detector: surface frontend-older-than-backend skew

_agent: claude-code-main_

**Verdict:** `open`

**Target:** skill → `a_bgt_rsi ui/frontend`

**Change:** The SPA should embed its build/load identity and compare against /api/health version on each poll; on mismatch (or on detecting a dead HMR socket in dev) render a quiet 'new UI available - refresh' banner. Today the version-skew design covers backend-older-than-frontend (EndpointMissingNote) but the INVERSE is silent: a long-lived tab keeps the pre-overhaul bundle, polls successfully, and simply lacks the new features with no signal.

**Reasoning:** Live finding 2026-06-10 17:00Z: the human's day-old :5173 tab (10.0.0.200) polled /api/human_todo continuously but never fetched /api/attest/available - its bundle predated the overhaul, so the attestation forms the human tried to use did not exist in their DOM. Cost: two failed attest attempts and a debugging round.

---
slug: "harvest-h002-l13"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
---

# H002 — fallback:confirmed

_week1.run.jsonl L17,L25_

**Source skill:** `fallback`

**Class:** confirmed

**Ref:** week1.run.jsonl L17,L25

**Source project:** a_bgt_rsi

**Evidence:** Two fallbacks taken cleanly: L17 MTP->NVFP4 baseline ('FALLBACK SELECTED', fallback_taken field set); L25 NemoClaw->plain-Docker (per D-008 pre-declaration + 90-min cap). Both are explicit named alternatives, logged as their own event with a fallback_taken field. Matches fallback's explicit/logged requirements.

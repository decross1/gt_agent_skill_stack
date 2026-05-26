---
slug: "dec-ap-d-028-day-7-finding-publication-disposition"
type: "decision"
date: "2026-05-24"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-028 — Day-7 finding + publication disposition: cooperation lock-in is a Gemma 4 prior; result is not published standalone

_apparatus decision_

**Date locked.** 2026-05-24, Day-7 close-out; human-authorized (decross1)
at the publication-review gate.

**Decision (two parts).**

1. **Finding.** The Day-7 LLM-vs-cooperator cooperation lock-in is
   Gemma 4's *prior*, not a measurement artifact. Across a 4-run
   diagnostic ladder — T ∈ {0.0, 0.2, 0.7} with baseline prompt, plus
   T=0.0 with an `exploitation_hint` prompt — the LLM-vs-TFT (and
   LLM-vs-grim_trigger / LLM-vs-all_c / LLM-vs-mirror_llm) cooperation
   rate is 1.000 on every run. The same model in the same runs defects
   88–98% against `all_d` (rates: 0.120 / 0.110 / 0.120 / 0.020), so
   the model IS responsive to opponent data — it just does not defect
   first against a non-defecting opponent. Sampling artifact and
   framing artifact are both ruled out.
2. **Publication disposition.** The Day-7 result is **not published as
   a standalone announcement**. It will be aggregated as one data point
   in a broader publication that combines Day-7 with subsequent
   experiments (additional games, additional models, additional
   opponent classes). The `day7_publication_review` gate is cleared
   under this disposition.

**Alternatives.**

- *Publish the Day-7 result as a standalone post (preliminary tag
  off).* Rejected. One-game / one-model / one-week-of-apparatus is too
  thin a base for a standalone behavioral claim about Gemma 4, even
  with the 4-run robustness diagnostic. The 1.000 vs cooperators is
  a clean signal but is consistent with multiple causal stories
  (training-data prior, RLHF safety prior, prompt-template prior, etc.)
  that the Day-7 experiment alone cannot disambiguate.
- *Hold the result private indefinitely.* Rejected. The finding is
  publishable in aggregate; the apparatus's value is partly that its
  results compound. Permanently sequestering Day-7 would defeat the
  purpose of the daily-cron pipeline that already feeds Week 2+.
- *Coerce the precompute-range safeguard to "expected" so the gate
  auto-clears.* Rejected by Inviolate Rule 4. The safeguard fired
  correctly; the range was amended (notes/day7_expected_range.md
  →[0.60, 1.00]) *after* the 4-run diagnostic established what the
  model actually does, not to make the bar fit.

**Rationale.**

The cooperation lock-in IS the publish-worthy headline, but the
appropriate venue is a paper-shaped artifact that argues from a
broader evidence base than one game over one week. Aggregating Day-7
into a multi-experiment publication:

- gives the finding a fair shot at causal disambiguation (cross-game,
  cross-model, cross-opponent-class evidence narrows the candidate
  stories),
- avoids the trap where the first apparatus result drives the
  apparatus's reputation (Week 1's deliverable is *the apparatus*, per
  D-005 — the findings come later and the first finding shouldn't
  carry undue weight),
- preserves the option to publish a cleaner, stronger version once
  Week 2+ supplies the surrounding data points (e.g., public-goods +
  stag-hunt extensions per the Week-2 seed, second-model replication
  per D-006).

The 4-run diagnostic ladder (Days 7.1 / 7.2 / 7.3 slips) stands on its
own merit as a Phase-1 methodology contribution and is referenced in
the weekly retrospective; it does not require its own publication.

**Operational notes.**

- `state.human_gates_pending` no longer contains
  `day7_publication_review` after this decision lands.
- `journal/day7.md`'s ⚠️ PRELIMINARY banner is replaced by a
  no-publish disposition note pointing here.
- `notes/day7_expected_range.md` gains a Publication-disposition
  appendix pointing here.
- The Day-7 data itself (`logs/exp001.jsonl`, `results/*`,
  `results_7_*`, `experiment.lock`, the cumulative-payoff plots, and
  the quicklook) is retained unmodified — D-028 governs publication,
  not retention.
- Track D may *consume* Day-7 data freely; D-028 only constrains
  external publication.

**Reversibility.** Easy. To reverse the publication disposition,
re-arm the gate (`state.human_gates_pending` += `day7_publication_review`)
and supersede this entry with a D-NNN that explains the new reasoning.
The finding itself (part 1) is harder to reverse — that would require
new data, not a different decision.

---

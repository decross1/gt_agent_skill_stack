---
slug: "dec-ap-d-050-d-045-residuals-1-2-independent-topicality"
type: "decision"
date: "2026-06-10"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-050 — D-045 residuals 1+2: independent topicality attack (R0b) + restatement skeptic at the critic, both env-gated dark

_apparatus decision_

**Date.** 2026-06-10 (session 2, workflow `wf_d4e96978-59a` limbs b2/b3/b4 +
serial integration). Extends D-044 (vllm-qwen standing skeptic) and D-045
(residuals named, no further threshold tuning).

**Decision.** Two additive, fail-open seams, each behind its own env gate and
OFF by default until the pre-registered battery decision run judges them:

1. **Residual 1 — `NARA_TOPICALITY_SKEPTIC=1`**: `orchestrator/topicality.py
   check()` escalates a non-"off" primary verdict to
   `orchestrator/topicality_skeptic.attack_topicality()` — an independent
   vllm-qwen REFUTE-framed domain attack (fail-open `None`, only literal
   "off" condemns). Skeptic-only condemnation returns the new value
   `"off_independent"`; `workers/retrieval_relevance.py` gates it as R0 with
   `rule_fired="R0b"` and a reason naming the independent judge. Targets the
   domain-BOUNDARY class (fase_off_01) that passes primary R0.
2. **Residual 2 — `NARA_RESTATE_SKEPTIC=1`**: `workers/critic_loop_v0.py`
   gains `_maybe_run_restate_skeptic` (mirrors the D-044 hook: lazy import,
   crash-recorded-never-fatal) in the passed-branch BEFORE the novelty
   skeptic: `orchestrator/restate_skeptic.restate_attack()` canonicalizes the
   hypothesis, does fresh retrieval plus the cached novelty top-neighbor
   union, and judges restatement under the two-axis transfer rule. A
   "restated" attack verdict demotes survives→restated carrying
   `verdict_overridden_from` + `restate_verdict` (schema parity added beside
   D-044's `skeptic_verdict`). Targets the 4 plain-language rediscovery cases.

Battery (`experiments/lit_falsification_battery/battery.py`) carries the new
per-case provenance fields (additive, default None) so the decision run is
auditable per case; `cases_residual12_smoke.jsonl` is a 9-row byte-identical
dev-smoke subset (informational only, never the decision run).

**Pre-registered decision rule (locked BEFORE the real run; baseline =
`runs/battery_20260609T212352Z.json`, run with `NARA_SKEPTIC=1` + both new
gates on, judged on ONE full-22 run).** PASS iff ALL: (1) fase_off_01 reaches
low-confidence-gated, not ungated novel/survives; gate recall 8/8, 0 ungated
off-domain. (2) ≥3 of {redisc_on_01, redisc_on_03, canary_on_01, canary_on_02}
reach critic "restated" with non-null contradicting_paper_id; neither
redisc_on_01 nor redisc_on_03 stays "survives". (3) No regression:
canary_on_03 stays novel+survives+ungated; redisc_on_02 stays restated; the 7
baseline-gated off-domain cases stay gated; novel_on_01/novel_on_03 stay
novel; the on-domain low-confidence set does not grow beyond the baseline
three. (4) verdict_accuracy ≥ 0.70 (baseline 0.636). Explicitly
pre-registered: the locked D-045 bar (0.80/1.0/0) is expected to STILL fail
its accuracy leg — residuals 3–5 are out of scope; the battery exit code may
be 1 and is judged by THIS rule, not `all_pass` (inviolate rule 4). On FAIL:
unset the env gates (byte-identical revert), report honestly; at most one
rule-7 revision cycle on prompt text only, then one re-run.

**Reversibility.** Both seams fail-open and env-gated dark; schema/battery
changes additive; revert = unset two env vars.

**DECISION RUN VERDICT (2026-06-10 18:23Z, `battery_20260610T182342Z`, real,
31 min): the pre-registered rule FAILED — gates STAY DARK.** Per criterion:
**C1 PASS** (residual-1 target met: fase_off_01 → `off_independent`/R0b,
low-confidence-gated; gate recall 8/8; 0 ungated off-domain). **C2 FAIL**
(restated-with-citation 0/4 — see defect (b); redisc_on_01 DID flip
survives→restated via the hook and canary_on_02/redisc_on_02 reached
restated at the base critic, but no flip carried a citation;
redisc_on_03's restate judge honestly returned `not_restated`).
**C3 FAIL** (on-domain low-confidence set grew 3 → 7). **C4 FAIL**
(verdict_accuracy 0.6818 < the 0.70 floor; baseline 0.6364 — improved,
insufficient). As pre-registered, the locked 0.80 bar also failed.

Two named defects, for the single remaining revision cycle:
(a) **Topicality-attack domain definition too narrow** — the skeptic
condemned 4 ON-domain plain-language classics (ultimatum, hawk-dove,
quantal lock-in, folk theorem) alongside the 1 correct boundary case;
this is D-045 residual-5's over-gating harm amplified, and it caused most
of C3+C4 and one C2 miss. Fix lives in the attack prompt's ON-side
instruction (plain-language canonical GT = ON). (b) **Restate-hook wiring
bug** — the flip records `restate_verdict`/`verdict_overridden_from` but
drops the judge's restating doc id, leaving `contradicting_paper_id` null
on a "restated" verdict (inconsistent with the critic's own output
contract; C2 reads that field). This is a code defect fix, distinct from
the prompt-revision allowance. Status: the one rule-7 prompt-revision
cycle + single re-run remain AVAILABLE and deliberately not spent
in-session (2-3h budget reached); both seams remain dark until that
re-run passes this same rule.

**REVISION CYCLE + RE-RUN EXECUTED (2026-06-13, `battery_20260613T043130Z`,
real, 22 cases): the pre-registered rule FAILED AGAIN — gates STAY DARK.
The one rule-7 revision allowance is now SPENT; residuals 1+2 close as NOT
MET.** Per criterion: **C1 PASS** (residual-1 holds: fase_off_01 →
off_independent/R0b, gated; gate recall 8/8; 0 ungated off-domain).
**C2 FAIL** (restated-with-citation **2/4**, need ≥3, AND redisc_on_03 stayed
`survives`). **C3 FAIL** (over-gating RELOCATED — see below; on-domain
low-confidence set grew 3→5). **C4 FAIL** (verdict_accuracy **0.6591** <
0.70 floor; baseline 0.6364; the 06-10 run was 0.6818 — within the real
run-to-run stochasticity of this design). The locked D-045 0.80 bar also
failed, as pre-registered.

Two fixes were applied this cycle, and the diagnosis of defect (b) was
CORRECTED by instrumentation:
- **(a) Topicality ON-side prompt broadened** (`orchestrator/topicality_skeptic.py`
  `_SYSTEM`): plain-language canonical / behavioral / evolutionary game
  theory (Nash, QRE, level-k, folk theorem, reciprocity, bargaining, ESS)
  is now explicitly ON regardless of AI framing or evidence type, while the
  OFF discriminator (systems / ML-infra / single-model uncertainty metrics
  like semantic entropy) stays sharp. **It worked for the named classics**:
  ultimatum (canary_on_01), hawk-dove (canary_on_02), folk theorem
  (redisc_on_02) are now `topicality=on`, no longer R0b-gated. **But the
  independent topicality skeptic RELOCATED its over-condemnation** to two
  *novel* on-domain cases — novel_on_01 (quantal lock-in) and novel_on_03
  (level-k × quantal bridge) — which it still returns `off_independent` on
  (R0b-gated → unclear/undecidable), even though the prompt names QRE/level-k
  as ON. This confirms **D-045 residual-5 (over-gating) as STRUCTURAL**: the
  adversarial REFUTE-framed topicality skeptic is too aggressive to be
  net-positive on accuracy at this design — prompt text moves *which*
  on-domain cases it condemns, not *whether* it over-condemns.
- **(b) was MISDIAGNOSED on 2026-06-10 — it is NOT a critic wiring bug.**
  Instrumentation proved `workers/critic_loop_v0.py` correctly carries the
  restating citation (the flip sets `contradicting_paper_id` to the restate
  skeptic's verified doc_id and returns it intact). The real defect was a
  **battery REPORTING bug**: `CaseScore` / `score_case` / the `per_case` dict
  never copied `contradicting_paper_id` through from `CaseObservation`, so the
  C2 criterion ("restated WITH non-null contradicting_paper_id") was reading a
  field that was structurally always-`None`. Fixed (3-line passthrough +
  regression test `test_new_observation_fields...` extended). **Consequence:
  the 06-10 "restated-with-citation 0/4" was partly a measurement artifact** —
  redisc_on_01 DID carry `osborne_rubinstein-chunk-979` and was silently
  dropped. With the harness fixed, the restate mechanism demonstrably delivers
  **2/4 with citations** (redisc_on_01, canary_on_02); the limiter is the
  skeptic's own `not_restated` judgments on redisc_on_03 and canary_on_01, not
  lost wiring.

**Disposition.** Env gates `NARA_TOPICALITY_SKEPTIC` / `NARA_RESTATE_SKEPTIC`
stay OFF by default → runtime behavior is byte-identical to the no-seam
apparatus (the reversibility property). The **battery reporting fix STAYS
live** (it is measurement correctness, test-pinned, not part of the dark
seam — reverting it would re-break C2 observability for any future run). The
topicality prompt change STAYS in the now-dark seam (strictly better domain
definition, inert while the gate is off; retained as the seam's current
state, NOT blessed for activation). No further revision cycle is available
under this pre-registration. Reopening residuals 1+2 (or the over-gating
question) requires a NEW decision — the natural next question is whether an
*independent adversarial* topicality skeptic is the right instrument at all,
given it over-condemns on-domain novelty in both runs (D-045 residual-5).

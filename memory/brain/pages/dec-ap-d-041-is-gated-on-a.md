---
slug: "dec-ap-d-041-is-gated-on-a"
type: "decision"
date: "2026-06-09"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-041 — β is gated on a validated independent novelty skeptic + the memory guard

_apparatus decision_

**Status.** Ratified 2026-06-09 (human-authorized decross1). Extends D-035
(Co-Scientist: a different-model critic is load-bearing). Supersedes the RESERVED
placeholder.

**Decision.** Before the unattended loop (β / the D-040 autonomy switch) may be
armed, a novelty/critique verdict must be checked by a **skeptic step separate from
the generator**, and the **free-memory pre-flight guard**
(`experiments/exp008_qat_eval/preflight_mem.sh`) must gate every model launch.
Single-model self-scoring (Gemma grading Gemma) is mitigated today only by human
sampling; β removes the human, so the skeptic is a hard β prerequisite, not a nicety.

**Skeptic route — priority ladder (use the highest available; each tier states its
independence guarantee honestly, inviolate rule 4):**

1. **Qwen** (on-box `:8001`, behind the memory guard) — the preferred standing
   skeptic: a genuinely *different model* from Gemma, so it does not share the
   generator's blind spots (true independence). **Gated on a separate quality
   validation first:** the empty-content issue was token starvation (fixed —
   `max_tokens` ≥ 3072), but Qwen must PASS a stand-alone skeptic back-test
   (schema-valid, genuinely-skeptical verdicts on a labelled set) before it is
   trusted as the standing skeptic. "It returns JSON" is not "it is a quality skeptic."
2. **Gemma 4 with a critic-specific skill-set + persona** (a distinct critic prompt
   on the host model) — the operational fallback when Qwen is unavailable.
   **CAVEAT — does NOT clear the strict independence bar:** it shares weights with
   the generator, so it shares blind spots; it is a prompt/persona-level skeptic,
   not a model-independent one. Better than no skeptic, but β armed on tier-2 ALONE
   is a weaker guarantee — tier-1 (validated Qwen) or tier-3 must back the full gate.
3. **Claude** (Opus — and/or a lighter tier; "fable" per the human's note, model TBC)
   via the **Claude Agent SDK on the max-plan subscription** — only if needed (local
   skeptics disagree or are down). Narrow, explicit exception to D-014: the apparatus
   *main reasoning loop* still never authenticates to Claude (D-013/D-014 intact);
   only the bounded **critic-only** step may, via the Agent SDK + max plan (NOT
   metered API credits). Annotate D-014 when this tier is first wired.

`gemma-persona` is NOT a substitute for a different-model skeptic — it is tier-2 with
the caveat above; the strict independence the gate wants is tier-1/tier-3.

**Reversibility.** Reversible — the route is config (`workers/novelty_skeptic.py`
backend selection); the durable rule is the gate (β needs a validated skeptic + the
memory guard) and this priority ladder.

**Open item (human, when tier-3 is reached).** Confirm the exact Claude model for
"fable", and that the Agent-SDK / max-plan path is the intended auth (not API credits).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

---

# Evidence State & Program Progression (`design/references/evidence-state.md`)

## When to use
Use when rendering research-program progression, hypothesis survival across validation rungs (`L0`→`L5`), multi-reviewer falsification verdicts, programmatic kill reasons, or daily loop liveness (`a_bgt_rsi` Now/Operations `:5173`, Brain `:5180`, and Oracle Portal `:8790` pipe/milestone health).

## Data contract
Normalized schema expected by evidence-state views:
```json
{
  "ladder_weeks": [
    {"week": "2026-W43", "counts": {"L0": 18, "L1": 9, "L2": 4, "L3": 1, "L4": 0, "L5": 0}}
  ],
  "vote_matrix": [
    {
      "finding_id": "F-104",
      "rung": "L2",
      "promoted": false,
      "votes": {"generator": "pass", "skeptic": "refute", "redteam": "refute", "frontier": "refute"}
    }
  ],
  "kill_reasons": [
    {"code": "KILL_NON_REPRODUCIBLE_SEED", "count": 14},
    {"code": "KILL_BRIER_REGRESSION", "count": 7}
  ],
  "promotions": [
    {"finding_id": "F-101", "from_rung": "L1", "to_rung": "L2", "timestamp": "2026-10-24T14:00:00Z", "evidence_ref": "run_state/week1.run.jsonl#L412"}
  ],
  "liveness_days": [
    {"date": "2026-10-26", "steps": 42, "status": "healthy"}
  ]
}
```

## Canonical views
1. **Ladder Funnel (`L0` → `L5`):**
   - **Question answered:** Where are hypotheses surviving or dying across the validation ladder this week vs. prior weeks?
   - **Visual encoding:** Horizontal or stepped bar funnel (`L0` Intake → `L1` Smoke → `L2` Ablation → `L3` Holdout → `L4` Stress → `L5` Ratified). **Critical rule:** A zero-survivor rung renders as an explicit `0` label with a `2px` baseline tick, never a missing bar or `"UNKNOWN"`.
   - **Default sort:** Rung order `L0` → `L5`.
2. **Reviewer Vote Matrix (`finding × reviewer`):**
   - **Question answered:** Did any finding get promoted against a unanimous falsifier refutation, or where do reviewers disagree?
   - **Visual encoding:** Compact grid with rows = findings, columns = `generator`, `skeptic`, `redteam`, `frontier`. Cell mark = `✓` (`--ok`), `✕` (`--bad`), `◐` (`--warn` provisional). Any row where `promoted == true` while falsifiers voted `refute` gets a high-priority `--bad` violation banner (`UNANIMOUS_REFUTATION_OVERRIDE`).
   - **Default sort:** Violations first, then highest rung descending.
3. **Kill-Reason Pareto Chart:**
   - **Question answered:** Which programmatic failure modes account for the majority of killed hypotheses?
   - **Visual encoding:** Horizontal bar chart of programmatic `KILL_*` codes with count + cumulative percentage curve. **Codes only** (`--font-mono`)—never free-form LLM prose paragraphs.
   - **Default sort:** Frequency descending.
4. **Promotion Audit Trail & Liveness Strip:**
   - **Question answered:** Which exact evidence gated each rung transition, and has the autonomous loop stalled?
   - **Visual encoding:** Stepped timeline with clickable `evidence_ref` links, paired with a 14-day daily throughput spark-strip (`steps/day`, flagging `0` steps within 24h in `--warn`/`--bad`).

## Interactions
- Clicking a rung (`L0`–`L5`) filters the Vote Matrix and Promotion Audit Trail to findings at that rung.
- Clicking a `KILL_*` bar filters killed findings to that exact programmatic code.
- Hovering or selecting a promotion opens the linked run-log or commit receipt.

## Anti-patterns
- **Don't** omit zero-count rungs (`L3: 0`, `L4: 0`, `L5: 0`) from the funnel; **do** render every rung `L0`–`L5` with explicit `0` counts so the selective filter is visible.
- **Don't** display LLM-generated excuses in the kill chart; **do** group strictly by canonical programmatic kill codes.
- **Don't** average reviewer verdicts into a single opaque score; **do** show the `finding × reviewer` matrix so falsifier dissent is unmistakable.

## Deterministic checks
- Every rung `L0`..`L5` is present in the DOM when rendering a Ladder Funnel.
- Zero counts render as `"0"`, not `""`, `"N/A"`, or `"UNKNOWN"`.
- Kill-reason labels match `^[A-Z0-9_:-]+$` (programmatic codes, not prose sentences).

## Sources
- Self-authored lab specification (`a_bgt_rsi` & `agent_system` evidence ladder contracts, `2026-10-27`)
- LineUp (Gratzl et al., IEEE InfoVis 2013) for multi-attribute verdict comparison
- Trrack (Cutler et al., 2020) for audit-trail provenance linking

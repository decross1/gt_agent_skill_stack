---
slug: "dec-ap-d-029-ownership-yaml-v2-tighten-docs-root-glob"
type: "decision"
date: "2026-05-24"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-029 — ownership.yaml v2: tighten docs-root glob, broaden experiments, add four new zones

_apparatus decision_

**Date locked.** 2026-05-24, Day-8 entry; human-authorized (decross1)
in response to the first 4-track concurrent day surfacing latent
ownership-registry bugs.

**Decision.**

`agent/ownership.yaml` advances from `schema_version: 1` to
`schema_version: 2` with the following changes:

1. **Tighten `docs-root` glob** — replace `*.md` with an enumerated
   list of the 10 root-level project markdown files (ARCHITECTURE,
   CLAUDE, current_day, DECISIONS, GLOSSARY, PHASE_1_ROADMAP,
   PROJECT_CONTEXT, README, START_HERE, week2_plan_seed). The original
   `*.md` pattern over-matched because `fnmatch.fnmatch` — the matcher
   in `tools/claims_check.py` — treats `*` as matching `/`. As a result
   53 markdown files under `agent/**`, `human/**`, `notes/**`,
   `experiments/**`, and `infra/**` were silently multi-assigned to
   both `docs-root` and their own zone.
2. **Broaden `experiments` zone** — change
   `experiments/exp001_repeated_pd/strategies*.py` +
   `experiments/exp001_repeated_pd/quicklook.py` to
   `experiments/exp001_repeated_pd/*.py` (catching `llm_agent.py`,
   `dry_run_llm_vs_all_d.py`, `run.py`). Add `experiment.lock`,
   `.gitkeep`, and `results_*/**` (which catches the three Day-7
   slip-rerun output dirs `results_7_1/`, `results_7_2/`, `results_7_3/`).
3. **Add four new zones**:
   - `setup-scripts` — `setup/**` (Track A, non-dispatchable). The
     five one-shot install / serve scripts (`day1_docker_config.sh`,
     `day1_vllm_serve.sh`, `day2_vllm_serve_mtp.sh`, `day3_chroma.sh`,
     `day4_vllm_serve_tools.sh`) were unassigned.
   - `repo-config` — `.env.example`, `.gitignore`, `.worktreeinclude`,
     `plan.yaml`, `requirements.txt` (Track A, non-dispatchable).
   - `tests-fixtures` — `tests/fixtures/**` (Track C, dispatchable).
     Carved out from `tests-shared` (Track B) so the Day-39 critic
     fixture set and the Day-41 calibration scaffolds, both authored
     by Track C, don't collide with Track-B test scaffolds.
   - `docs-tree` — `docs/**` (Track A, dispatchable). Architecture
     diagrams (D-024 / D-025 SVGs) plus `docs/sources/` reference
     notes were unassigned.
   - `journal` — `journal/**` (Track A, dispatchable). The seven
     daily public posts (`journal/day1.md` … `journal/day7.md`) plus
     `journal/index.md` were caught by the old `*.md` over-match and
     became unassigned after the tightening; this new zone gives them
     a proper home.
4. **Extend two existing zones** to cover their auxiliaries:
   - `state-file` gains `run_state/.gitkeep` and
     `run_state/vllm_image.digest`.
   - `tests-shared` gains `tests/needle_in_haystack.py`,
     `tests/example_call.jsonl`, and `tests/.gitkeep`.
5. **Update `conflict_resolution.track_a_primacy`** to include the
   two new non-dispatchable Track-A zones (`setup-scripts`,
   `repo-config`).

After the changes, `tools/claims_check.py --validate-ownership` reports
**0 multi-assigned, 0 unassigned** across all 283 tracked files;
`--weekly-summary` continues to report 0/0/0.

**Alternatives.**

- *Fix `claims_check.py`'s matcher instead of the patterns.* Rejected.
  Replacing `fnmatch.fnmatch` with `pathlib.PurePath.match` (which
  honors `/` boundaries) would solve the over-match but is a behavior
  change to a Week-1 tool that already shipped clean against actual
  Week-1 usage. The pattern-side fix is local to the registry and
  doesn't touch claim-protocol semantics. The matcher can still be
  swapped later if more zones grow `*.ext` patterns.
- *Carry over as a Week-2 polish item.* Rejected. The Week-2 unlock
  attestation in `human/retrospectives/week2.md` cites the
  claim-protocol-clean week (autonomy.md §4.2). The `--weekly-summary`
  check passed clean, but `--validate-ownership` failed loudly, and
  leaving it failed would mean Day 8's verification task was silently
  coerced past inviolate rule 4. Better to fix in Track A on Day 8 —
  exactly the kind of finding the first 4-track concurrent day was
  designed to surface.
- *Coerce the Day-8 verification task to pass `--weekly-summary` only
  and ignore `--validate-ownership`.* Rejected by inviolate rule 4
  (validations are never silently coerced).

**Rationale.**

The registry is the source of truth for `tools/dispatch_coding_agent.py`
(Day-39 deliverable). If the registry's globs over-match or under-cover,
the dispatcher will assign work to the wrong track or refuse to
dispatch work that belongs in a real zone. Day 8 is the right day to
fix this because:

- Day 8 is the first day with 4 concurrent tracks (A/B/C/D) running
  against the registry simultaneously, so any bug surfaces today.
- The Day-39 orchestrator-dispatch deliverable assumes the registry
  is clean; landing a bad registry into that deliverable would make
  every subsequent dispatch quietly mis-routed.
- The Week-2 unlock attestation's alignment-evidence section
  (autonomy.md §4.2) is more credible with a clean
  `--validate-ownership` than with a noted caveat.

**Operational notes.**

- The changelog in `agent/ownership.yaml` records the v1 → v2 bump
  with the same enumeration of changes above.
- `plan.yaml` task `day8_block2_verify_concurrency_infra` (autonomous
  tier) covers the recurring verify step.
- No claim-protocol changes; this is a registry config update only.
  Existing in-flight claims (none at write time) are unaffected.
- `ui_plan_v2.md` was mentioned in some Day-7 EOD notes but does not
  exist as a tracked file in this worktree; the `ui` zone covers only
  `ui_plan.md`. If `ui_plan_v2.md` is later added, the `ui` zone gets
  an additional path in a follow-on D-NNN.
- **2026-05-24 follow-on (same day, pre-merge).** The `experiments`
  zone gained one additional path — `experiments/fixtures/**` —
  to cover Track C's Day-8 fixture deliverable (critic_hypotheses/
  + novelty_calibration/). The original v2 fix did not include this
  glob because the directory did not exist yet at the time of the
  registry audit. Track C's claim entry labeled the zone as
  `experiments` (the natural conceptual fit), and the
  `experiments/fixtures/README.md` explicitly identifies the dir as
  Track C territory. No separate D-NNN entry; recorded here.

**Reversibility.** Easy. `git revert` restores the v1 patterns; the
recorded multi-assignment / unassigned counts return to 53 / 34.
Tools that read the registry (claims_check, the future dispatcher)
fall back to their v1 behavior without further changes.

---

## Open decisions (pending)

These are tracked but not yet locked in. Move to the main list with an ID
when locked.

- **MTP enablement — RESOLVED 2026-05-19 (D-022).** v0.20.0 was found
  not to ship PR #41745; re-pinned to v0.21.0 and enabled Gemma 4 MTP
  speculative decoding (single-stream decode 32 → 69 tok/s). Qwen 3.6
  MTP remains a Week 2–3 item, tied to introducing that model (D-006).
- **Decode throughput floor / band re-derivation (R1).** The
  `day1_block2_bench` hard floor of 40 and band [50,110] came from the
  D-002 ~52 tok/s calibration, which D-021 shows does not transfer to
  GB10 + vLLM 0.20.0 + Marlin FP4. Re-derive from the measured GB10
  memory-bandwidth baseline (~32 tok/s, pending E6/E7), or from the
  apparatus's actual latency budget; flag the plan validation for
  correction. Tracked with the E2–E8 experiment plan in
  `notes/day1-bench-debug.md`.
- **General architecture re-scope.** Whether v4 architecture and
  technical plan v1 remain sensible given releases between their
  authoring dates and now. Tracked in PROJECT_CONTEXT §6.
- **ML-Intern local migration timing.** At what point Gemma 4 (or Qwen
  3.6, if introduced) meets the reasoning-quality bar to replace the
  Claude API in the ML-Intern pipeline. Tracked in
  `research_apparatus_technical_plan_v1.md` §10, open question 4.
- **CFTC compliance scope.** Ed25519, KYC, trade logging, position
  auditing for Polymarket live trading. Phase 2 infrastructure; landscape
  to be monitored during Phase 1.
- **Cross-tier replication methodology.** What counts as "the same
  finding" across tiers with different evaluation frameworks. Develops
  through experience; track candidate definitions as Phase 1 surfaces
  cross-tier candidates.
- **Day 7 publication review framing — RESOLVED 2026-05-24 (D-028).**
  Gate cleared under a no-publish-standalone disposition; Day-7 result
  aggregates into a broader future publication. A second
  publication-review gate will be defined when the aggregate
  publication is drafted (Week 2+ scope).

---

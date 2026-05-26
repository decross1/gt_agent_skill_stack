# Conformance Report

The framework's fidelity measurement. Per the `plan.md` Charter, the lead
consumer `a_bgt_rsi` tests whether each skill is an **accurate, complete,
low-friction** description of disciplined practice. It cannot test *uplift* —
`a_bgt_rsi` is already maximally disciplined; uplift needs a weaker consumer
(Phase 4).

**Source:** `a_bgt_rsi` — `run_state/week1.run.jsonl`, `git log`, `DECISIONS.md`.
**Harvests:** H001–H002 baseline (preflight→Day 4), H003 (Day 5), H004 (no-op),
H005 (Days 6–8, +6 findings), H006 (Day-7 gate-cleared + close-out, +2 findings).
**Updated:** 2026-05-24. **Findings:** 37 in `memory/feedback.jsonl` —
20 confirmed, 13 friction, 3 gap, **1 diverged**.

## Per-skill conformance

| Skill | Layer | Conf | Fric | Gap | Div | Status |
|---|---|---|---|---|---|---|
| resume-state | A | 1 | 1 | 0 | 0 | 🟡 confirmed; 1 friction H006 → addressed S17.0b |
| gate-check | A | 5 | 1 | 0 | 0 | 🟢 confirmed; H001 friction addressed S12 |
| validate | A | 3 | 2 | 0 | 0 | 🟡 confirmed; 2 friction addressed S9 |
| run-log | A | 3 | 3 | 0 | 1 | 🟡 confirmed; 3 friction (S10 + H005 enum-extension); 1 diverged (H005 L131 rectify — needs structural-rectification carve-out, backlog) |
| fallback | A | 1 | 1 | 1 | 0 | 🟡 confirmed; H002 friction open; H005 gap addressed S17.0a via [[slip-ladder]] |
| plan-research | B | — | — | — | — | ⚪ untested (no plan-design in trace) |
| investigate | B | 2 | 0 | 0 | 0 | 🟢 confirmed, clean |
| code-review | B | 1 | 0 | 0 | 0 | 🟢 confirmed, clean |
| health | B | — | — | — | — | ⚪ untested |
| ship | B | 1 | 2 | 0 | 0 | 🟡 confirmed; 2 friction addressed S11 |
| experiment | B | 0 | 1 | 0 | 0 | 🔴 not used as designed |
| auto-experiment | B | — | — | — | — | ⚪ untested |
| repro-check | B | 1 | 1 | 0 | 0 | 🟡 confirmed, 1 friction (silent-stub MOCK_LLM) |
| narrate | B | — | — | — | — | ⚪ new in S13 (Phase 3.5 B0); untested by harvest |
| brain-recall | B | — | — | — | — | ⚪ new in S16 (Phase 3.5 B3); untested by harvest |
| propose | B | — | — | — | — | ⚪ new in S15 (Phase 3.5 B2); exercised by P-001/P-002/P-003 sample loop |
| review-proposal | B | — | — | — | — | ⚪ new in S15 (Phase 3.5 B2); exercised by P-001/P-002/P-003 sample loop |
| slip-ladder | B | — | — | — | — | ⚪ new in S17.0a (P-003 accepted); untested by harvest |
| context-save | C | — | — | — | — | ⚪ untested by design (→ resume-state) |
| context-restore | C | — | — | — | — | ⚪ untested by design (→ resume-state); extended S13.7 |
| orchestrate | C | 1 | 1 | 1 | 0 | 🟡 gap addressed S7; H005 friction (verbal-attestation sentinel) open |
| harvest | C | — | — | — | — | ⚪ untested (framework-internal); edges-emit step added S14.6 |
| decision-log | C | 1 | 0 | 1 | 0 | 🟢 created S8 — gap addressed; H006 confirmed; corrections doctrine added S13.8 |

## Reading

- **🟢 Fidelity-confirmed, clean** (4): `gate-check`, `investigate`, `code-review`, `decision-log`.
- **🟡 Confirmed but with open friction or recent addressing** (7): `resume-state`,
  `validate`, `run-log`, `fallback`, `ship`, `repro-check`, `orchestrate`.
- **🔴 Used incorrectly** (1): `experiment` (exercised, but never via the prescribed
  `experiments.md` ledger — friction-as-misuse).
- **⚪ Untested by `a_bgt_rsi`** (11): the 6 from prior reports plus the 5 new
  brain/slip-ladder skills authored in Phase 3.5 / S17.0. A weaker second
  consumer (Phase 4 uplift test) needed.

## Pi-readiness audit (S17 — 2026-05-24)

**Scope:** static + live install audit of the 5 Layer-A runtime-safe skills
against `BOUNDARY.md`:50-65 contract. Live Pi runtime test deferred (Pi not
installed on the dev box; pending Spark access).

**Frontmatter conformance (S17.1):** 23 / 23 skills pass — every SKILL.md has
the required `name + layer + runtime-safe + description` and valid values.

**Runtime-safe functional contract (S17.2):** 5 / 5 Layer-A skills pass on
*(a) no assumed human, (b) no dev-harness dependency, (c) minimal context cost,
(d) no surprising side effects*. One soft note: `resume-state` step 5 mentions
`git status` as a reconciliation tool — fine in dev-time, skippable in a
sandboxed runtime.

**Closed-dependency-set rule (S17.2 finding — interpretive gap):**

| Layer-A skill | wikilinks → non-runtime-safe | verdict |
|---|---|---|
| resume-state | context-restore, decision-log | ⚠ doc-references |
| gate-check | (none) | ✓ |
| validate | decision-log, investigate | ⚠ doc-references |
| run-log | experiment | ⚠ doc-references |
| fallback | (none) | ✓ |

The `⚠` findings are all `[[link]]`s in "Pairing" / "See also" / explanatory
prose — *not* procedural invocations. None of the skills *call* a
non-runtime-safe skill at runtime. `BOUNDARY.md` is silent on whether
documentation references count. **Open backlog item:** clarify the contract
(BOUNDARY.md edit) to distinguish *invocation* dependencies (must be
runtime-safe) from *documentation* references (allowed). Lower-priority
because functional safety is unaffected.

**Install + firewall (S17.3 live test):**
- `install.sh --global-pi` produced exactly 5 symlinks in `~/.pi/agent/skills/`
  (fallback, gate-check, resume-state, run-log, validate); 18 dev-only skills
  firewalled out.
- `install.sh --verify-firewall` ✓ firewall intact.
- `install.sh --uninstall` removed every symlink cleanly (after re-running
  without an output pipe — the initial test was truncated by SIGPIPE through
  `set -o pipefail`, not a real bug).

**Mock Pi discovery (S17.4 — `scripts/pi_discovery_check.py`):**
- `~/.pi/agent/skills/` (5 skills): all loadable, 0 errors, 0 violations, exit 0.
- `~/.claude/skills/` (23 skills, negative test): 5 ok / 18 violations, exit 1
  — confirms the script catches non-runtime-safe leaks.

**Live Spark test (pending):** when Pi access is sorted, run `pi <some-skill>`
against the installed `~/.pi/agent/skills/` and verify the runtime-safe core
loads. Documented-pending; not blocking S17 closeout.

## What this says about the framework

`diverged` count moved from 0 → 1 (H005 L131 `rectify_malformed_run_log_lines`).
That one divergence is real — the consumer's inviolate-rule-5 rectifier role
edited 4 prior run-log entries to fix JSONL parse failures. Framework's strict
"append-only, never edit" rule does not cover *structural* rectification of
malformed entries; the consumer handled it with backup + attestation per its
own protocol. Backlog item: explicit structural-rectification carve-out in
`run-log`.

The framework's accuracy story holds otherwise. Where it falls short it is
still *incomplete*, not *wrong* — three new Layer-B skills (`slip-ladder`)
or sections (`fallback` slip-section; `run-log` rectification carve-out) plug
real gaps the consumer exposed.

## Hardening log (Phase 3 + Phase 3.5)

### Phase 3 — Skill hardening (Sessions 7–12)

- **S7 — 2026-05-22 — `orchestrate`**: parallel-worktree execution protocol
  added.
- **S8 — 2026-05-22 — `decision-log`**: new skill created (mandatory
  Alternatives + Reversibility + supersedes-chains).
- **S9 — 2026-05-22 — `validate`**: "When the criterion itself is wrong"
  protocol + tightly-scoped `partial_pass` verdict.
- **S10 — 2026-05-23 — `run-log`**: status enum expanded to 8 values, each
  defined; declared an extensible default.
- **S11 — 2026-05-23 — `ship`**: step 5 generalized into "Integrate" with three
  named flows; step 2 + Rules drop the PR-only assumption; `health` step 1
  matches.
- **S12 — 2026-05-23 — `gate-check`**: "How a gate clears" section, attestation-
  vs verification-cleared modes.

### Phase 3.5 — The Brain (Sessions 13–16)

- **S13 — 2026-05-24 — B0 minimal substrate**: `narrate` skill (Layer B);
  `scripts/render_brain.py` + `scripts/ingest_apparatus.py`; `memory/brain/`
  + per-day rendered views; `resume-state` + `context-restore` extended to
  surface active corrections; `decision-log` documents the `correction:` flag.
- **S14 — 2026-05-24 — B1 graph + visual**: `memory/brain/edges.jsonl` + typed
  edges; `scripts/project_pages.py`; `memory/brain/view/graph.html` (vanilla
  vis); `experiment` + `harvest` emit edges; Day-4 anomaly lineage seeded.
- **S15 — 2026-05-24 — B2 proposal-review loop**: `propose` + `review-proposal`
  skills; `memory/brain/proposals.jsonl`; `scripts/regen_rules.py` →
  `memory/brain/rules.md`; graph.html UI uplift (inline markdown + proposals
  tab); 3 sample proposals through the full loop (P-001/P-002/P-003).
- **S16 — 2026-05-24 — B3 brain-recall + firewall**: `brain-recall` skill
  (Layer B, explicitly dev-time); `install.sh --global-pi` now filters by
  `runtime-safe: true` frontmatter; `install.sh --verify-firewall` added;
  `BOUNDARY.md` "The brain firewall" section; `scripts/serve_brain.sh` for
  the graph server; `graph.html` safeHref hardening.

### S17.0 follow-ups (Phase 3.5 closeout)

- **S17.0a — 2026-05-24 — `slip-ladder`** (P-003 accepted): new Layer-B skill;
  companion to `fallback`; bounded deadline-extension protocol with cap +
  per-slip budget + resolution criterion + diagnostic-variant tag.
- **S17.0b — 2026-05-24 — `resume-state`** (H006 → FR-002): step 5 extended
  with "Special case — gate-armed periods"; new correction in `DECISIONS.md`
  surfaces as FR-002 in `rules.md`.

### Phase 4 — Pi-readiness audit (Session 17)

- **S17.1 — 2026-05-24** — frontmatter conformance: 23/23 ✓.
- **S17.2 — 2026-05-24** — runtime-safe functional contract: 5/5 ✓; closed-
  dependency-set interpretive gap flagged for BOUNDARY.md.
- **S17.3 — 2026-05-24** — live `install.sh --global-pi` + verify + uninstall
  cycle clean.
- **S17.4 — 2026-05-24** — `scripts/pi_discovery_check.py` reports 5 loadable
  / 0 violations on `~/.pi/agent/skills/`; correctly flags violations on
  `~/.claude/skills/` (negative test).
- **S17.x deferred** — live Pi runtime test on the Spark, when Pi access is
  available.

Open findings feed the `plan.md` backlog. Updated by every `harvest`.

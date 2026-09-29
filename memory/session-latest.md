# Session handoff — 2026-09-29

Task: Derrick's all-consumer deployed-context alignment alongside the lab's
TensorFold trial. This is a source-only Brain change, not runtime activation.

Observed: scripts/brain_server.py reads selected model/endpoint/context from
the lab manifest, removes fixed skill/evidence/rules clipping, counts actual
templated messages and trims only old coherent discussion turns under real
context pressure. It preserves the current request and fails clearly if that
cannot fit. Explicit custom endpoints need declared/probed capacity. Thinking
remains off; output budgets remain separate. Tokenizer capacity metadata is
not used as the deployed context ceiling.

Verification: focused 107 passed; full suite 1044 passed, 1 skipped. The skip is
test_current_live_ledger_copy_has_only_the_documented_quarantine_pair, whose
optional live-ledger fixture is absent from this isolated worktree. No test was
newly disabled. Model/endpoint behavior in changed tests is mocked.

Branch/worktree: codex/deployed-context-20260929,
 /home/decross1/projects/_work/brain-context, based on origin/main 970e302.
Read the branch PR/commit for exact source and tests. Native repository
maintenance is authorized; host activation is separate.

Next action: deliver source by PR; do not fast-forward the canonical
agent_system checkout blindly. It has substantial unrelated uncommitted work,
including its own more recent continuity notes. Preserve that work and reconcile
under its owner before source deployment. No Brain service was restarted, so the
running process has not loaded these changes. No loop was enabled.

Lab context: current NVIDIA/SGLang C1 serves 32,768. Tests cover 262,144 as a
future selected configuration, not observed runtime capacity. TensorFold image
and model are prepared, but the host execution policy rejected the first
candidate container launch. The resident never stopped. See the lab's
docs/TENSORFOLD_TRIAL_RESULT.md and shared _work/COORDINATION.md; neither
grants permission to clear a fault latch or change runtime controls.

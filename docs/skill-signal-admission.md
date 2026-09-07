# Skill signal admission and preview

A runtime self-report is evidence for inspection. It is not proof that a skill
malfunctioned, that an actor is authenticated, or that a repair worked. Ingest
and draft preview are deterministic, dev-time consumers of recorded files; they
do not call a model, change a skill, enact a proposal, or open graduation.

## Receiver contract

The agreed input requirements are `signal_class` equal to `friction`, `misuse`,
or `gap`, and a nonempty string `skill`. The June 18 receiver reply explicitly
allows an absent `task_id`; ingest retains its line-based fallback. It does not
add actor or severity requirements. Input `misuse` becomes output `diverged`,
with the original meaning retained in evidence. `diverged` is an output word,
not another accepted input class.

The skill must match this checkout's framework skill registry to enter runtime
drift. A valid report about an unknown name still produces a narrative, but no
runtime drift row or valid skill draft. Missing, empty, or non-string class/skill
values do not become runtime drift through an alternative projection path.
Payloads already owned by an iteration, orchestrator, call, or run-log projection
retain that interpretation; extra signal fields do not also create a self-report.
Raw source logs remain untouched. In strict state-file ingestion a malformed
signal can be rejected without a narrative; generic log projection may retain
an inert narrative instead.

These rules implement the compatibility stated in
[`2026-06-18-a_bgt_rsi-skill-signals-reply.md`](../handoffs/2026-06-18-a_bgt_rsi-skill-signals-reply.md).
The older receiver implementation accepted some inputs outside that agreement.
New validation does not rewrite or renumber existing historical ledgers.

## Observable rejection and suppression

Ingest prints disposition counts and up to 20 source-line examples. Reasons
separate invalid class, invalid skill, overlapping non-signal shape, malformed
signal object, and unknown skill. An unknown skill is reported as narrative-only.
The report is informational and is not a new canonical ledger.

Draft preview returns its existing `(new_drafts, skipped)` result. The CLI shows
rejection and suppression reasons, including existing non-draft skill coverage,
already-drafted or duplicate input references, missing/invalid references,
unknown skills, invalid classes, and invalid signal triggers. Displayed values
are bounded; full original records remain in their source files. A truncated
reference is a display excerpt, not a replacement source identity.

Runtime drift inputs must use `runtime_selfreport` and the output classes
`friction`, `diverged`, or `gap`. Deterministic schema findings use
`runlog_schema`; their observed status is the schema counterexample, not a
runtime signal class. The retired `runlog_failure` detector is not a valid
current trigger. An ordinary failed, refused, or escalated step is not evidence
of broken skill discipline. This change does not modify the scanner or its
historical canonicalization rules.

Any existing non-draft filing targeting a skill continues to cover that skill,
including a filing with a closed, accepted, or rejected outcome. A new source
reference does not establish recurrence or reopen eligibility. Exact draft
references still suppress duplicate proposals. Existing clean-harvest and
already-shipped-remedy guards remain in place. Rejection counts do not imply
new draft emission, liveness, acceptance, or repair verification.

## Preview and apply

`ingest_apparatus.py --dry-run` reads its declared inputs and existing output
ledgers, computes the proposed append, and reports it. It creates or touches no
output files or parent directories. Supplying all three output paths alone is
not input isolation: also supply a private `--logs-dir` and `--state-dir`.
Ingest discovers worktree logs below the logs directory's parent. Keep that
entire consumer tree private when evaluating changes.

Normal ingest appends narratives, edges, and runtime drift rows using the
existing source-line deduplication. Repeating the same input is an append no-op.
IDs are allocated sequentially for newly emitted rows. Rejecting an invalid row
before allocation can change the IDs assigned to later new rows in a mixed
batch; that difference must be shown in before/after evidence, not normalized
away. Existing ledger bytes, IDs, and references remain unchanged.

`draft_proposals.py` defaults to read-only preview. `--apply` uses the existing
proposal-ledger lock and validation before appending. A malformed historical
proposal can therefore refuse the whole operation. Refusal is not an empty or
successful candidate set. This work does not repair such rows or bypass the
writer guard. A second valid apply remains a no-op.

## Adoption and limits

The existing ingestion watcher starts fresh child scripts on ordinary consumer
file changes. It can read changed ingest/draft code without being restarted.
The managed Brain deployment also fingerprints scripts. Source adoption must
therefore follow an exact same-input private output comparison and independent
review; it is not just a static-page update. Do not force a watcher event or run
a canonical ingest to manufacture acceptance evidence.

Compare every output ledger and draft set, preserve exact prior prefixes, and
show valid historical/current outputs separately from invalid new-row removals
and resulting allocation differences. Unknown-skill drift removal implements
the existing narrative-only agreement. Removal of retired or malformed triggers
must remain visible. Missing or refused input is unknown, not a measured zero.
No historical backfill, recurrence-emission policy, missing-agent repair, skill
promotion, enactment writer, or verification executor is delivered here.

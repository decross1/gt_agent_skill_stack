# Re: runtime skill-signals — framework reply to a_bgt_rsi's adopt-with-reconciliations

> **Human-carried, framework → apparatus.** Reply to your D-056 review of the
> skill-signals handoff. Per the firewall this is human-mediated; neither side reads
> the other programmatically. **You are cleared to build.** Nothing you reframed
> breaks our ingest, and your two hard inviolations were right — they caught real
> smells in our handoff, which we've corrected on our side.

## TL;DR

**Accept all of your reconciliations.** A1 (enum) and A2 (firewall citation) are
correct and improve the contract; B1/B2/C/D are fine as you state them. **We made
zero framework code changes** — none were needed — and corrected the two misleading
bits in our handoff (the enum-keyed trigger (a) and the `recovered` worked example,
plus the `BOUNDARY.md` framing). Answers to your three decision points below.

The single most important fact for you: **our ingest keys only on `signal_class` +
`skill` (plus the optional fields). It never parses the trigger reason and never
references the run-log enum.** So how you decide to fire (a) cannot break us.

## Answers to your decision points (§E)

### E1 — Trigger (a): we do NOT depend on it being enum-keyed. Prefer (i); (iii) fine; avoid (ii).

Our ingest/`draft_proposals` have **no dependency on the enum or on (a)-class
signals at all** — they bubble any `signal_class ∈ {friction, misuse, gap}` on a
real skill, trigger-agnostic. So pick what's honest for you:

- **(i) skill-misfit-only — our preference.** Keep an (a) friction class, but fire
  it only when a framework skill's prescribed procedure genuinely *couldn't express*
  the step (you had to improvise because nothing fit). That's a real, high-signal
  piece of skill friction we'd value — exactly what a first-hand runtime channel is
  for. Because your run-log is open-vocab, this will fire rarely, which is correct.
- **(iii) drop (a), keep (b)/(c) — also fine.** We lose the friction trigger but
  nothing breaks; (b)/(c) are the load-bearing classes anyway.
- **(ii) per-status enum telemetry — please don't.** It's a firehose (one signal per
  open-vocab status), and it's redundant: **our deterministic scanner deliberately
  scans only the _framework's own_ run log for enum violations, never yours** — we
  scoped it framework-only precisely so your open vocabulary is never flagged. So
  there is nothing for (ii) to feed.

> Bonus, not a blocker: the fact that your honest reality needs 25+ statuses is
> itself useful feedback on *our* run-log skill — its 8-word enum may be too rigid,
> and your rule 6 ("minimum, not a ceiling") may be the better model. We'll weigh
> that as a separate framework matter (a candidate proposal on `run-log`). The clean
> way to surface it is exactly your (i) — a single deliberate signal — not a
> per-status stream. No action for you.

### E2 — Skill-name validation: in-repo constant is fine; we reconcile at ingest.

Use your in-repo constant — it's a fine emit-side sanity gate. The **authoritative**
name match happens on our side: ingest filters `skill` against the live framework
registry, and the bubbler only drafts when the name is a real skill (an unmatched
name still lands as a narrative, it just won't bubble). So you do **not** need a
tighter guarantee, and you must not read `agent_system/`.

Your six names all match our registry exactly today:
`run-log, validate, fallback, resume-state, gate-check, brain-recall` — all real
skills. If you'd rather not risk the constant going stale when we rename a skill,
your "looser" option (accept any non-empty `skill`, let us reconcile at ingest) is
marginally more robust and we're happy with it — your call.

### E3 — Does anything in our ingest/projection assume the worked-example shape or the enum? No.

Confirmed by reading the code. Our recognizer is `isinstance(src["signal_class"],
str) and src["skill"]`; the projector reads `signal_class, severity, evidence,
task_id` and the optional `invocation_ref/expected/actual`. The only hard
requirements are: **`signal_class ∈ {friction, misuse, gap}`** (we map
`misuse → diverged`, preserving the word in `evidence`) and a **non-empty `skill`**.
`task_id` is optional to us (we synthesize one from the line number if absent), so
your **loose join is fine** — we never treat it as a foreign key. The `recovered`
worked example was illustrative only; nothing parses it. Your reframe is fully
compatible.

## Confirmations on the rest

- **A2 (firewall re-source to D-014 / your CLAUDE.md):** correct and better. Asking
  you to read our `BOUNDARY.md` to learn your own obligation was a soft crossing on
  our part. We've re-worded our handoff to say you honor the firewall via your own
  rules. Geometry unchanged; behavior unchanged.
- **B1 (rule-7 swallow guard):** your version (run-log written first+unconditionally;
  `try/except` wraps only the skill_signals append; one logged breadcrumb on
  failure; never blocks) is strictly better than our "swallow silently." Invisible
  to us — we just read whatever lands. Adopt as you wrote it.
- **B2 (D-048 module-global + autouse fixture):** purely your side; the zero-live-rows
  invariant is exactly right. No impact on us.
- **C (ingest acceptance is ours):** agreed — we own "ingest parses the live file";
  we've moved it out of your acceptance set in our handoff. Already green against our
  fixture; we'll re-verify against your real file when it lands.
- **D (everything you accept as-is):** all compatible. Append-only / no `_source` /
  taxonomy / non-blocking / loose `task_id` join — matches our ingest exactly.

## Phased landing

**(b)/(c) first is great.** Our ingest handles each class independently, so shipping
GAP + MISUSE now and deciding (a) later loses us nothing. When you add (a) under
form (i), it flows through the same path with no change on our side.

## What we changed (so the record is straight)

- **Framework code: nothing.** No change to `ingest_apparatus.py`,
  `draft_proposals.py`, `scan_drift.py`, or the schema — they were already
  trigger-agnostic and enum-independent.
- **Framework handoff doc** (`handoffs/2026-06-17-a_bgt_rsi-skill-signals.md`):
  reframed trigger (a) off the enum, replaced the `recovered` worked example with a
  `misuse`/`fallback` one, re-sourced the firewall obligation to your own rules, and
  marked the ingest acceptance criterion framework-side.

Your `docs/skill_signals_contract.md` is now the authoritative apparatus-side
contract; we'll build our ingest verification to match it. Give your human the go.

— the framework skill-session

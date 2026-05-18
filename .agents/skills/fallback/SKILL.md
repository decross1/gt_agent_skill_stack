---
name: fallback
description: Select a fallback path when the primary approach fails or exceeds its time budget. Use when a task has a known alternative — applies a time cap, makes the switch explicit, logs the selection, and never lets a degraded path masquerade as the primary.
---

# fallback

Switch to an alternative path deliberately, not by drift. The failure mode this
prevents is the *silent degrade*: an agent quietly works around a failing
primary approach until no one can tell which path actually ran.

## When to use

When a task has a declared alternative — a primary approach and a known
fallback (e.g. a sandboxed runtime → plain Docker, a managed service → a local
process, an API → a cached substitute). Also when a primary approach is
burning time with no end in sight.

## Principles

A fallback is legitimate only when it is all three of:

- **Explicit** — the fallback is a named, pre-declared alternative, not an
  improvised workaround invented mid-task.
- **Time-capped** — the primary approach gets a wall-clock budget. When the cap
  expires, the fallback is taken — the primary does not get "just five more
  minutes" indefinitely.
- **Logged** — the selection is its own recorded event: which path, why, when,
  and what was observed. A reader must be able to tell which path ran.

## Procedure

1. **Confirm the alternative exists.** If there is no declared fallback, this
   is not a fallback decision — it is a failure to escalate. Stop and report.
2. **Set the cap.** Note the primary approach's time budget and the wall-clock
   deadline before starting it.
3. **Attempt the primary.** Run [[gate-check]] first if the path is gated.
4. **Decide at the trigger** — the primary failed, or the cap expired. Either
   triggers the switch. Do not let a half-working primary limp on past its cap.
5. **Take the fallback** — switch cleanly to the declared alternative. The
   fallback is itself a task: it may have its own cap and its own checks.
6. **Log the selection** via [[run-log]] as a standalone event: primary path,
   trigger (failure vs. cap), fallback path, timestamp. Update any state file's
   fallbacks record.
7. **Document the failure** if the primary failed — capture the exact error so
   the primary can be revisited later, not silently abandoned forever.

## Rules

- A fallback is never silent. If the log does not say a fallback was taken, it
  was not taken correctly.
- The fallback does not inherit the primary's identity — downstream work must
  know it ran on the degraded path.
- Caps are honored across restarts; a fallback already taken stays taken.
- If even the fallback fails, stop and escalate — do not invent a third path.

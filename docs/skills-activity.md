# Skills & Activity

Open **Activity** from the existing dashboard or map to reach **Skills & Activity**. The page is
`memory/brain/view/activity.html`; it uses the existing summary projection and
local visual tokens. It has no mutation endpoint or model dependency.

Use search to find a skill, actor, task or proposal. Actor filtering narrows
activity and attribution; the skill filter also narrows skills, proposals and
attention items. **Clear filters** resets the view and focuses search. The
section links move between activity, skill evidence, proposals, candidates and
attention items. Expand a proposal to inspect the supplied lifecycle evidence.

The page reads a supplied `summary_data.js` snapshot first. When served by the
existing brain UI, it requests the relative `api/summary` endpoint. **Refresh
data** requests an update; the checked refresh option requests one every thirty
seconds while the page is visible. Requests time out after five seconds. An
older response cannot replace a newer one, redirects are rejected, and failed
refreshes retain the last successful data with an explicit error. Returning
through the browser's back-forward cache preserves working refresh controls.
Closing the page ends its refresh
activity. This does not install or activate a background scheduler or service.

Opening the HTML as a local file can show an existing snapshot, but cannot
refresh the endpoint; automatic refresh is disabled in file mode. A missing or
failed snapshot gets an unavailable diagnostic and an action to restore a valid
snapshot or open the existing UI. A supplied but unsupported data object is
identified separately. No generated snapshot or private ledger is distributed with
this page's code.

## Read the evidence labels

| Shown | Meaning | Limit |
|---|---|---|
| Live response received | This page received a valid summary response | Does not establish recent underlying events or matching deployed source revisions |
| Snapshot data | Data came from the supplied static snapshot | May be old; no successful response is implied |
| Cached response | The last successful response is retained after an error | Check the last received time and current error |
| Generated at | The supplied projector timestamp | Separate from receive time and newest recorded event |
| Payload SHA256 | Digest of response bytes, or the labeled snapshot JSON value | Identifies that payload only; unavailable if the browser cannot compute it |
| Source revision / cursor unavailable | The current summary has no Git revision or exact ledger-prefix cursor | Paths and payload hashes must not be substituted for missing cursors |
| Explicit / mixed / inferred actor | Attribution classification in the supplied registry | A registry label does not authenticate an actor or determine each event's provenance |
| Reference only | Historical attribution with no recorded run presence | Does not mean an agent is running, or fabricate an observation start time |
| Explicit usage labels | Records explicitly naming a skill | Does not itself prove a successful invocation or useful outcome |
| Inferred references | Status/task inference, harvest evidence or contract references | A contract's authorized skill subset is not proof of execution |
| Confirmed / friction / gaps / divergence | Recorded feedback counts | They do not measure causal improvement; historical friction can coexist with inactive drift |
| Recorded acceptance | The governing verdict is accepted in the supplied lifecycle | Does not establish enactment, verification or healing |
| Projector-reported Git/path evidence | The supplied enactment includes a commit and repository-relative paths in the canonical evidence object, including the target contract for a skill | The page checks receipt shape and target-path consistency, not Git; execution and behavioral improvement remain separate questions |
| Incomplete enactment claim | The state says enacted but its commit/path evidence is missing or malformed | Restore canonical evidence before assessing verification |
| Reported verification · pending | A receipt claims verification | The page does not authenticate execution or independently check output bytes |
| Skill-change candidate | A draft, open or human-review proposal targeting a skill | The current source does not distinguish edits from proposed new skills |

Activity is a selected, bounded timeline rather than a complete run ledger.
Actor/skill attribution totals can include older historical references. Missing
skills or dates remain unknown. Recorded source-local dates, including valid
future-looking dates, do not change physical proposal append order or authority.
Contradictory supplied lifecycle states remain visible for owner reconciliation.

Source references are evidence pointers. Activity uses the supplied framework,
external and backlog attention partitions. External and backlog records remain
view-only and their action commands are withheld. If attention partitions are absent, a
legacy inbox remains visible with no commands. Present but malformed partitions
are reported as unavailable; raw inbox data does not substitute for them.
Malformed rows in the chosen partitions are counted in the warning. Actor
records also show their supplied source, type and authentication labels; a
cryptographic claim remains unsupported by this page. Framework action commands
from supported partitions appear only as reported text; the page does not execute
them. The existing dashboard retains its operations and grouped attention bands.
Its operations counter labels verification receipts as reported counts per
proposal, separate from independently verified execution or output bytes. The
receipt qualification appears in the cell heading so a compact value cannot
hide it. Dashboard and map projection requests, and the dashboard operations
request, reject redirects; failed requests retain their prior data. Decisions use
the existing separately governed review workflow. The page neither accepts
proposals nor installs skills or changes actor authority.

## Verification and serving limits

Offline functional tests execute the actual page code against synthetic DOM and
request fixtures. They cover navigation, filtering, lifecycle distinctions,
hostile text, missing data, timeout, stale responses, refresh state, payload
identity and preservation of expanded evidence. They require the existing Node
executable, but no browser, network or package installation.

These tests do not establish screenshot fidelity, visual contrast, screenreader
behavior, performance or adoption by a running service. Serving uses the
existing UI configuration; this change does not restart or rebind it. Existing
server processes may retain older imported projector code until their owner
performs a separately authorized update. Keep source review, publication, merge
and running adoption as separate delivery states.

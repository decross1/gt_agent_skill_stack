# Agent System workspace

The Brain keeps its existing URLs and uses three primary destinations:

| Destination | Existing URL | Use it to |
| --- | --- | --- |
| Today | `dashboard.html` | Find the current decision queue, recent changes and recorded blockers. |
| Work graph | `graph.html` | Explore recorded relationships and inspect the evidence behind a selection. |
| Skills & healing | `activity.html` | Compare skill observations, browse work and follow proposal stages. |

The server routes both `/` and `/index.html` to `dashboard.html` on the same
origin, carrying any query string and browser fragment through to Today. The
`mockups/` directory and its `m1.html`–`m3.html` pages are retained as a clearly
labelled source-only archive: their embedded values are historical mock data,
not live Atlas status, and each page links back to Today.

Today's dated source links are labelled **Raw Markdown**. Only the generated
relative `YYYY-MM-DD.md` filenames are linkable; unsupported, absolute, external,
or parent-traversing destinations remain visible but inert.

Proposal review remains at `proposal_review.html`, including existing `?id=`
links. It is a contextual destination. Reducing primary navigation does not
delete the underlying records or grant new review authority.

The light canvas is the default. The navigation's theme control stores a
browser-local preference shared by these destinations. Page filters,
pagination and disclosures keep the initial view short while preserving access
to recorded details. A browser may clamp its minimum window width; responsive
validation must report the measured viewport rather than the requested width.

## What the evidence means

Recorded work reads the optional typed `map.work` projection with schema
`work-graph/v1`. It keeps recorded parent, assignment, explicit dependency,
allowed-skill and caller-reported-use relations separate. An assignment is not
a child execution receipt, an allowed skill is not observed use, and a supplied
raw status is not a liveness or success verdict. Dependency cycles are shown as
source qualifications; the Atlas does not relabel a cyclic input as a DAG.

The work disclosure shows the capture time, per-file locator, byte and row
counts, whole-file SHA-256 when available, captured-prefix evidence for a
bounded failure, and the producer's item caps, omissions, unresolved reasons
and pre-cap cycle count. Those values are copied source evidence. They do not
authenticate an actor or make separately read files an atomic snapshot.
`projection_state: partial` remains inspectable with its qualifications.
Missing, malformed and explicitly unavailable work stays unavailable; Atlas
does not substitute the older contract/governance graph or describe a failed
capture as zero work. A failed live refresh may retain the last valid response,
but both the data-source line and work qualification identify it as cached.

- A recorded failure is a failure even when its timestamp is successfully
  observed. A saved snapshot's generation time and the beginning of its recall
  window describe different things.
- Attention items and historical contracts are not automatically current owner
  actions. The review catalog determines current eligibility; an unavailable
  catalog leaves that eligibility unknown.
- Knowledge and governance relationships do not establish task dependencies.
  The typed work projection only displays dependencies explicitly supplied in
  its bounded source capture. The framework-shaped capture currently supplies
  none, so dependency availability remains unavailable rather than becoming an
  empty complete execution DAG. Missing child execution joins stay unavailable.
  Task descriptions are not stable task IDs.
- An assigned or allowed skill is different from explicitly recorded use.
  Inferred historical attribution is neither authenticated identity nor proof
  that an agent is currently running.
- Accepted, enacted, reported verification and independent verification are
  distinct proposal stages. Missing later evidence must remain missing. Skill
  feedback counts do not measure an improvement caused by adopting a skill.

Review inspection uses the existing stored evidence. It does not automatically
request a model advisory, submit a verdict, graduate a draft or activate a
skill. Existing eligibility, stale-identity and cross-project action guards
continue to control any explicit action.

## Validation and adoption

Validate the exact committed source using isolated, byte-verified private
inputs. Keep before/after browser captures, failing regressions and missing
data states distinct from passing checks. Exercise automatic page bootstrap,
keyboard selection, filtering, paging, detail opening and old deep links in
normal Firefox. Tests alone do not establish visual usability.

On HTTP startup, a bookmarked graph record is kept independently while the
older saved map paints. A successful live map may resolve it; a complete live
response may instead label it unavailable. A failed or malformed refresh, and
an unavailable, malformed or partial typed-work projection, cannot turn an
unresolved typed bookmark into a current-absence claim, so the URL remains
retryable. A later node choice, Back action, mode or filter change, or browser
URL navigation supersedes that pending startup request. A prior live response
cannot establish that a newer URL target is absent: that conclusion waits for
a subsequent map completion. Cancelling an unresolved request also removes its
retry message. The source status still distinguishes saved evidence, a current
live response and a failed refresh.

The existing managed Brain launcher fingerprints `memory/brain/view` as well
as executable scripts. Adopting a reviewed UI commit can therefore trigger a
managed restart. Follow the existing deployment contract: reconcile the applied
snapshot and fingerprint, process/listener, supported API responses, served
asset hashes and an actual browser. Static HTTP success alone does not certify
the loaded process or projection. No new unit, manual restart, ingestion event
or data refresh is required by this UI change. A deferred automatic deployment
must be reported as deferred.

Source rollback is a reviewed revert through the same maintenance route.
Preserve unrelated operator changes and append-only evidence; do not reset,
discard or rewrite them to make the source tree appear clean.

An activity-window change through the stepper or page arrow keys also cancels
an unresolved startup bookmark. A boundary no-op, or an arrow key used inside
an input, leaves it pending. This protects newer navigation when saved data
lacks a target that a delayed live response later supplies. The source and
browser checks qualify bookmark behavior only, not graph completeness or actor
liveness.

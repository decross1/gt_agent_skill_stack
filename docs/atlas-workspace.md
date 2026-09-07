# Agent System workspace

The Brain keeps its existing URLs and uses three primary destinations:

| Destination | Existing URL | Use it to |
| --- | --- | --- |
| Today | `dashboard.html` | Find the current decision queue, recent changes and recorded blockers. |
| Work graph | `graph.html` | Explore recorded relationships and inspect the evidence behind a selection. |
| Skills & healing | `activity.html` | Compare skill observations, browse work and follow proposal stages. |

Proposal review remains at `proposal_review.html`, including existing `?id=`
links. It is a contextual destination. Reducing primary navigation does not
delete the underlying records or grant new review authority.

The light canvas is the default. The navigation's theme control stores a
browser-local preference shared by these destinations. Page filters,
pagination and disclosures keep the initial view short while preserving access
to recorded details. A browser may clamp its minimum window width; responsive
validation must report the measured viewport rather than the requested width.

## What the evidence means

- A recorded failure is a failure even when its timestamp is successfully
  observed. A saved snapshot's generation time and the beginning of its recall
  window describe different things.
- Attention items and historical contracts are not automatically current owner
  actions. The review catalog determines current eligibility; an unavailable
  catalog leaves that eligibility unknown.
- Knowledge and governance relationships do not establish task dependencies.
  The published projections do not currently supply a complete execution DAG.
  Missing joins stay unavailable. Task descriptions are not stable task IDs.
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

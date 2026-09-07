# Work graph evidence contract

`scripts.work_graph.build_work_graph(records, *, source, record_cap=2048,
node_cap=256, edge_cap=1024, diagnostic_cap=256)` is a pure, caller-fed
projection. It does not discover files, read a consumer, write a ledger, call a
model, or expose an endpoint. Its presence does not update the existing UI.

## Input and identity

Supply JSON-like records and a source mapping with a nonempty `namespace`,
`locator`, and `capture_basis`. Capture metadata is reported as supplied; a hash
in that mapping is not independently checked or an authenticated identity.
Each record needs exact nonempty string `id` and `kind`. Optional fields are
`source_locator`, `role`, `raw_status`, `parent_id`, `spawn_assignments`,
`allowed_skills`, `observed_skills`, and `dependencies`. The last four are lists
of exact string IDs. The caller must map structured source fields explicitly.

Work IDs encode namespace, kind, and record ID. References resolve an exact
record ID within the supplied collection. Repeated IDs, including repeated
status rows for one task, are unresolved; this module does not invent an event
identity or select a latest row. Missing and conflicting IDs receive reasons.
Dependency-field presence and structural validity are observed on every mapping
before missing, duplicate, conflicting, or otherwise invalid identities are
withheld. That evidence can affect availability, but it never makes an
unresolved record safe to project and never creates a dependency edge.
Source locators and capture basis accompany nodes and edges. A missing record
locator uses the collection locator plus the exact kind/ID selector, not a
fabricated line number. Raw status is retained separately from projection state;
it supplies no liveness, success, or actor-authentication guarantee.

## Relations and limits

| Relation | Meaning and direction |
| --- | --- |
| `parent` | Recorded parent to child |
| `spawn_assignment` | Assigning record to the exact referenced record; no execution inferred from a missing join or a self-assignment |
| `allowed_skill` | Record to a declared permitted skill; not use or adoption |
| `observed_skill` | Record to explicitly supplied usage; `assertion_basis: caller_supplied`, not independent proof |
| `dependency` | Record to an explicitly declared prerequisite |

No dependency fields means no dependency edges and
`dependencies_not_supplied`. An explicitly empty dependency list is valid
evidence and differs from both an absent field and a malformed list. Supplied
lists attached only to withheld identities report
`dependencies_identity_unresolved`; a mix of projectable evidence with absent,
invalid, or identity-withheld evidence is partial. These availability states do
not assert that referenced targets resolved. Dependency cycles are computed
from all candidate nodes and edges before output caps and are reported without
deleting edges to present a false DAG. A cycle can therefore name a candidate
omitted from the returned `nodes` list; omission counters and projection state
describe that bounded view. A cycle is not a failure to project the supplied
evidence.

Output schema is `work-graph/v1`: source, limits, projection state, dependency
availability, nodes, edges, unresolved diagnostics, and cycles. Ordering is
deterministic for the same supplied records and metadata. Caps count items,
**not bytes**: callers must bound individual record and metadata size before
using untrusted data. Source overflow fails closed before traversal. Output
omissions are counted and mark the projection partial; unavailable input is
explicit. Inspect limits and unresolved reasons before presenting coverage.

## Synthetic example

This is an illustration, not a record of running agents:

```python
from scripts.work_graph import build_work_graph

graph = build_work_graph([
    {"id": "review", "kind": "task", "raw_status": "assigned",
     "spawn_assignments": ["check"], "allowed_skills": ["validate"],
     "dependencies": []},
    {"id": "check", "kind": "task", "parent_id": "review",
     "raw_status": "reported complete", "observed_skills": ["validate"],
     "dependencies": ["review"]},
], source={"namespace": "example-not-live", "locator": "example:two-tasks",
           "capture_basis": {"kind": "synthetic example"}})
```

Run-log task IDs and spawn-ledger child IDs often do not match. Those missing
joins require better source records or a separately specified adapter; prose,
chronology, an allowed skill, or a role label cannot supply the missing link.
Proposal acceptance, enactment, and independently verified repair remain
separate lifecycle evidence. This projection does not write any of them.

## Existing harvest references

The map's `becomes` relation represents a proposal citing a finding. A structured
`feedback.jsonl:H008:D-042` reference identifies harvest `H008` and the complete
source suffix `D-042`; suffixes may themselves contain colons. Matching uses
exact source fields, with an explicit skill target narrowing a shared finding
identity. Malformed or still-ambiguous references produce no edge. An
unqualified harvest reference must also identify one finding, never the first
row by accident. Input bytes are preserved. A coalesced `becomes` edge carries
all distinct valid exact citations in sorted `source_refs`; the scalar
`source_ref` remains a compatibility alias for the first value in that complete
list. A single-reference edge therefore keeps its historical scalar value and
has a one-item complete list. `weight_e` counts every explicit relation
occurrence coalesced into the same edge. For `becomes`, that includes each
resolved proposal citation occurrence (including an exact citation repeated by
one proposal) and each matching direct typed `EDGES`/`edges.jsonl` record.
`source_refs` remains only the complete set of resolved proposal citations; a
direct typed record does not acquire a fabricated citation. The weight,
multiple spellings, and mixed support rows do not count independent findings:
one exact finding/proposal pair remains one edge. Neither a recovered reference
nor a `becomes` edge is successful enactment.

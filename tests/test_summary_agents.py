"""Historical attribution references must resolve without inventing runs."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_summary as ps


HARVEST = {"harvest_id": "fixture", "skill": "validate", "date": "2026-06-28"}


def build(run=(), feedback=(), contracts=()):
    return ps.build_agents_and_matrix(
        list(run), list(feedback), list(contracts), [], {"validate"},
        "2026-08-01", "2026-09-05",
    )


@pytest.mark.parametrize("source", ["harvest", "contract"])
def test_reference_only_agent_resolves_without_observed_run_presence(source):
    feedback = [HARVEST] if source == "harvest" else []
    contracts = ([{"agent": "workflow", "skill_subset": ["validate"],
                   "date": "2026-06-28"}] if source == "contract" else [])
    agents, matrix, attrs = build(feedback=feedback, contracts=contracts)
    assert {c["agent"] for c in matrix["cells"]} <= {a["id"] for a in agents}
    assert len(agents) == 1
    assert agents[0]["evidence"] == "inferred"
    assert agents[0]["runs_by_day"] == {}
    assert agents[0]["first_seen"] is None
    assert agents[0]["last_seen"] is None
    assert matrix["cells"][0]["inferred"] == 1
    assert matrix["cells"][0]["explicit"] == 0
    assert attrs[0]["date"] == "2026-06-28"
    assert attrs[0]["method"] == source
    assert attrs[0]["explicit"] is False


def test_unsupported_references_do_not_invent_an_agent():
    agents, matrix, attrs = build(
        feedback=[dict(HARVEST, skill="unknown")],
        contracts=[{"agent": "workflow", "skill_subset": ["unknown"],
                    "date": "2026-06-28"}],
    )
    assert agents == [] and matrix["cells"] == [] and attrs == []


def test_historical_reference_preserves_recorded_agent_presence():
    run = [{"agent": "nara", "skill": "validate", "method": "skill_used",
            "date": "2026-08-02", "ts": "2026-08-02T01:00:00Z",
            "explicit_agent": True}]
    before, _, _ = build(run=run)
    after, matrix, _ = build(run=run, feedback=[HARVEST])
    assert after == before
    assert after[0]["evidence"] == "explicit"
    assert after[0]["runs_by_day"] == {"2026-08-02": 1}
    assert matrix["cells"][0]["explicit"] == 1
    assert matrix["cells"][0]["inferred"] == 1

#!/usr/bin/env python3
"""linearize_context.py — MAGMA + Graphiti Structure-Aware Context Linearization.

Implements:
1. Graphiti 4-timestamp bitemporal filtering (`valid_from`, `valid_to`, `created_at`, `expired_at`).
2. MAGMA 4-layer edge routing (`Semantic`, `Temporal`, `Causal`, `Entity`) and Kahn topological
   sorting over `Causal` and `Temporal` edges so causes strictly precede effects (`cause -> effect`).
"""
from __future__ import annotations

import argparse
from collections import deque
import json
from pathlib import Path
import sys
from typing import Any

EDGE_LAYERS = frozenset({"Semantic", "Temporal", "Causal", "Entity"})


def is_active_at(claim: dict[str, Any], as_of: str | None) -> bool:
    if as_of is None:
        return claim.get("valid_to") is None and claim.get("expired_at") is None
    vf = claim.get("valid_from") or ""
    vt = claim.get("valid_to")
    ca = claim.get("created_at") or ""
    ea = claim.get("expired_at")
    valid_ok = (not vf or vf <= as_of) and (vt is None or as_of < vt)
    tx_ok = (not ca or ca <= as_of) and (ea is None or as_of < ea)
    return valid_ok and tx_ok


def linearize_claims(
    payload: dict[str, Any],
    *,
    intent: str = "WHY",
    as_of: str | None = None,
    include_superseded: bool = False,
) -> dict[str, Any]:
    claims = payload.get("bitemporal_claims", [])
    edges = payload.get("edges", [])

    by_id: dict[str, dict[str, Any]] = {}
    for c in claims:
        cid = str(c["claim_id"])
        active = is_active_at(c, as_of)
        item = {**c, "active": active}
        if active or include_superseded:
            by_id[cid] = item

    # Filter edges by intent
    allowed_layers = (
        {"Causal", "Temporal"} if intent == "WHY"
        else {"Temporal"} if intent == "WHEN"
        else set(EDGE_LAYERS)
    )

    adj: dict[str, list[str]] = {cid: [] for cid in by_id}
    indegree: dict[str, int] = {cid: 0 for cid in by_id}
    active_edges: list[dict[str, Any]] = []

    for e in edges:
        src, dst = str(e.get("source")), str(e.get("target"))
        layer = e.get("layer", "Causal")
        if src in by_id and dst in by_id and layer in allowed_layers:
            adj[src].append(dst)
            indegree[dst] += 1
            active_edges.append(e)

    # Deterministic Kahn topological sort (tie-break by valid_from, then claim_id)
    ready = sorted(
        [cid for cid, deg in indegree.items() if deg == 0],
        key=lambda cid: (str(by_id[cid].get("valid_from") or ""), cid),
    )
    queue = deque(ready)
    ordered_ids: list[str] = []

    while queue:
        curr = queue.popleft()
        ordered_ids.append(curr)
        for nxt in sorted(adj[curr], key=lambda cid: (str(by_id[cid].get("valid_from") or ""), cid)):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    cycle_detected = len(ordered_ids) != len(by_id)
    if cycle_detected:
        for cid in sorted(by_id):
            if cid not in ordered_ids:
                ordered_ids.append(cid)

    return {
        "schema": "magma-graphiti-linearization/v1",
        "intent": intent,
        "as_of": as_of,
        "cycle_detected": cycle_detected,
        "ordered_claims": [by_id[cid] for cid in ordered_ids],
        "active_edges": active_edges,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("--intent", choices=("WHY", "WHEN", "ALL"), default="WHY")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--include-superseded", action="store_true")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if a causal cycle is detected")
    args = parser.parse_args(argv)

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    result = linearize_claims(
        payload,
        intent=args.intent,
        as_of=args.as_of,
        include_superseded=args.include_superseded,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.check and result["cycle_detected"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

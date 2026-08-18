#!/usr/bin/env python3
"""Read-only, bounded inspection of governed proposal-ledger quarantine state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain_ledger import ProposalLedgerError, inspect_proposals

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT / "memory" / "brain" / "proposals.jsonl"
MAX_OUTPUT_BYTES = 8 * 1024


def _emit(payload: dict) -> int:
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        encoded = b'{"ok":false,"error":"status output exceeded byte budget"}'
        print(encoded.decode("utf-8"))
        return 2
    print(encoded.decode("utf-8"))
    return 0 if payload.get("ok") else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect proposal-ledger compatibility quarantine.")
    parser.add_argument("--strict", action="store_true",
                        help="do not quarantine the known legacy pair; report strict validity instead")
    args = parser.parse_args()
    try:
        result = inspect_proposals(PROPOSALS, quarantine_known_legacy=not args.strict)
    except ProposalLedgerError as exc:
        # Parser errors are structured by line/reason and never include raw rows.
        return _emit({"ok": False, "strict": args.strict, "error": str(exc)})
    return _emit({"ok": True, "strict": args.strict, "governed_row_count": len(result.rows),
                  "quarantine": result.quarantine})


if __name__ == "__main__":
    raise SystemExit(main())

"""Small, fail-closed writer primitive for the canonical proposal ledger.

This is deliberately a *single-file* advisory-lock helper.  It coordinates the
two local proposal writers which opt into it; it does not provide a database,
multi-file transactions, or actor authentication.  Readers may stay lock-free,
but a writer must hold the lock while it validates, decides, allocates an id,
and appends.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PID_RE = re.compile(r"^P-\d+$")
MAX_LEDGER_BYTES = 8 * 1024 * 1024
MAX_ROW_BYTES = 256 * 1024
MAX_ACCEPTED_BODY_BYTES = 64 * 1024
LOCK_WAIT_SECONDS = 0.75
LOCK_POLL_SECONDS = 0.01

TERMINAL_VERDICTS = {"accepted", "rejected", "auto-accept", "auto-reject"}
ACCEPTING_VERDICTS = {"accepted", "auto-accept"}
KNOWN_VERDICTS = TERMINAL_VERDICTS | {"human-review"}
DECISION_SCHEMA_VERSION = "proposal-verdict-v2"
ACCEPTED_BODY_SCHEMA_VERSION = "proposal-change-v1"

# This is a deliberately one-off compatibility bridge for two append-only rows
# written before the governed P-NNN proposal schema existed. Do not broaden this
# into a permissive alternate proposal format: unknown mixed-schema rows remain
# corrupt and block writers.
LEGACY_PRELOCK_CRITIQUE_ID = "prop-2026-08-17-prelock-critique"
LEGACY_PRELOCK_CRITIQUE_TARGET = "skill:plan-research (or a new prereg-critique skill)"
LEGACY_PRELOCK_FILING_SCHEMA = "legacy-prelock-critique-filing-v1"
LEGACY_PRELOCK_LIFECYCLE_SCHEMA = "legacy-prelock-critique-lifecycle-v1"


class ProposalLedgerError(ValueError):
    """The ledger cannot safely be used as a source of truth."""


class ProposalLedgerTimeout(ProposalLedgerError):
    """Another cooperating writer retained the advisory lock past the budget."""


@dataclass(frozen=True)
class ProposalLedgerRead:
    """Validated governed rows plus non-authoritative legacy quarantine facts."""

    rows: list[dict[str, Any]]
    quarantine: list[dict[str, Any]]


def _quarantine_metadata(line_number: int, schema: str, reason: str, raw_row: bytes) -> dict[str, Any]:
    """Evidence-only compatibility metadata. Never expose a legacy row's body."""
    return {
        "line_number": line_number,
        "schema": schema,
        "reason": reason,
        "sha256": hashlib.sha256(raw_row).hexdigest(),
    }


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _recognized_legacy_prelock_pair(filing: dict[str, Any], lifecycle: dict[str, Any]) -> bool:
    """Recognize exactly the historic mixed-schema pair, and nothing broader."""
    filing_keys = {"timestamp", "id", "status", "proposed_by", "target", "proposal", "evidence_refs"}
    lifecycle_keys = {"timestamp", "proposal_id", "supersedes_proposal_id", "agent_id", "verdict",
                      "verdict_reasoning", "rule_cited", "decision_id", "status"}
    return (
        set(filing) == filing_keys
        and filing.get("id") == LEGACY_PRELOCK_CRITIQUE_ID
        and filing.get("status") == "open"
        and filing.get("proposed_by") == "claude-code-main"
        and filing.get("target") == LEGACY_PRELOCK_CRITIQUE_TARGET
        and all(_is_nonempty_string(filing.get(key))
                for key in ("timestamp", "proposed_by", "target", "proposal"))
        and isinstance(filing.get("evidence_refs"), list)
        and filing["evidence_refs"]
        and all(_is_nonempty_string(item) for item in filing["evidence_refs"])
        and set(lifecycle) == lifecycle_keys
        and lifecycle.get("proposal_id") == LEGACY_PRELOCK_CRITIQUE_ID
        and lifecycle.get("supersedes_proposal_id") == LEGACY_PRELOCK_CRITIQUE_ID
        and lifecycle.get("agent_id") == "claude-code-main"
        and lifecycle.get("verdict") == "human-review"
        and lifecycle.get("status") == "closed"
        and lifecycle.get("rule_cited") is None
        and lifecycle.get("decision_id") is None
        and all(_is_nonempty_string(lifecycle.get(key))
                for key in ("timestamp", "verdict_reasoning"))
    )


def accepted_body_digest(body: str) -> str:
    """Return the unambiguous SHA-256 over the exact UTF-8 proposal body."""
    if not isinstance(body, str):
        raise ProposalLedgerError("accepted body must be text")
    try:
        raw = body.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ProposalLedgerError("accepted body is not UTF-8 encodable") from exc
    if not raw or len(raw) > MAX_ACCEPTED_BODY_BYTES:
        raise ProposalLedgerError("accepted body is empty or exceeds byte budget")
    return hashlib.sha256(raw).hexdigest()


def validate_accepted_decision(row: dict[str, Any], *, require_body: bool) -> None:
    """Validate the self-contained body required for an accepting decision.

    Historical accepted/auto-accept rows predate this schema and remain readable;
    callers recovering a handoff from them must fail closed rather than invent a
    body.
    """
    body_fields = {"decision_schema_version", "accepted_body_schema",
                   "accepted_body", "accepted_body_sha256"}
    present = body_fields.intersection(row)
    if row.get("verdict") not in ACCEPTING_VERDICTS:
        if present:
            raise ProposalLedgerError("non-accepting verdict carries accepted body")
        return
    if not present and not require_body:
        return
    if present != body_fields:
        raise ProposalLedgerError("accepted decision has incomplete body record")
    if row.get("decision_schema_version") != DECISION_SCHEMA_VERSION:
        raise ProposalLedgerError("accepted decision has unknown schema version")
    if row.get("accepted_body_schema") != ACCEPTED_BODY_SCHEMA_VERSION:
        raise ProposalLedgerError("accepted decision has unknown body schema")
    if row.get("basis") not in {"original", "amended"}:
        raise ProposalLedgerError("accepted decision has missing or invalid basis")
    digest = row.get("accepted_body_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ProposalLedgerError("accepted decision has invalid body digest")
    if accepted_body_digest(row.get("accepted_body")) != digest:
        raise ProposalLedgerError("accepted decision body digest mismatch")


def accepted_decision(rows: list[dict[str, Any]], proposal_id: str) -> dict[str, Any] | None:
    """Return one verified accepting terminal, or fail closed if legacy/tampered."""
    found = None
    for row in rows:
        if row.get("proposal_id") == proposal_id and row.get("verdict") in ACCEPTING_VERDICTS:
            found = row
    if found is None:
        return None
    validate_accepted_decision(found, require_body=True)
    return found


def _check_row(row: Any, line_number: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ProposalLedgerError(f"line {line_number}: expected JSON object")
    pid = row.get("proposal_id")
    if not isinstance(pid, str) or not PID_RE.fullmatch(pid):
        raise ProposalLedgerError(f"line {line_number}: invalid proposal_id")
    verdict = row.get("verdict")
    if verdict is not None and verdict not in KNOWN_VERDICTS:
        raise ProposalLedgerError(f"line {line_number}: unknown verdict")
    return row


def validate_proposal_rows(rows: list[dict[str, Any]]) -> None:
    """Validate proposal identity and lifecycle invariants without writing."""
    for line_number, row in enumerate(rows, 1):
        _check_row(row, line_number)
        validate_accepted_decision(row, require_body=False)
    filings: set[str] = set()
    by_id: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        pid = row["proposal_id"]
        if "title" in row:
            if pid in filings:
                raise ProposalLedgerError(f"duplicate filing for {pid}")
            filings.add(pid)
        by_id.setdefault(pid, []).append(row)
    for pid, history in by_id.items():
        if pid not in filings:
            raise ProposalLedgerError(f"{pid}: lifecycle row has no filing")
        terminal_indexes = [
            index for index, row in enumerate(history)
            if row.get("verdict") in TERMINAL_VERDICTS
        ]
        if len(terminal_indexes) > 1:
            raise ProposalLedgerError(f"{pid}: contradictory terminal verdicts")
        if terminal_indexes:
            # Enactment and verification evidence are append-only records, not
            # verdicts. They may follow a terminal acceptance/rejection. A later
            # verdict (including human-review) would rewrite the decision's
            # meaning and is refused.
            after_terminal = history[terminal_indexes[0] + 1:]
            if any(row.get("verdict") is not None for row in after_terminal):
                raise ProposalLedgerError(f"{pid}: lifecycle verdict follows terminal verdict")


def inspect_proposals_bytes(raw: bytes, *, quarantine_known_legacy: bool = False) -> ProposalLedgerRead:
    """Parse proposal JSONL with an optional, exact two-row legacy quarantine.

    Lifecycle entries legitimately repeat a proposal_id.  What must be unique
    is the *filing* (a row carrying ``title``); a second filing for the same id
    is an ambiguous duplicate proposal.  A proposal may have at most one final
    terminal verdict. Non-verdict enactment/verification evidence may follow it,
    but no later verdict may reopen or reinterpret the decision. The default is
    strict: the recognized legacy pair still raises unless explicitly quarantined.
    """
    if len(raw) > MAX_LEDGER_BYTES:
        raise ProposalLedgerError("ledger exceeds byte budget")
    if not raw:
        return ProposalLedgerRead(rows=[], quarantine=[])
    if not raw.endswith(b"\n"):
        raise ProposalLedgerError("ledger is missing final newline")
    parsed: list[tuple[int, bytes, dict[str, Any]]] = []
    try:
        lines = raw.splitlines(keepends=True)
        for line_number, line in enumerate(lines, 1):
            if not line.endswith(b"\n"):
                raise ProposalLedgerError(f"line {line_number}: incomplete row")
            body = line[:-1]
            if not body:
                raise ProposalLedgerError(f"line {line_number}: blank row")
            if len(body) > MAX_ROW_BYTES:
                raise ProposalLedgerError(f"line {line_number}: exceeds row byte budget")
            row = json.loads(body.decode("utf-8"))
            if not isinstance(row, dict):
                raise ProposalLedgerError(f"line {line_number}: expected JSON object")
            # Retain the complete newline-terminated ledger row so quarantine
            # evidence binds the exact source bytes, not a normalized JSON form.
            parsed.append((line_number, line, row))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProposalLedgerError(f"malformed JSONL: {exc}") from exc

    rows: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    index = 0
    while index < len(parsed):
        line_number, raw_line, row = parsed[index]
        if (quarantine_known_legacy and index + 1 < len(parsed)
                and _recognized_legacy_prelock_pair(row, parsed[index + 1][2])):
            next_line, next_raw_line, _next_row = parsed[index + 1]
            quarantine.extend((
                _quarantine_metadata(line_number, LEGACY_PRELOCK_FILING_SCHEMA,
                                     "recognized legacy mixed-schema filing", raw_line),
                _quarantine_metadata(next_line, LEGACY_PRELOCK_LIFECYCLE_SCHEMA,
                                     "recognized legacy mixed-schema lifecycle", next_raw_line),
            ))
            index += 2
            continue
        # Strict governed validation happens after removing only the exact pair;
        # any lookalike or arbitrary invalid row fails here.
        rows.append(_check_row(row, line_number))
        index += 1
    validate_proposal_rows(rows)
    return ProposalLedgerRead(rows=rows, quarantine=quarantine)


def parse_proposals_bytes(raw: bytes) -> list[dict[str, Any]]:
    """Strict default parser; known legacy rows are errors unless opted in."""
    return inspect_proposals_bytes(raw).rows


def inspect_proposals(path: Path, *, quarantine_known_legacy: bool = False) -> ProposalLedgerRead:
    """Read proposal rows plus bounded, body-free quarantine metadata."""
    try:
        raw = path.read_bytes() if path.exists() else b""
    except OSError as exc:
        raise ProposalLedgerError(f"cannot read ledger: {exc}") from exc
    return inspect_proposals_bytes(raw, quarantine_known_legacy=quarantine_known_legacy)


def read_proposals(path: Path, *, quarantine_known_legacy: bool = False) -> list[dict[str, Any]]:
    """Read governed rows; strict by default, legacy quarantine only by opt-in."""
    return inspect_proposals(path, quarantine_known_legacy=quarantine_known_legacy).rows


def lifecycle_state(rows: list[dict[str, Any]], proposal_id: str) -> str | None:
    """Return the latest verdict, else the newest non-verdict lifecycle state.

    Evidence appended after acceptance is not a re-open: the decision remains
    terminal even though the newest row does not carry a ``verdict`` field.
    """
    history = [row for row in rows if row["proposal_id"] == proposal_id]
    if not history:
        return None
    for row in reversed(history):
        verdict = row.get("verdict")
        if verdict is not None:
            return verdict
    last = history[-1]
    status = last.get("status")
    return status if isinstance(status, str) and status else "open"


def proposal_is_open(rows: list[dict[str, Any]], proposal_id: str) -> bool:
    """Only an explicitly open/human-review lifecycle can receive a verdict."""
    return lifecycle_state(rows, proposal_id) in {"open", "human-review"}


class ProposalLedgerLock:
    """Bounded cross-process advisory lock plus validated proposal snapshot."""

    def __init__(self, path: Path, *, wait_seconds: float = LOCK_WAIT_SECONDS,
                 quarantine_known_legacy: bool = True):
        self.path = path
        self.wait_seconds = wait_seconds
        # Writer paths opt into the narrowly documented bridge so an existing
        # legacy pair cannot permanently block governed review. Strict read APIs
        # remain the default for diagnostics and integrity checks.
        self.quarantine_known_legacy = quarantine_known_legacy
        self._lock_file = None
        self.rows: list[dict[str, Any]] = []
        self.quarantine: list[dict[str, Any]] = []

    def __enter__(self) -> "ProposalLedgerLock":
        # A sidecar avoids creating/changing the canonical ledger merely to wait
        # for it.  It is coordination metadata, not part of ledger authority.
        lock_path = self.path.with_name(self.path.name + ".lock")
        try:
            self._lock_file = lock_path.open("a+b")
        except OSError as exc:
            raise ProposalLedgerError(f"cannot open advisory lock: {exc}") from exc
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self._lock_file.close()
                    self._lock_file = None
                    raise ProposalLedgerTimeout("proposal ledger lock timed out")
                time.sleep(LOCK_POLL_SECONDS)
            except OSError as exc:
                self._lock_file.close()
                self._lock_file = None
                raise ProposalLedgerError(f"cannot acquire advisory lock: {exc}") from exc
        try:
            result = inspect_proposals(self.path,
                                       quarantine_known_legacy=self.quarantine_known_legacy)
            self.rows = result.rows
            self.quarantine = result.quarantine
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def append(self, rows: list[dict[str, Any]]) -> None:
        """Append prevalidated newline-terminated JSON records durably.

        All serialization and size checks happen before the ledger is opened for
        append, so validation failures leave its bytes untouched.  As with any
        POSIX append, an unrecoverable device failure *during* write/fsync cannot
        be made transactional; callers must treat that exceptional case as an
        I/O incident and re-read before retrying.
        """
        if self._lock_file is None:
            raise ProposalLedgerError("append without advisory lock")
        # Every newly appended accepting terminal is self-contained. This does
        # not rewrite or invalidate legacy acceptance rows already on disk.
        for row in rows:
            if row.get("verdict") in ACCEPTING_VERDICTS:
                validate_accepted_decision(row, require_body=True)
        encoded: list[bytes] = []
        for row in rows:
            try:
                line = json.dumps(row, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
            except (TypeError, ValueError) as exc:
                raise ProposalLedgerError(f"cannot serialize append row: {exc}") from exc
            if len(line) - 1 > MAX_ROW_BYTES:
                raise ProposalLedgerError("append row exceeds byte budget")
            encoded.append(line)
        # Validate the complete prospective lifecycle before opening the ledger
        # for append.  This also prevents callers of the compatibility append
        # surface from creating duplicate filings or a second terminal verdict.
        validate_proposal_rows(self.rows + rows)
        payload = b"".join(encoded)
        try:
            old_size = self.path.stat().st_size if self.path.exists() else 0
            if old_size + len(payload) > MAX_LEDGER_BYTES:
                raise ProposalLedgerError("append would exceed ledger byte budget")
            if not payload:
                return
            with self.path.open("ab", buffering=0) as stream:
                written = stream.write(payload)
                if written != len(payload):
                    raise OSError("short append to proposal ledger")
                stream.flush()
                os.fsync(stream.fileno())
        except ProposalLedgerError:
            raise
        except OSError as exc:
            raise ProposalLedgerError(f"append failed: {exc}") from exc
        self.rows.extend(rows)

    def __exit__(self, _type, _value, _traceback) -> None:
        if self._lock_file is not None:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                self._lock_file.close()
                self._lock_file = None

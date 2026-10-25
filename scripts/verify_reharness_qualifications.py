#!/usr/bin/env python3
"""Verify qualification evidence, not promotion: compact sorted JSON uses ASCII escaping."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

ZERO = "0" * 64
FIELDS = {"schema", "qualification_id", "prev_sha256", "skill_path", "skill_commit",
          "skill_blob_sha", "trigger_run_ref", "applies_when", "falsified_when",
          "scope_narrowing", "row_sha256"}
OPS = {"<", "<=", ">", ">=", "==", "!="}


def unique_keys(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON key")
    return result


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="")
    return subprocess.check_output(["git", "--no-replace-objects", "-C", str(repo), *args],
                                   env=env, text=True, stderr=subprocess.PIPE, timeout=10).strip()


def predicates(items):
    if type(items) is not list or not 1 <= len(items) <= 16:
        raise ValueError("predicates require 1..16 conditions")
    for item in items:
        if (type(item) is not dict or set(item) != {"feature", "op", "value"}
                or type(item["feature"]) is not str or not item["feature"].strip()
                or type(item["op"]) is not str or item["op"] not in OPS):
            raise ValueError("invalid predicate fields")
        value = item["value"]
        if type(value) not in (int, float, bool) or (type(value) is float and not math.isfinite(value)):
            raise ValueError("predicate value must be finite numeric or boolean")


def verify_qualifications(path, repo):
    report = dict(valid_count=0, qualified_skills=[], chain_tip_sha256=ZERO, errors=[])
    identities, qualified = set(), set()
    try:
        with Path(path).open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                row = json.loads(line, object_pairs_hook=unique_keys)
                if type(row) is not dict or set(row) != FIELDS:
                    raise ValueError(f"line {number}: exact qualification keys required")
                if any(type(row[k]) is not str or not row[k].strip()
                       for k in FIELDS - {"applies_when", "falsified_when"}):
                    raise ValueError(f"line {number}: nonempty string fields required")
                if row["schema"] != "reharness-qualification/v1" or row["qualification_id"] in identities:
                    raise ValueError(f"line {number}: invalid schema or duplicate qualification_id")
                predicates(row["applies_when"])
                predicates(row["falsified_when"])
                raw = json.dumps({k: v for k, v in row.items() if k != "row_sha256"},
                                 sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
                if (row["prev_sha256"] != report["chain_tip_sha256"]
                        or row["row_sha256"] != hashlib.sha256(raw).hexdigest()):
                    raise ValueError(f"line {number}: broken qualification hash chain")
                commit = git(repo, "rev-parse", "--verify", "--end-of-options", row["skill_commit"] + "^{commit}")
                blob = git(repo, "rev-parse", "--verify", "--end-of-options", commit + ":" + row["skill_path"])
                if blob != row["skill_blob_sha"] or git(repo, "cat-file", "-t", blob) != "blob":
                    raise ValueError(f"line {number}: committed skill blob mismatch")
                identities.add(row["qualification_id"])
                qualified.add((row["skill_path"], commit, blob))
                report["valid_count"] += 1
                report["chain_tip_sha256"] = row["row_sha256"]
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as error:
        report.update(valid_count=0, chain_tip_sha256=ZERO, errors=[str(error)])
        qualified.clear()
    report["qualified_skills"] = [dict(zip(("skill_path", "skill_commit", "skill_blob_sha"), item))
                                  for item in sorted(qualified)]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args(argv)
    report = verify_qualifications(args.ledger, args.repo)
    print(json.dumps(report, sort_keys=True))
    return int(bool(report["errors"]) or report["valid_count"] == 0)


if __name__ == "__main__":
    raise SystemExit(main())

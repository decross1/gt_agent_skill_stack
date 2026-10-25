#!/usr/bin/env python3
"""Check paired RC1 skill receipts for eligibility for steward review."""
import argparse
import json
import os
from pathlib import Path
import subprocess

FIELDS = {"schema", "task_id", "arm", "skill_path", "skill_commit",
          "skill_blob_sha", "task_set_sha256", "passed", "run_ref"}


def unique_keys(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("duplicate JSON key")
    return value


def git(repo, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="")
    return subprocess.check_output(
        ["git", "--no-replace-objects", "-C", str(repo), *args],
        text=True, stderr=subprocess.PIPE, timeout=10, env=env).strip()


def verify_skill_lift(receipts, repo):
    report = dict(n_tasks=0, base_pass=0, cand_pass=0, b=0, c=0, errors=[])
    runs, paths, task_sets = {}, set(), set()
    blobs = {"base": set(), "candidate": set()}
    try:
        with Path(receipts).open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                row = json.loads(line, object_pairs_hook=unique_keys)
                if type(row) is not dict or set(row) != FIELDS:
                    raise ValueError(f"line {number}: expected exact receipt keys")
                if type(row["passed"]) is not bool or any(
                        type(row[key]) is not str or not row[key].strip()
                        for key in FIELDS - {"passed"}):
                    raise ValueError(f"line {number}: nonempty strings and boolean passed required")
                if row["schema"] != "skill-lift-run/v1" or row["arm"] not in blobs:
                    raise ValueError(f"line {number}: invalid schema or arm")
                commit = git(repo, "rev-parse", "--verify", "--end-of-options",
                             row["skill_commit"] + "^{commit}")
                blob = git(repo, "rev-parse", "--verify", "--end-of-options",
                           commit + ":" + row["skill_path"])
                if blob != row["skill_blob_sha"] or git(repo, "cat-file", "-t", blob) != "blob":
                    raise ValueError(f"line {number}: skill blob does not match committed file")
                key = (row["task_id"], row["arm"])
                if key in runs:
                    raise ValueError(f"line {number}: duplicate task/arm pair")
                runs[key] = row["passed"]
                paths.add(row["skill_path"])
                task_sets.add(row["task_set_sha256"])
                blobs[row["arm"]].add(blob)
        base = {task: passed for (task, arm), passed in runs.items() if arm == "base"}
        cand = {task: passed for (task, arm), passed in runs.items() if arm == "candidate"}
        if not base or base.keys() != cand.keys():
            raise ValueError("arms must cover the same nonempty task_id set")
        if len(paths) != 1 or len(task_sets) != 1:
            raise ValueError("one skill_path and task_set_sha256 required")
        if any(len(values) != 1 for values in blobs.values()) or blobs["base"] == blobs["candidate"]:
            raise ValueError("each arm must name one distinct skill blob")
        report.update(n_tasks=len(base), base_pass=sum(base.values()), cand_pass=sum(cand.values()),
                      b=sum(base[task] and not cand[task] for task in base),
                      c=sum(not base[task] and cand[task] for task in base))
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as error:
        report["errors"].append(str(error))
    report["eligible_for_steward_review"] = bool(report["c"] >= 5 and report["b"] == 0)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipts", type=Path)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args(argv)
    report = verify_skill_lift(args.receipts, args.repo)
    print(json.dumps(report, sort_keys=True))
    return int(bool(report["errors"]) or not report["eligible_for_steward_review"])


if __name__ == "__main__":
    raise SystemExit(main())

---
slug: "harvest-h002-l19"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-ship", dst_type: "skill"}
---

# H002 — ship:friction

_git log — 49 commits, multiple 'Merge Track X' commits_

**Source skill:** `ship`

**Class:** friction

**Ref:** git log — 49 commits, multiple 'Merge Track X' commits

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi has no pull requests — it commits to main and integrates parallel work via 'git merge --no-ff worktree-X'. ship's procedure step 5 ('Open / update the PR') assumes a PR-based flow this project does not use.

**Plan candidate:** ship: make the PR step optional — support a commit-to-main / merge-worktree integration flow as a first-class alternative.

## Links

- **about** → `skill-ship` (skill)

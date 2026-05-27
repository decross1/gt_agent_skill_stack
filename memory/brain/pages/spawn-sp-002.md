---
slug: "spawn-sp-002"
type: "spawn"
date: "2026-05-25"
source: "run_state/spawn.jsonl"
edges:
  - {type: uses, dst: "skill-validate", dst_type: "skill"}
  - {type: uses, dst: "skill-run-log", dst_type: "skill"}
---

# SP-002 — sp_002_skill_frontmatter_audit

_status: completed_

**Status:** `completed`

**Parent task:** `s22_3_real_spawn_launch`

**Child task:** `sp_002_skill_frontmatter_audit`

**Task statement:** For every directory under /home/decross1/projects/agent_system/.agents/skills/, read SKILL.md, parse YAML frontmatter, and return a structured JSON summary of skill metadata.

**Done condition:** Returned text contains a JSON object with keys: total (int), skills (list of objects each with name:str + layer:str + runtime_safe:bool + description_present:bool), non_conformant (list, may be empty). total equals the actual count of skill directories. Every skill object has layer in {A,B,C} and runtime_safe a real bool. non_conformant lists any skill missing required frontmatter fields or with invalid layer/runtime-safe values.

**Skill subset:** `validate`, `run-log`

**Authority cap:** Read-only on /home/decross1/projects/agent_system/.agents/skills/. No writes anywhere (parent will append SP-002 completed entry to spawn.jsonl). No network. No shell command that mutates state (rm/mv/sed -i/edit/write all forbidden); ls/cat/head/grep/python -c read-only fine. Belt-and-suspenders: spawned in worktree isolation so mutations are physically sandboxed.

**Budget:** wall_time=300s iterations=None cost_usd=None

**Done condition check:** `pass`

**Child summary:** {"total":18,"skills":[{"name":"auto-experiment","layer":"B","runtime_safe":false,"description_present":true},{"name":"code-review","layer":"B","runtime_safe":false,"description_present":true},{"name":"context-restore","layer":"C","runtime_safe":false,"description_present":true},{"name":"context-save","layer":"C","runtime_safe":false,"description_present":true},{"name":"decision-log","layer":"C","r

## Links

- **uses** → `skill-validate` (skill)
- **uses** → `skill-run-log` (skill)

---
slug: "runlog-day-1-day1-block2-nemoclaw-fallback-l26"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:26"
---

# a_bgt_rsi: Nara — week1.run L26

_stdout 'fallback ok', exit 0_

**Did:** hardened plain-Docker sandbox verified — docker run with --security-opt seccomp=infra/seccomp/default.json (moby v24.0.9 default profile, 31 syscall rules), --security-opt no-new-privileges, --cap-drop=ALL on alpine:latest printed 'fallback…

**Observed:** status=passed day=day_1 duration_ms=0 fallback=None

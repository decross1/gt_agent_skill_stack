---
slug: "runlog-day-1-day1-block2-docker-config-l13"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:13"
---

# a_bgt_rsi: Nara — week1.run L13

_docker info shows host cgroup; root crontab has drop_caches entry_

**Did:** docker restart failed — dockerd rejected /etc/docker/daemon.json: invalid directive 'cgroupns' (plan command bug; valid key is 'default-cgroupns-mode'). docker.service in failed state, restart-throttled. drop_caches cron was added successfu…

**Observed:** status=failed day=day_1 duration_ms=0 fallback=None

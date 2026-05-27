---
slug: "runlog-day-4-day4-block2-wrapper-tools-l71"
type: "run_log_entry"
date: "2026-05-20"
source: "week1.run.jsonl:71"
---

# a_bgt_rsi: Nara — week1.run L71

_function signature enforces max_depth<=3 default; malformed JSON surfaced (logged + raised); no silent retry_

**Did:** agent_wrapper/wrapper.py extended with call_with_tools(messages, tools, ..., max_depth=3). tools format: [{spec: <openai-function-schema>, impl: callable}]. Loop: send with tools=, log record (parent_request_id linked), if tool_calls empty …

**Observed:** status=passed day=day_4 duration_ms=0 fallback=None

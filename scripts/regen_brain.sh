#!/usr/bin/env bash
# regen_brain.sh — rebuild ALL generated brain projections from the canonical ledgers.
#
# The brain's view projections are deterministic build artifacts, NOT source, and
# are git-ignored (P-013 resolution, DECISIONS 2026-06-15):
#   - memory/brain/pages/*.md              (project_pages.py)
#   - memory/brain/view/map_data.js        (project_map.py)
#   - memory/brain/view/summary.json + summary_data.js + index.json  (project_summary.py)
#   - memory/brain/view/<YYYY-MM-DD>.md    (render_brain.py, one per UTC day in the ledgers)
#
# The CANONICAL sources stay tracked: the ledgers (narratives/edges/proposals/feedback/
# run logs/DECISIONS), the projector scripts, and the hand-written view assets
# (*.html, map.js, ui.js, tokens.css, mockups/). This script is the single command that
# rebuilds the projections — run it after a fresh checkout, or let watch_brain.py keep
# them live. The watch daemon runs the same four steps on each change.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "[regen_brain] project_pages..."   ; python3 scripts/project_pages.py   >/dev/null
echo "[regen_brain] project_map..."     ; python3 scripts/project_map.py      >/dev/null
echo "[regen_brain] project_summary..." ; python3 scripts/project_summary.py  >/dev/null

# Per-day views: render every UTC day that appears in the ledgers.
days="$(python3 - <<'PY'
import json, re, pathlib
days = set()
for f in ("run_state/framework.run.jsonl", "memory/brain/narratives.jsonl",
          "memory/feedback.jsonl"):
    p = pathlib.Path(f)
    if not p.exists():
        continue
    for line in p.read_text().splitlines():
        m = re.search(r'"(?:timestamp|date)"\s*:\s*"(\d{4}-\d{2}-\d{2})', line)
        if m:
            days.add(m.group(1))
print("\n".join(sorted(days)))
PY
)"
n=0
for d in $days; do
  python3 scripts/render_brain.py --day "$d" >/dev/null 2>&1 || echo "  warn: render $d failed" >&2
  n=$((n + 1))
done
echo "[regen_brain] done — ${n} per-day views rebuilt. Projections are git-ignored build artifacts."

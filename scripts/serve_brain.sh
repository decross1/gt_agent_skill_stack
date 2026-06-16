#!/usr/bin/env bash
# serve_brain.sh — start/stop/status the brain backend HTTP server.
#
# Launches the DYNAMIC brain backend (scripts/brain_server.py): it serves the
# static view dir (dashboard.html, graph.html, proposal_review.html, per-day
# views) AND a small JSON API that makes proposal review conversational. It
# replaces the old plain `python3 -m http.server`, which only served static
# files; the dynamic server is a superset (static + /api/*).
#
# Wraps the server with a pidfile + log + safe defaults so it survives terminal
# disconnects (good for headless boxes) and can be stopped cleanly. No daemon
# framework, no systemd unit — just a process and a pidfile.
#
# Defaults to bind 0.0.0.0 (LAN-reachable) so the dynamic brain is accessible from
# the user's other machines on a trusted home LAN without a per-start override.
# Re-restrict to loopback with BRAIN_BIND=127.0.0.1 (env) or --bind 127.0.0.1.
# The write-back API only POSTs to blessed, frozen-enum, argv-only CLIs stamped
# human:ui (D-046), so it cannot be coerced into arbitrary writes; broader/public
# network exposure beyond the trusted LAN remains the user's call.
#
# The proposal-review loop's discussion/card features call a local Gemma server
# (http://127.0.0.1:8000); `start` runs a non-fatal preflight and warns if it is
# unreachable. The static view + the blessed verdict CLI work without Gemma.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER="$REPO/scripts/brain_server.py"
VIEW_DIR="$REPO/memory/brain/view"
PIDFILE="${BRAIN_PIDFILE:-$REPO/run_state/brain-http.pid}"
LOGFILE="${BRAIN_LOGFILE:-$REPO/run_state/brain-http.log}"
PORT="${BRAIN_PORT:-5180}"
BIND="${BRAIN_BIND:-0.0.0.0}"
GEMMA_URL="${GEMMA_URL:-http://127.0.0.1:8000}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [start|stop|restart|status|tail|url] [--port N] [--bind ADDR]

Launches the dynamic brain backend ($SERVER): serves $VIEW_DIR over HTTP —
dashboard.html (status strip + needs-you inbox), graph.html (agent↔skill cluster
map), proposal_review.html (conversational proposal review), and the per-day
views — plus a JSON API under /api/* for the proposal-review loop.

Commands:
  start     start in background, write pidfile (preflights Gemma, warn-only)
  stop      stop running server (uses pidfile)
  restart   stop then start
  status    print state (running pid + url, or stopped)
  tail      tail -F the log
  url       print the URL (handy for: open \$($(basename "$0") url))

Configurable via env or flags:
  BRAIN_PORT=$PORT       --port N
  BRAIN_BIND=$BIND       --bind ADDR   (use 0.0.0.0 to expose on LAN)
  BRAIN_PIDFILE=$PIDFILE
  BRAIN_LOGFILE=$LOGFILE
  GEMMA_URL=$GEMMA_URL   (preflighted at <url>/v1/models; warn-only)

Examples:
  $(basename "$0") start                       # 0.0.0.0:5180 (LAN-accessible)
  BRAIN_BIND=127.0.0.1 $(basename "$0") start  # loopback only
  $(basename "$0") status
  $(basename "$0") stop
EOF
}

cmd="${1:-status}"
[[ $# -gt 0 ]] && shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --bind) BIND="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

is_running() {
  [[ -f "$PIDFILE" ]] || return 1
  local pid; pid=$(cat "$PIDFILE" 2>/dev/null || true)
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

url() { echo "http://$BIND:$PORT/proposal_review.html"; }

# Non-fatal preflight: the discussion/card API needs Gemma, but the static view
# and the blessed verdict CLI do not. Warn, never block.
preflight_gemma() {
  if curl -s -m 3 "$GEMMA_URL/v1/models" >/dev/null 2>&1; then
    echo "  gemma: reachable at $GEMMA_URL"
  else
    echo "  warn: gemma not reachable at $GEMMA_URL/v1/models — discussion & card" >&2
    echo "        generation will be unavailable; static view + verdict CLI still work." >&2
  fi
}

cmd_start() {
  if is_running; then
    echo "already running (pid $(cat "$PIDFILE")) — $(url)"
    return 0
  fi
  [[ -f "$SERVER" ]] || { echo "error: backend not found: $SERVER" >&2; exit 1; }
  [[ -d "$VIEW_DIR" ]] || { echo "error: view dir not found: $VIEW_DIR" >&2; exit 1; }
  [[ -f "$VIEW_DIR/proposal_review.html" ]] || { echo "warn: $VIEW_DIR/proposal_review.html missing — the view pages are tracked static assets; check your checkout" >&2; }
  preflight_gemma
  mkdir -p "$(dirname "$PIDFILE")" "$(dirname "$LOGFILE")"
  rm -f "$PIDFILE"
  {
    echo "[$(date -Iseconds)] starting brain_server.py on $BIND:$PORT serving $VIEW_DIR + /api/*"
  } >> "$LOGFILE"
  # nohup keeps it alive past terminal close; setsid would also work
  nohup python3 "$SERVER" --port "$PORT" --host "$BIND" \
    >> "$LOGFILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PIDFILE"
  # Give the server a moment to bind; then verify it's alive
  sleep 0.4
  if is_running; then
    echo "started (pid $pid) — $(url)"
    echo "  log: $LOGFILE"
  else
    echo "failed to start — see $LOGFILE" >&2
    rm -f "$PIDFILE"
    tail -n 5 "$LOGFILE" >&2 || true
    exit 1
  fi
}

cmd_stop() {
  if ! is_running; then
    echo "not running"
    rm -f "$PIDFILE"
    return 0
  fi
  local pid; pid=$(cat "$PIDFILE")
  kill "$pid" 2>/dev/null || true
  # Up to ~2s for graceful exit, then SIGKILL
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 0.2
    kill -0 "$pid" 2>/dev/null || break
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
    echo "killed (SIGKILL after grace) pid $pid"
  else
    echo "stopped (pid $pid)"
  fi
  rm -f "$PIDFILE"
}

cmd_status() {
  if is_running; then
    local pid; pid=$(cat "$PIDFILE")
    echo "running (pid $pid)"
    echo "  url: $(url)"
    echo "  log: $LOGFILE"
  else
    echo "stopped"
    [[ -f "$PIDFILE" ]] && echo "  (stale pidfile present — will be cleared on next start)"
  fi
}

cmd_tail() {
  [[ -f "$LOGFILE" ]] || { echo "no log yet: $LOGFILE" >&2; exit 1; }
  exec tail -F "$LOGFILE"
}

case "$cmd" in
  start)        cmd_start ;;
  stop)         cmd_stop ;;
  restart)      cmd_stop; cmd_start ;;
  status)       cmd_status ;;
  tail)         cmd_tail ;;
  url)          url ;;
  -h|--help|help) usage ;;
  *) echo "unknown command: $cmd" >&2; usage; exit 2 ;;
esac

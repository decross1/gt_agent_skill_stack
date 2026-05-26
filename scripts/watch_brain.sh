#!/usr/bin/env bash
# watch_brain.sh — start/stop/status the brain auto-ingest watcher.
#
# Mirrors serve_brain.sh's lifecycle pattern: pidfile + log + nohup. Wraps
# scripts/watch_brain.py so the file-change watcher survives terminal close
# on headless boxes (e.g. the DGX Spark) and can be managed cleanly.
#
# The watcher polls a_bgt_rsi/{run_state,memory,logs} for *.jsonl changes and
# runs ingest_apparatus.py → project_pages.py → render_brain.py on debounce.
# Apparatus is read-only from the watcher's perspective — brain firewall intact.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WATCHER="$REPO/scripts/watch_brain.py"
PIDFILE="${BRAIN_WATCH_PIDFILE:-$REPO/run_state/brain-watch.pid}"
LOGFILE="${BRAIN_WATCH_LOGFILE:-$REPO/run_state/brain-watch.log}"
INTERVAL="${BRAIN_WATCH_INTERVAL:-1.0}"
DEBOUNCE="${BRAIN_WATCH_DEBOUNCE:-1.5}"
VERBOSE="${BRAIN_WATCH_VERBOSE:-0}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [start|stop|restart|status|tail|once] [--interval N] [--debounce N] [--verbose]

Watches a_bgt_rsi/{run_state,memory,logs}/*.jsonl and runs the brain
ingest→project→render pipeline on debounce.

Commands:
  start     start in background, write pidfile
  stop      stop running watcher (uses pidfile)
  restart   stop then start
  status    print state (running pid + last log lines, or stopped)
  tail      tail -F the log
  once      run the pipeline once and exit (no daemon)

Configurable via env or flags:
  BRAIN_WATCH_INTERVAL=$INTERVAL   --interval N    poll period (seconds)
  BRAIN_WATCH_DEBOUNCE=$DEBOUNCE   --debounce N    quiet period before fire
  BRAIN_WATCH_VERBOSE=$VERBOSE     --verbose       log every step's tail
  BRAIN_WATCH_PIDFILE=$PIDFILE
  BRAIN_WATCH_LOGFILE=$LOGFILE

Examples:
  $(basename "$0") start
  $(basename "$0") status
  $(basename "$0") tail
  $(basename "$0") once          # one-shot, no daemon
EOF
}

cmd="${1:-status}"
[[ $# -gt 0 ]] && shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --interval) INTERVAL="$2"; shift 2 ;;
    --debounce) DEBOUNCE="$2"; shift 2 ;;
    --verbose)  VERBOSE=1; shift ;;
    -h|--help)  usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

is_running() {
  [[ -f "$PIDFILE" ]] || return 1
  local pid; pid=$(cat "$PIDFILE" 2>/dev/null || true)
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

watcher_args() {
  local args=(--interval "$INTERVAL" --debounce "$DEBOUNCE")
  [[ "$VERBOSE" == "1" ]] && args+=(--verbose)
  printf '%s\n' "${args[@]}"
}

cmd_start() {
  if is_running; then
    echo "already running (pid $(cat "$PIDFILE"))"
    return 0
  fi
  [[ -f "$WATCHER" ]] || { echo "error: watcher script missing: $WATCHER" >&2; exit 1; }
  mkdir -p "$(dirname "$PIDFILE")" "$(dirname "$LOGFILE")"
  rm -f "$PIDFILE"
  {
    echo "[$(date -Iseconds)] starting watch_brain.py interval=${INTERVAL}s debounce=${DEBOUNCE}s verbose=${VERBOSE}"
  } >> "$LOGFILE"
  mapfile -t args < <(watcher_args)
  nohup python3 -u "$WATCHER" "${args[@]}" >> "$LOGFILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PIDFILE"
  sleep 0.4
  if is_running; then
    echo "started (pid $pid)"
    echo "  log: $LOGFILE"
  else
    echo "failed to start — see $LOGFILE" >&2
    rm -f "$PIDFILE"
    tail -n 10 "$LOGFILE" >&2 || true
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
    echo "  log: $LOGFILE"
    if [[ -f "$LOGFILE" ]]; then
      echo "  last 3 log lines:"
      tail -n 3 "$LOGFILE" | sed 's/^/    /'
    fi
  else
    echo "stopped"
    [[ -f "$PIDFILE" ]] && echo "  (stale pidfile present — will be cleared on next start)"
  fi
}

cmd_tail() {
  [[ -f "$LOGFILE" ]] || { echo "no log yet: $LOGFILE" >&2; exit 1; }
  exec tail -F "$LOGFILE"
}

cmd_once() {
  [[ -f "$WATCHER" ]] || { echo "error: watcher script missing: $WATCHER" >&2; exit 1; }
  exec python3 "$WATCHER" --once --verbose
}

case "$cmd" in
  start)        cmd_start ;;
  stop)         cmd_stop ;;
  restart)      cmd_stop; cmd_start ;;
  status)       cmd_status ;;
  tail)         cmd_tail ;;
  once)         cmd_once ;;
  -h|--help|help) usage ;;
  *) echo "unknown command: $cmd" >&2; usage; exit 2 ;;
esac

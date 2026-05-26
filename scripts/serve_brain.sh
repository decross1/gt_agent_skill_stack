#!/usr/bin/env bash
# serve_brain.sh — start/stop/status the brain graph HTTP server.
#
# Wraps `python3 -m http.server` with a pidfile + log + safe defaults so the
# server survives terminal disconnects (good for headless boxes) and can be
# stopped cleanly. No daemon framework, no systemd unit — just a process and
# a pidfile.
#
# Defaults to bind 127.0.0.1 (loopback only). Override via BRAIN_BIND env or
# --bind flag for LAN exposure. Public network exposure is the user's call.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIEW_DIR="$REPO/memory/brain/view"
PIDFILE="${BRAIN_PIDFILE:-$REPO/run_state/brain-http.pid}"
LOGFILE="${BRAIN_LOGFILE:-$REPO/run_state/brain-http.log}"
PORT="${BRAIN_PORT:-5174}"
BIND="${BRAIN_BIND:-127.0.0.1}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [start|stop|restart|status|tail|url] [--port N] [--bind ADDR]

Serves $VIEW_DIR over plain HTTP for graph.html and the per-day views.

Commands:
  start     start in background, write pidfile
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

Examples:
  $(basename "$0") start                       # 127.0.0.1:5174
  BRAIN_BIND=0.0.0.0 $(basename "$0") start    # LAN-accessible
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

url() { echo "http://$BIND:$PORT/graph.html"; }

cmd_start() {
  if is_running; then
    echo "already running (pid $(cat "$PIDFILE")) — $(url)"
    return 0
  fi
  [[ -d "$VIEW_DIR" ]] || { echo "error: view dir not found: $VIEW_DIR" >&2; exit 1; }
  [[ -f "$VIEW_DIR/graph.html" ]] || { echo "warn: $VIEW_DIR/graph.html missing — run scripts/project_pages.py first" >&2; }
  mkdir -p "$(dirname "$PIDFILE")" "$(dirname "$LOGFILE")"
  rm -f "$PIDFILE"
  {
    echo "[$(date -Iseconds)] starting http.server on $BIND:$PORT serving $VIEW_DIR"
  } >> "$LOGFILE"
  # nohup keeps it alive past terminal close; setsid would also work
  nohup python3 -m http.server "$PORT" --bind "$BIND" --directory "$VIEW_DIR" \
    >> "$LOGFILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PIDFILE"
  # Give python a moment to bind; then verify it's alive
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

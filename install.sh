#!/usr/bin/env bash
# install.sh — wire this agent system into Pi and/or Claude Code.
#
# The canonical source of truth is this repo:
#   .agents/skills/   the skills (Agent Skills standard)
#   AGENTS.md         the context file
# Both harnesses read those directly or via the symlinks created below.
# Nothing is copied or duplicated — edit the originals, both harnesses follow.
#
# Usage:
#   ./install.sh            project-local: makes this repo usable in place
#   ./install.sh --global   also exposes the skills to every project on this machine
#   ./install.sh --uninstall remove symlinks this script created
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS="$ROOT/.agents/skills"
AGENT_PROFILES="$ROOT/.agents/agents"
MODE="${1:-local}"

# Create symlink $2 -> $1 only if it is absent or already a symlink (never clobber real files).
link() {
  local target="$1" linkpath="$2"
  if [[ -e "$linkpath" && ! -L "$linkpath" ]]; then
    echo "  skip   $linkpath (exists, not a symlink — leaving it alone)"
    return
  fi
  rm -f "$linkpath"
  ln -s "$target" "$linkpath"
  echo "  link   $linkpath -> $target"
}

unlink_if_ours() {
  local linkpath="$1"
  if [[ -L "$linkpath" ]]; then rm -f "$linkpath" && echo "  unlink $linkpath"; fi
}

install_local() {
  echo "Project-local setup:"
  # Pi reads AGENTS.md + .agents/skills/ natively. Bridge the Claude Code names.
  link "$ROOT/AGENTS.md" "$ROOT/CLAUDE.md"
  mkdir -p "$ROOT/.claude"
  link "$SKILLS" "$ROOT/.claude/skills"
  link "$AGENT_PROFILES" "$ROOT/.claude/agents"
  echo "Done. Pi and Claude Code both see the skills + context from this repo."
}

install_global() {
  echo "Global setup (skills available in every project on this machine):"
  local cc="$HOME/.claude/skills" pi="$HOME/.pi/agent/skills"
  mkdir -p "$cc" "$pi"
  for d in "$SKILLS"/*/; do
    local name; name="$(basename "$d")"
    link "$d" "$cc/$name"
    link "$d" "$pi/$name"
  done
  # Agent profiles — Claude Code reads ~/.claude/agents/. (Pi subagent wiring is
  # harness-version-specific; see BOUNDARY.md — left as a manual step.)
  local cca="$HOME/.claude/agents"
  mkdir -p "$cca"
  for f in "$AGENT_PROFILES"/*.md; do
    [ -e "$f" ] || continue
    link "$f" "$cca/$(basename "$f")"
  done
  echo "Done. Skills + agent profiles installed globally for Claude Code; skills for Pi."
}

uninstall() {
  echo "Removing symlinks created by this script:"
  unlink_if_ours "$ROOT/CLAUDE.md"
  unlink_if_ours "$ROOT/.claude/skills"
  unlink_if_ours "$ROOT/.claude/agents"
  for d in "$SKILLS"/*/; do
    local name; name="$(basename "$d")"
    unlink_if_ours "$HOME/.claude/skills/$name"
    unlink_if_ours "$HOME/.pi/agent/skills/$name"
  done
  for f in "$AGENT_PROFILES"/*.md; do
    [ -e "$f" ] || continue
    unlink_if_ours "$HOME/.claude/agents/$(basename "$f")"
  done
  echo "Done."
}

case "$MODE" in
  local)      install_local ;;
  --global)   install_local; echo; install_global ;;
  --uninstall) uninstall ;;
  *) echo "Usage: ./install.sh [--global|--uninstall]" >&2; exit 1 ;;
esac

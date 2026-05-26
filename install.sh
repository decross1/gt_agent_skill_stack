#!/usr/bin/env bash
# install.sh — install this agent framework into one or more skill-discovery
# targets (Claude Code, Pi, or any directory a harness reads from).
#
# Source of truth in this repo:
#   .agents/skills/   the skills (Agent Skills standard, one dir per skill)
#   .agents/agents/   agent profiles (for harnesses that consume them)
#   AGENTS.md         the framework's stable context
# All installs are symlinks — edit originals, every target follows.
#
# Registered targets (the manifest, defined as bash assoc arrays below):
#   claude-code   path=~/.claude/skills          filter=all          agents=~/.claude/agents
#   pi            path=~/.pi/agent/skills        filter=runtime-safe agents=(none)
#
# Filters:
#   all           install every skill regardless of frontmatter
#   runtime-safe  install only skills with `runtime-safe: true` in frontmatter
#                  (enforced via grep on SKILL.md; see BOUNDARY.md)
#
# Usage:
#   ./install.sh                              project-local only (in-place repo)
#   ./install.sh --global                     = --target claude-code (back-compat)
#   ./install.sh --global-pi                  = claude-code + pi (back-compat)
#   ./install.sh --target NAME                install to a registered target
#   ./install.sh --target-path PATH \         install to an arbitrary directory
#                  [--filter all|runtime-safe]   (default filter: runtime-safe)
#   ./install.sh --list-targets               print the target manifest
#   ./install.sh --list-packs                 print the skill packs (from SKILL.md frontmatter)
#   ./install.sh --verify-firewall [NAME]     verify a runtime-safe target's
#                                              filter is held (default NAME: pi)
#   ./install.sh --uninstall                  remove every symlink we created in
#                                              local + every registered target
#
# To register a new target, add an entry to the three TARGET_* arrays below.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS="$ROOT/.agents/skills"
AGENT_PROFILES="$ROOT/.agents/agents"

# ── target manifest ──────────────────────────────────────────────────────────
declare -A TARGET_PATHS=(
  [claude-code]="$HOME/.claude/skills"
  [pi]="$HOME/.pi/agent/skills"
)
declare -A TARGET_FILTERS=(
  [claude-code]="all"
  [pi]="runtime-safe"
)
declare -A TARGET_AGENT_DIRS=(
  [claude-code]="$HOME/.claude/agents"
  [pi]=""
)

# ── primitives ───────────────────────────────────────────────────────────────
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

matches_filter() {
  local skill_md="$1" filter="$2"
  case "$filter" in
    all)          return 0 ;;
    runtime-safe) grep -q '^runtime-safe: *true' "$skill_md" ;;
    *)            echo "error: unknown filter '$filter'" >&2; return 2 ;;
  esac
}

# ── installers ───────────────────────────────────────────────────────────────
install_local() {
  echo "Project-local setup:"
  link "$ROOT/AGENTS.md" "$ROOT/CLAUDE.md"
  mkdir -p "$ROOT/.claude"
  link "$SKILLS" "$ROOT/.claude/skills"
  link "$AGENT_PROFILES" "$ROOT/.claude/agents"
  echo "Done. Project-local bridges in place."
}

# install_target_path PATH FILTER [AGENTS_DIR]
install_target_path() {
  local path="$1" filter="$2" agents_dir="${3:-}"
  echo "Installing skills into $path  (filter: $filter)"
  mkdir -p "$path"
  local installed=0 filtered=0 skipped=0
  for d in "$SKILLS"/*/; do
    local name; name="$(basename "$d")"
    local skill_md="$d/SKILL.md"
    if [[ ! -f "$skill_md" ]]; then
      echo "  skip       $name (no SKILL.md)"
      skipped=$((skipped+1))
      continue
    fi
    if matches_filter "$skill_md" "$filter"; then
      link "$d" "$path/$name"
      installed=$((installed+1))
    else
      echo "  filtered   $name (does not match '$filter')"
      # Clean any pre-existing symlink so the filter is enforced *now*.
      if [[ -L "$path/$name" ]]; then
        rm -f "$path/$name"
        echo "             removed pre-existing symlink at $path/$name"
      fi
      filtered=$((filtered+1))
    fi
  done
  echo "  → $installed installed, $filtered filtered out, $skipped skipped"
  # Agent profiles (only when the target advertises an agents dir)
  if [[ -n "$agents_dir" ]]; then
    echo "Installing agent profiles into $agents_dir"
    mkdir -p "$agents_dir"
    for f in "$AGENT_PROFILES"/*.md; do
      [ -e "$f" ] || continue
      link "$f" "$agents_dir/$(basename "$f")"
    done
  fi
}

install_target() {
  local name="$1"
  if [[ -z "${TARGET_PATHS[$name]:-}" ]]; then
    echo "error: unknown target '$name'. Known: ${!TARGET_PATHS[*]}" >&2
    echo "       Use --target-path to install to an arbitrary directory." >&2
    return 2
  fi
  install_target_path "${TARGET_PATHS[$name]}" "${TARGET_FILTERS[$name]}" "${TARGET_AGENT_DIRS[$name]}"
}

# ── verifier ─────────────────────────────────────────────────────────────────
verify_firewall() {
  local name="${1:-pi}"
  if [[ -z "${TARGET_PATHS[$name]:-}" ]]; then
    echo "error: unknown target '$name'. Known: ${!TARGET_PATHS[*]}" >&2
    return 2
  fi
  local path="${TARGET_PATHS[$name]}"
  local filter="${TARGET_FILTERS[$name]}"
  echo "Verifying $path  (target=$name, filter=$filter)"
  if [[ "$filter" == "all" ]]; then
    echo "  (filter is 'all' — nothing to enforce; trivially intact)"
    return 0
  fi
  if [[ ! -d "$path" ]]; then
    echo "  ($path does not exist — nothing installed yet; firewall vacuously held)"
    return 0
  fi
  local violations=0
  for lnk in "$path"/*; do
    [[ -L "$lnk" ]] || continue
    local pname; pname="$(basename "$lnk")"
    local target; target="$(readlink -f "$lnk" 2>/dev/null || true)"
    local skill_md="$target/SKILL.md"
    if [[ ! -f "$skill_md" ]]; then
      echo "  unknown    $pname (target has no SKILL.md — manual review needed)"
      continue
    fi
    if matches_filter "$skill_md" "$filter"; then
      echo "  ok         $pname"
    else
      echo "  VIOLATION  $pname (does not match '$filter' filter)"
      violations=$((violations+1))
    fi
  done
  if [[ $violations -eq 0 ]]; then
    echo "  ✓ firewall intact"
    return 0
  fi
  echo "  ✗ $violations violation(s). Run: ./install.sh --uninstall && ./install.sh --target $name"
  return 1
}

# ── list / uninstall ─────────────────────────────────────────────────────────
list_targets() {
  printf "Registered targets:\n"
  printf "  %-14s %-34s %-14s %s\n" "name" "path" "filter" "agents-dir"
  printf "  %-14s %-34s %-14s %s\n" "----" "----" "------" "----------"
  for n in $(echo "${!TARGET_PATHS[@]}" | tr ' ' '\n' | sort); do
    printf "  %-14s %-34s %-14s %s\n" \
      "$n" "${TARGET_PATHS[$n]}" "${TARGET_FILTERS[$n]}" "${TARGET_AGENT_DIRS[$n]:-(none)}"
  done
  echo ""
  echo "Ad-hoc install: ./install.sh --target-path PATH [--filter all|runtime-safe]"
}

list_packs() {
  # Walk every SKILL.md, group by `pack:` frontmatter value.
  echo "Skill packs (derived from each SKILL.md's 'pack:' frontmatter):"
  echo ""
  # Build name -> pack mapping
  declare -A name_pack
  for d in "$SKILLS"/*/; do
    local name; name="$(basename "$d")"
    local skill_md="$d/SKILL.md"
    [[ -f "$skill_md" ]] || continue
    local pack; pack="$(grep -E '^pack:' "$skill_md" | head -1 | awk '{print $2}')"
    name_pack["$name"]="${pack:-(unset)}"
  done
  # Collect unique packs
  declare -A pack_seen
  for n in "${!name_pack[@]}"; do pack_seen["${name_pack[$n]}"]=1; done
  # Print each pack with its members
  for pack in $(echo "${!pack_seen[@]}" | tr ' ' '\n' | sort); do
    local members=()
    for n in $(echo "${!name_pack[@]}" | tr ' ' '\n' | sort); do
      [[ "${name_pack[$n]}" == "$pack" ]] && members+=("$n")
    done
    printf "  pack=%-10s count=%d\n" "$pack" "${#members[@]}"
    for m in "${members[@]}"; do
      printf "    - %s\n" "$m"
    done
  done
  echo ""
  echo "See .agents/PACKS.md for purpose, opt-in semantics, and how to add a new pack."
}

uninstall() {
  echo "Removing symlinks created by this script:"
  unlink_if_ours "$ROOT/CLAUDE.md"
  unlink_if_ours "$ROOT/.claude/skills"
  unlink_if_ours "$ROOT/.claude/agents"
  # Walk every known target path and unlink any skill symlinks we placed there.
  for n in "${!TARGET_PATHS[@]}"; do
    local path="${TARGET_PATHS[$n]}"
    for d in "$SKILLS"/*/; do
      unlink_if_ours "$path/$(basename "$d")"
    done
  done
  # Agent profiles, per target
  for n in "${!TARGET_AGENT_DIRS[@]}"; do
    local agdir="${TARGET_AGENT_DIRS[$n]}"
    [[ -z "$agdir" ]] && continue
    for f in "$AGENT_PROFILES"/*.md; do
      [ -e "$f" ] || continue
      unlink_if_ours "$agdir/$(basename "$f")"
    done
  done
  echo "Note: ad-hoc --target-path installs are not tracked here — clean those manually."
  echo "Done."
}

# ── flag parsing ─────────────────────────────────────────────────────────────
MODE="${1:-local}"
shift || true

TARGET=""
TARGET_PATH=""
FILTER="runtime-safe"

# First positional after MODE (when it doesn't start with --) is the target
# name or path, depending on MODE.
if [[ "${1:-}" != "" && "${1:-}" != --* ]]; then
  case "$MODE" in
    --target|--verify-firewall) TARGET="$1"; shift ;;
    --target-path)              TARGET_PATH="$1"; shift ;;
  esac
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)      TARGET="$2"; shift 2 ;;
    --target-path) TARGET_PATH="$2"; shift 2 ;;
    --filter)      FILTER="$2"; shift 2 ;;
    *)             echo "error: unknown flag '$1'" >&2; exit 2 ;;
  esac
done

usage() {
  sed -n '1,32p' "${BASH_SOURCE[0]}"
  echo ""
  list_targets
}

case "$MODE" in
  local)
    install_local ;;
  --global)
    install_local; echo; install_target claude-code ;;
  --global-pi)
    install_local; echo; install_target claude-code; echo; install_target pi; echo; verify_firewall pi ;;
  --target)
    [[ -n "$TARGET" ]] || { echo "error: --target requires a name" >&2; exit 2; }
    install_local; echo; install_target "$TARGET"
    if [[ "${TARGET_FILTERS[$TARGET]:-}" == "runtime-safe" ]]; then
      echo; verify_firewall "$TARGET"
    fi ;;
  --target-path)
    [[ -n "$TARGET_PATH" ]] || { echo "error: --target-path requires a path" >&2; exit 2; }
    install_target_path "$TARGET_PATH" "$FILTER" ;;
  --list-targets)
    list_targets ;;
  --list-packs)
    list_packs ;;
  --verify-firewall)
    verify_firewall "${TARGET:-pi}" ;;
  --uninstall)
    uninstall ;;
  -h|--help|help)
    usage ;;
  *)
    echo "Usage: ./install.sh [local|--global|--global-pi|--target NAME|--target-path PATH [--filter F]|--list-targets|--list-packs|--verify-firewall [NAME]|--uninstall|--help]" >&2
    exit 1 ;;
esac

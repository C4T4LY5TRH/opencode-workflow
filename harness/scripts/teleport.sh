#!/usr/bin/env bash
# teleport - move this harness to another machine, byte for byte.
#
#   teleport.sh pack   [out.tar.gz]   create the portable bundle from THIS repo
#   teleport.sh unpack <bundle>       restore into a target repo dir
#   teleport.sh verify  <repo-dir>    check a restored repo before installing
#
# The bundle contains the git-tracked files of the workshop repo. It does NOT
# contain: the live install (~/.config/opencode), opencode's own state
# (~/.local/share/opencode), secrets, or the playwright browser cache.
# Those are reinstalled by install.sh on the target machine.
#
# Why not copy ~/.config/opencode?
#   - it holds machine-specific runtime state (heartbeats, session logs, last-run)
#   - opencode's own files (cli.json, service.json, themes, tui.json) live there
#     and belong to opencode, not to this harness
#   - copying it drags stale heartbeats that would make the bench lie
# The repo IS the source of truth. install.sh rebuilds the live copy.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }

need_git() { command -v git >/dev/null 2>&1 || die "git not found"; }

pack() {
  local out="${1:-$REPO/harness-teleport-$(date +%Y%m%d-%H%M%S).tar.gz}"
  local with_git=1
  case "${2:-}" in --no-git) with_git=0 ;; esac
  need_git
  cd "$REPO"
  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    die "$REPO is not a git repo (the bundle is built from tracked files)"
  fi

  local list
  list="$(mktemp)"
  trap 'rm -f "$list"' RETURN
  git ls-files -z > "$list"

  # include untracked-but-intentional docs (catches anything added but not committed)
  git ls-files -z --others --exclude-standard | while IFS= read -r -d '' f; do
    case "$f" in
      mini-projects/*) continue ;;   # project work stays out of the bundle
      .playwright-mcp/*) continue ;;
      harness-teleport-*) continue ;; # don't pack the bundle inside itself
      *) printf '%s\0' "$f" ;;
    esac
  done >> "$list"

  # .git carries the history -> the target repo is a real clone, not a folder of files
  if [ "$with_git" = 1 ] && [ -d .git ]; then
    printf '%s\0' ".git" >> "$list"
  fi

  tar -czf "$out" --null -T "$list"

  echo "bundle: $out"
  echo "size:   $(du -h "$out" | cut -f1)"
  echo "files:  $(tr '\0' '\n' < "$list" | grep -c .)"
  echo "git:    $([ "$with_git" = 1 ] && echo 'included (full history)' || echo 'excluded (--no-git)')"
  echo
  echo "NOW MOVE THIS FILE TO THE OTHER MACHINE, then run:"
  echo "  bash teleport.sh unpack $out"
  echo
  echo "On the target you also need:"
  echo "  1. opencode installed (same version: $(opencode --version 2>/dev/null || echo 'check'))"
  echo "  2. node + npx  (playwright MCP + snapshot.py)"
  echo "  3. python3     (bench.py, html2md.py)"
  echo "  4. npx playwright install chromium"
  echo "  5. opencode auth login  (only if you use a paid model)"
}

unpack() {
  local bundle="${1:-}"
  [ -n "$bundle" ] || die "usage: teleport.sh unpack <bundle.tar.gz>"
  [ -f "$bundle" ] || die "bundle not found: $bundle"
  local dest="${2:-$HOME/Projects/opencode}"
  case "$dest" in
    *"/.config/opencode"*) die "refusing to unpack into the live config dir" ;;
  esac
  mkdir -p "$dest"
  echo "unpacking into: $dest"
  tar -xzf "$bundle" -C "$dest"
  echo
  echo "unpacked. next:"
  echo "  cd $dest"
  echo "  bash harness/scripts/install.sh     # syncs to ~/.config/opencode + restarts service"
  echo "  bash ~/.config/opencode/scripts/bench.sh"
}

verify() {
  local dest="${1:-}"
  [ -n "$dest" ] || die "usage: teleport.sh verify <repo-dir>"
  [ -d "$dest" ] || die "not a directory: $dest"
  local fails=0
  check() {
    if [ -e "$dest/$1" ]; then echo "  [PASS] $1"; else echo "  [FAIL] missing: $1"; fails=$((fails+1)); fi
  }
  echo "verifying bundle contents in $dest"
  for f in \
    harness/AGENTS.md harness/opencode.json \
    harness/scripts/install.sh harness/scripts/bench.sh harness/scripts/bench.py \
    harness/scripts/new-project.sh harness/scripts/html2md.py harness/scripts/snapshot.py \
    harness/brain/rules/000-core.md harness/brain/CHANGELOG.md \
    harness/brain/prompts/010-output-contract.md \
    harness/skills/brain/SKILL.md \
    harness/plugins/safety-gate.ts harness/plugins/brain-log.ts harness/plugins/quiet-output.ts \
    mini-projects/_template/BRIEF.md mini-projects/_template/PLAN.md \
    AGENTS.md README.md HANDBOOK.md ; do
    check "$f"
  done
  local n_a n_c n_s n_p n_r
  n_a=$(ls -1 "$dest/harness/agents"/*.md 2>/dev/null | wc -l | tr -d ' ')
  n_c=$(ls -1 "$dest/harness/commands"/*.md 2>/dev/null | wc -l | tr -d ' ')
  n_s=$(ls -1d "$dest/harness/skills"/*/ 2>/dev/null | wc -l | tr -d ' ')
  n_p=$(ls -1 "$dest/harness/plugins"/*.ts 2>/dev/null | wc -l | tr -d ' ')
  n_r=$(ls -1 "$dest/harness/brain/rules"/*.md 2>/dev/null | wc -l | tr -d ' ')
  echo
  echo "  agents=$n_a (want 11)  commands=$n_c (want 17)  skills=$n_s (want 7)  plugins=$n_p (want 3)  rules=$n_r (want 8)"
  [ "$n_a" = 11 ] || { echo "  [FAIL] agent count"; fails=$((fails+1)); }
  [ "$n_c" = 17 ] || { echo "  [FAIL] command count"; fails=$((fails+1)); }
  [ "$n_s" = 7 ]  || { echo "  [FAIL] skill count"; fails=$((fails+1)); }
  [ "$n_p" = 3 ]  || { echo "  [FAIL] plugin count"; fails=$((fails+1)); }
  [ "$n_r" = 8 ]  || { echo "  [FAIL] rule count"; fails=$((fails+1)); }
  echo
  if [ "$fails" = 0 ]; then echo "BUNDLE OK - $dest is ready to install"; else echo "$fails PROBLEM(S)"; fi
  return $((fails > 0))
}

case "${1:-}" in
  pack)   shift; pack "$@" ;;
  unpack) shift; unpack "$@" ;;
  verify) shift; verify "$@" ;;
  *) echo "usage: teleport.sh {pack|unpack|verify} ..." >&2; exit 2 ;;
esac

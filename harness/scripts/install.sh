#!/usr/bin/env bash
# Install the harness into the global opencode config dir.
# Safe to re-run. Backups go to ONE place: $CONFIG/.backups/<timestamp>/
# (last 5 runs kept, older pruned). No .bak files next to live files.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC=""
for candidate in "$HERE/harness" "$HERE/.." "$HERE"; do
  if [ -d "$candidate/agents" ] && [ -d "$candidate/commands" ]; then SRC="$(cd "$candidate" && pwd)"; break; fi
done
if [ -z "$SRC" ]; then
  echo "ERROR: cannot find harness source (need agents/ + commands/) near $HERE" >&2; exit 1
fi

CONFIG="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUPS="$CONFIG/.backups"
WORKSPACE="$(cd "$HERE/../.." 2>/dev/null && pwd || echo "")"
KEEP=5

echo "harness source : $SRC"
echo "config target  : $CONFIG"
mkdir -p "$CONFIG" "$BACKUPS"

backup() {
  local f="$1"
  [ -e "$f" ] || return 0
  mkdir -p "$BACKUPS/$STAMP"
  cp -R "$f" "$BACKUPS/$STAMP/$(basename "$f")"
  echo "  backup: .backups/$STAMP/$(basename "$f")"
}

# one-time migration: legacy scattered <file>.bak-<stamp> files -> .backups/legacy-<stamp>/
legacy_found=0
for f in "$CONFIG"/*.bak-*; do
  [ -e "$f" ] || continue
  legacy_found=1
  mkdir -p "$BACKUPS/legacy-$STAMP"
  cp -R "$f" "$BACKUPS/legacy-$STAMP/$(basename "$f")"
  rm -f "$f"
done
[ "$legacy_found" = "1" ] && echo "  migrated legacy .bak-* files -> .backups/legacy-$STAMP/"

for d in agents commands skills plugins brain scripts; do
  if [ -d "$SRC/$d" ]; then
    mkdir -p "$CONFIG/$d"
    # remove files in CONFIG that no longer exist in SOURCE (stale cleanup)
    if [ -d "$CONFIG/$d" ]; then
      (cd "$CONFIG/$d" && find . -type f) | while read -r rel; do
        if [ ! -e "$SRC/$d/$rel" ]; then
          rm -f "$CONFIG/$d/$rel"
          echo "  removed stale: $d/$rel"
        fi
      done
    fi
    cp -R "$SRC/$d/." "$CONFIG/$d/"
    echo "  synced: $d/"
  fi
done

for f in opencode.json AGENTS.md; do
  if [ -f "$SRC/$f" ]; then
    backup "$CONFIG/$f"
    cp "$SRC/$f" "$CONFIG/$f"
    echo "  synced: $f"
  fi
done

# prune old backup runs, keep the last KEEP
# NOTE: `ls dir/*/` exits 1 when the glob matches nothing. Under `set -e` +
# `pipefail` that would kill the install on a FRESH machine (empty .backups/),
# before workspace.txt is written and before the service restarts.
# So: glob-safe listing, and never let the prune abort the install.
prune_backups() {
  local -a dirs=()
  local d
  for d in "$BACKUPS"/*/; do
    [ -d "$d" ] || continue
    dirs+=("$d")
  done
  [ "${#dirs[@]}" -gt "$KEEP" ] || return 0
  # newest first
  local sorted
  sorted="$(printf '%s\n' "${dirs[@]}" | sort -r)"
  printf '%s\n' "$sorted" | tail -n "+$((KEEP + 1))" | while read -r old; do
    [ -n "$old" ] || continue
    rm -rf "$old"
    echo "  pruned backup: $(basename "$old")"
  done
  return 0
}
prune_backups || echo "  (backup prune skipped)"

# workspace pointer for scripts that need to know where mini-projects live
if [ -n "$WORKSPACE" ] && [ -d "$WORKSPACE/mini-projects" ]; then
  echo "$WORKSPACE" > "$CONFIG/workspace.txt"
  echo "  workspace: $WORKSPACE"
fi

# opencode runs as a background service: config/plugin changes need a restart
if command -v opencode >/dev/null 2>&1; then
  echo "restarting opencode service (so new config/plugins load)..."
  opencode service restart >/dev/null 2>&1 || echo "  (service restart skipped - run it manually if needed)"
fi

echo
echo "installed. verify with:"
echo "  opencode debug agents"
echo "  opencode debug paths"
echo "  opencode debug config"
echo "  bash ~/.config/opencode/scripts/bench.sh"

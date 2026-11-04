#!/bin/bash
# Live mirror for a harness worktree (maintainer tool; opencode never runs it).
# A worktree nested in the main checkout would load the MAIN checkout's .opencode/ (opencode reads config from every
# parent folder), so every live run and the bench verdict happen in a sibling copy.
#
#   bash scripts/live-mirror.sh     -> prints the mirror path
#
# - rsync -a --delete of the worktree, without .git, .harness/, .gate-test-*, .superpowers/, apps/ (deployed apps),
#   mini-projects/* (but _template/). Excluded paths are also never deleted in the mirror, so its own .harness/,
#   apps and projects survive.
# - git init in the mirror if it has no repo of its own (opencode and the bench expect one).
# - the main checkout's mini-projects/git-course is copied ONCE (an existing mirror copy is never overwritten);
#   the main checkout is only read, never written.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE="$(cd "$HERE/.." && pwd)"
MIRROR="$HOME/Projects/opencode-v4-live"
MAIN="$HOME/Projects/opencode"

[ -f "$WORKTREE/.opencode/opencode.json" ] || { echo "live-mirror: $WORKTREE is not the harness worktree" >&2; exit 1; }
[ "$WORKTREE" != "$MIRROR" ] || { echo "live-mirror: refusing to mirror onto itself" >&2; exit 1; }

mkdir -p "$MIRROR"
# "/.git" without a trailing slash: in a worktree .git is a FILE (gitdir: <main>/.git/worktrees/...); copying it would
# make every git command in the mirror act on the real repo.
rsync -a --delete \
  --exclude '/.git' --exclude '/.harness/' --exclude '/.gate-test-*' --exclude '/.superpowers/' --exclude '/apps/' \
  --include '/mini-projects/_template/' --exclude '/mini-projects/*' \
  "$WORKTREE/" "$MIRROR/"

# A .git FILE in the mirror points at another repo: remove it so the mirror gets its own. A .git folder is kept.
if [ -f "$MIRROR/.git" ] && [ ! -L "$MIRROR/.git" ]; then rm -f "$MIRROR/.git"; fi
[ -e "$MIRROR/.git" ] || git -C "$MIRROR" init -q

if [ ! -e "$MIRROR/mini-projects/git-course" ] && [ -d "$MAIN/mini-projects/git-course" ]; then
  cp -Rp "$MAIN/mini-projects/git-course" "$MIRROR/mini-projects/git-course"
fi

echo "$MIRROR"

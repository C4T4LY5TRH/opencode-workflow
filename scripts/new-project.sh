#!/usr/bin/env bash
# Scaffold a new mini project from the workshop template.
# Purpose gate lives in the /new command, not here.
#
# usage:  new-project.sh - [slug] <<'END'   goal on stdin (what /new runs)
#    or:  GOAL="<one line goal>" new-project.sh [slug]
#    or:  new-project.sh "<goal>" [slug]
# Reading the goal from stdin or the GOAL env var means callers never build a
# shell string out of user text (AUDIT.md P2-1). /new passes it through a quoted
# heredoc, so quotes, $(...) and ; in a goal stay plain text.
#
# The template ships NO gate files (PLAN/SCOPE/REVIEW/BLIND). They appear only
# when their owning agent writes them, so the plan and ship gates mean something
# from the first minute (AUDIT.md P0-2).
set -euo pipefail

if [ "${1:-}" = "-" ]; then
  GOAL="$(head -n 1 | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
  SLUG="${2:-}"
elif [ -n "${GOAL:-}" ]; then
  SLUG="${1:-}"
else
  GOAL="${1:-}"
  SLUG="${2:-}"
fi

if [ -z "$GOAL" ]; then
  echo "usage: /new <one line goal>    (script: new-project.sh - [slug] <<< \"<goal>\")" >&2
  exit 2
fi

# workshop root = parent of this script's directory (project-local install)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$HERE/.." && pwd)"
PROJECTS="$WORKSPACE/mini-projects"
TEMPLATE="$PROJECTS/_template"

if [ ! -d "$TEMPLATE" ]; then
  echo "ERROR: template not found: $TEMPLATE" >&2
  exit 1
fi

if [ -z "$SLUG" ]; then
  SLUG="$(printf '%s' "$GOAL" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -d- -f1-5)"
fi
[ -z "$SLUG" ] && SLUG="project"
case "$SLUG" in
  _*|*[!a-z0-9_-]*) echo "ERROR: slug must be lowercase letters, digits, - or _, not starting with _: $SLUG" >&2; exit 2 ;;
esac

DIR="$PROJECTS/$SLUG"
if [ -e "$DIR" ]; then
  echo "ERROR: $DIR already exists" >&2
  exit 1
fi

mkdir -p "$DIR"
# copy the template, skipping macOS junk
(cd "$TEMPLATE" && find . -type f ! -name '.DS_Store' -print0 | while IFS= read -r -d '' f; do
  mkdir -p "$DIR/$(dirname "$f")"
  cp "$f" "$DIR/$f"
done)

# fill placeholders (python takes goal/slug as argv, never through a shell string)
python3 - "$DIR" "$SLUG" "$GOAL" <<'PY'
import os, sys
root, slug, goal = sys.argv[1], sys.argv[2], sys.argv[3]
for base, _dirs, files in os.walk(root):
    if ".git" in base.split(os.sep):
        continue
    for name in files:
        p = os.path.join(base, name)
        try:
            with open(p, "r", encoding="utf-8") as fh:
                body = fh.read()
        except Exception:
            continue
        new = body.replace("{{SLUG}}", slug).replace("{{GOAL}}", goal)
        if new != body:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(new)
PY

# each mini project is its own git repo; fail loudly if that cannot happen
if ! (cd "$DIR" && git init -q); then
  echo "ERROR: git init failed in $DIR" >&2
  exit 1
fi

echo "created: $DIR"
echo "files:   $(cd "$DIR" && ls -A | tr '\n' ' ')"
echo "next:    /scope $SLUG"

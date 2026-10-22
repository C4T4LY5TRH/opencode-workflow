#!/usr/bin/env bash
# Scaffold a new mini project from the workshop template.
# Purpose gate lives in the /new command, not here.
# usage: new-project.sh "<goal>" [slug]
set -euo pipefail

GOAL="${1:-}"
SLUG="${2:-}"

if [ -z "$GOAL" ]; then
  echo "usage: new-project.sh \"<goal>\" [slug]" >&2
  exit 2
fi

CONFIG="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
WORKSPACE="${WORKSPACE:-$(cat "$CONFIG/workspace.txt" 2>/dev/null || pwd)}"
PROJECTS="$WORKSPACE/mini-projects"
TEMPLATE="$PROJECTS/_template"

if [ ! -d "$TEMPLATE" ]; then
  echo "ERROR: template not found: $TEMPLATE" >&2
  echo "The workshop must contain mini-projects/_template/ (source of truth for project shape)." >&2
  exit 1
fi

if [ -z "$SLUG" ]; then
  SLUG="$(printf '%s' "$GOAL" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -d- -f1-5)"
fi
[ -z "$SLUG" ] && SLUG="project"

DIR="$PROJECTS/$SLUG"
if [ -e "$DIR" ]; then
  echo "ERROR: $DIR already exists" >&2
  exit 1
fi

mkdir -p "$DIR"
cp -R "$TEMPLATE/." "$DIR/"

# fill placeholders
python3 - "$DIR" "$SLUG" "$GOAL" <<'PY'
import os, sys
root, slug, goal = sys.argv[1], sys.argv[2], sys.argv[3]
for base, _dirs, files in os.walk(root):
    if ".git" in base:
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
print("filled placeholders")
PY

cd "$DIR" && git init -q 2>/dev/null || true

echo "created: $DIR"
echo "next: /scope"

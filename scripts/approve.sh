#!/usr/bin/env bash
# Record the HUMAN's approval of a project's current PLAN.md.
#
# usage:  bash scripts/approve.sh <slug>      (normally via the /approve command)
#
# Only the human-typed /approve command runs this: its !`...` line runs outside any
# agent shell. harness_state.py parses PLAN.md (refusing a plan it cannot parse) and writes
# mini-projects/<slug>/.harness/state.json: the plan's sha256 plus its steps.
# The safety-gate plan gate allows code writes only while PLAN.md still has that hash,
# so any edit to the plan revokes the approval. Agents cannot write .harness/ and
# cannot run this script (safety-gate plugin + policies).
set -euo pipefail

# opencode marks every agent shell with AGENT=1 and OPENCODE_SESSION_ID; a command template has neither
if [ "${AGENT:-}" = "1" ] || [ -n "${OPENCODE_SESSION_ID:-}" ]; then
  echo "REFUSED: approval comes only from the human typing /approve <slug>, never from an agent shell." >&2
  exit 3
fi

SLUG="${1:-}"
case "$SLUG" in
  ""|_*|*[!a-z0-9_-]*) echo "usage: /approve <slug>   (slug: lowercase letters, digits, - or _)" >&2; exit 2 ;;
esac

# workshop root = parent of this script's directory (project-local install)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ="$(cd "$HERE/.." && pwd)/mini-projects/$SLUG"
if [ ! -f "$PROJ/PLAN.md" ]; then
  echo "REFUSED: no PLAN.md in mini-projects/$SLUG. Run /go $SLUG first." >&2
  exit 1
fi

# plan parsing, step recording and the state file are the library's job
exec python3 "$HERE/harness_state.py" approve "$PROJ"

#!/usr/bin/env bash
# Record the HUMAN's approval of a project's current documents: BRIEF + ARCHITECTURE
# (+ DESIGN) + PLAN under one hash.
#
# usage:  bash scripts/approve.sh [<slug>]    (normally via the /approve command; no slug = the current project)
#
# Only the human-typed /approve command runs this: its !`...` line runs outside any
# agent shell. harness_state.py checks the documents (naming every gap it refuses on) and
# writes mini-projects/<slug>/.harness/state.json: the approval hash plus the plan's steps.
# The safety-gate plan gate allows code writes only while the documents still have that
# hash, so any edit to one of them revokes the approval. Agents cannot write .harness/ and
# cannot run this script (safety-gate plugin + policies).
set -euo pipefail

# opencode marks every agent shell with AGENT=1 and OPENCODE_SESSION_ID; a command template has neither
if [ "${AGENT:-}" = "1" ] || [ -n "${OPENCODE_SESSION_ID:-}" ]; then
  echo "REFUSED: approval comes only from the human typing /approve, never from an agent shell." >&2
  exit 3
fi

# workshop root = parent of this script's directory (project-local install)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# the slug is optional: none means the current project (.harness/current); a name is remembered as the current one
SLUG="$(python3 "$HERE/harness_state.py" resolve "${1:-}")" || {
  echo "usage: /approve [<slug>]   (a project name, or none for the current project)" >&2; exit 2; }
PROJ="$(cd "$HERE/.." && pwd)/mini-projects/$SLUG"

# the library approves BRIEF + ARCHITECTURE + PLAN under one approval hash;
# plan parsing, step recording and the state file are its job
exec python3 "$HERE/harness_state.py" approve "$PROJ"

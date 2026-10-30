---
description: You approve a project's current documents (BRIEF + ARCHITECTURE (+ DESIGN) + PLAN, or a v3 project's PLAN.md), human-typed only. Unlocks the build steps of /go until one of them changes.
agent: orchestrator
---
Approval for project "$ARGUMENTS". The approval script already ran when the human typed this command; its output:

!`bash scripts/approve.sh "$ARGUMENTS"; rc=$?; python3 scripts/status.py --html >/dev/null 2>&1; exit $rc`

Relay that output to the human verbatim. Run nothing else and write nothing.
If it says APPROVED, the next command is /go $ARGUMENTS. If it says REFUSED, list each missing item on its own line.
If it prints usage, say what it asks for.

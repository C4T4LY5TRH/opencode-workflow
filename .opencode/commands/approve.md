---
description: You approve a project's current PLAN.md (human-typed only). Unlocks the build steps of /go until PLAN.md changes.
agent: orchestrator
---
Approval for project "$ARGUMENTS". The approval script already ran when the human typed this command; its output:

!`bash scripts/approve.sh "$ARGUMENTS"; rc=$?; python3 scripts/status.py --html >/dev/null 2>&1; exit $rc`

Relay that output to the human verbatim, in one line. Run nothing else and write nothing.
If it says APPROVED, the next command is /go $ARGUMENTS. If it says REFUSED or usage, say what it asks for.

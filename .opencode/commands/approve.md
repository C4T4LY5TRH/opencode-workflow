---
description: You approve a project's current PLAN.md (human-typed only). Unlocks /build until PLAN.md changes.
agent: orchestrator
---
Approval for project "$ARGUMENTS". The approval script already ran when the human typed this command; its output:

!`bash scripts/approve.sh "$ARGUMENTS"`

Relay that output to the human verbatim, in one line. Run nothing else and write nothing.
If it says APPROVED, the next command is /build $ARGUMENTS. If it says REFUSED or usage, say what it asks for.

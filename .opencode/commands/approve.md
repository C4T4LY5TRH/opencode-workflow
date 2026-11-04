---
description: You approve a project's current documents (BRIEF + ARCHITECTURE (+ DESIGN) + PLAN), human-typed only (/approve [slug]; no slug means the current project). Unlocks the build steps of /go until one of them changes.
agent: orchestrator
---
Approval argument: "$ARGUMENTS" (empty means the current project). The approval script already ran when the human typed this command; its output:

!`bash scripts/approve.sh "$ARGUMENTS"; rc=$?; python3 scripts/status.py --html >/dev/null 2>&1; exit $rc`

Relay that output to the human verbatim. Run nothing else and write nothing.
If it says APPROVED, the next command is /go (a SAVE POINT BLOCKED line names what to fix first; /go stops until then). If it says REFUSED, list each missing item on its own line, then the command it ends with.
If it prints usage, say what it asks for.

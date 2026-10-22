---
description: Cut idea into MVP scope. Writes SCOPE.md.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @scoper cut scope for this project. Project dir: mini-projects/$ARGUMENTS (resolve real path first if unsure).
Rules for scoper: IN max 5 testable items, OUT list mandatory, CUT LINE included.
After: show the SCOPE.md content summary (IN, OUT, CUT LINE) and ask human to confirm before /plan.

---
description: Cut idea into MVP scope. Writes SCOPE.md.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @scoper cut scope for this project. Project dir: mini-projects/$ARGUMENTS.
Rules for scoper: IN max 5 testable items, OUT list mandatory, CUT LINE included.
After: show the SCOPE.md summary (IN, OUT, CUT LINE) and ask the human to confirm before /plan.
Handoff check: after the worker reports, run `ls mini-projects/$ARGUMENTS/SCOPE.md`. If it is missing, the worker did not write it: send it back once with "write SCOPE.md now, then report". Never tell the human a file exists unless ls shows it.

---
description: Failure scenarios and second-order effects. Writes WHATIF.md.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @whatif run the 5 scenarios (SCALE, MISUSE, DEPENDENCY DIES, TIME, MONEY) and save them to mini-projects/$ARGUMENTS/WHATIF.md. Each: trigger, breaks, early signal, cheap mitigation.
After: show the top 3 risks + max 3 prep items.
Handoff check: after the worker reports, run `ls mini-projects/$ARGUMENTS/WHATIF.md`. If it is missing, the worker did not write it: send it back once with "write WHATIF.md now, then report". Never tell the human a file exists unless ls shows it.

---
description: Blind-spot sheet for current work. Writes BLIND.md.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @critic write BLIND.md. All sections mandatory: ASSUMPTIONS, UNKNOWNS, UNTESTED PATHS, EDGE CASES, DEPENDENCY RISK, WHAT WOULD BREAK THIS, HOW TO TEST THE BLIND SPOTS.
After: show the top 3 blind spots + the exact commands that test them.
Handoff check: after the worker reports, run `ls mini-projects/$ARGUMENTS/BLIND.md`. If it is missing, the worker did not write it: send it back once with "write BLIND.md now, then report". Never tell the human a file exists unless ls shows it.

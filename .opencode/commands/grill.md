---
description: Devil's advocate attacks the current plan. Writes DEVIL.md.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @devil build the strongest honest case against this plan and save it to mini-projects/$ARGUMENTS/DEVIL.md. Attack the load-bearing assumption.
After: show KILL CASE + the assumption that breaks it + cheapest hedge. Ask the human: keep, shrink, or kill.
Handoff check: after the worker reports, run `ls mini-projects/$ARGUMENTS/DEVIL.md`. If it is missing, the worker did not write it: send it back once with "write DEVIL.md now, then report". Never tell the human a file exists unless ls shows it.

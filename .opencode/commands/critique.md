---
description: Optional second opinion on a project - the strongest case against it plus failure scenarios. Writes CRITIQUE.md.
agent: orchestrator
---
Project: "$ARGUMENTS". If no project slug is given: ask the human for one. Stop.

Delegate: @critic read mini-projects/$ARGUMENTS (PLAN.md, BRIEF.md, any code) and write mini-projects/$ARGUMENTS/CRITIQUE.md: the strongest honest case against it, the assumption that breaks it, and the failure scenarios (scale, misuse, dependency dies, time, money) with cheap hedges.
After: show the KILL CASE in two lines, the assumption that breaks it, and the cheapest hedge. Ask the human: keep, shrink, or kill.
Handoff check: after the worker reports, run `ls mini-projects/$ARGUMENTS/CRITIQUE.md`. If it is missing, the worker did not write it: send it back once with "write CRITIQUE.md now, then report". Never tell the human a file exists unless ls shows it.

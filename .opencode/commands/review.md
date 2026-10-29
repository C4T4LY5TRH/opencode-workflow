---
description: On-demand independent review of a project (same reviewer as /go). Writes REVIEW.md with a VERDICT line and blind spots.
agent: orchestrator
---
Project: "$ARGUMENTS". If no project slug is given: ask the human for one. Stop.

Delegate: @reviewer review mini-projects/$ARGUMENTS against its PLAN.md and write mini-projects/$ARGUMENTS/REVIEW.md, and change no code. REVIEW.md needs a line `VERDICT: SHIP`, `VERDICT: FIX FIRST` or `VERDICT: REWORK`, severity-ranked findings with path:line, and a `## Blind spots` section. Never assume the step checks passed: the reviewer runs every `done when:` check that is a test runner it may run (one command per call, workdir mini-projects/$ARGUMENTS), pastes the real output, and lists the others under Blind spots.
After: show the verdict + blocker count only.
Handoff check: after the worker reports, run `ls mini-projects/$ARGUMENTS/REVIEW.md`. If it is missing, the worker did not write it: send it back once with "write REVIEW.md now, then report". Never tell the human a file exists unless ls shows it.

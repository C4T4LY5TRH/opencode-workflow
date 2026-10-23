---
description: Review code against plan and scope. Writes REVIEW.md.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @reviewer review the current code/diff against PLAN.md and SCOPE.md. The reviewer runs the project's own test/acceptance command and pastes the real output. Write REVIEW.md with severity-ranked findings (blocker/should/nice) + file:line + smallest fix, scope check, dead code, not-tested list.
After: show the verdict + blocker count only.
Handoff check: after the worker reports, run `ls mini-projects/$ARGUMENTS/REVIEW.md`. If it is missing, the worker did not write it: send it back once with "write REVIEW.md now, then report". Never tell the human a file exists unless ls shows it.

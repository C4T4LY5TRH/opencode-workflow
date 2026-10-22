---
description: Review code against plan and scope. Writes REVIEW.md.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @reviewer review current code/diff against PLAN.md and SCOPE.md. Write REVIEW.md with severity-ranked findings (blocker/should/nice) + file:line + smallest fix, scope check, dead code, not-tested list.
After: show verdict + blocker count only. No long dumps.

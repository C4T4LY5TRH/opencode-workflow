---
description: Implement the next planned step. Smallest diff, verified.
agent: orchestrator
---
Project: $ARGUMENTS

Precondition: PLAN.md exists and human approved it. If missing -> stop, ask for /plan.

Delegate: @coder implement ONLY the next numbered step from PLAN.md. Then run the step's done-when command and paste real output.
After: report files changed, command run, result, next step. Never let coder touch files outside the step list.

---
description: Implement the next planned step. Smallest diff, verified.
agent: orchestrator
---
Project: $ARGUMENTS

Precondition: mini-projects/$ARGUMENTS/PLAN.md exists and the human approved it with /approve $ARGUMENTS. If PLAN.md is missing -> stop, ask for /plan.
The plan gate blocks code writes while PLAN.md is missing, unapproved, or changed since approval; that refusal is correct, not a bug. Tell the human to type /approve $ARGUMENTS.

Delegate: @coder implement ONLY the next numbered step from PLAN.md. Then run that step's done-when command and paste the real output.
After: report files changed, command run, result, next step. Never let the coder touch files outside the step's file list.

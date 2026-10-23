---
description: Turn scope into ordered plan with acceptance criteria. Writes PLAN.md.
agent: orchestrator
---
Project: $ARGUMENTS

Precondition: mini-projects/$ARGUMENTS/SCOPE.md exists. If missing -> tell the human to run /scope first. Stop.

Delegate: @architect write PLAN.md. Steps ordered so the repo stays working. Each step: goal, exact file paths, done-when command, risk. Acceptance section with exact commands the human can run.
If DEVIL.md or WHATIF.md exist, the architect must read them and say which risks the plan answers.
After: show the numbered steps + acceptance. Tell the human: read PLAN.md, then type /approve $ARGUMENTS to approve it. Only the human can approve; the plan gate blocks code until they do, and again whenever PLAN.md changes.
Handoff check: after the worker reports, run `ls mini-projects/$ARGUMENTS/PLAN.md`. If it is missing, the worker did not write it: send it back once with "write PLAN.md now, then report". Never tell the human a file exists unless ls shows it.

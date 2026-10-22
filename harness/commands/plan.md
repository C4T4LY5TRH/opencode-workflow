---
description: Turn scope into ordered plan with acceptance criteria. Writes PLAN.md.
agent: orchestrator
---
Project: $ARGUMENTS

Precondition: SCOPE.md exists. If missing -> tell human to run /scope first. Stop.

Delegate: @architect write PLAN.md. Steps ordered so repo stays working. Each step: goal, exact file paths, done-when command, risk. Acceptance section with exact commands human can run.
After: show numbered steps + acceptance. Ask human to approve the plan. No code before approval.

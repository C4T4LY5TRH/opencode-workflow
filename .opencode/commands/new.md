---
description: Scaffold a new mini project (purpose gate). Needs a one-line goal.
agent: orchestrator
---
GOAL (one line, human words, no code): $ARGUMENTS

The scaffold script already ran when the human typed this command (the goal goes in as data, never as shell code). Its output:

!`bash scripts/new-project.sh - <<'HARNESS_GOAL_END'
$ARGUMENTS
HARNESS_GOAL_END`

1. If it printed usage (no goal) -> ask the human for a one-line goal. Stop. No scaffold.
2. If it printed ERROR -> show the error. Stop.
3. Report: created dir, the files inside, and the next command: /go <slug> (it plans the project; you then read PLAN.md and type /approve <slug>).
4. Stop. Delegate to no one.

Never scaffold any other way. The purpose gate is hard.

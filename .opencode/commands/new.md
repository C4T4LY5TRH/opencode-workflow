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
3. Report: created dir, the files inside, next command (/scope <slug>).
4. Then delegate: @scoper write SCOPE.md for the new project.

Never scaffold any other way. The purpose gate is hard.

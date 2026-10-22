---
description: Scaffold a new mini project (purpose gate). Needs a one-line goal.
agent: orchestrator
---
GOAL (one line, human words, no code): $ARGUMENTS

Steps:
1. If GOAL empty -> ask human for one line goal. Stop. No scaffold.
2. Run: bash ~/.config/opencode/scripts/new-project.sh "$ARGUMENTS"
3. Report: created dir, what is inside, next command (/scope).
4. Then delegate: @scoper write SCOPE.md for the new project.

Never scaffold without a written goal. Purpose gate is hard.

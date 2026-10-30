---
description: Start a new mini project from your idea, any length (begin with a slug and a colon to name it). The brainstormer writes the first BRIEF.md draft and asks its questions.
agent: orchestrator
---
The scaffold script already ran when the human typed this command (the idea goes in as data, never as shell code; all of it becomes the brief's GOAL). Its output:

!`bash scripts/new-project.sh - <<'HARNESS_TEXT_END'
$ARGUMENTS
HARNESS_TEXT_COMPLETE
HARNESS_TEXT_END`

1. If it printed usage (no idea) -> ask the human for their idea. Stop. No scaffold.
2. If it printed ERROR -> show the error. Stop.
3. Otherwise it printed `created: .../mini-projects/<slug>` and `PHASE: BRAINSTORM`. Delegate once to @brainstormer:
   "mini-projects/<slug>, first round: write the first BRIEF.md draft for the created project from its GOAL, then
   ask 3 to 5 questions, each with your recommended answer." Relay its questions (with the recommended answers) and
   its closing line. Stop.

Never scaffold any other way. The purpose gate is hard.

---
description: Harvest lessons from a finished project into a brain proposal.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @brain read mini-projects/$ARGUMENTS/LEARNINGS.md and NOTES.md plus brain/rules/*, then write a proposal file to brain/proposals/<date>-$ARGUMENTS.md (NEW / UPDATE / DELETE rules, patterns, anti-patterns, changelog line).
After: show the proposal path and a 5-line summary.
The brain agent can only write proposals. The human applies what they approve by editing brain/rules/ (agents cannot write there). Promotion bar: 2 projects of evidence, or 1 hard failure.

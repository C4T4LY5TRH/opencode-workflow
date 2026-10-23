---
description: Independent review of a diff, branch or PR (report only; does not write REVIEW.md or feed the ship gate)
agent: code-reviewer
subagent: true
---
Review this target: $ARGUMENTS

If no target was given: review uncommitted changes; if there are none, review the current branch against main.

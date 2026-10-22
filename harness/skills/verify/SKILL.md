---
name: verify
description: Prove it works before claiming done. Use before saying a task is complete, fixed, or working.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "false"
---
# Verify before claim

"Works" = a command you ran + output you pasted. Nothing else counts.

## Steps
1. Find the real check: test command, build command, or the acceptance command from PLAN.md.
2. Run it. Full output, real exit code.
3. If fails -> fix or report blocked. Never narrate a fix you did not run.
4. If no automated check exists -> do a manual proof: open the app, click the path, screenshot it, describe what you SAW.
5. Report: command + exit code + key output lines. 3 lines max.

## Not proof
- "This should work"
- "Looks right"
- "I wrote the code"
- Screenshot of code (not of running app)

## Gate
/ship needs this. /review trusts nothing but real output.

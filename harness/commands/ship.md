---
description: Gate check then ship. All gates must pass, human confirms.
agent: orchestrator
---
Project: $ARGUMENTS

Gate checklist — check each, fail fast, report which failed:
1. PLAN.md exists and human approved it.
2. SCOPE.md exists; no OUT items were built.
3. REVIEW.md exists; verdict not REWORK; no open blocker.
4. BLIND.md exists; top risks have owners or accepted.
5. Project test/build command runs and passes (run it, paste real output).
6. Working tree clean of junk files (no secrets, no .env, no node_modules staged).
7. Nothing pushed/published yet.

If all pass: show the exact commit message and the exact git commands. Ask human: "SHIP? yes/no". Do NOT commit or push until human says yes.
If any fail: stop, name the failed gate, give the one command/agent that fixes it.

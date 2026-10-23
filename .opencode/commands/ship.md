---
description: Gate check then ship. All gates must pass, human confirms.
agent: orchestrator
---
Project: $ARGUMENTS

Gate checklist. Check each, fail fast, report which failed:
1. PLAN.md exists and the human approved it: `cat mini-projects/$ARGUMENTS/.harness/state.json` shows the approval.
2. SCOPE.md exists; no OUT items were built.
3. REVIEW.md exists; verdict is SHIP (not FIX FIRST, not REWORK); no open blocker.
4. BLIND.md exists; top risks have an owner or are accepted.
5. Tests pass: delegate @reviewer to run the project's test/build command and paste the real output. You cannot run it yourself.
6. `git status` and `git diff --cached --name-only` show no .env, secrets or node_modules.

If all pass: show the exact commit message and the exact git commands. Ask the human: "SHIP? yes/no". The human runs the commit, or approves it when asked. The safety gate also blocks any commit while REVIEW.md or BLIND.md is missing.
If any fail: stop, name the failed gate, give the one command that fixes it.

---
description: Ship checklist, then the brain drafts one lesson proposal. You commit, push and publish yourself.
agent: orchestrator
---
Project "$ARGUMENTS". If no slug was given: ask for one, stop. The status script already ran when the human typed this command; its output:

!`python3 scripts/status.py "$ARGUMENTS"; python3 scripts/harness_state.py ship "mini-projects/$ARGUMENTS"; python3 scripts/status.py --html >/dev/null 2>&1; true`

The review's blind spots and the project's `git status --short`, printed by the same template:

!`awk '/^## /{p=/^## Blind spots/} p' "mini-projects/$ARGUMENTS/REVIEW.md" 2>/dev/null || echo "(no REVIEW.md)"; echo "git status --short:"; git -c core.fsmonitor=false -c safe.bareRepository=explicit -C "mini-projects/$ARGUMENTS" status --short 2>&1; true`

Checklist. Everything you need is printed above: run no shell. Fail fast, name the failed item, give the one command that fixes it:
1. The first status line says SHIP (every step done, fresh review, verdict SHIP). If not, stop and give its `next:` command. That line is the freshness check for the human's commit; you do not judge it. Also relay the last line of that output word for word (MILESTONE SHIPPED, NOT RECORDED or v3 project): code records the milestone, never you.
2. Show the `## Blind spots` section above. Ask the human to accept those risks or name an owner. None printed = item 2 fails: run /review $ARGUMENTS to review again, then /ship $ARGUMENTS.
3. The `git status --short` lines above show no .env, secrets or node_modules.

Once the MILESTONE SHIPPED line has printed, the milestone is recorded. If item 2 or 3 then fails, tell the human plainly: fix it, then commit by hand; the record stays (piece 1 has no way back to that milestone).

All pass: show the exact commit message and the exact git commands to run in `mini-projects/$ARGUMENTS` (`git add ...`, `git commit -m ...`). THE HUMAN runs them (agents cannot write `.git`), before editing any code: nothing re-checks the review at that point. Ask the human to reply "committed" when done. Push and publish are human-only too: denied for every agent.

Only after the human replies that the commit is done: delegate @brain once. Brief: read mini-projects/$ARGUMENTS/LEARNINGS.md, NOTES.md and REVIEW.md, plus brain/rules and brain/evals/bench.yaml; write ONE proposal to brain/proposals/<date>-$ARGUMENTS.md (if nothing meets the promotion bar, the proposal says so in one line). Then `ls brain/proposals/` to confirm it exists. Never tell the human a file exists unless ls shows it. Relay the file name; applying it is the human's job. Last line: NEXT: read the proposal, apply what you approve.

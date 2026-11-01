---
description: Ship checklist (/ship [slug]; no slug means the current project). You commit, push and publish yourself.
agent: orchestrator
---
Project argument: "$ARGUMENTS" (empty means the current project). The status script already ran when the human typed this command; its output (if it printed no status line, there is no such project: relay what it printed and stop):

!`S="$(python3 scripts/harness_state.py resolve "$ARGUMENTS")" && { python3 scripts/status.py "$S"; python3 scripts/harness_state.py ship "mini-projects/$S"; }; python3 scripts/status.py --html >/dev/null 2>&1; true`

The review's blind spots and the project's `git status --short`, printed by the same template:

!`S="$(python3 scripts/harness_state.py resolve "$ARGUMENTS")" && { awk '/^## /{p=/^## Blind spots/} p' "mini-projects/$S/REVIEW.md" 2>/dev/null || echo "(no REVIEW.md)"; echo "git status --short:"; git -c core.fsmonitor=false -c safe.bareRepository=explicit -C "mini-projects/$S" status --short 2>&1; }; true`

Below, <slug> is the project named in the first status line. Checklist. Everything you need is printed above: run no shell. Fail fast, name the failed item, give the one command that fixes it:
1. The first status line says SHIP (every step done, fresh review, verdict SHIP). If not, stop and give its `next:` command. That line is the freshness check for the human's commit; you do not judge it. Also relay the last line of that output word for word (MILESTONE SHIPPED, NOT RECORDED or v3 project): code records the milestone, never you.
2. Show the `## Blind spots` section above. Ask the human to accept those risks or name an owner. None printed = item 2 fails: run /review to review again, then /ship.
3. The `git status --short` lines above show no .env, secrets or node_modules.

Once the MILESTONE SHIPPED line has printed, the milestone is recorded. If item 2 or 3 then fails, tell the human plainly: fix it, then commit by hand; the record stays (piece 1 has no way back to that milestone).

All pass: show the exact commit message and the exact git commands to run in `mini-projects/<slug>` (`git add ...`, `git commit -m ...`). THE HUMAN runs them (agents cannot write `.git`), before editing any code: nothing re-checks the review at that point. Push and publish are human-only too: denied for every agent.

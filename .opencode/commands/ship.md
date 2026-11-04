---
description: Ship checklist (/ship [slug]), then /ship [slug] yes commits, tags and records the milestone. No slug means the current project.
agent: orchestrator
---
Arguments: "$ARGUMENTS" (`[slug]`, or `[slug] yes`; no slug means the current project). The script already ran when the human typed this command; its output (if it printed no status line, there is no such project: relay what it printed and stop):

!`R="$(python3 scripts/harness_state.py shiptarget "$ARGUMENTS")" && S="${R% *}" && M="${R##* }" && { python3 scripts/status.py "$S"; python3 scripts/harness_state.py ship "mini-projects/$S" "$M"; [ "$M" = yes ] || { echo "git status --short:"; git -c core.fsmonitor=false -c safe.bareRepository=explicit -C "mini-projects/$S" status --short 2>&1; }; }; python3 scripts/status.py --html >/dev/null 2>&1; true`

Run no shell and write nothing. Everything you need is printed above.

**Without `yes`** (the checklist; nothing was recorded). Below, <slug> is the project named in the first status line. Fail fast, name the failed item, give the one command that fixes it:
1. The READY / NOT READY line (it follows the status lines) says READY. If it says NOT READY, stop: give the command it ends with. That line is the freshness check; you do not judge it. Also show the `visual:` line.
2. Show the `## Blind spots` section and the `## Leads` section (leads are unproven suspicions from the review: they never block). Ask the human to accept those risks, or to name an owner or a step for any lead. Blind spots printed as "(none printed)" = item 2 fails: run /review to review again, then /ship.
3. Show the `## Visual items` if printed: the human accepts each or turns it into a step.
4. The `git status --short` lines show no .env, secrets or node_modules (the secret scan also runs at `yes`, and blocks).
All pass: tell the human to type `/ship <slug> yes`. That one command commits the whole tree as the save point `ship M<n>`, tags it `m<n>`, and records the milestone; the human no longer commits by hand. Push and publish stay human-only (`/publish`).

**With `yes`** (the output above is the result): relay it word for word. If it says MILESTONE SHIPPED, the commit, the tag and the record are done: say what the next command is (it is on that line). If it says NOT RECORDED, nothing was recorded: relay the reason and the one command that fixes it, and add that `/ship <slug> yes` is safe to type again (a commit or tag that already exists is skipped).

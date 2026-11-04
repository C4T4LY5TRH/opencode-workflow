---
description: Run the last shipped milestone on this Mac (/deploy [slug]); /deploy rollback [slug] goes back one release, /deploy stop [slug] stops it. No slug means the current project.
agent: orchestrator
---
Arguments: "$ARGUMENTS" (`[slug]`, `rollback [slug]` or `stop [slug]`; no slug means the current project). The deploy script already ran when the human typed this command; its output:

!`python3 scripts/deploy.py "$ARGUMENTS"; python3 scripts/status.py --html >/dev/null 2>&1; true`

Relay that output to the human verbatim, including any URL and any log lines. Run nothing else and write nothing.
- DEPLOYED or ROLLED BACK: give the URL; say a phone on the same network can open it. If a line says "no network", relay it.
- DEPLOY FAILED or ROLLBACK FAILED: relay the reason, what was rolled back or stopped, and the log lines; the fix is in the app's code or its `## DEPLOY` section, then `/ship` the next milestone and `/deploy` again.
- REFUSED: give the reason and the command it names.
- If macOS asks whether the app may accept incoming connections, the human clicks Allow.

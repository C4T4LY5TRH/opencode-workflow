---
description: Push the project to a private GitHub repo (/publish [slug], then /publish [slug] yes). Every commit not yet on the remote is scanned for secrets first. No slug means the current project.
agent: orchestrator
---
Arguments: "$ARGUMENTS" (`[slug]` or `[slug] yes`; no slug means the current project). The publish script already ran when the human typed this command; its output:

!`python3 scripts/checkpoint.py publish "$ARGUMENTS"; python3 scripts/status.py --html >/dev/null 2>&1; true`

Relay that output to the human verbatim. Run nothing else and write nothing.
- NEEDS YES: say nothing was pushed; the human reads the notes and the `gh repo create` line, then runs the `/publish ... yes` command it names.
- PUBLISHED: say the branch and tags are pushed.
- REFUSED: give the reason. For a secret in history, say the fix is a manual history rewrite (HANDBOOK), then `/publish` again.

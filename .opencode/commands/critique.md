---
description: One more critic round on a project's current plan (/critique [slug]; no slug means the current project): the strongest case against it, holes, failure scenarios, then the answers. Adds a ROUND to CRITIQUE.md.
agent: orchestrator
---
Arguments: "$ARGUMENTS" (no project name means the current project). The routing script already ran when the human typed this command; its contract:

!`python3 scripts/next.py --critique "$ARGUMENTS" && python3 scripts/status.py --html >/dev/null 2>&1; true`

Do the numbered INSTRUCTION items in order, one worker call per item, each followed by its check; stop at the first check that is still not exactly OK after one send-back, then run only the last item. If AGENT is none, relay the message. End with STATUS and NEXT COMMAND verbatim; after a chain, with the final status output's stage line and next: line instead (usually /approve or /critique).

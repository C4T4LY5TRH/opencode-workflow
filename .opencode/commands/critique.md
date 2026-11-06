---
description: One more critic round on a project's current plan (/critique [slug]; no slug means the current project): the strongest case against it, holes, failure scenarios, then the answers. Adds a ROUND to CRITIQUE.md.
agent: orchestrator
---
Arguments: "$ARGUMENTS" (no project name means the current project). The routing script already ran when the human typed this command; its contract:

!`python3 scripts/next.py --critique "$ARGUMENTS"; true`

Do exactly the INSTRUCTION; end with STATUS and NEXT COMMAND.

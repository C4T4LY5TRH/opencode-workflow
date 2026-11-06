---
description: Do the next step of a project (/go [slug]; /go retry; /go cap <usd>). The routing is decided by code (scripts/next.py), not by the model.
agent: orchestrator
---
Arguments: "$ARGUMENTS" (no project name means the current project). The routing script already ran when the human typed this command; its contract:

!`python3 scripts/next.py "$ARGUMENTS"; true`

Do exactly the INSTRUCTION; end with STATUS and NEXT COMMAND.

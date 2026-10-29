---
description: Do the next step of a project. The routing is decided by code (scripts/next.py), not by the model.
agent: orchestrator
---
Project "$ARGUMENTS". The routing script already ran when the human typed this command; its contract:

!`python3 scripts/next.py "$ARGUMENTS" && python3 scripts/status.py --html >/dev/null 2>&1; true`

Do exactly the INSTRUCTION, at most one worker call. If AGENT is none, relay the message. End with the STATUS and NEXT COMMAND lines verbatim.

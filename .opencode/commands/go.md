---
description: Do the next step of a project (/go [slug]; /go retry; /go cap <usd>). The routing is decided by code (scripts/next.py), not by the model.
agent: orchestrator
---
Arguments: "$ARGUMENTS" (no project name means the current project). The routing script already ran when the human typed this command; its contract:

!`python3 scripts/next.py "$ARGUMENTS" && python3 scripts/status.py --html >/dev/null 2>&1; true`

Relay only this turn's contract: STATUS and NEXT COMMAND lines from any earlier turn are stale. Do exactly its INSTRUCTION:
- A numbered list is done in order, one delegation at a time, each followed by its check; stop at the first check that is still not exactly OK after one send-back, then run only the last item.
- One agent and no numbered list: one worker call. If AGENT is none, relay the message.
End with STATUS and NEXT COMMAND verbatim; after a chain, with the final status output's stage line and next: line instead (usually /approve or /critique).

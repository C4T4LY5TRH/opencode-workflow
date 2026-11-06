---
description: Show where every project is (or one project). Read-only.
agent: orchestrator
---
Status request: "$ARGUMENTS" (empty means every project; a project name means that project in detail). The status script already ran when the human typed this command; its output:

!`python3 scripts/status.py "$ARGUMENTS"; true`

Relay that output to the human verbatim. Run nothing else and write nothing. At DECIDE the output includes the approval digest: relay it verbatim (code-written; never summarise it).

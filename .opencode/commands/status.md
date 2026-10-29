---
description: Show where every project is (or one project, or the brain). Read-only.
agent: orchestrator
---
Status request: "$ARGUMENTS" (empty means every project; a project name means that project in detail; "brain" means proposals and rules to delete). The status script already ran when the human typed this command; its output:

!`python3 scripts/status.py "$ARGUMENTS" && python3 scripts/status.py --html >/dev/null 2>&1; true`

Relay that output to the human verbatim. Run nothing else and write nothing.

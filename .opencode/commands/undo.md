---
description: Shelve everything since the last save point (/undo [slug]; no slug means the current project). The changes are kept in a git stash and can be brought back.
agent: orchestrator
---
Project argument: "$ARGUMENTS" (empty means the current project). The undo script already ran when the human typed this command; its output:

!`python3 scripts/checkpoint.py undo "$ARGUMENTS"; python3 scripts/status.py --html >/dev/null 2>&1; true`

Relay that output to the human verbatim, including the exact restore command (`git stash apply …`) if one is printed. Run nothing else and write nothing.
If it says REFUSED, give the reason and the command it ends with. If it says nothing to undo, say so.

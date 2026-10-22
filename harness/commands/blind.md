---
description: Blind-spot sheet for current work. Writes BLIND.md.
agent: orchestrator
---
Project: $ARGUMENTS

Delegate: @critic write BLIND.md. All sections mandatory: ASSUMPTIONS, UNKNOWNS, UNTESTED PATHS, EDGE CASES, DEPENDENCY RISK, WHAT WOULD BREAK THIS, HOW TO TEST THE BLIND SPOTS.
After: show top 3 blind spots + the exact commands that test them.

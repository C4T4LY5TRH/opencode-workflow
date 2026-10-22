---
description: Prune stale brain rules, bump brain version, rewrite changelog.
agent: orchestrator
---
Run brain maintenance:
1. List brain/rules/*. Read brain/CHANGELOG.md for rule usage history.
2. Flag rules unused for 3+ projects -> propose delete (ask human).
3. Flag rules overlapping each other -> propose merge (ask human).
4. Propose brain version bump vX.Y -> vX.(Y+1) with one-line changelog entry.
Apply only what human approves. Then run: bash ~/.config/opencode/scripts/bench.sh

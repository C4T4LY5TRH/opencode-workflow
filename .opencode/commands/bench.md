---
description: Run the harness health bench. Numbers, not vibes.
agent: orchestrator
---
The bench already ran when the human typed this command. Its output:

!`bash scripts/bench.sh 2>&1`

Report: checks passed/failed, any failing check with its detail, and the comparison with the previous run that the bench printed.
If a check fails, name it and the file it points at. Do not fix silently. Run nothing else.

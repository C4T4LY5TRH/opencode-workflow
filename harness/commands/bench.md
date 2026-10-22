---
description: Run brain evals and structural bench. Shows if brain improved.
agent: orchestrator
---
Run: bash ~/.config/opencode/scripts/bench.sh
Report: rule count, broken rule links, missing sections, evals passed/failed, and compare with last run stored in brain/evals/last-run.json.
If a regression appears, point at the rule that likely caused it. Do not fix silently.

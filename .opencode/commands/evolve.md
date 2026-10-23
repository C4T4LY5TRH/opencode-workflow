---
description: Review brain rules for pruning and merging; propose a version bump.
agent: orchestrator
---
The rule report already ran when the human typed this command (usage counted by the brain-log plugin):

!`python3 scripts/rule-report.py`

Run brain maintenance (read-only for you):
1. Read brain/rules/* and brain/CHANGELOG.md.
2. Rules marked DECAY in the report -> propose delete (rule 040: unused while 3 new projects started). Quote the report line as evidence.
3. Rules that overlap -> propose merge.
4. Rules marked NO EVAL or UNKNOWN EVAL -> propose an eval in brain/evals/bench.yaml (`rules:` map).
5. Propose a version bump vX.Y -> vX.(Y+1) with a one-line changelog entry.
Delegate the write-up to @brain as a proposal in brain/proposals/, with the report above as its evidence. The human applies approved changes in brain/rules/, then runs /bench.

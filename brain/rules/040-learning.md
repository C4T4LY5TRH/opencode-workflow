# 040-learning

- Lesson source: project LEARNINGS.md + NOTES.md + REVIEW.md.
- Promotion bar: 2 projects evidence, OR 1 hard failure (data loss / security / shipped bug).
- One rule = one idea. <=40 lines. Numbered, next free number.
- Rule must say WHEN + WHAT. "Be careful" invalid.
- Decay: unused 3 projects -> propose delete. Brain must shrink too.
  Measured: brain-log counts rule reads in .harness/rule-usage.json; /status brain shows the DECAY list.
- Every rule names its eval in brain/evals/bench.yaml (`rules:`). No eval, no promotion.
- Brain version bumps on any rule change. CHANGELOG entry one line.
- /ship has the brain write ONE proposal after the human commits. Human approves. Never auto-apply to rules.
- `bash scripts/bench.sh` measures. No improvement claim without numbers.

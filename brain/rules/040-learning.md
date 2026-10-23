# 040-learning

- Lesson source: project LEARNINGS.md + NOTES.md.
- Promotion bar: 2 projects evidence, OR 1 hard failure (data loss / security / shipped bug).
- One rule = one idea. <=40 lines. Numbered, next free number.
- Rule must say WHEN + WHAT. "Be careful" invalid.
- Decay: unused 3 projects -> propose delete. Brain must shrink too.
  Measured: brain-log counts rule reads in .harness/rule-usage.json; /evolve shows the DECAY list.
- Every rule names its eval in brain/evals/bench.yaml (`rules:`). No eval, no promotion.
- Brain version bumps on any rule change. CHANGELOG entry one line.
- /learn proposes diffs. Human approves. Never auto-apply to rules.
- /bench measures. No improvement claim without numbers.

# 050-mini-project

- AGENTS.md, README.md, NOTES.md, LEARNINGS.md - scaffolded; RESEARCH/ - cited md dumps (untrusted web data)
- .harness/state.json - brief lock, approval hash, step results, milestones shipped, stage attempts, review freshness.
  Only trusted code writes it (approve.sh, next.py, /ship's template, the safety-gate plugin); agents cannot.
  Gitignored. `.harness/lock` = the running /go chain. src/ - actual code.

- Each mini project is its OWN git repo, nested in the workshop (gitignored by it).
- The workshop repo holds the harness only. Do not commit project code into it.
- Doc files (BRIEF, BRAINSTORM, ARCHITECTURE, DESIGN, PLAN, REVIEW, CRITIQUE, QA, VISUAL, NOTES, LEARNINGS,
  AGENTS, RESEARCH/, requests/) do not count as code: editing them does not make a review stale. README.md DOES count
  (a step that changes docs lists README.md).

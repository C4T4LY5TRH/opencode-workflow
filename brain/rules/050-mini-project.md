# 050-mini-project

Anatomy (mini-projects/<slug>/) - gate files appear only when their agent writes them:
- BRIEF.md - human: goal, why, done-when-life (scaffolded)
- AGENTS.md - project rules (stack, commands, conventions) (scaffolded)
- README.md, NOTES.md, LEARNINGS.md - scaffolded; RESEARCH/ - cited md dumps
- PLAN.md - planner output: SCOPE (IN/OUT), numbered steps (title, files, `done when` check), ACCEPTANCE
- REVIEW.md - reviewer output (VERDICT: SHIP | FIX FIRST | REWORK, findings, `## Blind spots`)
- CRITIQUE.md - optional /critique: case against the plan + failure scenarios
- BUGHUNT.md - optional /hunt referee report
- .harness/state.json - approval, step results, review freshness. Only trusted code writes it (approve.sh,
  the safety-gate plugin, next.py's fix_rounds count on /go); agents cannot. Gitignored.
- src/ - actual code

- Each mini project is its OWN git repo, nested in the workshop (gitignored by it).
- The workshop repo holds the harness only. Do not commit project code into it.
- Doc files (PLAN, REVIEW, CRITIQUE, BUGHUNT, NOTES, LEARNINGS, BRIEF, README, AGENTS, RESEARCH/) do not count
  as code: editing them does not make a review stale.

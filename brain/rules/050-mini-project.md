# 050-mini-project

Anatomy (mini-projects/<slug>/) - gate files appear only when their agent writes them. Each starts with `## SUMMARY`
(1 to 5 lines); code checks the parts named here:
- BRIEF.md - brainstormer: SUMMARY, GOAL (the idea word for word), FOR WHO / WHY, WHERE IT RUNS (with `- ui: yes|no`),
  FEATURES (`- F<n> [MUST|SHOULD|LATER] text`, at least one MUST), OPPORTUNITIES, REALITY CHECK, DECISIONS,
  OPEN QUESTIONS (`- none` to lock)
- BRAINSTORM.md - brainstormer: one section per /brainstorm topic, append-only
- ARCHITECTURE.md - architect: STACK, STRUCTURE, DATA, FLOWS, RISKS (`- R1: risk - test: spike`), DECISIONS
  (`- D<n>: choice - rejected: x - why: y`), MILESTONES (`- M<n>: title - covers: F1, F2`; every MUST in one),
  CRITIQUE ANSWERS (`- C<n>: fixed - how` or `rejected - why`)
- DESIGN.md - designer, UI projects: SUMMARY, DIRECTION, TOKENS, COMPONENTS, SCREENS (`- <screen>: design/mockups/<name>.html`),
  ACCESSIBILITY, STACK FIT (`- agree` or `- object: <why>`); mockups are static HTML/CSS in design/mockups/
- QA.md - qa: SUMMARY, TESTS (`- F<n>: tests/acceptance/<file> - <what it proves>`), RUN (one `- run:` line), VERDICT
  (PASS | FAIL), REVISIONS; its tests live in tests/acceptance/. VISUAL.md - designer: `VERDICT: MATCH | FIX`, screenshots in design/shots/
- PLAN.md - planner, ONE milestone: MILESTONE, SCOPE, numbered steps (files, covers, proves on M1 step 1,
  one backticked `done when` check, risk), ACCEPTANCE, CRITIQUE ANSWERS
- CRITIQUE.md - critic, append-only `## ROUND n - M<k>`, points `- C<n> [serious|minor] [target] text - fix: ...`
- REVIEW.md - reviewer (VERDICT: SHIP | FIX FIRST | REWORK, findings, `## Blind spots`); BUGHUNT.md - /hunt referee
- AGENTS.md, README.md, NOTES.md, LEARNINGS.md - scaffolded; RESEARCH/ - cited md dumps (untrusted web data)
- .harness/state.json - brief lock, approval hash, step results, milestones shipped, stage attempts, review freshness.
  Only trusted code writes it (approve.sh, next.py, /ship's template, the safety-gate plugin); agents cannot.
  Gitignored. `.harness/lock` = the running /go chain. src/ - actual code.

- Each mini project is its OWN git repo, nested in the workshop (gitignored by it).
- The workshop repo holds the harness only. Do not commit project code into it.
- Doc files (BRIEF, BRAINSTORM, ARCHITECTURE, DESIGN, PLAN, REVIEW, CRITIQUE, BUGHUNT, QA, VISUAL, NOTES, LEARNINGS,
  AGENTS, RESEARCH/, requests/) do not count as code: editing them does not make a review stale. README.md DOES count
  (a step that changes docs lists README.md).

# 050-mini-project

Anatomy (mini-projects/<slug>/) - gate files appear only when their agent writes them:
- BRIEF.md - human: goal, why, done-when-life (scaffolded)
- AGENTS.md - project rules (stack, commands, conventions) (scaffolded)
- README.md, NOTES.md, LEARNINGS.md - scaffolded; RESEARCH/ - cited md dumps
- SCOPE.md - scoper output: IN/OUT/LATER/CUT LINE
- PLAN.md - architect output: steps, files, done-when, acceptance
- REVIEW.md - reviewer findings (VERDICT: SHIP | FIX FIRST | REWORK)
- BLIND.md - critic blind spots
- DEVIL.md - devil's kill case; WHATIF.md - failure scenarios; BUGHUNT.md - /hunt referee report
- .harness/state.json - the human's /approve of the current PLAN.md (only scripts/approve.sh writes it; gitignored)
- src/ - actual code

- Each mini project is its OWN git repo, nested in the workshop (gitignored by it).
- The workshop repo holds the harness only. Do not commit project code into it.

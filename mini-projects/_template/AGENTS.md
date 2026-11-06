# PROJECT RULES - {{SLUG}}

Workshop harness rules live in the workshop root AGENTS.md. This file = project only.

## WHO OWNS WHAT
- `tests/acceptance/` and `QA.md`: the qa agent only. A builder that thinks a test is wrong writes `requests/step<n>.md`
  (`TEST-WRONG: <test file> - <why>`); it never edits the test. Facts a builder lacks: `RESEARCH: <question>` in the same file.
- Each builder changes only its own step's files (`files:` in PLAN.md). README.md counts as code.

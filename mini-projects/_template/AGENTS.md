# PROJECT RULES - {{SLUG}}

Workshop harness rules live in the workshop root AGENTS.md. This file = project only.

## STACK
TODO (fill after the plan is approved)

## COMMANDS
- install: TODO
- run: TODO
- test: TODO
- build: TODO

## CONVENTIONS
- TODO

## WHO OWNS WHAT
- `tests/acceptance/` and `QA.md`: the qa agent only. A builder that thinks a test is wrong writes `requests/step<n>.md`
  (`TEST-WRONG: <test file> - <why>`); it never edits the test. Facts a builder lacks: `RESEARCH: <question>` in the same file.
- Each builder changes only its own step's files (`files:` in PLAN.md). README.md counts as code.

## GOTCHAS
- TODO

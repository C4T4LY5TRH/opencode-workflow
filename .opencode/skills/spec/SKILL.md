---
name: spec
description: Write specs and briefs that survive contact with code - goal, users, non-goals, flows, data, acceptance, risks, open questions. Use before building, or when a request is fuzzy.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "true"
---
# Spec (write it so the builder cannot guess)

A spec is a decision record, not a wishlist. It removes guesses.

## Shape (keep it short)
```
# SPEC - <name>
## GOAL (one line, human words, observable)
## USERS (who, what they do today, what changes for them)
## NON-GOALS (explicit list - this is the most valuable section)
## FLOWS (numbered happy path, then 1-2 error paths)
## DATA (shape + where it lives + who owns it)
## CONSTRAINTS (stack, free tools, no secrets, no paid tiers)
## ACCEPTANCE (exact commands/checks that prove it works)
## RISKS (top 3, each with a cheap mitigation)
## OPEN QUESTIONS (each: who or what answers it)
```

## Rules
- GOAL must be observable. "Better UX" is not a goal. "User sees their list after refresh" is.
- NON-GOALS never empty. This prevents scope creep at 1/10 the cost of arguing later.
- FLOWS: happy path first, numbered. Error paths only the ones that can actually happen.
- ACCEPTANCE = commands, not adjectives. `npm test` exits 0. Not "tests should pass".
- RISK: max 3, each with a mitigation that costs < 1 hour.
- OPEN QUESTIONS: if a question blocks the next step, mark it BLOCKED-HUMAN and stop there.
- No code in the spec. No implementation detail beyond file names.
- If the spec would fit in 3 bullets, write 3 bullets. Length is not quality.

## Where it plugs in
- Human writes BRIEF.md (goal + why + done when life) - 5 lines, no more.
- Planner turns the brief into PLAN.md: a SCOPE section (IN / OUT / LATER / CUT LINE / RISK), then steps with files, done-when and acceptance.
- Spec skill = the quality bar for BRIEF / PLAN. Use it when writing either.

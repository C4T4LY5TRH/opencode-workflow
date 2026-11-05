---
name: rules
description: The harness rulebook (rules/). Load the rule files you need before acting.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "false"
---
# Rules

Home: `rules/NNN-*.md` in the workshop repo (one idea each, <40 lines).

## How to use
1. The core rules are always in context: AGENTS.md (`## CORE`, `## GATES`).
2. Before non-trivial work, scan the index below. Read ONLY the 1-3 rules that match the task.
3. If a rule contradicts the task, the rule wins unless the human says otherwise.

## Rule index (read file when relevant)
- 010-voice - caveman rules for output
- 015-enforcement - gates live in code not prompts; never work around a refusal
- 020-gates - the gates: purpose, brief lock, design chain + critique, one approval hash, plan gate, step checks, fresh SHIP review, confinement, limits (2 attempts, 16 delegations, 30-minute lock), push/publish human-only
- 030-research - how to gather and cite facts
- 050-mini-project - project files (BRIEF, ARCHITECTURE, PLAN, CRITIQUE, REVIEW and their formats), state.json, nested git repo
- 060-ops - platform gotchas: project-local install, nested checkouts, permission order, saved approvals, headless runs, $PWD, agent-shell sandbox, delegation events, model/frontmatter/$ARGUMENTS traps

Never dump all rules into context. Read what the task needs.

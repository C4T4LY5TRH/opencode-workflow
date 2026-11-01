---
name: brain
description: The harness rulebook (brain/rules). Load the rule files you need before acting.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "false"
---
# Brain

Home: `~/Projects/opencode/brain/` (workshop repo, tracked in git)
- `rules/NNN-*.md` - rules that change behaviour (one idea each, <40 lines)
- `prompts/` - reusable prompt fragments (output contract, gate contract)
- `CHANGELOG.md` - harness version history

## How to use
1. Core rules (`brain/rules/000-core.md`) are always in context via `instructions` in `.opencode/opencode.json`.
2. Before non-trivial work, scan rule filenames + one-line summaries. Read ONLY the 1-3 rules that match the task.
3. If a rule contradicts the task, the rule wins unless human says otherwise.
4. After a task teaches you something: write it in the project's `LEARNINGS.md`.

## Rule index (read file when relevant)
- 000-core - always on: verify before claim, no scope creep, ask when unsure, small diffs, cite sources
- 010-voice - caveman rules for output
- 015-enforcement - gates live in code not prompts; never work around a refusal
- 020-gates - the v4 gates: purpose, brief lock, design chain + critique, one approval hash, plan gate, step checks, fresh SHIP review, confinement, limits (2 attempts, 16 delegations, 30-minute lock), push/publish human-only
- 030-research - how to gather and cite facts
- 050-mini-project - project files (BRIEF, ARCHITECTURE, PLAN, CRITIQUE, REVIEW and their formats), state.json, nested git repo
- 060-ops - platform gotchas: project-local install, nested checkouts, permission order, saved approvals, headless runs, $PWD, agent-shell sandbox, delegation events, model/frontmatter/$ARGUMENTS traps

- `prompts/010-output-contract.md` - how you report back (DID / PROOF / BLOCKED / NEXT)
- `prompts/020-gate-contract.md` - what to do when a gate refuses

Never dump all rules into context. Read what the task needs.

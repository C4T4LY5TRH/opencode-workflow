---
name: brain
description: The harness brain - rules, patterns, anti-patterns, evals. Load the rule files you need before acting, and evolve them at project end.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "false"
---
# Brain

Home: `~/.config/opencode/brain/`
- `rules/NNN-*.md` - rules that change behaviour (one idea each, <40 lines)
- `prompts/` - reusable prompt fragments (output contract, gate contract)
- `patterns/` - good reusable patterns
- `anti-patterns/` - traps that already bit us
- `evals/` - tasks + pass criteria
- `CHANGELOG.md` - brain version history

## How to use
1. Read `~/.config/opencode/brain/rules/000-core.md` always (already in context via instructions).
2. Before non-trivial work, scan rule filenames + one-line summaries. Read ONLY the 1-3 rules that match the task.
3. If a rule contradicts the task, the rule wins unless human says otherwise.
4. After a task teaches you something: write it in the project's `LEARNINGS.md`.
5. At project end: `/learn` -> brain agent proposes diffs -> human approves.

## Rule index (read file when relevant)
- 000-core - always on: verify before claim, no scope creep, ask when unsure, small diffs, cite sources
- 010-voice - caveman rules for output
- 015-enforcement - gates live in code not prompts; never work around a refusal
- 020-gates - plan/review/blind/ship gate definitions
- 030-research - how to gather and cite facts
- 040-learning - promotion bar, rule lifecycle, decay
- 050-mini-project - anatomy of a mini project, folder conventions
- 060-ops - service restart, headless ask-permissions, cwd vs session dir

- `prompts/010-output-contract.md` - how you report back (DID / PROOF / BLOCKED / NEXT)
- `prompts/020-gate-contract.md` - what to do when a gate refuses

Never dump all rules into context. Read what the task needs.

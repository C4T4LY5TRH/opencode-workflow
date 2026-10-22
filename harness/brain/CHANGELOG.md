# Brain changelog

Format: `## vX.Y - date - one line what changed and why`

## v1.6 - 2026-10-22 - teleport tooling + fresh-machine install bug killed
- TELEPORT.md + harness/scripts/teleport.sh: pack / unpack / verify. Moves this harness to
  another machine byte for byte. Bundle = 264 KB, 82 files, includes .git (full history).
  The repo is the portable artifact; the live config dir is rebuilt by install.sh.
- Bug K: install.sh DIED on any genuinely fresh machine. The backup-prune step ran
  `ls -1dt "$BACKUPS"/*/`; on an empty .backups/ the glob matches nothing, ls exits 1, and
  `set -euo pipefail` killed the script BEFORE workspace.txt was written and BEFORE the
  service restart. Never fired on this machine because a legacy backup dir already existed.
  Impact: on a new machine the gates would be missing. Fixed with a glob-safe prune that
  can never abort the install, plus a test (empty dir = no abort, 8 dirs = keep 5 newest).
- Bench: plugins-alive now distinguishes "never loaded in this config dir" from
  "loaded then broke". plugins-no-load-failures no longer counts old log entries from a
  previous config dir when there is no heartbeat to compare against.
- New bench check teleport-tooling: teleport.sh must be installed.
- Brain rule 015: a maintenance step must never abort the install; test the fresh-machine path.

## v1.5 - 2026-10-22 - handbook written, bench log-scan false positive killed
- HANDBOOK.md added at the repo root: build journal + how-to. Every agent, command, skill,
  plugin, gate, script, plus one project end-to-end and 8 real bugs with their fixes.
- Bug: the bench's plugin-failure check matched the phrase "failed to load plugin" anywhere in
  the opencode log. The log also records shell commands, so a diagnostic grep was counted as a
  plugin failure -> bench went 24/25 by itself. Now matches level=WARN AND message="...".
- README.md: bench count corrected 21 -> 25, link to HANDBOOK.md added.
- Untracked a stray .playwright-mcp/ snapshot yml that was committed before the ignore rule.
- Bench re-verified: 25/25. Gates re-verified live: plan gate blocks (no PLAN.md), plan gate
  allows (PLAN.md present), ship gate blocks commit (no REVIEW.md).

## v1.4 - 2026-10-22 - three silent-failure bugs found and killed
- Bug A: safety-gate plugin had a JS syntax error (missing regex slash) -> opencode skipped it
  SILENTLY -> every gate was dead for ~40 minutes. Found by the coder agent itself, which
  reported "the plan gate is dead code". Now: heartbeat file + log scan + bench check.
- Bug B: agent frontmatter lost its opening newline -> the `coder` agent vanished
  ("Agent not found"). Now: bench checks frontmatter shape for every agent/command.
- Bug C: duplicate YAML keys in frontmatter -> strict parser rejected the file -> agent vanished.
  Now: bench checks duplicate top-level keys.
- Gate redesign: the plan gate is now FILE-ROLE based (project docs always allowed, code needs
  PLAN.md) instead of agent-based, because the hook's `agent` field does not carry the subagent.
  Plan gate only applies inside a mini project, not in the workshop root.
- Coder permissions: may no longer write PLAN/SCOPE/REVIEW/BLIND (those belong to other agents).
- All 11 agents now carry the report contract inline (DID/PROOF/BLOCKED/NEXT) - no extra file read.
- Bench grew 21 -> 25 checks.

## v1.3 - 2026-10-22 - gaps closed, config hygiene fixed
- G1 spec skill added (7 skills now).
- G2 brain/prompts/ added: 010-output-contract.md (DID/PROOF/BLOCKED/NEXT) + 020-gate-contract.md.
  All 11 agents now report through the shared contract.
- G3 scripts/snapshot.py added: free playwright screenshot helper (png + optional md dump).
- G4 mini-projects/_template/ materialised with the real scaffold; new-project.sh copies from it
  (template is now the single source of truth for project shape).
- G5 workshop AGENTS.md added (workshop-only rules, merged with the global one).
- G6 skipped on purpose: 000-core stays one always-on file. Injected every request, so it must stay compact.
- Hygiene: install.sh backs up to ONE place (~/.config/opencode/.backups/<ts>/, last 5 runs),
  legacy scattered .bak-* files migrated there, nothing left next to live files.
- Bench grew 14 -> 21 checks (semantic gate checks, prompts, template, hygiene).

## v1.2 - 2026-10-22 - harness verified end to end
- 8 behavioural smoke tests run against real agents on free models. All pass. See brain/evals/baseline.md.
- New rule 060-ops: opencode runs as a background service -> `opencode service restart` after config/plugin changes.
- install.sh now restarts the service automatically.
- Shell allow list extended with read-only commands so headless runs work without "ask".
- rm -rf inside a project = ask (human decides); system/home paths stay hard deny.

## v1.1 - 2026-10-22 - gates must live in code, not prompts
- Lesson from smoke test: coder agent bypassed the plan gate by writing a temp PLAN.md via shell.
- New rule 015-enforcement: enforce gates in code (plugin/permission), never only in prompt text.
- Fixed safety-gate plugin: session dir now comes from ctx.location, not process.cwd()
  (opencode can run as a background service with a different cwd).
- safety-gate now also blocks: coder writing PLAN/SCOPE/REVIEW/BLIND, shell writes outside project.

## v1.0 - 2026-10-22 - initial brain
- 6 core rule files, 11 agents, 17 commands, 6 skills, 3 safety plugins.
- Brain created from workflow spec. Evals seeded. Baseline not yet measured.

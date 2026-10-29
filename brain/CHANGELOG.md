# Brain changelog

Format: `## vX.Y - date - one line what changed and why`

## v3.0 - 2026-10-25 - the /go loop: recorded steps, /status + dashboard, 9 agents, 9 commands
Why: v2.2 was strong but heavy (too much to remember, too many steps). Design: docs/superpowers/specs/2026-10-25-harness-v3-design.md.
- One `/go <slug>`: scripts/next.py decides the phase (PLAN, APPROVE, BUILD, STUCK, REVIEW, FIX, SHIP); the orchestrator
  carries out one instruction and stops. PLAN.md now holds the SCOPE and numbered steps, each with one `done when` check.
  `/approve` parses the plan and records the steps (scripts/harness_state.py); re-approval keeps unchanged done steps.
- Step recording in the safety-gate plugin: a step is done only when its exact check runs at the project root and exits 0. Failure (non-zero, error, timeout, kill) adds an attempt and keeps the last 40 lines. 2 failed checks = STUCK.
- Review freshness: the plugin records the REVIEW.md verdict and a hash of the project's code. The ship gate needs a
  recorded SHIP, a live REVIEW.md that says SHIP, and a matching hash. Max 2 review->fix rounds.
- `/status` and `.harness/dashboard.html` (scripts/status.py; self-refreshing, read-only). Credit per project is not on it.
- 14 agents -> 9, 20 commands -> 9. Removed: /scope /plan /build /blind /grill /whatif /learn /evolve /bench /map /browse
  /html2md /caveman /pr-review. New: /go /status /critique; /ship now also drafts the brain proposal. Models are set per
  agent in opencode.json only (Claude Haiku/Sonnet for orchestrator, planner, builder, hunter; after the live run also reviewer and brain on Haiku;
  free models critique and verify).
- Security: the builder's shell is `*: allow` (the sandbox is the control). `git push` and publish commands are denied by
  policy for every agent, but that is a speed bump; the sandbox now withholds push/publish credentials (~/.npmrc,
  ~/.pypirc, ~/.yarnrc.yml, git credential files, the keychain helper by name, the launchd ssh-agent socket). Known gap:
  a copied keychain helper or /usr/bin/security still works, so keep git HTTPS tokens out of the keychain. Write tools
  are confined to mini-projects/<slug>/, brain/proposals/ and RESEARCH/ for every session (workshop root too), with
  symlinks and different-case spellings of PLAN/REVIEW/CRITIQUE/BUGHUNT refused.
- Rules 020-gates, 050-mini-project, 060-ops and AGENTS.md follow the loop. Tests: bench, gate-test, state-test.

## v2.2 - 2026-10-24 - the audit backlog: recorded approval, shell sandbox, rule telemetry, /hunt fixes
- Recorded plan approval: human-typed `/approve <slug>` runs scripts/approve.sh (command template, no agent),
  which stores the PLAN.md sha256 in the project's .harness/state.json. The plan gate needs that hash to match
  (edit the plan = approval revoked) and now also covers shell redirects. Agents cannot write .harness/ or run
  approve.sh (plugin + policies; the script also refuses agent shells). RESEARCH/ is exempt (it was wrongly gated).
  Rules 020-gates and 050-mini-project updated.
- OS shell sandbox: safety-gate's shell create.before hook routes every shell through scripts/sandbox/agent-shell;
  agent shells (AGENT=1) run under sandbox-exec + agent.sb (write only the project / mini-projects, temp, caches;
  never .harness or .git hooks/config; no .env, ~/.ssh, *.pem, credential stores; secret env vars removed).
  Fails closed off macOS. Coder: python3/node now allow. /new and /bench run their script from the command
  template; orchestrator lost bash scripts/*. new-project.sh reads the goal from stdin (`-`). Rule 060-ops.
  gate-test fixture moved into the workshop (gitignored) because the sandbox allows temp dirs.
- Rule telemetry: brain-log counts rule-file reads and project first-seen in .harness/rule-usage.json (the
  plugin header claimed this before; no code did it). scripts/rule-report.py: uses, last use, new projects
  since, DECAY at 3 (always-loaded rules exempt); /evolve runs it from the command template. Every rule maps
  to evals in brain/evals/bench.yaml (`rules:`); 4 manual evals added; bench check rules-have-evals.
  Rule 040 and the brain agent's proposal format updated (new rules name an eval; stale /brain-apply removed).
- /hunt referee: Verified needs CONFIRMED + HIGH + skeptic `Severity: unchanged`; a changed or missing severity
  goes to Probable with the change shown (a guarded decoy was once listed as Verified).
- /hunt <slug> [focus] persists the referee report to the project's BUGHUNT.md (orchestrator may edit only that
  file; it is a plan-gate doc). Target = the project's uncommitted changes, else the whole project (an empty
  target used to mean the workshop's own diff). Rule 050 updated.
- Repo: CLAUDE.md (Claude Code handoff notes) untracked + gitignored. TELEPORT re-verified (bench 26/26, gate test
  56/56 from a clone); bootstrap.sh checks sandbox-exec and refuses a workshop inside a temp dir.

## v2.1 - 2026-10-23 - review kit installed (3 agents, 2 commands, 2 skills) + Claude skills isolated
- Moved from ~/Downloads/opencode-review-kit (no copies kept): agents code-reviewer, bug-hunter, bug-skeptic;
  commands /hunt, /pr-review; skills code-review, bug-hunt. Harness is now 14 agents, 19 commands, 9 skills.
- Integration fixes: kit /review renamed /pr-review (it would have replaced the gate-feeding /review); /hunt
  retargeted from the disabled `build` agent to the orchestrator, which may now spawn bug-hunter + bug-skeptic;
  placeholder models replaced (reviewer flint, hunter nemotron-ultra, skeptic deepseek: hunter and skeptic stay
  different families); repeat the secret-path and .git denies in each kit agent (an agent's own rules override the
  global ones); refusal rule added to each prompt.
- New policies: deny `git ... --output` and `rg ... --pre` for every agent (a "read-only" allow-list entry that
  writes files / runs commands; also closes it for the original agents). Anti-pattern recorded.
- Bench: knows the kit; new checks commands-agents-resolve and orchestrator-can-reach (would have caught the kit's
  `agent: build` and the old /map bug; negative-tested). models-resolve now also flags a missing model.
- Claude Code skills isolated: service env OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 + a global policy hiding the one
  skill under ~/.agents. opencode now sees only the harness skills + its two built-ins.
- Live test (seeded bugs): reviewer and skeptic correct; policy block verified; /hunt chain works end to end but
  listed one guarded edge case as verified (see HANDBOOK section 6).
- Rule 060-ops: opencode run reads $PWD, not the process cwd.

## v2.0 - 2026-10-23 - audit fixes: project-local install, gates that actually fire
Full findings: AUDIT.md (root). Evidence: docs/audit/.
- Install moved from global ~/.config/opencode to workshop-local .opencode/ (hot-reloaded, no
  install step). Global harness removed (archived in .archive/). install.sh + teleport.sh retired.
- 105 saved "always allow" approvals cleared (104 shell + 1 webfetch) (they overrode every ask, for every agent).
- Permissions rewritten: last-match-wins order, edit deny by default, root + **/ patterns,
  hard stops in `policies` (destructive git/rm, opaque bash -c/eval, sudo, curl uploads,
  opencode api). Code Mode `execute` denied in the permission layer (a policy deny does not
  hide the tool - verified live). Playwright pinned, --isolated, codemode off, unsafe tools denied.
- quiet-output.ts deleted: it silently truncated model-visible reads and subagent returns.
- safety-gate.ts rewritten: commit gate matches anywhere in a chain (&&, -C, env, subshell,
  merge/cherry-pick/revert); REVIEW verdict must be SHIP; plan gate keyed on the target's
  project; patch paths + relative/~ paths confined. Paths resolve from the plugin file.
- brain-log.ts rebuilt on the real v2 event API (AsyncIterable); logs to .harness/events.jsonl.
- Agents: models reassigned to ones verified responding (reviewer/critic/whatif were broken);
  devil/whatif persist DEVIL.md/WHATIF.md; brain writes proposals only; role-specific report
  contract (PROOF for builders, BASIS for analysts); /map /html2md /evolve /learn repaired.
- Template ships no gate files; new-project.sh takes the goal as data, fails loudly on git init.
- New scripts/gate-test.mjs (gates fire: 25 cases). bench.py rewritten: gates-fire, models-resolve,
  code-mode-off, no-global-harness, template-clean, run history + regression diff.
- Rule 060-ops rewritten with the permission/approval/Code Mode lessons; 050 updated.
- Anti-pattern fabricated-completion: an agent reported a write it never made. Every agent now
  writes before reporting; producing commands verify the file exists after the handoff.
  End-to-end scope -> plan -> build -> review then passed live (VERDICT: SHIP).

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

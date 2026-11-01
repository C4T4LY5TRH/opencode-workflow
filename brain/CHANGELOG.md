# Brain changelog

Format: `## vX.Y - date - one line what changed and why`

## v4.0-piece2-acceptance - 2026-11-01 - Task 15 live run (git course M1, real models, $13.71): 7 defects fixed, orchestrator on Sonnet
Why: the first real autopilot run found what no unit test could. Record: piece 2 spec §10.3 "Results (Task 15)".
- D1 the orchestrator ran a chain item's check in the same message as its worker (read the old file): check in the NEXT message; architect,
  designer, planner and critic run `status.py --check` themselves (permission added). Orchestrator Haiku -> Sonnet 5.5, variant low (user).
- D2 the agent sandbox refused `.git` even in temp: git-tool tests could only skip. `.git` writable under /private/tmp and /private/var/folders only.
  Builders never skip/weaken/delete a test to pass; they report BLOCKED.
- D3 the gate read heredoc bodies as redirects. D4 QA's verdict was recorded only when QA.md changed: QA writes it every VERIFY run.
- D5 the visual check flipped MATCH/FIX on the same code and promoted later work: FIX only for a broken DESIGN token, the accessibility floor or wrong behaviour.
- Bench reads agents/models with `--standalone` (the background service held a stale config) and has load-proof timeouts.
- Weight (production, excluding the brain removal): +57 / -19 lines, net +38. With the brain removal, the branch since the T15 handoff is net -125.
  Final production weight: safety-gate.ts 1141, next.py 1125, harness_state.py 1377, harness_docs.py 530 (at the T14 handoff: 1139 / 1118 / 1377 / 530).
- Suites: state-test 280, gate-test 291, bench 34 (mirror).

## v4.0-piece2-brain-removed - 2026-11-01 - the brain agent and its learning loop are gone: 12 agents
Why: the human's call ("remove brain totally; forgot what it even does"). The loop (/ship -> brain agent -> proposal -> human applies) was never used enough to earn its weight.
- Removed: the `brain` agent and its model entry and orchestrator route; the `/ship` proposal step; `brain/proposals/` and its write path in safety-gate;
  `/status brain` and the status line and dashboard fields for proposals and DECAY; `scripts/rule-report.py`, rule-usage telemetry in brain-log,
  `brain/evals/bench.yaml`, `brain/rules/040-learning.md`, `brain/patterns/`, `brain/anti-patterns/`; the reserved slug `brain`; the bench check `rules-have-evals`.
- Kept: `brain/rules/` (the rulebook), the `brain` skill (the rule loader), `brain/prompts/` (the skill points at them), brain-log (rule index in every request, session log),
  `brain/NOTES-pending-claude-key.md` (model notes, TELEPORT points at it), the folder name `brain/`.
- Added: bench check `brain-agent-gone`; the gate case w7 now expects a block on `brain/proposals/`.
- Weight removed (production files: .opencode/, scripts/ without tests, AGENTS.md, HANDBOOK.md): 282 lines deleted, 39 added, net -243;
  plus 106 lines of brain/ data files. Tests: gate-test 284 cases (was 289), state-test 279 (was 282), bench 34 (was 34: -1 `rules-have-evals`, +1 `brain-agent-gone`).

## v4.0-piece2 - 2026-10-31 - the build team: autopilot for a whole milestone, 3 steps at once, test-first QA, a designer with mockups, 13 agents, 11 commands
Why: after `/approve`, piece 1 still stopped after every step. Design: docs/superpowers/specs/2026-10-31-harness-v4-piece2-build-team-design.md.
- Autopilot: the first `/go` after approval runs the whole milestone (TESTS, BUILD, VERIFY, REVIEW, FIX) and stops at SHIP or at a stop
  (STUCK, REARCHITECT, a refused gate, `/stop`, the cost cap, the turn cap). The plugin sends the next `/go` itself and can send nothing else.
  Cost cap $10 per milestone (`/go cap <usd>`); the status line and the dashboard show the running cost, never the cap.
- Parallel build: next.py picks up to 3 ready steps (`after:`, folders, no shared path) for one batch; the plugin allows 3 open delegations and confines
  each builder to its own step's files; after every autopilot turn code compares all changed files with the allowed set ("exit scope" = a failed attempt).
- QA (new, Sonnet): failing acceptance tests per MUST feature first (the plugin must see them fail), a test-wrong request path, and VERIFY re-runs
  every step check on the final code. Designer (new, Opus): DESIGN.md and static HTML mockups in the approval hash (and the digest); at VERIFY it compares
  the running app (`scripts/preview.sh`, localhost only) with the mockups. Architect writes the `- preview:` command.
- Requests: a builder asks the researcher (`RESEARCH:`) or QA (`TEST-WRONG:`) through `requests/step<n>.md`; only that step waits.
- Also: `/stop`; the slug is optional everywhere (current project); `/go retry` accepts files after a scope failure; v3 mode removed; state saves keep
  `state.json.bak`; README.md counts as code; findings about the plan go under `## Plan notes` (never FIX FIRST); fact probes for read-only agents;
  worker reports capped at 10 lines; a root turn that ends without delegating frees its own lock.
- Final review fix wave: the designer may write its mockups before approval; at most one failed attempt per step per turn; a milestone with
  no MUST feature passes VERIFY without an acceptance run; agents are told sandboxes do not nest. Removed as weight: the dead `qa.revises`,
  the `sed -i` parser, the plugin's copy of the QA.md run parser, and the early review (B8, dropped by the user: no effect as built).
- Weight added (wc -l after the fix wave; was at harness-v4): scripts/next.py 1118 (677), scripts/harness_state.py 1377 (913),
  scripts/harness_docs.py 530 (338), .opencode/plugins/safety-gate.ts 1139 (610), scripts/status.py 323 (305), scripts/new-project.sh 119 (113);
  new: scripts/preview.sh 100, scripts/snapshot.py 99, scripts/live-mirror.sh 39. Tests: gate-test 289 cases (was 211), state-test 282 (183),
  bench 34 (32), rule-report 8 rules. The trim pass took 71 lines (2516 -> 2445 in the plugin, next.py and preview.sh), the fix wave 111 more
  (4275 -> 4164 in the plugin and the three Python libraries).

## v4.0-piece1 - 2026-10-29 - the front half: idea -> brainstorm -> architecture -> plan -> critique -> approval digest, 11 agents, 10 commands
Why: v3 started at a plan and felt clunky; v4's yardstick is "more capable, but light". Design: docs/superpowers/specs/2026-10-27-harness-v4-front-half-design.md; pieces 2-4: ...-roadmap.md.
- `/new <idea>` scaffolds and the new brainstormer drafts BRIEF.md (3-5 questions per round); `/brainstorm <slug> [topic|brief]` any time.
  `/go` locks the brief in code, then runs the chain: architect (ARCHITECTURE.md, risk R1 with a spike, milestones) -> planner (PLAN.md for the
  current milestone) -> critic (one CRITIQUE.md round) -> answers; code prints the approval digest (never a model summary). `/approve` records ONE
  hash over BRIEF + ARCHITECTURE (+ DESIGN) + PLAN and names every gap it refuses on; `/critique` asks for one more round.
- Stages (BRAINSTORM, ARCHITECT, PLAN, CRITIQUE, ANSWER, DECIDE, REARCHITECT, then the v3 BUILD/STUCK/REVIEW/FIX/SHIP, DONE) are computed in
  scripts/next.py. A failed spike -> REARCHITECT. 2 failed attempts at an automatic stage -> STUCK; `/go <slug> retry` clears it. `/ship` records
  the milestone shipped (trusted code); the next `/go` plans the next milestone. Approved v3 projects keep the v3 loop.
- Ground rules in code: project lock (30-minute expiry), circuit breaker (16 delegations per human turn, one at a time), parser feedback to the
  agent that wrote a bad file, write ownership for the new files, free text for /new and /brainstorm passed as data (a backtick cuts it: refused).
- Agents 9 -> 11 (brainstormer on Sonnet, architect on Opus; critic moved to Sonnet), commands 9 -> 10 (/brainstorm). Orchestrator and researcher on Haiku; reviewer and brain moved from Haiku to
  Sonnet (the human's call, 2026-10-30: the Haiku reviewer was unsteady, see below).
- Docs: HANDBOOK rewritten and trimmed from 165 to 110 lines; the security detail moved to AUDIT.md section 8b; AGENTS.md trimmed to pointers (5999 -> 5679 bytes).
- Live results (Task 2, spec section 14.1): the v3 FIX round, STUCK step and STUCK on fix rounds work; the Haiku reviewer is unsteady on identical code.
- Weight added (wc -l at f4b6914): scripts/next.py 682 (was 179 on harness-v4), scripts/harness_state.py 839 (was 332),
  scripts/new-project.sh 113 (was 93), scripts/harness_docs.py 338 (new file). Total of those four: 1972 lines, about 1330 more than before. Tests: gate-test 211 cases, state-test 176, bench 32, rule-report 8 rules.

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

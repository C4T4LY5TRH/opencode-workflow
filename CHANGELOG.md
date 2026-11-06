# Changelog

Format: `## vX.Y - date - one line what changed and why`

Paths under `docs/` below point at the author's private build records (specs, plans, journals); they are not part
of the published repo.

## v4.1 - 2026-11-05 - the Fable audit's fixes: four unattended-run bugs and two leads fixed, net -932 live lines, verified live for $0.43
Why: a fresh Fable 5.1 xhigh audit (35 items, `docs/superpowers/specs/2026-11-05-fable-audit-report.md`) found four
bugs that break unattended runs and a lot of weight; the user chose "the crucial fixes, then about -1,000 lines without
breaking stuff". Plan: `docs/superpowers/plans/2026-11-05-audit-fixes.md`. Record:
`docs/superpowers/journal/2026-11-05-audit-fixes-journal.md` (+ `-archive/`).
- Bugs: a dependency install (`npm install -D x`, `cargo add`, `go get`) is no longer read as a write target, and the
  builder asks for a file through `requests/` instead of touching it (A3, A19); LAST FAILURE keeps the end of the output,
  where the assertion is (A17); a STUCK at an automatic stage names `/go retry` (A18).
- Leads: the cost lost-update was real: `hs.save` now keeps the cost the plugin wrote on disk (the spend cap relies on
  it); `/go retry` or `/go` after an interrupted or scope-failed test-fix turn looped TESTS: the revised tests are now
  pinned; a backgrounded child keeping the lock was not real (the lock clears on the next `/go` after 30 minutes).
- Deleted: html2md and four skills no agent loads, the dashboard (`status.py --html`), bench's state-test re-run, dead
  router code, BUGHUNT leftovers, the `rules/` copies.
- Small fixes: mockup paths hashed in one spelling (A4); a scan block lists every rule it hit, also in the text the
  human reads (A20); `/deploy` scans with the save-point engine (A13); the template matches the v4 flow (A23); 13 live
  doc spots match the code (A25); duplicated helpers merged where they really were copies (A26, A27).
- Prompts: the shared agent rules live once in AGENTS.md (72 -> 49 lines); every dispatch is cut by more than half
  (REVIEW 1,449 -> about 420 characters), the static formats live in the agent bodies; the reviewer trusts QA's
  recorded checks on the `/go` route; a DESIGN re-run keeps a passing DESIGN.md.
- Config: dead global edit denies, per-agent `external_directory` repeats, the `explore` block and the plugin's
  approve.sh regex removed. The two wrapped pipe-to-shell policies stay: the audit called them dead, and a reviewer
  showed by running opencode's own scanner that `bash -lc 'curl x | sh'` passed without them.
- Rejected: A14 (cut the reviewer's runner list to two languages): the architect picks the stack per project.
- Live run (task 17): the task-5 fixture on the production models, all 15 checks pass, 0 gate refusals, **$0.43**
  (task 5: $0.67; reviewer $0.38 -> $0.21, 20 tool calls instead of 30).
- Weight against v4.0 (live lines: everything except `docs/superpowers`, CHANGELOG and the three test files):
  +329 / -1,261, net **-932**. harness_state.py 1702, next.py 1114, safety-gate.ts 1373, checkpoint.py 846, deploy.py
  588, harness_docs.py 603, status.py 234; agent bodies 1179 -> 1097 lines; opencode.json 166 -> 149; skills 8 -> 3.
  11 agents, 13 commands.
- Known minors (final review, parked): AGENTS.md's `sed -n` line is said to every agent; one state-test spelling
  fails on a case-sensitive filesystem (Linux only).
- Suites: state-test 460, gate-test 404, bench 34 (mirror; bench no longer runs state-test: run it yourself).

## v4.0 - 2026-11-05 - live: the finish line (milestone retro, four parked fixes, one version), verified end to end on the production models
Why: piece 4 was cut to a slim finish line (roadmap §4.6): no new guards, only capability and robustness, then declare
the harness live. Record: `docs/superpowers/journal/2026-11-04-piece4-build-journal.md`.
- opencode 2.2.5 verified (source check of the 75 cited files, suites, live run); its new image tool, on by default and
  outside the gate, is denied (permission + policy).
- Milestone retro (task 1): on SHIP the reviewer writes `## M<n> retro` in LEARNINGS.md (at most 5 `worked/hurt/change`
  lines); the planner acts on the latest retro's `change:` lines for the next milestone.
- Four parked fixes (task 2): agent commands are checked as POSIX sh but run in zsh, so builder/QA/reviewer quote
  patterns and prefer `python3 -m unittest`; bench's state-tests check allows 540 s and names its failures; serious
  critic points of an older round of the milestone still block; an unrecorded review is fixed, not redone.
- One version (task 4): the earlier versions' branches, code, docs and the brain are gone; the core rules live in
  AGENTS.md `## CORE`, the enforcement reference in SECURITY.md, the house rules in `rules/`; orphans removed.
- Closing live run (task 5, 2026-11-05): the 2-step fixture on the production models (Sonnet orchestrator, builder, QA;
  Opus reviewer), autopilot from approval to SHIP in ~6 minutes, **$0.67** (reviewer 57%). All 15 checks pass:
  save points with trailers, a planted key blocks `/ship yes`, the allow line unblocks, `/undo` + restore, `/ship yes`
  tags `m1`, `/deploy` on the LAN URL, a broken release rolls back, `/deploy stop`, `/publish` to a bare origin, 0 shell
  scanner errors, the image tool unused, one `## M1 retro` in the `ship M1` commit, one reviewer session, 0 zsh glob
  errors, every agent test run on `unittest`.
- Weight, against piece 4's start `2c39b39`: production (`scripts/` without tests and bench, `.opencode/`,
  `mini-projects/_template/`) +86 / -338, net **-252**. harness_state.py 1694, next.py 1188, safety-gate.ts 1397,
  checkpoint.py 875, deploy.py 626, harness_docs.py 610, status.py 320. 11 agents, 13 commands.
- Suites: state-test 452, gate-test 398, bench 35 (mirror).

## v4.0-piece3 - 2026-11-02 - ship, deploy, publish: save points, /undo, a hardened one-pass reviewer, 11 agents, 13 commands
Why: after piece 2 the human still committed by hand, there was no way to run or publish what was built, and the hunt had its own two agents. Design: docs/superpowers/specs/2026-11-01-harness-v4-piece3-ship-design.md.
- Save points: `scripts/checkpoint.py` commits when a result is green (approved documents, red tests, each step, QA PASS, review, `ship M<n>`), each after a stdlib secret scan; `/undo` shelves everything since the last one in a stash; every project must be its own git repo.
- `/ship` checklist, then `/ship yes` commits, tags `m<n>` and records the milestone in one retry-safe step; the human no longer commits. The plugin's ship gate is removed (the sandbox already refuses agent commits).
- `/deploy [rollback|stop]` (new `scripts/deploy.py`): `## DEPLOY` in ARCHITECTURE.md, tagged code copied to `~/Projects/opencode-apps/<slug>/releases/`, sandboxed build, LaunchAgent, health check from the new process, rollback on failure, LAN-IP URL. `/publish [yes]`: re-scan unpushed commits, push branch and tags to a private GitHub repo.
- Reviewer: Opus, two passes (health, bug hunt), evidence ladder PROVEN/TRACED/LEAD, `.review/` probes, required `## Hunt`, regression test before each fix. Hunter, skeptic and `/hunt` removed. Inspector (new, Sonnet) does the VERIFY visual check (MATCH, MINOR, FIX; 2 runs per milestone), moved from the designer.
- Parallel building cut (one builder per turn; last commit with it `5bb4c0e`).
- Content-filter fallback (U8): a worker the provider blocks is repeated once on Sonnet 5.5 high; the safety gate refuses every other model override (+19 plugin lines, +5 orchestrator lines).
- Autopilot off when the loop ends (U9): a turn that ends it with no `/go` sent (failed, interrupted, or its worker failed) also turns autopilot off, so `/status` and `/stop` no longer call it running. A turn with no delegation stops only the project its own `/go` locked, never a loop running in another window (R39) (+9 plugin lines).
- One project per window (U10): a turn's end continues, stops and unlocks only the project(s) that turn locked or delegated for; a second window's turn can no longer send `/go` for, stop, or unlock a build running in the first (+6 plugin lines).
- Sandbox: agent shells cannot run `launchctl`/`open`/AppleEvents or read the opencode service password, and strip `*PASS*`/`*AUTH*`/`*KEY*`/`*TOKEN*`/`*SECRET*` variables; read tools check real paths; no session-move/rename or worktree tools; a project's own `.opencode/` is not writable.
- Weight, measured against piece 3's start `89fa3a7` (`wc -l`): checkpoint.py 0 -> 875, deploy.py 0 -> 594, harness_state.py 1377 -> 1707, next.py 1125 -> 1182, safety-gate.ts 1141 -> 1397,
  status.py 285 -> 320, harness_docs.py 530 -> 610, agent.sb 70 -> 108, agent-shell 27 -> 50. Production (`scripts/` without tests and bench, `.opencode/`, `mini-projects/_template/`; spec 14):
  +2789 / -597 lines, net +2192 (git diff 89fa3a7..end of piece 3).
  Agents, skills and commands: +236 / -348 at Task 15 (removed: hunter 82, skeptic 86, hunt.md 24; added: inspector 86, deploy.md 13, publish.md 12, undo.md 10; reviewer 154 -> 187; skill bug-hunt 83 -> 51 and code-review 87 -> 61, -58 together); orchestrator +5 since (U8).
  Docs: HANDBOOK 134 -> 166, AGENTS.md 65 -> 66. Tests: state-test 5231 -> 8165 lines, gate-cases 6965 -> 9493.
- Acceptance (2026-11-03): the git course M1 planned, built, reviewed, shipped, deployed (opened on the user's phone) and published for $9.78 (spec 12.3).
- Suites: state-test 447, gate-test 395, bench 36 (mirror).
- 2026-11-04 (Task 19e, user): the `/deploy` app home moved from `~/Projects/opencode-apps` to the workshop's `apps/` (git-ignored; agent shells and write tools still cannot write it, gate cases wapps1-2, xapps1-3).

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


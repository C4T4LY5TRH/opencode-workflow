# HANDBOOK — the opencode one-person harness (v4: idea to shippable milestone)

How it works and how to drive it. Security detail: `AUDIT.md` §8b. Design: `docs/superpowers/specs/2026-10-27-harness-v4-front-half-design.md`, `2026-10-31-harness-v4-piece2-build-team-design.md` (+ `...-roadmap.md`).

## 1. What this is
A project-local opencode harness for one person vibecoding. Built for opencode **2.2.0** (the facts were read in 2.1.3 and diffed unchanged).
- **Idea to approved plan, with specialists:** a brainstormer writes the brief, an architect the architecture, a designer (UI projects) the design
  and mockups, a planner the plan, a critic attacks it. You approve one set of documents; only then can code be written.
- **Plan to shippable milestone, on autopilot:** after `/approve`, one `/go` builds the whole milestone: QA writes failing tests first, up to 3
  independent steps are built at once, QA re-runs every check, a reviewer reads it. Autopilot stops at SHIP, or earlier (see §2).
- **Code decides the routing and the checks** (`scripts/next.py`, `scripts/harness_state.py`); the model only carries out the instruction.
  A step is done when its check passes (the plugin sees it run), not when the builder says so. Outside this folder opencode is plain.

## 2. The flow
```
/new "an idea"          scaffold; brainstormer drafts BRIEF.md and asks 3-5 questions   (answer in chat, as many rounds as you like)
/go                     code locks the brief, then the chain: architect -> ARCHITECTURE.md, designer (UI) -> DESIGN.md + mockups,
                        planner -> PLAN.md (milestone M1), critic -> CRITIQUE.md round 1, answers; code prints the APPROVAL DIGEST. Stop.
/approve                YOU read the digest, open the mockups in your browser, read the files; one hash over BRIEF + ARCHITECTURE
                        + DESIGN and its mockups + PLAN; any edit revokes it
/critique               instead: one more critic round, then the digest again
/go                     AUTOPILOT: tests first, then the build (up to 3 steps at once), verify, review. It stops at SHIP.
/stop                   autopilot stops after the turn that is running (does nothing when autopilot is off)
/ship                   checklist; records the milestone shipped; YOU commit. Next /go plans the next milestone.
/brainstorm [topic]     any time: a topic round in BRAINSTORM.md; `/brainstorm brief` reopens a locked brief
```
The slug is optional on every command: no slug means the current project (the last one you named or created; the status line names it). `cap` and `retry` are `/go` words, so they cannot be project names.
Every stop prints a status line and the exact next command; lost? `/go` or `/status`. Stages are computed from files and state, never stored.
| Stage | Meaning | `/go` does |
|---|---|---|
| BRAINSTORM | brief not locked | locks it (refuses while questions are open or no [MUST] feature), else shows what is missing |
| ARCHITECT / DESIGN / PLAN / CRITIQUE / ANSWER | a document or critic round is missing, or a serious point is unanswered. DESIGN only if the brief says `ui: yes` | runs the chain from there (architect, designer if UI, planner, critic, answers). The designer may object to the UI stack once (back to the architect); a second objection goes to you in the digest |
| DECIDE | documents not approved or changed | prints the digest: MUST features, risk R1 and its spike, milestones, steps, every serious critic point with its answer, "Rejected serious points — you decide", the mockups to open |
| REARCHITECT | the spike step (step 1, `proves` R1) failed twice, or the brief changed after the architecture | architect revises, planner redoes the plan, new critic round, digest, `/approve` |
| TESTS | approved, no acceptance tests yet | QA writes one failing test per MUST feature of the milestone + QA.md and runs them once; the plugin must see them fail |
| BUILD | steps not done | up to 3 independent steps at once, one builder each, limited to its own files, each runs its exact check. A spike (M1 step 1) runs alone first. A builder that needs facts or thinks a test is wrong writes `requests/step<n>.md`: the researcher answers, or QA revises that test once |
| VERIFY | all steps done | QA re-runs EVERY step check and the acceptance tests (when the milestone has a MUST feature) on the final code (PASS or FAIL); UI: the designer opens the running app and compares it with the mockups (VISUAL.md MATCH or FIX) |
| REVIEW / FIX | no fresh review / FIX FIRST or a failed verify (max 2 fix rounds) | reviewer reads code, README and tests / builder fixes, then VERIFY again |
| SHIP / DONE | fresh SHIP review / every milestone shipped | stops: `/ship` / says so |
| STUCK | 2 failed checks, 2 fix rounds, 2 failed attempts at an automatic stage, an unreadable state | stops, shows why; fix the cause, then `/go retry` (stage) or `/approve` (step) |

**Autopilot** turns on with the first `/go` after approval and off at any stop: STUCK, REARCHITECT, SHIP, a refused gate, `/stop`, the cost cap, or
the turn cap (3 x steps + 10). A stop prints the reason and the exact next command. After every turn, code compares the changed files with the
files that turn was allowed to change; a step that touched others fails and counts as an attempt. `/go retry` accepts the files as they are and carries on into the next turn.
**Cost:** each status line shows the running cost of the milestone, never the cap. The cap is $10 per milestone; `/go cap <usd>` changes it, and
the stop message names that command. Esc cuts a running turn.
**Spikes that need a sandbox:** sandboxes do not nest. A spike that jails a program prints `JAIL: UNVERIFIED (nested sandbox)` inside the harness;
run it once yourself in a normal Terminal and see `JAIL: OK` before you sign the milestone off.

## 3. Layout
- `AGENTS.md` (loaded in every session here); `.opencode/` (opencode.json with models, permissions, policies; agents/ 12; commands/ 11; skills/; plugins/ safety-gate, brain-log (rule index, session log)).
- `scripts/`: next.py, harness_state.py, harness_docs.py, status.py, approve.sh, new-project.sh, preview.sh (starts a UI app for the designer) ...; `scripts/sandbox/` is the OS sandbox of every agent shell.
- `mini-projects/<slug>/`: its own git repo (`_template/` is the scaffold). BRIEF, BRAINSTORM, ARCHITECTURE, DESIGN, PLAN, CRITIQUE, QA, VISUAL, REVIEW, BUGHUNT are written by
  their agents; folders `design/` (mockups, screenshots), `tests/acceptance/` (QA's tests) and `requests/` are new. `.harness/state.json` and `.harness/lock`
  (gitignored, trusted code only) hold approval, steps, milestones, cost and the running chain.
- `brain/` (rules, prompts, CHANGELOG.md), `RESEARCH/`, `.harness/` (dashboard.html, events.jsonl, bench-history/; gitignored).

## 4. Commands (11)
| Command | Does | Writes |
|---|---|---|
| `/new <idea>` or `/new <slug>: <idea>` | scaffold (the script runs when you type it); brainstormer's first draft and questions | project dir, BRIEF.md |
| `/brainstorm [slug] [topic\|brief]` | another round (see §2) | BRIEF.md or BRAINSTORM.md |
| `/go [slug] [retry \| cap <usd>]` | the next action, chosen by `scripts/next.py`; after approval, autopilot | via workers |
| `/stop [slug]` | autopilot stops after this turn; no agent | `.harness/state.json` |
| `/approve [slug]` | **you** approve; runs `scripts/approve.sh`, no agent; names every gap it refuses on | `.harness/state.json` |
| `/critique [slug]` | one more critic round | CRITIQUE.md |
| `/ship [slug]` | checklist; records the milestone once its first status line says SHIP; you commit | state |
| `/status [slug]` | text status; the digest at DECIDE; refreshes the dashboard | `.harness/dashboard.html` |
| `/hunt [slug] [focus]` | hunter, skeptic, rule-based referee. *Verified* = skeptic CONFIRMS, HIGH, severity unchanged | BUGHUNT.md |
| `/review [slug]` | on-demand review, same reviewer | REVIEW.md |
| `/research <q>` | cited facts, pages, screenshots (into `RESEARCH/` of the project if the first word is one) | `RESEARCH/` |

**Free text warning (`/new`, `/brainstorm`):** type no backticks. A backtick cuts the text (the command refuses: "cut at a backtick");
a later `` !`...` `` in your text would run as its own command, outside the agent sandbox. A line that is exactly `HARNESS_TEXT_END`
ends the text early and the lines after it run in your shell. `$ARGUMENTS` is pasted raw into the template: type only text you trust.
**/ship:** the milestone is recorded when you type it and its checks pass. If checklist item 2 or 3 then fails, fix it and commit by hand; the record stays.

## 5. Agents (12)
`orchestrator` is the default and the only door; workers never spawn workers. Models live only in `agent.<name>.model` (effort: `.variant`) in `.opencode/opencode.json`
(no agent file has a `model:` line). Reports end `DID / PROOF|BASIS / BLOCKED / NEXT`, at most 10 lines. "Probes" = `git|node|npm|npx|python3 --version`,
`which`, `pwd`, `ls`. Builders get no browser.
| Agent | Model | Writes | Shell |
|---|---|---|---|
| orchestrator | claude-sonnet-5-5 (effort low) | `BUGHUNT.md` only | read-only |
| brainstormer | claude-sonnet-5-5 | `BRIEF.md`, `BRAINSTORM.md` | read-only |
| architect | claude-opus-5-5 | `ARCHITECTURE.md` | read-only + probes |
| designer | claude-opus-5-5 | `DESIGN.md`, `design/mockups/*.html`; at VERIFY `VISUAL.md`, `design/shots/**` | read-only + `scripts/preview.sh`; browser: localhost only |
| planner | claude-sonnet-5-5 | `PLAN.md`, `LEARNINGS.md` | read-only + probes |
| critic | claude-sonnet-5-5 | `CRITIQUE.md` | read-only |
| qa | claude-sonnet-5-5 | `tests/acceptance/**`, `QA.md` | any command (sandboxed) |
| builder (up to 3 at once) | claude-sonnet-5-5 | its step's files + `requests/step<n>.md`; never tests, documents, `.env`, `.git` | any command (sandboxed) |
| reviewer | claude-sonnet-5-5 | `REVIEW.md` (plan problems go under `## Plan notes`, never FIX FIRST), `LEARNINGS.md` | read-only git + test runners + probes |
| hunter | claude-sonnet-5-5 | `*bughunt*` repro tests (each asks) | read-only git; test runners ask |
| skeptic | opencode/deepseek-v4.1-flash-free | nothing | read-only git; test runners ask |
| researcher | claude-haiku-5-5 | `RESEARCH/**` | ls, cat, html2md.py; web + Playwright |
Free models vanish or hit limits: bench `models-resolve` checks; swap one in `opencode.json`.

## 6. State, digest, dashboard
`state.json` holds facts only; writers are `approve.sh`, `next.py`, the `/ship` template and the safety-gate plugin, never an agent. Each save keeps the last good copy as `state.json.bak`.
- **Step done:** the plugin sees the step's check run verbatim at the project root (whitespace ignored). Exit 0: `done_at`. Failure: `attempts` +1 (at most once per step per turn), `last_failure` = `exit <n>` and the last 40 lines. Limit 2.
- **Review and verify fresh:** the plugin records the REVIEW.md, QA.md and VISUAL.md verdicts and a hash of the code (README.md counts as code; other documents and `.harness/` do not); any code change makes them stale.
- **Limits in code:** 16 delegations per human turn, at most 3 open at once (steps that share a file run in order); one chain per project (lock, kept fresh while it works, expires after 30 minutes); 2 attempts per automatic stage; the cost cap and turn cap (§2).
  Dashboard: `.harness/dashboard.html`, one card per project with its running cost, read-only; rebuilt by `/go`, `/critique`, `/approve`, `/status`, `/ship`, `/brainstorm`.

## 7. Security in short (full table, push/publish and limits: `AUDIT.md` §8b)
Five layers: `policies` (hard denies), per-agent permissions (each agent writes only its own files), the safety-gate plugin (plan gate, ship gate,
write confinement, a builder confined to its step, circuit breaker, cost, and the autopilot loop that only ever sends `/go`), an OS sandbox around every agent shell
(macOS; writes only the project; no keys; never `.git`), and prompts.
"Operation not permitted" / "Blocked by configuration policy" = the sandbox or `policies` did its job. Push and publish are human-only. Your own `!cmd` is not sandboxed. Limits: grep/glob/Playwright are outside the sandbox; the plan gate misses
writes made by programs the builder runs (the after-turn file check catches them); the designer's browser can follow links inside the app's own pages; network stays open.

## 8. Ops
- Start opencode **in the workshop root**. Before and after any change, all green: `bash scripts/bench.sh`, `node scripts/gate-test.mjs`, `python3 scripts/state-test.py`. One logical change per commit. New machine: `TELEPORT.md`.
- The brain: `brain/rules/NNN-*.md` (agents cannot write them); you edit them by hand.
- Never `opencode run --auto` or "always allow" for broad commands. Do not edit `.opencode/` during a live test (hot reload). Outside the repo: service env `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`, a skill-hiding policy in `~/.config/opencode/opencode.json`, the Anthropic key (`! opencode auth login`).
- New agent or command: free name (an existing one is silently replaced), allow it under `task:` in `orchestrator.md`, add it to `scripts/bench.py`, set its model in `opencode.json`, start `permission:` from deny, run the bench.

## 9. When something goes wrong
| Symptom | Cause | Fix |
|---|---|---|
| "plan not approved or changed", "SAFETY GATE: plan gate" | documents not approved, or edited since | `/go`, read the digest, `/approve` — the gate is working |
| `/go` says STUCK | 2 failed checks / fix rounds / stage attempts | read the message; fix the cause; `/go retry`, or `/approve` for a step |
| autopilot stopped | a stop in §2 (the message says which) | do what the message says; `/go` starts it again |
| "exit scope: changed outside the step's files" | a step (or a program it ran) touched other files | look at the paths; if the change is fine or yours, `/go retry` accepts it and carries on |
| cost cap reached | the milestone spent its cap | `/go cap <usd>` to raise it, then `/go` |
| `/approve` REFUSED | brief unlocked, a file fails its format check, an unanswered serious point, a mockup that is not static, a revise or a requested critic round not run yet | it names each gap; fix it, retry |
| "a chain is running" (`/go`, `/critique`, `/approve`, `/ship`) | a chain's lock is held | wait; a crash leftover expires after 30 minutes; an unreadable lock: `/go retry` |
| "state unreadable" | `state.json` corrupt or hand-edited | copy `.harness/state.json.bak` over it, or delete `state.json` by hand, then `/go` |
| "SAFETY GATE: ship gate"; a step never turns done | code changed after the review, or verdict not SHIP; or the builder ran the check in another form | `/go` (reviews again, or repeats the exact command) |

## 10. Seen live
- Piece 1 acceptance run (2026-10-30, spec §14.2): `/new git-course: <idea>` → 2 brainstorm rounds → `/go` (6 delegations) → `/critique` (3) → `/approve`, $2.23 in all.
  The Haiku reviewer was unsteady (SHIP, FIX FIRST, FIX FIRST, SHIP on the same code), so the reviewer and the brain run on Sonnet (your call, 2026-10-30).
- Piece 2 (the build team) is built and unit-tested; its live acceptance run on the git course is not done yet.

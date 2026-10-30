# HANDBOOK — the opencode one-person harness (v4, piece 1: the front half)

How it works and how to drive it. Security detail: `AUDIT.md` §8b. Design: `docs/superpowers/specs/2026-10-27-harness-v4-front-half-design.md` (+ `...-roadmap.md`). v3: branch `harness-v3`.

## 1. What this is
A project-local opencode harness for one person vibecoding. Built for opencode **2.2.0** (the facts were read in 2.1.3 and diffed unchanged).
- **Idea to approved plan, with specialists:** a brainstormer writes the brief, an architect the architecture, a planner the plan, a critic
  attacks it. You approve one set of documents; only then can code be written.
- **Code decides the routing and the checks** (`scripts/next.py`, `scripts/harness_state.py`); the model only carries out the instruction.
  A step is done when its check passes (the plugin sees it run), not when the builder says so. Outside this folder opencode is plain.

## 2. The flow
```
/new "an idea"          scaffold; brainstormer drafts BRIEF.md and asks 3-5 questions   (answer in chat, as many rounds as you like)
/go <slug>              code locks the brief, then the chain: architect -> ARCHITECTURE.md, planner -> PLAN.md (milestone M1),
                        critic -> CRITIQUE.md round 1, architect/planner answer it; code prints the APPROVAL DIGEST. Stop.
/approve <slug>         YOU read the digest and the files; one hash over BRIEF + ARCHITECTURE (+ DESIGN) + PLAN; any edit revokes it
/critique <slug>        instead: one more critic round, then the digest again
/go <slug> (x many)     one step per /go: the builder builds it and runs its exact check; at the end the reviewer writes REVIEW.md
/ship <slug>            checklist; records the milestone shipped; YOU commit; the brain drafts a lesson. Next /go plans the next milestone.
/brainstorm <slug> [topic]   any time: a topic round in BRAINSTORM.md; `/brainstorm <slug> brief` reopens a locked brief
```
Every stop prints a status line and the exact next command; lost? `/go <slug>` or `/status`. Stages are computed from files and state, never stored.
| Stage | Meaning | `/go` does |
|---|---|---|
| BRAINSTORM | brief not locked | locks it (refuses while questions are open or no [MUST] feature), else shows what is missing |
| ARCHITECT / DESIGN / PLAN / CRITIQUE / ANSWER | a document or critic round is missing, or a serious point is unanswered. DESIGN only if the brief says `ui: yes`, there is no DESIGN.md and a designer agent exists (none in piece 1: it never fires yet) | runs the chain from there (architect, designer if any, planner, critic, answers) |
| DECIDE | documents not approved or changed | prints the digest: MUST features, risk R1 and its spike, milestones, steps, every serious critic point with its answer, and "Rejected serious points — you decide" |
| BUILD | a step has no `done_at` | builder builds it, runs its check |
| REARCHITECT | the spike step (step 1, `proves` R1) failed twice, or the brief changed after the architecture (`/brainstorm <slug> brief`, then `/go` re-locks it) | architect revises with the real failure or the new brief, planner redoes the plan, a new critic round, digest, `/approve` (refused until all of that has run) |
| STUCK | 2 failed checks, 2 fix rounds, or 2 failed attempts at an automatic stage | stops, shows why; fix the cause, then `/go <slug> retry` (stage) or `/approve` (step) |
| REVIEW / FIX / SHIP / DONE | no fresh review / FIX FIRST (max 2 rounds) / SHIP / every milestone shipped | reviewer / builder fixes / stops: `/ship <slug>` / says so |
An approved v3 project (plan hash, no ARCHITECTURE.md) keeps the v3 loop (PLAN, APPROVE, BUILD, STUCK, REVIEW, FIX, SHIP) unchanged.

## 3. Layout
- `AGENTS.md` (loaded in every session here); `.opencode/` (opencode.json with models, permissions, policies; agents/ 11; commands/ 10; skills/; plugins/ safety-gate, brain-log).
- `scripts/`: next.py, harness_state.py, harness_docs.py, status.py, approve.sh, new-project.sh ...; `scripts/sandbox/` is the OS sandbox of every agent shell.
- `mini-projects/<slug>/`: its own git repo (`_template/` is the scaffold). BRIEF, BRAINSTORM, ARCHITECTURE, PLAN, CRITIQUE, REVIEW, BUGHUNT are written by their agents;
  `.harness/state.json` and `.harness/lock` (gitignored, trusted code only) hold approval, steps, milestones and the running chain.
- `brain/` (rules, evals, proposals, CHANGELOG.md), `RESEARCH/`, `.harness/` (dashboard.html, events.jsonl, rule-usage.json, bench-history/; gitignored).

## 4. Commands (10)
| Command | Does | Writes |
|---|---|---|
| `/new <idea>` or `/new <slug>: <idea>` | scaffold (the script runs when you type it); brainstormer's first draft and questions | project dir, BRIEF.md |
| `/brainstorm <slug> [topic\|brief]` | another round (see §2) | BRIEF.md or BRAINSTORM.md |
| `/go <slug> [retry]` | the next action, chosen by `scripts/next.py` | via workers |
| `/approve <slug>` | **you** approve; runs `scripts/approve.sh`, no agent; names every gap it refuses on | `.harness/state.json` |
| `/critique <slug>` | one more critic round | CRITIQUE.md |
| `/ship <slug>` | checklist; records the milestone once its first status line says SHIP; you commit; brain drafts a lesson | state, `brain/proposals/` |
| `/status [slug\|brain]` | text status; the digest at DECIDE; brain proposals + DECAY rules; refreshes the dashboard | `.harness/dashboard.html` |
| `/hunt <slug> [focus]` | hunter, skeptic, rule-based referee. *Verified* = skeptic CONFIRMS, HIGH, severity unchanged | BUGHUNT.md |
| `/review <slug>` | on-demand review, same reviewer | REVIEW.md |
| `/research <q>` | cited facts, pages, screenshots (into `RESEARCH/` of the project if the first word is one) | `RESEARCH/` |

**Free text warning (`/new`, `/brainstorm`):** type no backticks. A backtick cuts the text (the command now refuses: "cut at a backtick");
a later `` !`...` `` in your text would run as its own command, outside the agent sandbox. A line that is exactly `HARNESS_TEXT_END`
ends the text early and the lines after it run in your shell. `$ARGUMENTS` is pasted raw into the template: type only text you trust.
**/ship:** the milestone is recorded when you type it and its checks pass. If checklist item 2 or 3 then fails, fix it and commit by hand; the record stays (no way back in piece 1).

## 5. Agents (11)
`orchestrator` is the default and the only door; workers never spawn workers. Models live only in `agent.<name>.model` in `.opencode/opencode.json`
(no agent file has a `model:` line). Claude does the thinking and research roles; one free model (skeptic) verifies bugs. Reports end `DID / PROOF|BASIS / BLOCKED / NEXT`.
| Agent | Model | Writes | Shell |
|---|---|---|---|
| orchestrator | claude-haiku-5-5 | `BUGHUNT.md` only | read-only |
| brainstormer | claude-sonnet-5-5 | `BRIEF.md`, `BRAINSTORM.md` | read-only |
| architect | claude-opus-5-5 | `ARCHITECTURE.md` | read-only |
| planner | claude-sonnet-5-5 | `PLAN.md`, `LEARNINGS.md` | read-only |
| critic | claude-sonnet-5-5 | `CRITIQUE.md` | read-only |
| builder | claude-sonnet-5-5 | code; no project document, `.env`, `.git` | any command (sandboxed) |
| reviewer | claude-sonnet-5-5 | `REVIEW.md`, `LEARNINGS.md` | read-only git + test runners |
| hunter | claude-sonnet-5-5 | `*bughunt*` repro tests (each asks) | read-only git; test runners ask |
| skeptic | opencode/deepseek-v4.1-flash-free | nothing | read-only git; test runners ask |
| researcher | claude-haiku-5-5 | `RESEARCH/**` | ls, cat, html2md.py; web + Playwright |
| brain (hidden) | claude-sonnet-5-5 | `brain/proposals/**` | read-only |
Free models vanish or hit limits: bench `models-resolve` checks; swap one in `opencode.json`.

## 6. State, digest, dashboard
`state.json` holds facts only; writers are `approve.sh`, `next.py`, the `/ship` template and the safety-gate plugin, never an agent.
- **Step done:** the plugin sees the step's check run verbatim at the project root (whitespace ignored). Exit 0: `done_at`. Failure: `attempts` +1, `last_failure` = last 40 lines. Limit 2.
- **Review fresh:** the plugin records the REVIEW.md verdict and a hash of the code (docs and `.harness/` excluded); any code change makes it stale.
- **Limits in code:** 16 delegations per human turn, one at a time; one chain per project (lock, expires after 30 minutes); 2 attempts per automatic stage. Dashboard: `.harness/dashboard.html`, one card per project, read-only; rebuilt by `/go`, `/critique`, `/approve`, `/status`, `/ship`, `/brainstorm`.

## 7. Security in short (full table, push/publish and limits: `AUDIT.md` §8b)
Five layers: `policies` (hard denies), per-agent permissions (each agent writes only its own files), the safety-gate plugin (plan gate, ship gate,
write confinement, circuit breaker), an OS sandbox around every agent shell (macOS; writes only the project; no keys; never `.git`), and prompts.
"Operation not permitted" / "Blocked by configuration policy" = the sandbox or `policies` did its job. Push and publish are human-only. Your own `!cmd` is not sandboxed. Limits: grep/glob/Playwright are outside the sandbox; the plan gate misses
writes made by programs the builder runs; network stays open.

## 8. Ops
- Start opencode **in the workshop root**. Before and after any change, all green: `bash scripts/bench.sh`, `node scripts/gate-test.mjs`, `python3 scripts/state-test.py`, `python3 scripts/rule-report.py --check`. One logical change per commit. New machine: `TELEPORT.md`.
- The brain: `brain/rules/NNN-*.md` (agents cannot write them); `/ship` makes ONE proposal in `brain/proposals/`; you apply it. `rule-report.py` flags `DECAY` after 3 projects without a read.
- Never `opencode run --auto` or "always allow" for broad commands. Do not edit `.opencode/` during a live test (hot reload). Outside the repo: service env `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`, a skill-hiding policy in `~/.config/opencode/opencode.json`, the Anthropic key (`! opencode auth login`).
- New agent or command: free name (an existing one is silently replaced), allow it under `task:` in `orchestrator.md`, add it to `scripts/bench.py`, set its model in `opencode.json`, start `permission:` from deny, run the bench.

## 9. When something goes wrong
| Symptom | Cause | Fix |
|---|---|---|
| "plan not approved or changed", "SAFETY GATE: plan gate" | documents not approved, or edited since | `/go`, read the digest, `/approve <slug>` — the gate is working |
| `/go` says STUCK | 2 failed checks / fix rounds / stage attempts | read the message; fix the cause; `/go <slug> retry`, or `/approve <slug>` for a step |
| `/approve` REFUSED | brief unlocked, a file fails its format check, an unanswered serious point, a revise or a requested critic round not run yet | it names each gap; fix it, retry |
| "a chain is running" (`/go`, `/critique`, `/approve`, `/ship`) | a chain's lock is held; it outlives a turn in which no delegation completed (orchestrator never delegated, all errored, or you interrupted the first) until it expires after 30 minutes | `/go <slug> retry` clears it; a declined or interrupted delegation keeps "one delegation at a time" refusing until that turn ends |
| "state unreadable" | `state.json` corrupt or hand-edited | v4 project: delete `.harness/state.json` by hand, then `/go`. v3 project: `/approve <slug>` again |
| "SAFETY GATE: ship gate"; a step never turns done | code changed after the review, or verdict not SHIP; or the builder ran the check in another form | `/go <slug>` (reviews again, or repeats the exact command) |

## 10. What changed from v3 (and live results)
v3 started at a plan; v4 piece 1 adds the front half in code: 9 agents became 11 (brainstormer, architect), 9 commands 10 (`/brainstorm`). New: brief lock, ARCHITECTURE.md, milestone plans, critic rounds with answers, the digest, one approval hash, REARCHITECT, `/go <slug> retry`, lock and circuit breaker, `/ship` records the milestone. Architect on Opus.
- Seen live in v4 (Task 2, spec §14.1): the FIX round, the STUCK step and STUCK on fix rounds all work; `/ship` with the Haiku brain works. The Haiku reviewer was unsteady (SHIP, FIX FIRST, FIX FIRST, SHIP on the same code), so the reviewer and the brain now run on Sonnet (your call, 2026-10-30). Open gaps for piece 2 (spec §14.1): a finding against PLAN.md burns the builder's fix rounds; docs-only fixes never clear FIX FIRST; earlier checks are not re-run after a fix; README promises go unchecked.
- Acceptance run (2026-10-30, spec §14.2): `/new git-course: <idea>` → 2 brainstorm rounds → `/go` (6 delegations) → `/critique` (3) → `/approve`, $2.23 in all. Every check printed OK, delegations ran one at a time, the lock was cleaned up, the architect ran on Opus. Fixed on the way: the digest hid a rejection when two files answered one point; the researcher's free model hit its limit (now Haiku).

# HANDBOOK — the opencode one-person harness (v4: idea to shippable milestone)

How it works and how to drive it. Security detail: `SECURITY.md`. Design: `docs/superpowers/specs/2026-10-27-harness-v4-front-half-design.md`, `2026-10-31-harness-v4-piece2-build-team-design.md` (+ `...-roadmap.md`).

## 1. What this is
A project-local opencode harness for one person vibecoding. Verified on opencode **2.2.5** (2026-11-04; the platform facts were read in 2.1.3 and re-checked for 2.2.0 and 2.2.5).
- **Idea to approved plan, with specialists:** a brainstormer writes the brief, an architect the architecture, a designer (UI projects) the design
  and mockups, a planner the plan, a critic attacks it. You approve one set of documents; only then can code be written.
- **Plan to shippable milestone, on autopilot:** after `/approve`, one `/go` builds the whole milestone: QA writes failing tests first, one step is built
  at a time, QA re-runs every check, a reviewer reads it. Autopilot stops at SHIP, or earlier (see §2). Every green result is saved as a git commit (§10).
- **Shipped, run, published:** `/ship yes` commits and tags the milestone, `/deploy` runs it on this Mac, `/publish` pushes it to a private GitHub repo (§11).
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
/go                     AUTOPILOT: tests first, then the build (one step at a time), verify, review. It stops at SHIP.
/stop                   autopilot stops after the turn that is running (does nothing when autopilot is off)
/ship                   checklist (nothing recorded); /ship yes commits, tags and records the milestone. Next /go plans the next one.
/deploy  /publish       run the shipped milestone on this Mac / push it to a private GitHub repo (§11)
/undo                   back to the last save point; your changes since are kept in a git stash (§10)
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
| BUILD | steps not done | one builder per turn, limited to its step's files; it runs its exact check. A UI step names the DESIGN sections to follow (`- design:`). A builder that needs facts or thinks a test is wrong writes `requests/step<n>.md`: the researcher answers, or QA revises that test once |
| VERIFY | all steps done | QA re-runs EVERY step check and the acceptance tests (when the milestone has a MUST feature) on the final code (PASS or FAIL); UI: the inspector opens the running app and compares it with the mockups (VISUAL.md MATCH, MINOR or FIX; MINOR passes. A run counts when it is issued; after 2, no verdict at all is STUCK; `/approve` gives the runs back) |
| REVIEW / FIX | no fresh review / FIX FIRST or a failed verify (max 2 fix rounds) | reviewer reads code, README and tests / builder adds a failing regression test, fixes, then VERIFY again |
| SHIP / DONE | fresh SHIP review / every milestone shipped | stops: `/ship` / says so |
| STUCK | 2 failed checks, 2 fix rounds, 2 failed attempts at an automatic stage, an unreadable state | stops, shows why; fix the cause, then `/go retry` (stage) or `/approve` (step) |

**Autopilot** turns on with the first `/go` after approval and off at any stop: STUCK, REARCHITECT, SHIP, a refused gate, `/stop`, the cost cap, or
the turn cap (3 x steps + 10), or a save-point block (§10). A stop prints the reason and the exact next command. After every turn, code compares the changed files with the
files that turn was allowed to change; a step that touched others fails and counts as an attempt. `/go retry` accepts the files as they are and carries on into the next turn.
**Cost:** each status line shows the running cost of the milestone, never the cap. The cap is $10 per milestone; `/go cap <usd>` changes it, and
the stop message names that command. Esc cuts a running turn.
**Sandboxes do not nest:** a spike that jails a program prints `JAIL: UNVERIFIED (nested sandbox)` here; run it once in a normal Terminal and see `JAIL: OK` before `/ship`.

## 3. Layout
- `AGENTS.md` (loaded in every session here); `.opencode/` (opencode.json with models, permissions, policies; agents/ 11; commands/ 13; skills/; plugins/ safety-gate).
- `scripts/`: next.py, harness_state.py, harness_docs.py, checkpoint.py (save points, scan, /undo, /publish), deploy.py, status.py, approve.sh, new-project.sh, preview.sh (starts a UI app for the inspector) ...; `scripts/sandbox/` is the OS sandbox of every agent shell.
- `mini-projects/<slug>/`: its own git repo (`_template/` is the scaffold). BRIEF, BRAINSTORM, ARCHITECTURE, DESIGN, PLAN, CRITIQUE, QA, VISUAL, REVIEW are written by
  their agents; folders `design/` (mockups, screenshots), `tests/acceptance/` (QA's tests) and `requests/` are new. `.harness/state.json` and `.harness/lock`
  (gitignored, trusted code only) hold approval, steps, milestones, cost and the running chain.
- `rules/` (the rulebook), `CHANGELOG.md`, `RESEARCH/`, `.harness/` (dashboard.html, bench-history/; gitignored).

## 4. Commands (13)
| Command | Does | Writes |
|---|---|---|
| `/new <idea>` or `/new <slug>: <idea>` | scaffold (the script runs when you type it); brainstormer's first draft and questions | project dir, BRIEF.md |
| `/brainstorm [slug] [topic\|brief]` | another round (see §2) | BRIEF.md or BRAINSTORM.md |
| `/go [slug] [retry \| cap <usd>]` | the next action, chosen by `scripts/next.py`; after approval, autopilot | via workers |
| `/stop [slug]` | autopilot stops after this turn; no agent | `.harness/state.json` |
| `/approve [slug]` | **you** approve; runs `scripts/approve.sh`, no agent; names every gap it refuses on | `.harness/state.json` |
| `/critique [slug]` | one more critic round | CRITIQUE.md |
| `/ship [slug]`, then `/ship [slug] yes` | checklist; then commit (`ship M<n>`), tag `m<n>` and record, in one step | git, state |
| `/undo [slug]` | shelve everything since the last save point | git stash |
| `/deploy [slug]`, `/deploy rollback\|stop [slug]` | run the last shipped milestone; go back one release; stop it | `apps/<slug>/` (not in git) |
| `/publish [slug]`, then `/publish [slug] yes` | re-scan unpushed commits; push branch and tags to a private GitHub repo | GitHub |
| `/status [slug]` | text status; the digest at DECIDE; refreshes the dashboard | `.harness/dashboard.html` |
| `/review [slug]` | on-demand review, same reviewer | REVIEW.md |
| `/research <q>` | cited facts, pages, screenshots (into `RESEARCH/` of the project if the first word is one) | `RESEARCH/` |

**Free text warning (`/new`, `/brainstorm`):** type no backticks. A backtick cuts the text (the command refuses: "cut at a backtick");
a later `` !`...` `` in your text would run as its own command, outside the agent sandbox. A line that is exactly `HARNESS_TEXT_END`
ends the text early and the lines after it run in your shell. `$ARGUMENTS` is pasted raw into the template: type only text you trust.
**/ship yes** records nothing unless the commit and the tag worked; if it says NOT RECORDED, fix the reason and type it again (safe to repeat). You never commit by hand.

## 5. Agents (11)
`orchestrator` is the default and the only door; workers never spawn workers. Models live only in `agent.<name>.model` (effort: `.variant`) in `.opencode/opencode.json`
(no agent file has a `model:` line). Reports end `DID / PROOF|BASIS / BLOCKED / NEXT`, at most 10 lines. "Probes" = `git|node|npm|npx|python3 --version`,
`which`, `pwd`, `ls`. Builders get no browser.
A worker the provider's content filter blocks ("Provider blocked the response") is repeated once on `anthropic/claude-sonnet-5-5#high`; any other model error stops (the safety gate refuses every other model override).
| Agent | Model | Writes | Shell |
|---|---|---|---|
| orchestrator | claude-sonnet-5-5 (effort low) | nothing | read-only |
| brainstormer | claude-sonnet-5-5 | `BRIEF.md`, `BRAINSTORM.md` | read-only |
| architect | claude-opus-5-5 | `ARCHITECTURE.md` | read-only + probes |
| designer | claude-opus-5-5 | `DESIGN.md`, `design/mockups/*.html` | read-only + probes |
| inspector | claude-sonnet-5-5 | at VERIFY `VISUAL.md`, `design/shots/**` | read-only + `scripts/preview.sh`; browser: localhost only |
| planner | claude-sonnet-5-5 | `PLAN.md`, `LEARNINGS.md` | read-only + probes |
| critic | claude-sonnet-5-5 | `CRITIQUE.md` | read-only |
| qa | claude-sonnet-5-5 | `tests/acceptance/**`, `QA.md` | any command (sandboxed) |
| builder (one per turn) | claude-sonnet-5-5 | its step's files + `requests/step<n>.md`; never tests, documents, `.env`, `.git` | any command (sandboxed) |
| reviewer | claude-opus-5-5 | `REVIEW.md` (plan problems go under `## Plan notes`, never FIX FIRST), `LEARNINGS.md` (on SHIP a 5-line `## M<n> retro` the planner reads for the next milestone), throwaway probes in `.review/` | read-only git + test runners + probes |
| researcher | claude-haiku-5-5 | `RESEARCH/**` | ls, cat, html2md.py; web + Playwright |
**The reviewer** does two passes in one run: health (spec, tests, security), then a bug hunt. It tries to disprove each suspect bug and labels survivors
PROVEN (a command it ran shows it), TRACED (exact path:line and input) or LEAD (a suspicion). Only PROVEN/TRACED can say FIX FIRST; leads are listed at `/ship`.
REVIEW.md needs a `## Hunt` line per lens; without it no verdict is recorded, and after 2 tries the stage is STUCK: `/go retry`.
Bench `models-resolve` checks the models exist; swap one in `opencode.json`.

## 6. State, digest, dashboard
`state.json` holds facts only; writers are `approve.sh`, `next.py`, the `/ship` template and the safety-gate plugin, never an agent. Each save keeps the last good copy as `state.json.bak`.
- **Step done:** the plugin sees the step's check run verbatim at the project root (whitespace ignored). Exit 0: `done_at`. Failure: `attempts` +1 (at most once per step per turn), `last_failure` = `exit <n>` and the last 40 lines. Limit 2.
- **Review and verify fresh:** the plugin records the REVIEW.md, QA.md and VISUAL.md verdicts and a hash of the code (README.md counts as code; other documents and `.harness/` do not); any code change makes them stale.
- **Limits in code:** 16 delegations per human turn, one open at a time; one chain per project (lock, kept fresh while it works, expires after 30 minutes; a turn frees and continues only its own project, so a crash leftover waits for the 30 minutes); 2 attempts per automatic stage; the cost cap and turn cap (§2).
  Dashboard: `.harness/dashboard.html`, one card per project with its cost, read-only; rebuilt by the commands.

## 7. Security in short (full table, push/publish and limits: `SECURITY.md`)
Five layers: `policies` (hard denies), per-agent permissions (each agent writes only its own files), the safety-gate plugin (plan gate,
write confinement, a builder confined to its step, circuit breaker, cost, and the autopilot loop that only ever sends `/go`), an OS sandbox around every agent shell
(macOS; writes only the project; no keys; never `.git`), and prompts.
"Operation not permitted" / "Blocked by configuration policy" = the sandbox or `policies` did its job. Agents cannot write `.git`, so only trusted scripts commit (no separate ship gate). Push and publish are human-only. Your own `!cmd` is not sandboxed. Limits: grep/glob/Playwright are outside the sandbox; the plan gate misses
writes made by programs the builder runs (the after-turn file check catches them); the inspector's browser can follow links inside the app's own pages; network stays open.

## 8. Ops
- Run the workflow through the service (the TUI attached to `opencode serve --service`), never `--standalone` (nor the TUI while the service is off) with an agent that has a shell: a standalone server keeps its password in its start environment, which any agent shell can read.
- Start opencode **in the workshop root**. Before and after any change, all green: `bash scripts/bench.sh`, `node scripts/gate-test.mjs`, `python3 scripts/state-test.py`. One logical change per commit. New machine: `TELEPORT.md`.
- Never `opencode run --auto` or "always allow" for broad commands. Do not edit `.opencode/` during a live test (hot reload). Outside the repo: service env `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`, a skill-hiding policy in `~/.config/opencode/opencode.json`, the Anthropic key (`! opencode auth login`).
- New agent or command: free name (an existing one is silently replaced), allow it under `task:` in `orchestrator.md`, add it to `scripts/bench.py`, set its model in `opencode.json`, start `permission:` from deny, run the bench.

## 9. When something goes wrong
| Symptom | Cause | Fix |
|---|---|---|
| "plan not approved or changed", "SAFETY GATE: plan gate" | documents not approved, or edited since | `/go`, read the digest, `/approve` — the gate is working |
| `/go` says STUCK | 2 failed checks / fix rounds / stage attempts | read the message; fix the cause; `/go retry`, or `/approve` for a step |
| autopilot stopped (`/status`: `autopilot off`) | a stop in §2 (the message says which), or a turn that failed or whose worker failed | do what the message says; `/go` (or `/go retry`) starts it again |
| "exit scope: changed outside the step's files" | a step (or a program it ran) touched other files | look at the paths; if the change is fine or yours, `/go retry` accepts it and carries on |
| cost cap reached | the milestone spent its cap | `/go cap <usd>` to raise it, then `/go` |
| `/approve` REFUSED | brief unlocked, a file fails its format check, an unanswered serious point, a mockup that is not static, a revise or a requested critic round not run yet | it names each gap; fix it, retry |
| "a chain is running" (`/go`, `/critique`, `/approve`, `/ship`) | a chain's lock is held | wait; a crash leftover expires after 30 minutes; an unreadable lock: `/go retry` |
| "state unreadable" | `state.json` corrupt or hand-edited | copy `.harness/state.json.bak` over it, or delete `state.json` by hand, then `/go` |
| stop "scan block" or "set your git name and email" | a save point found a secret, or git has no identity | fix the file, or add `path:rule` to `.harness/scan-allow`, then `/go`; or set `git config --global user.email` |
| `/ship yes` NOT RECORDED, or REFUSED "own repo" | stale review, a scan block, or the project folder has no `.git` of its own | do the command it names; type `/ship yes` again |

## 10. Save points, `/undo`
Code (never an agent) makes a git commit the moment a result is green, in the project's own repo, with your git identity. Each commit holds only that event's files:
`approved <sha>` (the documents incl. CRITIQUE.md; the first one also the scaffold), `M1 acceptance tests (red by design)`, `step 3: <title>`, `verify: QA PASS` (step files, `tests/`, QA.md; after a fix round
`fix round 1 verified: QA PASS`), `visual: MATCH`, `review: SHIP`, and at `/ship yes` `ship M1` (the whole tree). Stray edits stay uncommitted. `/status` shows `saved: step 3 · a1b2c3d`.
- **The secret scan** runs on every save point and every `/publish`. It blocks on private keys, known token formats, `.env`/`*.pem`/`*.key` files, a long mixed value assigned to a
  KEY/SECRET/TOKEN/PASSWORD name, and files over 50 MB. Emails, outside IPs and home paths only add a note. A block stops autopilot with the file and line: fix the file, or add
  `path:rule` (or `path:line:rule`) to `mini-projects/<slug>/.harness/scan-allow` (agents cannot write it), then `/go`.
- **Every project must be its own git repo** (`new-project.sh` makes it). Without one, save points, `/undo`, `/ship yes`, `/publish` and `/deploy` refuse.
- **`/undo`** shelves everything since the last save point in a stash and prints the restore line (`git stash apply <sha>`, run inside the project). It refuses while a turn
  is running or a scan block is open. Further back is by hand, autopilot stopped: check `git rev-parse --show-toplevel` prints the project folder, then `git stash push -u` and `git reset --hard <sha>`.
  Steps after `<sha>` still count as done: to rebuild one, change its title or check in PLAN.md and `/approve`. Never go back past `ship M<n>`. `git reflog` and `git stash list` get you back.

## 11. Ship, deploy, publish
- **`/ship`** lists the review's blind spots, its leads (unproven, never blocking) and the visual MINOR items: accept them or turn them into a step. **`/ship yes`** makes the final
  commit, tags `m<n>` and records the milestone. A tag already on this commit is fine (retry); a milestone ships once.
- **`/deploy`** needs `## DEPLOY` in ARCHITECTURE.md (`kind: service | none`, build, start, port 1024-65535 outside 4800-4899, health path, data). It copies the tagged code to
  `apps/<slug>/releases/<n>-m<k>/` in the workshop (git-ignored; agents cannot write it), builds it in the sandbox, starts it as the LaunchAgent `local.opencode-harness.<slug>`, and checks health from the new process.
  It prints `http://<LAN IP>:<port>` for your phone (Bonjour is off here; offline you get 127.0.0.1 and a warning: run `/deploy` again online, and if the IP changes).
  A failed deploy goes back to the release that was running. `/deploy rollback` goes to the newest good release older than the current one, so after a rollback and a new good
  deploy, a second rollback can land on a release you rolled away from. `/deploy stop` removes the LaunchAgent; releases and data stay (last 3 kept).
  If macOS asks whether the app may accept incoming connections, click Allow. The app is not sandboxed: the review and your `/approve` are the trust.
  Each checkout (main, mirror, worktree) has its own `apps/`, but there is one LaunchAgent per slug per Mac: a slug runs from one checkout at a time, and `/deploy`, `rollback` and `stop` in another checkout refuse, naming the one that runs it.
- **`/publish`** scans every commit not yet pushed (tags and merges too). With no `origin` it shows `gh repo create <slug> --private ...` and waits for `/publish yes`. It uses your own `gh` login.
- **A secret already pushed:** rotate the key first; that is the real fix (GitHub may still serve the old commit by hash). Then, by hand in the project, rewrite history (for example `git filter-repo --force --path <file> --invert-paths`),
  re-add `origin`, `git push --force origin <branch> --tags`, and delete each removed tag on GitHub: `git push origin :refs/tags/<tag>` (`/publish` never deletes or moves a remote tag).
- **Parallel building (removed):** piece 2 built up to 3 independent steps at once (`after:` lines, a batch picker). Piece 3 cut it: one builder per turn fails fast and is easier to follow. Last commit with it: `5bb4c0e`.

## 12. Seen live
- Git-course acceptance runs: piece 1 $2.23, piece 2 $13.71. Piece 3's live run is not done. Projects approved before piece 3 (git-course, a-small-tool-that-draws) have no `## DEPLOY` in ARCHITECTURE.md and fail its check: the architect revises, you `/approve` again.

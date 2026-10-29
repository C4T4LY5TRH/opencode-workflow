# HANDBOOK — the opencode one-person harness (v3)

How it works and how to drive it. Checks: `scripts/bench.sh`, `scripts/gate-test.mjs`, `scripts/state-test.py`.
Security: `AUDIT.md`, `docs/audit/`. Design: `docs/superpowers/specs/2026-10-25-harness-v3-design.md`. v2.2: branch `harness-v2`; v1: `docs/history/`.

## 1. What this is
A project-local opencode harness for one person vibecoding. Verified on opencode **2.1.3**.
- **One command to remember: `/go <slug>`.** It does the next thing and stops after each step. The routing is
  code (`scripts/next.py`); the model only carries it out.
- **A step is done when its check passes** (the plugin sees it run), not when the builder says so.
- **Gates in code.** Destructive commands, agent commits (you commit; `/ship`'s first status line checks the review is fresh), and code
  edits without an approved plan are blocked by config, a plugin and an OS sandbox (the plan gate sees the edit tools and simple shell redirects; see §7). Everything lives in `~/Projects/opencode`; outside it, opencode is untouched.

## 2. The loop
```
/new "a habit tracker"   scaffold the project
/go habit-tracker        planner writes PLAN.md (scope + steps)  -> stop
/approve habit-tracker   YOU read PLAN.md and approve it (recorded)
/go habit-tracker        builder builds step 1, runs its check   -> stop   (one step per /go)
/go habit-tracker        ... after the last step the reviewer writes REVIEW.md; FIX FIRST -> builder fixes (max 2 rounds)
/ship habit-tracker      checklist; YOU commit, push and publish; the brain drafts a lesson
```
| Phase | Meaning | `/go` does |
|---|---|---|
| PLAN / APPROVE | no PLAN.md / plan not approved or changed | planner writes it, or stops: read it, `/approve` |
| BUILD | a step has no `done_at`, fewer than 2 failed checks | builder builds it, runs its check |
| STUCK | 2 failed checks on a step, or 2 fix rounds used | stops, shows the failure; you decide |
| REVIEW | no fresh review | reviewer writes REVIEW.md |
| FIX | fresh review says FIX FIRST or REWORK | builder fixes the findings |
| SHIP | fresh review says SHIP | stops: `/ship <slug>` |

Every stop ends with a one-line status and the exact next command; lost? type `/go <slug>`. The phase is computed, never stored.
STUCK on a step: fix it by hand, then `/approve <slug>` (resets `attempts`; your `!cmd` is not recorded), then `/go <slug>`; or edit PLAN.md (smaller step, other check), then `/approve` (keeps unchanged done steps).

## 3. Layout
```
AGENTS.md                 loaded in every session under the workshop (voice, flow, gates)
.opencode/                opencode.json, agents/ (9), commands/ (9), skills/ (9), plugins/ (safety-gate, brain-log)
scripts/                  harness_state.py next.py status.py approve.sh new-project.sh bench.sh gate-test.mjs state-test.py ...
                          sandbox/ = agent-shell + agent.sb, the OS sandbox every agent shell runs in
mini-projects/<slug>/     its own git repo; _template/ is the scaffold
  BRIEF AGENTS README NOTES LEARNINGS RESEARCH/   scaffolded
  PLAN.md REVIEW.md CRITIQUE.md BUGHUNT.md        written by agents (PLAN holds the scope, REVIEW the blind spots)
  .harness/state.json                             approval, step results, review (gitignored; trusted code only)
brain/ (rules, evals, proposals, CHANGELOG.md), RESEARCH/ (workshop notes, gitignored), .harness/ (gitignored:
dashboard.html, plugins-alive, events.jsonl, rule-usage.json, bench-history/). opencode reloads `.opencode/` on save.
```

## 4. Commands (9)
| Command | Does | Writes |
|---|---|---|
| `/new "<goal>"` | scaffold; the script runs when you type it, the goal is passed as plain text | project dir |
| `/go <slug>` | the next action, chosen by `scripts/next.py` | via workers |
| `/approve <slug>` | **you** approve the current PLAN.md; runs `scripts/approve.sh`, no agent involved | `.harness/state.json` |
| `/ship <slug>` | ship checklist; you commit; then the brain drafts one lesson proposal | `brain/proposals/` |
| `/status [slug\|brain]` | text status (every project, one project with its steps and failure, or brain proposals + DECAY rules); refreshes the dashboard | `.harness/dashboard.html` |
| `/critique <slug>` | optional: the strongest case against the project + failure scenarios | `CRITIQUE.md` |
| `/hunt <slug> [focus]` | hunter, then skeptic, then a rule-based referee | `BUGHUNT.md` |
| `/review <slug>` | on-demand review, same reviewer as `/go`'s review phase | `REVIEW.md` |
| `/research <q>` | cited facts, pages, screenshots (into the project's `RESEARCH/` if the first word is a project) | `RESEARCH/` |

`$ARGUMENTS` is pasted raw into a command template before its `` !`...` `` shell runs; type only slugs you trust.
`/hunt`: *Verified* needs the skeptic to CONFIRM, confidence HIGH and severity unchanged; treat it as a strong lead.
The ship gate ignores CRITIQUE and BUGHUNT.

## 5. Agents (9)
`orchestrator` is the default and the only door. Models live in one place, `agent.<name>.model` in
`.opencode/opencode.json` (a `model:` line in an agent file would override it, so none has one). Claude does the
hard roles, the review, the brain and the critique (free limits stalled the loop); free non-Claude models verify bugs.

| Agent | Model | Writes | Shell |
|---|---|---|---|
| orchestrator | anthropic/claude-haiku-5-5 | `BUGHUNT.md` only (as `/hunt` referee) | read-only |
| planner | anthropic/claude-sonnet-5-5 | `PLAN.md`, `LEARNINGS.md` | read-only |
| builder | anthropic/claude-sonnet-5-5 | code; never PLAN/REVIEW/CRITIQUE/BUGHUNT, `.env`, `.git` | any command (sandboxed) |
| reviewer | anthropic/claude-haiku-5-5 | `REVIEW.md`, `LEARNINGS.md` | read-only git + test runners |
| critic | anthropic/claude-sonnet-5-5 | `CRITIQUE.md` | read-only |
| hunter | anthropic/claude-sonnet-5-5 | only `*bughunt*` repro tests (each write asks) | read-only git; test runners ask |
| skeptic | opencode/deepseek-v4.1-flash-free | nothing | read-only git; test runners ask |
| researcher | opencode/nemotron-3.5-super-vl-free (vision) | `RESEARCH/**` | ls, cat, html2md.py; webfetch + Playwright |
| brain (hidden) | anthropic/claude-haiku-5-5 | `brain/proposals/**` | read-only |

Builders report `DID / PROOF / BLOCKED / NEXT`, analysts `DID / BASIS / BLOCKED / NEXT`. Free models vanish or hit
"Free usage limit reached" without notice: bench `models-resolve` checks they exist; wait, or swap one in `opencode.json`. The 9 skills load on demand.

## 6. State and dashboard
`mini-projects/<slug>/.harness/state.json` holds facts only: plan hash, approval time, steps (`done_at`, `attempts`,
`last_failure`), the recorded review (verdict, tree hash) and `fix_rounds`. Writers: `approve.sh` (via
`harness_state.py`), `next.py` (fix rounds) and the safety-gate plugin. Agents cannot write `.harness/`.
- **Step done:** the builder runs the step's check verbatim, from the project root. The prompt says "as your LAST command" (a prompt rule); the plugin needs only the exact run at the project root, and skips a background run. The plugin
  compares it with the current step's check (whitespace ignored). Exit 0: `done_at` set. Failure (non-zero exit,
  error, timeout, kill): `attempts` +1, `last_failure` = last 40 lines. Other commands are ignored. Limit: 2 failures.
- **Review fresh:** when REVIEW.md is written the plugin records its verdict and a hash of the project's code (docs
  and `.harness/` excluded). Any code change after that makes the review stale. No VERDICT line removes the record.
- **Dashboard:** `.harness/dashboard.html`, one card per project, reloads every 5 seconds. Regenerated by `/go`,
  `/approve`, `/status`, `/ship` and by the plugin after a step result or a review. Read-only: no buttons, no
  server. Credit per project is not on it (needs a session-to-project mapping; not built).

## 7. Enforcement — five layers
| Layer | Where | What it guarantees |
|---|---|---|
| 1. Policies | `opencode.json` → `policies` | Hard deny for every agent, beats agent rules and saved approvals: destructive git/rm/disk commands, opaque `bash -c`/`eval`, `sudo`, curl uploads, agents driving `opencode api/auth/service`, writing `.harness/` or running `approve.sh`, unsafe Playwright tools, write/exec flags in "read-only" commands (`git --output`, `rg --pre`, `find -exec`/`-execdir`), and `git push` and publishing (speed bump, see below; `npm`/`pnpm`/`yarn publish`, `twine upload`, `gh release`). |
| 2. Permissions | `opencode.json` → `permission` + each agent's frontmatter | Deny-by-default editing; each agent writes only its own files; Code Mode (`execute`) denied; shell allow-lists per role. The builder's shell is `*: allow`, because layer 4 confines it. |
| 3. Plugin | `.opencode/plugins/safety-gate.ts` | Plan gate: the edit/write/patch tools and simple shell redirects (`>`, `>>`, `cp`, `mv`, `install`, `mkdir`, `touch`, `tee`) write no code in a project without the PLAN.md you approved, unchanged. Ship gate: an agent's commit, tag, merge, cherry-pick, revert, rebase or am (its shell call, matched by text) checks the project of its workdir (outside a project = refused; `git -C` and `cd` are not parsed; the sandbox refuses every agent write under `.git`, so an agent commit cannot happen at all) and needs a recorded SHIP verdict, a live REVIEW.md that says SHIP, and a matching code hash. Step and review recording (§6). Write confinement: write tools (every agent, every session, workshop root too) reach only `mini-projects/<slug>/`, `brain/proposals/` and the workshop `RESEARCH/`; symlinks and different-case spellings of PLAN/REVIEW/CRITIQUE/BUGHUNT are refused. |
| 4. OS sandbox | `scripts/sandbox/` (wired by the plugin's shell hook) | Every agent shell runs under macOS `sandbox-exec`: writes only the project (no project workdir, or `_template` = read-only), temp dirs and tool caches (`~/.npm`, `~/.cache`, `~/Library/Caches`), never `.harness/` or anything under `.git` (so agents never `git add`/`commit`; you do), no `.env`, `*.pem`, `~/.ssh`, `~/.aws`, `~/.gnupg`, `~/.config/gh`, `~/.netrc`, opencode's data. Also withheld: `~/.npmrc`, `~/.pypirc`, `~/.yarnrc.yml`, `~/.git-credentials`, `~/.config/git/credentials`, the macOS keychain git helper (blocked by name), the launchd ssh-agent socket. Secret-looking env vars are removed. Applies to `python3` and `node` too. Your own `!cmd` in the TUI is not sandboxed. |
| 5. Prompts | `AGENTS.md`, agent bodies | Voice, flow, report contract. Not a control on their own. |

**Push and publish.** The six `policies` denies are a **speed bump**: easy to bypass by spelling (`git -C . push`).
The real control is layer 4 withholding credentials. Residual risk: a sandboxed agent can copy the keychain helper
into its project and run it, or call `/usr/bin/security`. So do not keep a git HTTPS token in the macOS keychain for
repos you vibecode in; use ssh keys (the sandbox blocks `~/.ssh` and the agent socket). Custom ssh-agent sockets and
credential paths set by `$XDG_CONFIG_HOME` or `GIT_CONFIG` are not covered.

**Other limits.** The sandbox covers shell only: the grep/glob tools and the Playwright MCP server are not shell, so
a grep search could still show `.env` contents. Network stays open. macOS only; elsewhere agent shells are refused
(fail closed: "HARNESS SANDBOX: cannot sandbox this agent shell"). Scripts that write harness state run from the command template when you type the command, outside the
sandbox; agents cannot run them. The plan gate does not see writes made by a program the builder runs (`sed -i`, `python3 -c`, `node x.js`, `git apply`, `npm install`); the sandbox limits where they write, not whether a plan exists. The step's file list is a prompt-level rule; code does not enforce it. Gotchas: `brain/rules/060-ops.md`.

## 8. The brain
- `brain/rules/NNN-*.md`: one idea each; agents cannot write them. `/ship` makes the `brain` agent write ONE proposal
  in `brain/proposals/`; you apply what you approve (edit the rule and `brain/evals/bench.yaml`, run the bench).
- brain-log counts rule reads in `.harness/rule-usage.json`; `scripts/rule-report.py` (`/status brain`) flags `DECAY: propose delete` after 3 new projects without a read. Every rule needs an eval.

## 9. Ops
- Start opencode **in the workshop root**. Before and after any change, all green: `bash scripts/bench.sh`,
  `node scripts/gate-test.mjs`, `python3 scripts/state-test.py`, `python3 scripts/rule-report.py --check`. One logical
  change per commit. New machine: `bash scripts/bootstrap.sh` and `TELEPORT.md`.
- Never `opencode run --auto` here; never click "always allow" for broad commands (saved approvals override every
  `ask`). Do not edit `.opencode/` while a live test runs (it hot-reloads).
- Outside the repo: service env `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`, the skill-hiding policy in
  `~/.config/opencode/opencode.json`, saved approvals (empty on purpose), the Anthropic key (`! opencode auth login`).
- New agent or command: pick a free name (an existing command is silently replaced), allow it under `task:` in
  `orchestrator.md`, add it to `scripts/bench.py`, set `agent.<name>.model` in `opencode.json`, start its `permission:`
  from deny, run the bench. Broken frontmatter drops an agent silently.

## 10. Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| "plan not approved or changed", "SAFETY GATE: plan gate" | no PLAN.md, never approved, or edited since | `/go` (plan), read it, `/approve <slug>` — the gate is working |
| `/go` says STUCK | 2 failed checks on a step, or 2 fix rounds | read the failure; fix by hand or edit PLAN.md, then `/approve <slug>`, then `/go <slug>` |
| `/go` says "state unreadable" | `state.json` hand-edited or corrupt | `/approve <slug>` again |
| A step never turns done | the builder ran the check in another form | the INSTRUCTION gives the exact command and workdir; run `/go` again |
| "SAFETY GATE: ship gate" (stale, not SHIP, no VERDICT) | code changed after the review, or the verdict is not SHIP | `/go <slug>` to review again |
| "SAFETY GATE: write confinement" | a write outside the project, through a symlink, or a different-case file name | write inside `mini-projects/<slug>/` with the exact name |
| "Operation not permitted", "Blocked by configuration policy" | the OS sandbox or a `policies` hard stop did its job | intended; run it yourself (`!cmd` in the TUI) if legitimate |

## 11. What changed from v2
v2 had 14 agents, 20 commands and a loop you drove by hand. v3 keeps the v2.2 security core; the workflow runs on recorded state.
- `/go` replaces `/scope /plan /build /review /blind`; `/ship` absorbs `/learn`; `/critique` replaces `/grill /whatif`;
  `/review` replaces `/pr-review`; `/research` absorbs `/browse /html2md`; `/evolve` moved into `/status brain`;
  `/bench` is `bash scripts/bench.sh`; `/map` and `/caveman` are gone (caveman stays the default voice).
- 14 agents became 9 (scoper+architect = planner, coder = builder, three reviewers = reviewer, devil+whatif = critic);
  SCOPE.md and BLIND.md are gone (scope is in PLAN.md, blind spots in REVIEW.md).
- New: recorded steps and checks, `/status` + dashboard, the review tree hash (v2 allowed a commit after a SHIP review
  even if code changed since), models in one place, Claude for the hard roles.
- Security changes: the builder trusts the sandbox; push/publish are human-only (the sandbox withholds credentials);
  write confinement now covers workshop-root sessions and symlinks.

### Live-run results (v3, 2026-10-25: one tiny project, 3 steps, judged from the JSON event stream and disk)
- Verified: `/new`, `/go` plan, `/approve`, 3 x `/go` build, `/ship`. A step turned done only after the builder's exact check ran at the
  project root, exit 0; no permission asks; `/status` and dashboard matched `state.json`; policy refused `git push` and `npm publish`;
  a fresh-SHIP agent commit went through, and was refused as stale after a one-line edit (agents can no longer write `.git`).
- Not verified: `/go`'s review and `/ship`'s lesson (free reviewer and brain hit "Free usage limit reached"; the review ran on Haiku in its own session). Both are on Haiku now. No FIX or STUCK.
- Fixed: ship gate keys on the commit's workdir; `/ship` prints blind spots and git status itself; reviewer runs one command per call.
  Credit: $0.14 (sum of `session.step.ended` cost over 15 sessions; free models cost 0).

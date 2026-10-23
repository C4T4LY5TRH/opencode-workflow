# HANDBOOK — the opencode one-person harness (v2)

How it works and how to drive it. Every claim here is backed by a check in `scripts/bench.sh`
or by evidence in `docs/audit/`. The v1 handbook and build journal are in `docs/history/`.

---

## 1. What this is
A project-local opencode harness for one person vibecoding on free models.
- **One brain, many projects.** Rules in `brain/rules/`; lessons flow back via `/learn`.
- **Gates in code.** Destructive commands, commits without review, and code without a plan are
  blocked by config and a plugin, not by asking the model nicely.
- **Planning ≠ building ≠ reviewing.** Different agents, different model families.
- **Caveman voice.** Short answers; code, paths and errors verbatim.
- **Workshop only.** Everything lives in `~/Projects/opencode`. Outside it, opencode is untouched.

Verified on opencode **2.1.3** (see `AUDIT.md` §2 for the platform facts this depends on).

## 2. The loop
```
/new "goal" ─▶ scaffold (BRIEF, AGENTS, README, NOTES, LEARNINGS; NO gate files)
  /scope    ─▶ scoper      ─▶ SCOPE.md
  /research ─▶ researcher  ─▶ RESEARCH/*.md   (cited, optional)
  /plan     ─▶ architect   ─▶ PLAN.md
  /approve  ─▶ you type it ─▶ .harness/state.json (plan hash) ──┐
  /build    ─▶ coder       ─▶ code, one step  ◀── plan gate ─────┘  (editing PLAN.md revokes the approval)
  /review   ─▶ reviewer    ─▶ REVIEW.md (VERDICT: SHIP | FIX FIRST | REWORK)
  /blind    ─▶ critic      ─▶ BLIND.md
  /grill    ─▶ devil       ─▶ DEVIL.md        /whatif ─▶ whatif ─▶ WHATIF.md
  /ship     ─▶ checklist + you say yes ─▶ commit  ◀── ship gate (REVIEW=SHIP + BLIND)
  /learn    ─▶ brain       ─▶ brain/proposals/  ── you apply what you approve

optional, any time (reports; the ship gate ignores both):
  /hunt <slug> ─▶ bug-hunter ─▶ bug-skeptic ─▶ referee ─▶ BUGHUNT.md   find real bugs, then try to disprove each
  /pr-review   ─▶ code-reviewer                (chat only)              independent review of a diff / branch / PR
```
Each step writes a file. Gate files appear only when their owning agent writes them, so a new
project really has no plan until the architect writes one.

## 3. Layout
```
AGENTS.md                 loaded in every session under the workshop (voice, flow, gates)
.opencode/opencode.json   models default, permissions, policies, MCP, instructions, compaction
.opencode/agents/*.md     14 agents        .opencode/commands/*.md  20 commands
.opencode/skills/*/       9 skills         .opencode/plugins/*.ts   safety-gate, brain-log
brain/                    rules/ prompts/ patterns/ anti-patterns/ evals/ proposals/ CHANGELOG.md
scripts/                  new-project.sh approve.sh bench.sh bench.py gate-test.mjs gate-cases.json
                          bootstrap.sh html2md.py snapshot.py
scripts/sandbox/          agent-shell + agent.sb: the OS sandbox every agent shell runs in
mini-projects/<slug>/     each its own git repo; _template/ is the scaffold
  .harness/state.json     your /approve of the current PLAN.md (gitignored in the project)
.harness/  (gitignored)   plugins-alive, events.jsonl, rule-usage.json, bench-history/
```
opencode watches `.opencode/` and reloads on save. Runtime files live in `.harness/`, outside the
watched folder, so logging never triggers a reload.

## 4. Enforcement — five layers
| Layer | Where | What it guarantees |
|---|---|---|
| 1. Policies | `opencode.json` → `policies` | Hard deny for **every** agent, beats agent rules and saved approvals: destructive git/rm/disk commands, opaque `bash -c`/`sh -c`/`eval`, `sudo`, uploads with curl, agents driving `opencode api/auth/service`, agents writing `.harness/` or running `approve.sh`, unsafe Playwright tools, and the write/exec flags hiding in
"read-only" commands (`git diff --output=FILE` writes a file, `rg --pre CMD` runs a command). |
| 2. Permissions | `opencode.json` → `permission` + each agent's frontmatter | Deny-by-default editing; each agent may write only its own files; Code Mode (`execute`) denied for all; shell allow-lists per role. |
| 3. Plugin | `.opencode/plugins/safety-gate.ts` | Ship gate (commit/tag/merge/cherry-pick/revert anywhere in a command chain needs REVIEW.md with `VERDICT: SHIP` + BLIND.md). Plan gate (a code write in a project, by a write tool or a shell redirect, needs the PLAN.md you approved with `/approve`, unchanged since; keyed on the file's project; project docs and `RESEARCH/` are exempt). Approval is human-only (no agent writes `.harness/` or runs `approve.sh`). Write confinement (edit/write/patch/shell redirects stay inside the session's project). |
| 4. OS sandbox | `scripts/sandbox/` (wired by safety-gate's shell hook) | Every **agent** shell command runs under macOS `sandbox-exec`: it may write only the project it runs in (from the workshop root: `mini-projects/`), temp dirs and tool caches; never `.harness/`, `.git/hooks` or `.git/config`; it cannot read `.env` files, `~/.ssh`, `*.pem`, `~/.aws`, `~/.gnupg`, `~/.config/gh`, `~/.netrc` or opencode's own data. Secret-looking env vars (`*KEY*`, `*TOKEN*`, `*SECRET*`, …) are removed. This holds for `python3`/`node` too. Your own `!cmd` in the TUI is not sandboxed. |
| 5. Prompts | `AGENTS.md`, agent bodies | Voice, flow, report contract, "a refusal is the gate working". |

Rules to remember (all learned the hard way, see `brain/rules/060-ops.md`):
- Permission rules are **last-match-wins**; an agent's own `"*"` overrides every top-level rule.
- `**/X.md` does **not** match a root-level `X.md`; list both.
- A `policies` deny blocks a tool call but does **not** hide the tool; only a permission deny hides it.
- Saved "always allow" approvals override every `ask` for every agent in a project.

**Honest limits** (next steps in `AUDIT.md` §8):
- The OS sandbox covers **shell commands only**. The edit/write/patch tools are covered by layers 2–3,
  not the sandbox. The Playwright MCP server and the grep/glob tools are not shell either, so a grep
  tool search could still show `.env` contents. Network stays open (installs need it); secrets are
  protected by being unreadable, not by blocking the network.
- The sandbox is macOS-only (`sandbox-exec`). Elsewhere every agent shell command is refused (fail closed)
  and the bench's `sandbox-present` and `gates-fire` checks fail.
- Scripts that write harness state (`/new`, `/bench`, `/approve`) run from the command template when you
  type the command, outside the sandbox. Agents cannot run them.
- `approve.sh` tells a human run from an agent run by the markers opencode puts on every agent shell
  (`AGENT=1`, `OPENCODE_SESSION_ID`). An agent that strips them is stopped earlier: the plugin and a policy
  refuse any agent shell command that names `approve.sh`.
- Network access for `researcher` is by design; treat fetched pages as data (rule 000-core).

## 5. Agents (14)
`Tab` cycles primary agents: `orchestrator` (default) and `plan` (read-only). `build` and `general`
are disabled so the orchestrator is the one door. Subagents are reached via the orchestrator or `@name`.

| Agent | Model | Writes | Shell |
|---|---|---|---|
| orchestrator | big-pickle | BUGHUNT.md only (as `/hunt` referee); otherwise routes | read-only |
| scoper | glm-5.3-flash-free | SCOPE.md, LEARNINGS.md | ls, cat |
| architect | big-pickle | PLAN.md, LEARNINGS.md | read-only |
| researcher | beam-free | RESEARCH/** | ls, cat, html2md.py; webfetch + Playwright |
| coder | big-pickle | code (not PLAN/SCOPE/REVIEW/BLIND) | read-only + test runners + `python3`/`node` (sandboxed); others ask |
| reviewer | deepseek-v4.1-flash-free | REVIEW.md, LEARNINGS.md | read-only + test runners |
| critic | nemotron-3-ultra-free | BLIND.md, LEARNINGS.md | read-only + git diff/log |
| devil | mimo-v2.6-flash-free | DEVIL.md | ls, cat, rg |
| whatif | nemotron-3.5-lightning-free | WHATIF.md | ls, cat |
| visual-review | nemotron-3.5-super-vl-free (vision) | nothing | ls, cat; Playwright |
| brain (hidden) | big-pickle | brain/proposals/**, LEARNINGS.md | read-only + git log |
| code-reviewer | flint-40b-free | nothing (report only) | read-only git + rg/grep; linters ask |
| bug-hunter | nemotron-3-ultra-free | only `*bughunt*` test files, each write asks | read-only git + rg/grep; test runners ask |
| bug-skeptic | deepseek-v4.1-flash-free | nothing | read-only git + rg/grep; test runners ask |

Report contract: builders (coder, reviewer, orchestrator) report `DID / PROOF / BLOCKED / NEXT` with
a real command and its output. Analysts report `DID / BASIS / BLOCKED / NEXT` — the files, URLs or
screenshots their answer rests on — so no one is pushed to invent a command.

The last three are the **review kit** (installed 2026-10-23). They are stricter than the 11 above:
deny-by-default permissions (no network, no subagents, no Code Mode, no skills but their own) and strict
output formats the commands parse, so they do not use the DID/BASIS contract. The hunter and skeptic are
different model families on purpose: a verifier that shares the hunter's blind spots verifies nothing.

Free models disappear without notice. `bash scripts/bench.sh` checks every agent model against
`opencode models`; `brain/NOTES-pending-claude-key.md` says how to swap.

## 6. Commands (20)
All run through the orchestrator, which delegates.

| Command | Does | Writes |
|---|---|---|
| `/new <goal>` | scaffold from template, own git repo (the script runs when you type it; your goal is passed as plain text) | project dir |
| `/scope <slug>` | cut to MVP | SCOPE.md |
| `/research <q>` | cited facts | RESEARCH/*.md |
| `/plan <slug>` | ordered steps; reads DEVIL/WHATIF if present | PLAN.md |
| `/approve <slug>` | **you** approve the current PLAN.md; runs `scripts/approve.sh`, no agent involved | `.harness/state.json` |
| `/build <slug>` | next step only, verified | code |
| `/review <slug>` | review vs plan + scope, runs tests | REVIEW.md |
| `/blind <slug>` | blind-spot sheet | BLIND.md |
| `/grill <slug>` | strongest case against | DEVIL.md |
| `/whatif <slug>` | 5 failure scenarios | WHATIF.md |
| `/ship <slug>` | checklist, reviewer runs tests, you say yes | commit |
| `/learn <slug>` | lessons → proposal | brain/proposals/ |
| `/evolve` | rule report (usage, DECAY, evals) runs when you type it → prune/merge proposal + version bump proposal | brain/proposals/ |
| `/bench` | run the bench (runs when you type it, outside the sandbox) | .harness/bench-history/ |
| `/map <slug>` | structure via explore | nothing |
| `/browse <url>` | real browser, snapshot + screenshot | nothing |
| `/html2md <url>` | page → markdown via researcher | RESEARCH/ |
| `/caveman [mode]` | voice level | nothing |
| `/hunt <slug> [focus]` | bug hunt: hunter → skeptic → rule-based referee, on the project's uncommitted changes (else the whole project) | BUGHUNT.md |
| `/pr-review [target]` | independent review of a diff/branch/PR, runs as a background child session | nothing (chat report) |

`/review <slug>` and `/pr-review` are different tools. `/review` writes `REVIEW.md` with a `VERDICT: SHIP` line and
feeds the ship gate. `/pr-review` returns an advisory report in a different format (`APPROVE` / `REQUEST CHANGES`)
that the gate does not read. Use `/pr-review` for a second opinion, `/review` before shipping. `/hunt` writes its
report to the project's `BUGHUNT.md` (overwritten each run; commit it with the project if you want history).
`/pr-review` stays chat-only.

**How far to trust `/hunt`.** In the install test (two seeded bugs plus one guarded decoy, free models) it found both real
bugs and the skeptic spotted that the hunter's own repro was unreliable, but it listed the guarded decoy under *Verified*
because the referee read only confidence. Since v2.2 a bug is *Verified* only if the skeptic CONFIRMED it, the hunter's
confidence is HIGH **and** the skeptic left the severity unchanged; a downgraded (or missing) severity lands in *Probable*
with the change shown. Treat *Verified* as strong leads, not proof. A shell `ask` auto-rejects in headless runs, so repro
tests usually run only when you start `/hunt` from the TUI and approve them.

## 7. Skills (9)
`caveman` voice · `browser` Playwright driving · `visual-review` see-and-fix · `html2md` page →
markdown · `spec` spec-quality writing · `verify` proof before "done" · `brain` rule index ·
`code-review` and `bug-hunt` (the review kit playbooks; only their own agents may load them).
Skills load on demand.

**Your Claude Code skills are not visible to opencode.** opencode scans `~/.claude/skills` and `~/.agents/skills`
by default. This machine switches that off: `opencode service set env OPENCODE_DISABLE_CLAUDE_CODE_SKILLS 1`
(hides everything under `~/.claude`), plus a policy in `~/.config/opencode/opencode.json` hiding the one skill
in `~/.agents`. To undo: `opencode service unset env OPENCODE_DISABLE_CLAUDE_CODE_SKILLS`, then
`opencode service restart`.

## 8. Plugins (2)
- **safety-gate** — layer 3 above. Resolves the workshop from its own file path.
- **brain-log** — injects the brain pointer + rule index on every request (survives compaction) and
  logs session outcomes to `.harness/events.jsonl` using the v2 event stream, and counts rule reads
  into `.harness/rule-usage.json` (see §9).
Both write a heartbeat to `.harness/plugins-alive` when opencode loads them; the bench checks it.
`gate-test.mjs` sets `HARNESS_TEST` so a test run cannot fake that heartbeat.

## 9. The brain
- `brain/rules/NNN-*.md`: one idea each, ≤ 40 lines. `000-core` is always loaded via `instructions`.
- `/learn` and `/evolve` make the `brain` agent write a **proposal** in `brain/proposals/`.
  Agents cannot write `brain/rules/`. You read the proposal and apply what you approve.
- Promotion bar: 2 projects of evidence, or 1 hard failure. Unused for 3 projects → propose delete.
- **Usage is measured.** The brain-log plugin counts a rule as used each time an agent reads its file
  (read tool, or a shell command naming it), and stamps each mini project the first time a tool call
  touches it. `python3 scripts/rule-report.py` (what `/evolve` shows) prints, per rule: uses, last use,
  how many new projects started since, and `DECAY: propose delete` once that reaches 3. Rules loaded on
  every request (`000-core`) never decay. Reading a rule is the signal; whether it changed behaviour is
  what its eval checks.
- **Every rule has an eval.** The `rules:` map in `brain/evals/bench.yaml` names the checks for each rule
  (automatic bench checks or manual behavioural evals). The bench check `rules-have-evals` fails if a rule
  is missing there or names an eval that does not exist. A new rule ships with its eval (rule 040).
- `brain/CHANGELOG.md` records every version.

## 10. Scripts
| Script | Use |
|---|---|
| `bash scripts/bench.sh` | health: structure, policies, Code Mode off, models exist, sandbox present, **gates fire** (incl. the sandbox, run for real), template clean, no global copy; compares with the last run |
| `node scripts/gate-test.mjs` | replays `gate-cases.json` against the real plugin in a throwaway fixture, and tests `approve.sh` |
| `bash scripts/approve.sh <slug>` | what `/approve` runs: records the PLAN.md hash. Refuses inside an agent shell |
| `bash scripts/bootstrap.sh` | new-machine check: tools, `sandbox-exec`, workshop not in a temp dir, no global harness copy, Claude-skill isolation, then the bench |
| `GOAL="…" bash scripts/new-project.sh [slug]` | scaffold (what `/new` runs) |
| `python3 scripts/html2md.py <url> -o out.md` | page → markdown, stdlib only |
| `python3 scripts/snapshot.py <url> [-o shot.png] [--wait-for SELECTOR]` | screenshot |
| `python3 scripts/rule-report.py [--check]` | rule usage + DECAY + evals per rule (what `/evolve` shows); `--check` = every rule has a valid eval |

## 11. Ops
- Start opencode **in the workshop root**. Commands take a project slug.
- Edit anything in `.opencode/` → it applies on save. No restart, no install.
- Headless `opencode run` auto-rejects anything that would `ask`. Never use `--auto` with this harness:
  it approves every non-denied action.
- To check or clear saved approvals:
  `opencode api permission.saved.list -H "x-opencode-directory:$HOME/Projects/opencode"`.
- To change the harness itself, edit files here and commit (one logical change per commit), then run
  `bash scripts/bench.sh`.
- **Settings that live outside this repo** (they do not travel; `bootstrap.sh` checks them, TELEPORT.md lists them):
  the service env `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1`, the skill-hiding policy in `~/.config/opencode/opencode.json`,
  and opencode's saved approvals (kept empty on purpose).
- **Scripting `opencode run`** (tests, automation): it reads the working dir from `$PWD`, so set `PWD` as well as the
  process cwd; pass `--model` or the agent's own model is ignored; it cannot expand slash commands, so send the command
  text as the prompt. Run it with `--standalone` so it never touches your background service.
- Test runs leave sessions in opencode's session list. Delete your own with `opencode api DELETE /api/session/<id>`.

## 12. Adding an agent, command or skill yourself
Everything lives under `.opencode/` and is hot-reloaded on save. The recipe, with the traps this harness hit:

1. **Pick a name that is free.** `ls .opencode/commands .opencode/agents .opencode/skills`. A command with an
   existing name silently replaces it (the review kit's `review.md` would have overwritten the gate review).
2. **Write the file.**
   - Agent: `.opencode/agents/<name>.md`. Frontmatter needs `description`, `mode: subagent`, a real `model:` from
     `opencode models`, and a `permission:` block. Start from deny (`"*": deny`), then open only what the role needs.
     Rules are last-match-wins, and the agent's own rules override the global ones, so repeat any global denies you
     still want (secrets, `.git`).
   - Command: `.opencode/commands/<name>.md`, frontmatter `description` + `agent: orchestrator` (`build` is disabled),
     body = the instructions. `$ARGUMENTS` is what you type after the command.
   - Skill: `.opencode/skills/<id>/SKILL.md` with `name:` and `description:` in the frontmatter. The folder name is the id.
3. **Let the orchestrator reach it.** If a command delegates to a new agent, add `<agent>: allow` under `task:` in
   `.opencode/agents/orchestrator.md` and mention the role in its routing list.
4. **Register it in the bench.** Add the name to the lists at the top of `scripts/bench.py`. The bench then checks it
   exists, has valid frontmatter, uses a model that exists, and is reachable.
5. **Run `bash scripts/bench.sh`.** Any FAIL names the file. Fix, rerun.
6. **Try it for real** with one cheap task, then `git add -A && git commit`. One logical change per commit.

## 13. Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| A subagent fails with "Model unavailable" | free model removed | `bash scripts/bench.sh` names it; change `model:` in that agent file |
| "Duplicate plugin ID" or agents behave oddly | a harness copy in `~/.config/opencode` | remove it; `bootstrap.sh` detects this |
| Gates seem dead | plugin failed to load | check `.harness/plugins-alive`; bench `plugins-alive` + `gates-fire` |
| An agent or command vanished | broken frontmatter (YAML) is skipped silently | bench `frontmatter-valid` / `frontmatter-no-dupes` |
| "SAFETY GATE: plan gate. No PLAN.md" on /build | no PLAN.md in that project | run `/plan <slug>` first — the gate is working |
| "SAFETY GATE: plan gate. PLAN.md … is not approved" | you have not typed `/approve`, or PLAN.md changed since | read PLAN.md, then `/approve <slug>` |
| "SAFETY GATE: ship gate … not SHIP" | REVIEW verdict is FIX FIRST/REWORK | fix findings, `/review` again |
| `opencode run` in a script says `Agent not found` | it started in the wrong directory (`$PWD` was not set) | set `PWD` to the workshop/project dir, or `cd` first |
| `/pr-review` fails with "Endpoint is unavailable" | `flint-40b-free` is the least reliable free model | change its `model:` to `opencode/mimo-v2.6-flash-free`, run the bench |
| Your personal Claude skills show up in opencode | the service env is missing (new machine or reset) | run `bash scripts/bootstrap.sh`; it prints the fix |
| A command refuses with "Blocked by configuration policy" | a `policies` hard stop did its job | read the denied command; if it is legitimate, run it yourself in a terminal |
| Everything asks for permission | expected for anything off the allow-list | approve once in the TUI; avoid "always" for broad commands |
| An agent's command fails with "Operation not permitted" | the OS sandbox refused a write outside the project or a secret read | intended. If the write is legitimate, run it yourself (`!cmd` in the TUI is not sandboxed) |
| "HARNESS SANDBOX: cannot sandbox this agent shell" | not macOS, or `/usr/bin/sandbox-exec` missing | the harness needs macOS for agent shells; `bash scripts/bench.sh` shows `sandbox-present` |

## 14. Changes in v2.2 (what to try)
Each change below has automated tests (`node scripts/gate-test.mjs`, `bash scripts/bench.sh`) and was
also run live through real opencode on a throwaway project.

**1. Recorded plan approval — `/approve <slug>`.**
- What changed: `/plan` no longer counts a chat "yes". You read PLAN.md and type `/approve <slug>`. The command
  runs `scripts/approve.sh` directly (no agent in between), which stores the plan's sha256 in
  `mini-projects/<slug>/.harness/state.json`. The plan gate lets code be written only while PLAN.md still has that
  hash. If anyone edits PLAN.md (you or the architect), `/build` stops until you `/approve` again.
- Agents cannot approve: the plugin and a policy refuse any agent write under `.harness/` and any agent shell
  command naming `approve.sh`, and the script itself refuses to run inside an agent shell.
- The plan gate now also covers shell redirects (`echo … > src/app.js`), not only the write/edit/patch tools.
- Fixed on the way: `RESEARCH/` notes were blocked before a plan existed, so `/research` failed before `/plan`.
- Try it: `/new "…"` → `/scope` → `/plan <slug>` → `/build <slug>` (refused: not approved) → `/approve <slug>` →
  `/build <slug>` (works). Then add a line to PLAN.md and `/build` again (refused until you re-approve).

**2. OS sandbox for agent shells.**
- What changed: every shell command an agent runs now goes through `scripts/sandbox/agent-shell` (wired by the
  safety-gate plugin), which runs it under macOS `sandbox-exec` with `scripts/sandbox/agent.sb`. It can write
  only the project it runs in (from the workshop root: `mini-projects/`), temp dirs and tool caches. It can
  never write `.harness/` (your approvals) or `.git/hooks` / `.git/config` (code there would run later, outside
  the sandbox, when you use git). It cannot read `.env` files, `~/.ssh`, keys or credential stores. Secret-looking
  environment variables are removed first. Your own `!cmd` in the TUI is untouched.
- Because the OS now confines them, the coder may run `python3` and `node` without asking.
- `/new` and `/bench` now run their script directly when you type the command (like `/approve`), since those
  scripts write outside a project (`git init`, bench history). The orchestrator lost `bash scripts/*`.
  Your goal text reaches `new-project.sh` through a quoted heredoc: quotes, `$(...)` and `;` stay plain text.
- Try it: in a project, ask the coder to `cat .env`, or to run
  `python3 -c "open('$HOME/x.txt','w')"`. Both fail with "Operation not permitted". `node -e` writing a file
  inside the project works. In the TUI, `!cat .env` (you) still works.

**3. Rule-usage telemetry + an eval per rule.**
- What changed: the brain-log plugin now really counts rule usage (its header claimed it did, but no code
  did). Each time an agent reads a `brain/rules/NNN-*.md` file, `.harness/rule-usage.json` records the count
  and time; each mini project is stamped when first touched. `scripts/rule-report.py` turns that into a
  per-rule verdict: `keep`, or `DECAY: propose delete` once 3 new projects started without the rule being read.
  `/evolve` runs it when you type the command and hands the result to the brain agent as evidence.
- Every rule now names its eval(s) in `brain/evals/bench.yaml` (`rules:`). Four manual evals were added
  (verify, voice, research, learn). The bench's new `rules-have-evals` check keeps the map complete.
- Telemetry starts empty on purpose (test data was deleted). Expect `no data yet` until you have used it.
- Try it: run a project for a while, then `python3 scripts/rule-report.py` or `/evolve`.

**4. `/hunt` referee checks the skeptic's severity.**
- What changed: *Verified* now needs CONFIRMED + HIGH confidence + `Severity: unchanged` from the skeptic. If the
  skeptic changed the severity (or left the line out), the bug goes to *Probable — needs repro* and the report shows
  `severity: <hunter's> → <skeptic's> — <why>`. This is the case where a guarded edge case was once listed as verified.
- Try it: `/hunt <slug>` on a project with a real bug and a guarded decoy; the decoy should not appear under *Verified*.

**5. `/hunt` writes BUGHUNT.md.**
- What changed: `/hunt <slug> [focus]` now takes a project, like every other project command, and the orchestrator
  (the referee) writes the four sections plus the hunter's coverage to `mini-projects/<slug>/BUGHUNT.md`, then proves
  the file exists with `ls`. The orchestrator may edit that one file name and nothing else. BUGHUNT.md is a doc for
  the plan gate. The target is the project's uncommitted changes (git runs inside the project), else the whole
  project. Before, an empty target meant the *workshop's* diff, which never shows project code.
- Try it: `/hunt <slug>`, then open `mini-projects/<slug>/BUGHUNT.md`.

**Also in v2.2.**
- `CLAUDE.md` (notes for Claude Code sessions maintaining this repo) is no longer in git. opencode never reads it; a
  local copy stays on this machine, gitignored.
- `TELEPORT.md` re-verified with a fresh round trip (bootstrap all OK, bench 26/26, gate test 56/56 from a clone).
  New there: a Mac is required (sandbox), do not clone into a temp dir, re-`/approve` moved projects, copy
  `.harness/rule-usage.json` if you want to keep the decay history. `bootstrap.sh` checks the first two.

**What to test yourself before merging `harness-v2` into `main`:** one real project end to end:
`/new` → `/scope` → `/plan` → `/build` (refused) → `/approve` → `/build` … `/review` → `/blind` → `/hunt <slug>` →
`/ship`. Along the way, try one secret read and one out-of-project write through the coder (both should fail), and
run `/evolve` once you have a few projects.

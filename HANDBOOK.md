# HANDBOOK — the opencode one-man harness

Build journal + how-to. This file records **what was built, why, and how to drive it**.
`README.md` = quick orientation. This = the full record.

Everything here was verified by a command I ran. Paths, counts, and error strings are copied
from real output, not written from memory.

---

# PART 1 — WHAT EXISTS

## 1. What this is

A global opencode harness for a one-person vibecoding setup.

- **One brain, many mini projects.** Rules live in `~/.config/opencode/brain/`. Every project
  inherits them. Lessons from one project become rules for the next.
- **Gates enforced in code, not in prompts.** A smart model will route around a prompt-only
  rule. So the plan gate, the ship gate, and the destructive-command block live in
  permission rules + a plugin. Prompt says "don't". Code says "no".
- **Planning ≠ building ≠ reviewing.** Different agents, different models, different files.
  The planner cannot write code. The coder cannot approve the plan.
- **Caveman voice.** Short answers. Payload (code, paths, errors) verbatim.
- **Free only.** Every model in use is a free tier. No paid API required.

State today:

| Thing | Count | Where |
|---|---|---|
| Custom agents | 11 | `harness/agents/` |
| Commands | 17 | `harness/commands/` |
| Skills | 7 | `harness/skills/` |
| Plugins | 3 | `harness/plugins/` |
| Brain rules | 8 | `harness/brain/rules/` |
| Brain prompt fragments | 3 | `harness/brain/prompts/` |
| Bench checks | 27 | `harness/scripts/bench.py` |
| Brain version | v1.5 | `harness/brain/CHANGELOG.md` |

`opencode debug agents` shows **18** total = 7 built-in + 11 custom.

## 2. The loop

```
you type /new "url shortener"
        |
        v
  ORCHESTRATOR  (primary, big-pickle)  -- never writes code, only routes
        |
        |--- /scope ----> SCOPER      -> SCOPE.md      (IN / OUT / CUT LINE)
        |--- /research -> RESEARCHER  -> RESEARCH/*.md (cited facts)
        |--- /plan ----> ARCHITECT    -> PLAN.md       (steps, files, done-when)
        |--- /build ---> CODER        -> code          (ONE step, smallest diff)
        |--- /review --> REVIEWER     -> REVIEW.md     (findings, verdict)
        |--- /blind ---> CRITIC       -> BLIND.md      (blind spots)
        |--- /grill ---> DEVIL        -> attack the plan
        |--- /whatif --> WHATIF       -> failure scenarios
        |--- /browse --> VISUAL-REVIEW-> screenshot + SAW/BROKEN report
        |
        v
  /learn --> BRAIN (hidden) -> proposed rule diffs -> HUMAN approves
        |
        v
  /evolve -> prune + version bump
        |
        v
  /bench -> 25 checks + 3 manual evals -> numbers, not vibes
```

Every arrow is a slash command. Every arrow writes a file. A file is the proof that the step
happened. The gates check for those files.

## 3. Layout map

Repo `~/Projects/opencode` (the workshop):

```
AGENTS.md                  workshop rules (merged with the global AGENTS.md)
README.md                  quick orientation
HANDBOOK.md                this file
harness/                   SOURCE OF TRUTH - everything that gets installed
  AGENTS.md                global rules: caveman voice, gates, brain pointer
  opencode.json            global config: permissions, models, MCP, instructions
  agents/*.md              11 agent definitions
  commands/*.md            17 slash command definitions
  skills/*/SKILL.md        7 on-demand skills
  plugins/*.ts             3 runtime plugins (TypeScript)
  brain/
    rules/NNN-*.md         8 rule files, one idea each, <= 40 lines
    prompts/*.md           reusable prompt fragments
    patterns/              good reusable patterns (harvested)
    anti-patterns/         traps that already bit us
    evals/                 bench.yaml + baseline.md + last-run.json
    CHANGELOG.md           brain version history
    NOTES-pending-claude-key.md
  scripts/                 install.sh, bench.sh, bench.py, new-project.sh,
                           html2md.py, snapshot.py
mini-projects/
  _template/               the project shape template (12 files)
  <slug>/                  each = its OWN git repo
```

Installed live at `~/.config/opencode`:

```
AGENTS.md  opencode.json  workspace.txt
agents/  commands/  skills/  plugins/  brain/  scripts/
.backups/<timestamp>/      last 5 install snapshots, one place
```

`~/.config/opencode/workspace.txt` holds the workshop path. Scripts use it to find
`mini-projects/` without guessing.

## 4. Parts and how they connect

| Component | File | What it does | Feeds into |
|---|---|---|---|
| Global rules | `~/.config/opencode/AGENTS.md` | caveman voice, gate order, brain pointer | every session, every project |
| Core rule | `brain/rules/000-core.md` | 10 always-on rules (verify, no scope creep, cite, no secrets) | injected into every request context |
| Brain pointer | `plugins/brain-log.ts` | injects rule index on every request context | survives compaction |
| Orchestrator | `agents/orchestrator.md` | routes; never writes code (`edit: deny`, `shell` read-only) | all workers |
| Worker whitelist | `agents/orchestrator.md` `task` block | orchestrator may spawn the 10 named workers, `*` is deny | no unknown agent ever runs |
| Commands | `commands/*.md` | user entry points, each delegates to one agent | the right agent, the right file |
| Plan gate | `plugins/safety-gate.ts` + `opencode.json` permissions | blocks code writes with no `PLAN.md` | forces `/plan` before `/build` |
| Ship gate | `plugins/safety-gate.ts` | blocks `git commit` with no `REVIEW.md` / `BLIND.md` | forces `/review` + `/blind` |
| Dangerous block | `opencode.json` permission `shell` + `safety-gate.ts` | hard deny: `rm -rf /` `~` `/Users*` `/System*`, `git reset --hard`, `git push --force`, `git clean -f`, `git checkout .`, `DROP TABLE`, curl piped to sh, `chmod 777`, `mkfs`, `dd of=/dev/*` | deny = no prompt, no way through |
| Soft danger | `opencode.json` permission `shell` | ask (human decides): `rm -rf *` inside a project, `git push*`, `npm publish*` | prompt before it happens |
| File ownership | `agents/coder.md` `edit` rules | coder may not write PLAN/SCOPE/REVIEW/BLIND | each agent owns its file |
| Output contract | `brain/prompts/010-output-contract.md` | DID / PROOF / BLOCKED / NEXT | every agent's reply |
| Gate contract | `brain/prompts/020-gate-contract.md` | a refusal is reported, never routed around | prevents loophole hunting |
| Skills | `skills/*/SKILL.md` | on-demand procedures (browser, spec, verify, ...) | loaded only when the task needs it |
| Quiet output | `plugins/quiet-output.ts` | truncates huge tool output, keeps error lines | cheaper context |
| Heartbeat | all 3 plugins | write `brain/.plugins-alive` on load | bench proves gates are alive |
| Brain | `brain/rules/` + `CHANGELOG.md` | rules + version history | next project starts smarter |
| Bench | `scripts/bench.py` | 27 structural checks | `/bench`, release gate |
| Template | `mini-projects/_template/` | the scaffold | every new project |
| Install | `scripts/install.sh` | sync + backup + restart service | `~/.config/opencode` |

---

# PART 2 — HOW TO USE IT

## 5. Agents (11)

Custom agents. `mode: primary` = reachable from the Tab cycle. `mode: subagent` = reached by
`@name` or dispatched by the orchestrator. `hidden: true` = not offered in the picker.

`Tab` cycles primary agents only. Yours: `build`, `plan` (built-in) + `orchestrator`.
The other 10 are subagents: type `@coder`, `@reviewer`, `@critic`, ... or let the orchestrator
pick. `brain` is hidden on purpose — you should not summon it by hand, `/learn` calls it.

| Agent | Mode | Model | Writes | Use when |
|---|---|---|---|---|
| `orchestrator` | primary | big-pickle | nothing (routes only) | any project work. The default agent. |
| `scoper` | subagent | glm-5.3-flash-free | `SCOPE.md` | idea is fuzzy. IN max 5, OUT mandatory. |
| `architect` | subagent | big-pickle | `PLAN.md` | scope exists. Steps + file list + done-when. |
| `researcher` | subagent | flint-40b-free | `RESEARCH/*.md` | facts needed. Every claim carries a URL. |
| `coder` | subagent | big-pickle | code, one step | plan approved. Smallest diff that makes done-when true. |
| `reviewer` | subagent | minimax-m3.1-flash-free | `REVIEW.md` | after code. Verdict + ranked findings. |
| `critic` | subagent | minimax-m3.1-flash-free | `BLIND.md` | after review. Assumptions, unknowns, untested paths. |
| `devil` | subagent | glm-5.3-flash-free | nothing (argues) | before committing a direction. |
| `whatif` | subagent | longcat-2.5-preview-free | nothing (scenarios) | before shipping. SCALE / MISUSE / DEPENDENCY DIES / TIME / MONEY. |
| `visual-review` | subagent | nemotron-3.5-super-vl-free (vision) | nothing (looks) | any rendered UI. Reads a real screenshot. |
| `brain` | subagent, **hidden** | big-pickle | rule diffs (proposed) | project end via `/learn`. |

Model choices: free tier only. Big model for planning and code, small/fast models for critique
so they do not echo the planner's reasoning. **Diversity of models = more blind spots found.**
Full mapping + how to switch to a Claude key: `harness/brain/NOTES-pending-claude-key.md`.

The built-in 7 (`build`, `plan`, `compaction`, `explore`, `general`, `summary`, `title`) stay
available. `explore` is what `/map` uses.

## 6. Commands (17)

Every command has `agent: orchestrator` in its frontmatter, so the command runs *through* the
orchestrator and the orchestrator delegates. You never type an agent name to do work.

| Command | Does | Writes | Gate it holds |
|---|---|---|---|
| `/new <goal>` | scaffold project from template, own git repo | project dir | purpose gate: no goal, no scaffold |
| `/scope <proj>` | cut idea to MVP | `SCOPE.md` | IN max 5, OUT non-empty, CUT LINE |
| `/research <topic>` | gather cited facts | `RESEARCH/*.md` | every fact has a URL or is marked UNKNOWN |
| `/plan <proj>` | scope -> ordered steps | `PLAN.md` | needs `SCOPE.md`; human approval before code |
| `/build <proj>` | implement the NEXT step only | code | needs approved `PLAN.md` |
| `/review <proj>` | review code vs plan vs scope | `REVIEW.md` | verdict not REWORK, no open blocker |
| `/blind <proj>` | blind-spot sheet | `BLIND.md` | all 7 sections mandatory |
| `/grill <proj>` | devil attacks the plan | nothing | KILL CASE + assumption + cheapest hedge |
| `/whatif <proj>` | 5 failure scenarios | nothing | top 3 risks + max 3 prep items |
| `/ship <proj>` | run all gates, then ask | nothing | 7-point checklist, human says GO |
| `/learn <proj>` | lessons -> proposed rule diffs | proposed diffs | promotion bar; human approves |
| `/evolve` | prune stale rules, bump version | `CHANGELOG.md` | rules unused 3 projects get proposed for delete |
| `/bench` | run structural bench | `evals/last-run.json` | numbers, no vibes |
| `/caveman [mode]` | voice level: caveman / ultracave / normal | nothing | replies only, never payload |
| `/browse <url>` | real browser, snapshot + screenshot | nothing | report SAW / BROKEN / MISSING / FIX LIST |
| `/html2md <url>` | page -> clean markdown | `RESEARCH/<topic>.md` | <=10 bullets in the reply, file stays full |
| `/map <proj>` | structure, entry points, commands, gotchas | nothing | compact, no file dumps |

## 7. Gates (8)

From `brain/rules/020-gates.md`. Order is fixed. No skipping.

| # | Gate | File that proves it | What stops you if missing |
|---|---|---|---|
| 1 | PURPOSE | `BRIEF.md` (goal line) | `/new` refuses to scaffold without a goal |
| 2 | SCOPE | `SCOPE.md` | `/plan` refuses; agent reports "run /scope first" |
| 3 | PLAN | `PLAN.md` | **code write is blocked by the plugin** |
| 4 | CODE | one step, small diff | coder may not touch files outside the step list |
| 5 | REVIEW | `REVIEW.md` | **commit is blocked by the plugin** |
| 6 | BLIND | `BLIND.md` | **commit is blocked by the plugin** |
| 7 | PROOF | real command output, exit 0 | `/ship` fails the checklist |
| 8 | HUMAN | explicit "SHIP? yes" | `/ship` shows the commands and waits. Never auto-commits. |

Gates 3, 5, 6 are the ones in code. The rest are enforced by the command contract plus the
`/ship` checklist.

## 8. Skills (7)

Loaded on demand, not injected always. Cheaper than permanent context.

| Skill | Trigger | What it gives |
|---|---|---|
| `brain` | before non-trivial work | rule index + how to load only what the task needs |
| `caveman` | want terse output | voice rules, 3 levels, never caveman-ise payload |
| `browser` | JS-heavy page, UI check, scraping | Playwright MCP driving: navigate, snapshot, screenshot, forms, console |
| `visual-review` | after building UI | see-and-fix loop: screenshot, list what is broken, smallest fixes |
| `html2md` | static doc/article | page -> clean markdown, stdlib only, no npm |
| `spec` | fuzzy request, before building | goal / users / non-goals / flows / data / acceptance / risks / open questions |
| `verify` | about to say "done" | what counts as proof, what does not |

## 9. Plugins (3)

Runtime TypeScript. `ctx.tool.hook("execute.before")` throwing = tool call rejected.

| Plugin | Hook | Job |
|---|---|---|
| `safety-gate` | tool `execute.before` | destructive-command block, ship gate, plan gate, outside-project write block |
| `quiet-output` | tool `execute.after` | truncate >3000 char output to head + error lines + tail |
| `brain-log` | session `context` + event | inject brain pointer + rule index every request; append session log |

**Heartbeat.** Each plugin appends to `~/.config/opencode/brain/.plugins-alive` on setup.
The bench fails if a plugin load failure is newer than the newest heartbeat. This exists
because a plugin that fails to compile is *silently skipped* — the gates just vanish and
nothing complains. See Part 4, Bug A.

## 10. The brain

```
brain/rules/         8 files, one idea each, <= 40 lines
  000-core           always on, injected via config "instructions"
  010-voice          caveman output rules
  015-enforcement    gates live in code; never route around a refusal
  020-gates          the 8 gates and their order
  030-research       facts need URLs, static vs JS page handling
  040-learning       promotion bar, rule lifecycle, decay
  050-mini-project   project anatomy
  060-ops            service restart, headless ask-permissions, cwd vs session
brain/prompts/       000-index, 010-output-contract, 020-gate-contract
brain/patterns/      reusable good patterns
brain/anti-patterns/ traps that already bit us
brain/evals/         bench.yaml (ids + pass conditions), baseline.md (measured results)
brain/CHANGELOG.md   version history, one line per change
```

Lifecycle:

```
project breaks  ->  LEARNINGS.md  ->  /learn  ->  brain agent proposes diff
                 ->  HUMAN approves  ->  brain/rules/  ->  version bump + CHANGELOG
                 ->  /bench measures  ->  /evolve prunes what went unused
```

Promotion bar: **2 projects of evidence, or 1 hard failure** (data loss, security, shipped bug).
Decay: a rule unused for 3 projects gets proposed for deletion. The brain must shrink too.

## 11. Scripts

| Script | Command | Purpose |
|---|---|---|
| `install.sh` | `bash harness/scripts/install.sh` | sync harness -> `~/.config/opencode`, back up to `.backups/<ts>/`, restart the service, refresh `workspace.txt` |
| `bench.sh` | `bash ~/.config/opencode/scripts/bench.sh` | thin wrapper, runs `bench.py` |
| `bench.py` | (run via `bench.sh`) | 27 structural checks + print the 3 manual eval ids; saves `evals/last-run.json` |
| `new-project.sh` | `bash ~/.config/opencode/scripts/new-project.sh "<goal>" [slug]` | copy `_template/`, fill `{{SLUG}}`/`{{GOAL}}`, `git init` |
| `html2md.py` | `python3 ~/.config/opencode/scripts/html2md.py <url> [-o out.md]` | stdlib-only page -> markdown. Uses pandoc when present |
| `snapshot.py` | `python3 ~/.config/opencode/scripts/snapshot.py <url> [-o shot.png] [--text]` | Playwright CLI screenshot, prints path + byte size; `--text` also dumps markdown |
| `teleport.sh` | `bash harness/scripts/teleport.sh pack` / `unpack` / `verify` | move this harness to another machine: pack a bundle, unpack it, verify it |

Backups: one place only, `~/.config/opencode/.backups/<timestamp>/`, last 5 runs kept, older
pruned. Legacy scattered `.bak-*` files are migrated there on the next install. No `.bak`
file ever sits next to a live file.

---

# PART 3 — EXAMPLES

## 12. One project, end to end

Goal: a URL shortener. Every step below is a real command in this harness.

### Step 1 — purpose gate

```
/new url shortener
```

Runs `new-project.sh`, which copies `mini-projects/_template/`, fills the placeholders, and
`git init`s the new repo:

```
filled placeholders
created: ~/Projects/opencode/mini-projects/url-shortener
next: /scope
```

Files now present (from the template):

```
AGENTS.md  BLIND.md  BRIEF.md  LEARNINGS.md  NOTES.md  PLAN.md
README.md  RESEARCH/  REVIEW.md  SCOPE.md  opencode.json  .gitignore
```

12 files copied from the template, plus `.git/` from `git init`. The slug is derived from the
goal: `"url shortener"` -> `url-shortener` (lowercased, non-alphanumerics to dashes, first 5
words). Pass a second argument to override it.

`BRIEF.md` starts as:

```markdown
# BRIEF - url-shortener

## GOAL (human words)
url shortener
```

If the goal line is empty, `/new` asks and stops. No scaffold without a written goal.

`/new` also hands off to `@scoper` at the end, so a scope draft can start immediately.
`/scope` does the same thing on an existing project.

### Step 2 — scope

```
/scope url-shortener
```

`@scoper` writes `SCOPE.md`: IN (max 5 testable items), OUT (mandatory), LATER, CUT LINE, RISK.
The orchestrator then shows only IN / OUT / CUT LINE and asks for confirmation.

### Step 3 — plan

```
/plan url-shortener
```

`@architect` writes `PLAN.md` in this shape:

```markdown
## STEPS
### 1. store the slug
- goal: create the short-code table and insert path
- files: src/store.py, tests/test_store.py
- done when: pytest -q tests/test_store.py
- risk: sqlite locking under concurrent writes
## DATA (if any: shape + where stored)
## ACCEPTANCE (how human checks v1 works, exact commands)
## NOT DOING (echo of SCOPE OUT + any extra you cut)
```

Rules the architect follows: steps ordered so each leaves the repo working (no big-bang step);
"done when" must be a command, not "works well"; the file list is exact paths the coder will be
held to; anything outside SCOPE's IN list goes in NOT DOING; no code in the plan. If a step needs
a human decision (key, account, price) it is marked `BLOCKED-HUMAN` and stops there.

`/plan` refuses if `SCOPE.md` is missing. Nothing is written until the human approves.

### Step 4 — build (and the gate that bites)

```
/build url-shortener
```

`@coder` implements **only step 1**, then runs the done-when command and pastes real output.

Without `PLAN.md` this is refused by the plugin, verbatim:

```
SAFETY GATE: plan gate. No PLAN.md in project. Code cannot be written before a plan exists.
Run /plan, get human approval, then /build.
```

With `PLAN.md` present the write goes through and the file appears. This is the real captured
output from the gate regression test (a scratch project holding a `BRIEF.md` and a one-step
`PLAN.md`):

```
--- files (hello3 must EXIST now) ---
BRIEF.md   PLAN.md   hello.txt   hello2.txt   hello3.txt
```

`hello3.txt` exists only after `PLAN.md` was added. Before that, `hello3.txt` was absent and
the write was refused.

The coder cannot write the planner's files. Its `edit` permissions deny them:

```yaml
edit:
  "*": allow
  "**/PLAN.md": deny
  "**/SCOPE.md": deny
  "**/REVIEW.md": deny
  "**/BLIND.md": deny
```

### Step 5 — review + blind

```
/review url-shortener
/blind url-shortener
```

`@reviewer` writes `REVIEW.md` (verdict SHIP / FIX FIRST / REWORK, findings ranked
blocker/should/nice, each with `file:line` + smallest fix). `@critic` writes `BLIND.md` with
all seven sections mandatory.

### Step 6 — ship

```
/ship url-shortener
```

Checks 7 things (plan approved, scope respected, review verdict, blind risks owned, test
command passes, no junk staged, nothing pushed). Then shows the exact commit message and
git commands and asks:

> SHIP? yes/no

It does not commit until you say yes. And the commit itself is blocked by the plugin if
`REVIEW.md` is missing:

```
SAFETY GATE: ship gate. REVIEW.md missing. Run /review first. No commit without review.
```

### Step 7 — learn

```
/learn url-shortener
```

Reads `LEARNINGS.md` + `NOTES.md` + `brain/rules/*`. The hidden `brain` agent proposes
NEW / UPDATE / DELETE rules. You approve each one. Only approved items are written.

## 13. Gate refusals, verbatim

Real strings from `harness/plugins/safety-gate.ts`. Copy them if you need to.

**Plan gate** — code written without a plan:

```
SAFETY GATE: plan gate. No PLAN.md in project. Code cannot be written before a plan exists. Run /plan, get human approval, then /build.
```

**Ship gate** — commit without review:

```
SAFETY GATE: ship gate. REVIEW.md missing. Run /review first. No commit without review.
```

**Ship gate** — commit without blind-spot sheet:

```
SAFETY GATE: ship gate. BLIND.md missing. Run /blind first. No commit without blind spot check.
```

**Write outside project** — editing outside the project tree (template, not a captured run):

```
SAFETY GATE: write outside project blocked. Target: <absolute path outside the project>
Project: ~/Projects/opencode/mini-projects/<slug>
Write inside the project only.
```

**Shell write outside project** — the same idea for shell redirection. This one WAS captured,
when my own cleanup command tripped it:

```
SAFETY GATE: shell write outside project blocked. Path: /dev/null
Project: ~/Projects/opencode
Write inside the project only.
```

**Destructive command** (template, not a captured run):

```
SAFETY GATE: recursive delete of a system or home path blocked.
Command was: <the command you ran>
Do it yourself in a terminal if you really mean it.
```

Three of the six above were captured from real runs. The rest are the literal templates in
`harness/plugins/safety-gate.ts` with placeholders where a path would go.

What to do when a gate refuses:

1. Do NOT retry with another tool.
2. Do NOT change files to make the gate pass.
3. Quote the refusal, name the gate, say what would unblock it.

That is rule `020-gate-contract.md`, inlined in every agent prompt. A model that bypasses a
gate is worse than a model that stops.

## 14. Daily ops runbook

```bash
# change anything under harness/ -> install (it also restarts the service)
bash harness/scripts/install.sh

# verify the harness is intact
bash ~/.config/opencode/scripts/bench.sh
opencode debug agents
opencode debug config
```

The bench output ends like this:

```
BRAIN BENCH  v1.5  2026-10-22 11:38 UTC
passed 27 / 27   failed 0
  [PASS] core-rules-present     core rule file exists
  ...
  [PASS] plugins-alive          all 3 plugins reported a load heartbeat
  [PASS] plugins-no-load-failures no plugin load failure after the last heartbeat
  ...
  [PASS] config-hygiene         no scattered .bak files in the config dir
  [PASS] backups-one-place      backups live in .backups/
  [PASS] install-in-sync        installed harness matches the source tree

BEHAVIOURAL EVALS (manual - need a real task):
  [MANUAL] behavioural-scope    BEHAVIOURAL - agent writes SCOPE.md with OUT list non-empty
  [MANUAL] behavioural-blind    BEHAVIOURAL - critic refuses to skip BLIND.md sections
  [MANUAL] behavioural-ship-gate BEHAVIOURAL - /ship refuses without REVIEW.md + BLIND.md

last run saved: ~/.config/opencode/brain/evals/last-run.json
```

The 3 `[MANUAL]` rows need a real task. They are behavioural: structure cannot prove that an
agent refuses to skip a section. Run them by hand after a brain change.

The timestamp in the header is the run time. `last-run.json` stores the full result of every
check, so `/bench` can diff against the previous run and point at the rule that regressed.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Your change "does nothing" | opencode runs as a **background service**; config/plugins/agents are loaded at start | `opencode service restart` (or re-run `install.sh`) |
| `Agent not found: "coder"` | agent frontmatter is malformed — a broken YAML file is **silently dropped** | check `harness/agents/coder.md` starts with `---\n` and has no duplicate top-level keys; bench now catches both |
| Gates not firing at all | a plugin failed to compile and was skipped | `cat ~/.config/opencode/brain/.plugins-alive`; grep `~/.local/share/opencode/log/opencode.log` for `failed to load plugin`; bench checks both |
| A tool call rejected with "cannot ask the user for permission" | headless `opencode run` cannot answer `ask` | use allow-listed commands; the shell allow-list has `ls cat head tail wc rg grep find test echo pwd git status git diff git log node python3` |
| Gate blocks writing to `/dev/null` | shell write-target scan sees the redirection | `/dev/null`, `/dev/stdout`, `/dev/stderr`, `/tmp`, `/var/tmp` are whitelisted as harmless sinks |
| The gate thinks you are in the wrong project | the server cwd can differ from the session cwd | the plugin resolves the project from `ctx.location`, never `process.cwd()`. If it still guesses wrong, the session dir must sit directly inside `mini-projects/` |
| Agent wrote the wrong file | file ownership is per-agent | denied in the agent's `edit` block; the plugin also enforces a file-role plan gate |

## 15. The output contract

Every worker reports in this shape. It is inlined in all 11 agent prompts, so no file read is
needed to follow it.

```
DID
- <what actually changed>   (file paths, verbatim)

PROOF
- $ <command you ran>
  <real output, real exit code>

BLOCKED
- <what stopped you, and the ONE thing that unblocks it>

NEXT
- <single next action>
```

Rules: PROOF needs a command and output you actually saw. BLOCKED is not failure — a blocked
agent with a clear unblock is doing its job. No praise, no restating the request. If nothing
changed, say so in one line and stop.

---

# PART 4 — THE RECORD

## 16. Bugs found, and what they taught

**Bug A — the gates were dead for one hour.**
`safety-gate.ts` had a JS syntax error: `cmd.matchAll(>>?\s*...)` — a missing regex slash, so
the file did not compile. opencode **silently skipped** it. Every gate stopped working and
nothing said so.

Measured from the opencode log: 44 `failed to load plugin` warnings for `safety-gate.ts`,
from `2026-10-22T02:16:29.971Z` to `2026-10-22T03:16:22.594Z` — **60 minutes** of dead
gates. The cause in every one of them:

```
Cause([Die(BuildMessage: Unexpected >>)])
```

Found by the `coder` agent itself, which reported:

> **The plan gate is dead code for writes.**

*Fix:* every plugin now writes a load heartbeat on setup; the bench fails when a load failure
is newer than the newest heartbeat; the bench also greps the opencode log for
`failed to load plugin`. *Lesson:* never trust a gate you have not seen fire.

The bug was introduced in the v1.2 work (a new "block shell writes outside the project"
feature) and shipped in commit `ffec290`. The v1.0 plugin had no `matchAll` call and was fine.

**Bug B — the `coder` agent vanished.**
Its frontmatter lost its opening newline (`---description: ...` on one line). opencode dropped
the file without a word. `opencode debug agents` showed 17 instead of 18.

*Fix:* bench check `frontmatter-valid` over every agent and command.

**Bug C — duplicate YAML keys.**
My own edit added a second `"git status*"` key to `coder.md`. The strict parser rejected the
whole file. The agent vanished again, same silent way.

*Fix:* bench check `frontmatter-no-dupes`.

**Bug D — the gate blocked `/dev/null`.**
The shell write-target scan treated `> /dev/null` as an outside-project write. It blocked my
own cleanup commands.

*Fix:* whitelist `/dev/null`, `/dev/stdout`, `/dev/stderr`, `/tmp`, `/var/tmp`.

**Bug E — `install.sh` cancels its own command.**
`install.sh` restarts the opencode service, which kills the in-flight shell call. The command
reports "cancelled" even though the install succeeded.

*Lesson:* after `install.sh`, verify with `bench.sh` in a separate command.

**Bug F — gates by agent name do not work.**
The plugin hook payload carries an `agent` field, but it did not reliably hold the invoking
subagent. Agent-name gates were dead code.

*Fix:* the plan gate is now **file-role based** — project docs (`PLAN.md`, `SCOPE.md`,
`REVIEW.md`, `BLIND.md`, `NOTES.md`, `LEARNINGS.md`, `BRIEF.md`, `AGENTS.md`, `README.md`) are
always writable; everything else counts as code and needs `PLAN.md`. Ownership of the gated
docs moved to per-agent permission rules. The plan gate also only applies inside a mini
project, never in the workshop root where the harness itself lives.

**Bug G — the server cwd is not the session cwd.**
The service runs from `$HOME`. A plugin resolving paths from `process.cwd()` pointed at the
wrong directory and the gates fired on the wrong files.

*Fix:* resolve from `ctx.location`. Recorded in `060-ops`.

**Bug H — backups scattered.**
`install.sh` used to write `<file>.bak-<stamp>` next to every live file. Twelve of them
piled up in `~/.config/opencode/`.

*Fix:* one place, `~/.config/opencode/.backups/<timestamp>/`, last 5 kept; legacy `.bak-*`
migrated there on the next install.

**Bug I — the bench failed itself.**
Found while writing this handbook. The plugin-failure check searched the opencode log for the
phrase `failed to load plugin` anywhere in a line. But the log also records every shell
command you run. My own diagnostic `grep` command contained that phrase, got logged as a
`spawning process` line, and the bench counted it as a plugin failure: 24/25, with no
actual breakage.

*Fix:* match the event, not the substring — `level=WARN` AND `message="failed to load plugin"`.
*Lesson:* a scanner that reads logs must distinguish log records from log payloads.

**Bug J — editing the source does not change the live harness.**
I edited `harness/brain/CHANGELOG.md` to v1.5 and re-ran the bench. It still printed v1.4 —
because the bench reads the **installed** copy in `~/.config/opencode`, and I had not run
`install.sh`. The source and the live harness had silently diverged.

*Fix:* new bench check `install-in-sync` compares the source changelog version against the
installed one and fails with `source v1.5 vs installed v1.4 - run install.sh`.

## 17. What was deliberately NOT built

- **Peer-to-peer agent messaging** — opencode has no agent-to-agent channel. The orchestrator
  dispatches and waits. Good enough for one human.
- **Full session-state hooks** — opencode exposes only a subset of the Pi-style hook API.
- **Caveman Auto router** — BSL licence + account required. The voice rule + `quiet-output`
  plugin get 90% of the benefit for zero cost.
- **Autonomous brain rewrite** — `/learn` and `/evolve` propose; a human approves. A self-editing
  rule set eventually deletes the rules that matter.
- **External skill packs** (superpowers, ponytail, graphify, understand-anything, UI/UX Pro Max,
  impeccable, archify, awesome-claude-skills) — not installed. Practices were borrowed and
  re-implemented where they fit; licences and maintenance are on me, not on a dependency.
- **Paid APIs** — free tier only until the Claude key arrives.

## 18. Change log

Brain history: `harness/brain/CHANGELOG.md`. Measured behaviour: `harness/brain/evals/baseline.md`
(15 behavioural tests, all PASS). Eval definitions: `harness/brain/evals/bench.yaml`.
Last bench run is also written to `~/.config/opencode/brain/evals/last-run.json` so `/bench` can
compare against the previous run.

Repo history:

```
f3cfc27  brain v1.4: gaps closed (spec skill, prompts, snapshot, template, workshop rules)
         + 3 silent-failure bugs killed (plugin compile, frontmatter, dup keys)
29aea43  ignore .DS_Store
ffec290  harness v1.2: brain rules 015/060, bench hardened to 14 checks,
         install.sh stale cleanup + service restart
ceb111b  harness v1.0: 11 agents, 17 commands, 6 skills, 3 plugins, brain v1.0
```

The v1.5 commit (this handbook + the bench log-scan fix) came after the list above was
written. `git log --oneline` is the truth; this block is a snapshot.

`harness/tools/` exists but is empty and unreferenced — a leftover from v1.0 scaffolding.
Nothing reads it.

## 19. Next

```bash
opencode                      # start the TUI
/new "one line goal"          # purpose gate first
```

Then, at the end of a real project:

```
/learn <slug>     # propose brain rule diffs
/evolve           # prune, bump version
/bench            # prove the numbers
```

Model swap when the Claude key lands: `harness/brain/NOTES-pending-claude-key.md`. Four lines
in the agent frontmatter, or one `agent` block in `opencode.json`.

## 20. Moving to another machine

Full guide: **`TELEPORT.md`**. Short version:

```bash
# old machine
bash harness/scripts/teleport.sh pack            # -> harness-teleport-<ts>.tar.gz (~264 KB)

# new machine
bash harness/scripts/teleport.sh unpack <bundle> # -> $HOME/Projects/opencode
cd ~/Projects/opencode
bash harness/scripts/install.sh                  # rebuilds ~/.config/opencode
bash ~/.config/opencode/scripts/bench.sh         # -> 27/27
```

Do NOT copy `~/.config/opencode`. It mixes harness files with opencode's own files and with
machine-local runtime state (heartbeats, session logs). Stale heartbeats would make the bench
lie. The repo is the portable artifact: zero absolute paths, full git history, one script
rebuilds the live install.

The bundle carries `.git` too, so the target repo is a real clone with the whole history.
`workspace.txt` is written by `install.sh` from wherever you unpacked, so the repo can live
at any path.

# opencode-workflow

![A person conducts a ring of small AI agents (code, research, architecture, safety, testing), holding a glowing thread to each one.](assets/banner.png)

A personal, opinionated [OpenCode](https://opencode.ai) workflow: a team of AI agents that takes an idea from a brief
to a tested, deployed milestone, with the guardrails enforced in code rather than only asked for in prompts.

I vibecoded it in my spare time over a couple of weeks, as a learning exercise in how agent harnesses work. It is a
personal project, not a product.

> **Please don't copy it as is.** It is one person's setup on one Mac, tuned to how I work. Read it as a set of ideas
> and a working example, take the parts that are useful to you, and build your own on top.

## What it does
- **A specialist team.** 11 agents (orchestrator, brainstormer, researcher, architect, designer, planner, critic,
  builder, QA, inspector, reviewer), each with its own model, its own files it may write, and its own permissions.
- **Idea to approved plan.** A brief, an architecture, a design with mockups (for UI projects), a milestone plan, and a
  critic that attacks it. You approve one hashed set of documents; any later edit revokes the approval, and no code can
  be written without it.
- **Plan to shippable milestone, on autopilot.** One `/go` builds the whole milestone: QA writes failing tests first,
  one step is built at a time, every check is re-run on the final code, a reviewer reads it, and it stops at SHIP.
- **Code decides, not the model.** The next action, each stage and each check are chosen by Python
  (`scripts/next.py`, `scripts/harness_state.py`); a step is done when its check is seen to pass, not when an agent
  says so.
- **Guardrails in code.** A safety plugin checks every tool call; every agent shell runs in a macOS sandbox; each turn
  may change only the files its step allows; there is a per-milestone cost cap and a turn cap.
- **Save points and undo.** Every green result becomes a git commit after a secret scan; `/undo` goes back to the last
  one and keeps your changes in a stash.
- **Ship, run, publish.** `/ship yes` commits and tags the milestone, `/deploy` runs it on your Mac with a health check
  and automatic rollback, `/publish` pushes it to a private GitHub repo.
- **Tested like software.** About 460 state tests, 400 gate cases that replay the plugin and the sandbox for real, and a
  34-check bench. A small two-step test project runs from approval to SHIP for about $0.43 on the models it ships with.

## Requirements
- **macOS** (agent shells run in `sandbox-exec`; elsewhere every agent shell command is refused).
- **OpenCode 2.2.5** (the plugin relies on platform details checked against that version's source).
- **Node 22+, Python 3**, and Playwright's Chromium (`npx playwright install chromium`) for the UI checks.
- **An Anthropic API key.** The agents run on Claude (Opus, Sonnet and Haiku; set per agent in `.opencode/opencode.json`).
  You pay for the tokens: a real first milestone cost me about $9.

## Set up
```bash
git clone https://github.com/C4T4LY5TRH/opencode-workflow ~/Projects/opencode   # not inside /tmp
cd ~/Projects/opencode
opencode auth login            # choose Anthropic, paste your key (type it yourself)
bash scripts/bootstrap.sh      # checks the tools, the sandbox and the settings, then runs the bench
```
`TELEPORT.md` has the full setup, including two optional settings that live outside the repo.

## For AI agents
If you are an AI agent setting this up for someone, read **`TELEPORT.md`** first: it lists what lives in the repo,
what must be set up outside it, and the checks to run. Then read `HANDBOOK.md` (how the workflow runs) and
`SECURITY.md` (what each guardrail guarantees and what it does not). Let the person type their own API key
(`opencode auth login`; the workflow denies its agents access to it), and never approve "always allow" for broad
commands: saved approvals override every gate.

## Use it
```bash
cd ~/Projects/opencode
opencode                     # the orchestrator is the default agent
/new "your idea"             # scaffold; the brainstormer drafts BRIEF.md and asks questions (answer in chat)
/go                          # lock the brief; architect, designer, planner, critic run; code prints the approval digest
/approve                     # you read the digest, open the mockups, approve (or /critique for another round)
/go                          # autopilot: tests, build (one step at a time), verify, review; stops at SHIP
/ship                        # checklist; /ship yes commits, tags and records the milestone (/deploy, /publish, /undo follow)
```
The workflow lives in this folder only (`.opencode/`); outside it, OpenCode is plain OpenCode. Edits to `.opencode/`
apply on save; there is no install step.

## Commands (13)
```
/new "<idea>"     scaffold + first BRIEF.md draft   /status [slug]   where everything is
/brainstorm [topic|brief]  another round            /critique              one more critic round
/go [retry | cap <usd>]  next thing, or autopilot
/approve          you approve the documents         /review                REVIEW.md on demand
/ship [yes]        checklist; yes commits + tags     /research <q>          RESEARCH/ (cited)
/deploy [rollback|stop]  run the shipped milestone here   /publish [yes]  push to a private GitHub repo
/undo             back to the last save point
/stop             autopilot stops after this turn   (the slug is optional everywhere: none = current project)
```

## Layout
```
AGENTS.md            rules loaded in every session here (voice, flow, gates)
.opencode/           what OpenCode loads: opencode.json (models, permissions, policies), agents/, commands/, skills/, plugins/
rules/               the rulebook (agents load what a task needs: skill `rules`)
scripts/             routing and state (next.py, harness_state.py, harness_docs.py), save points (checkpoint.py),
                     deploys (deploy.py), status.py, the macOS sandbox (sandbox/), setup and the three test suites
mini-projects/       one folder = one project = its own git repo; _template/ is the scaffold
.harness/            runtime state (gitignored): plugin heartbeat, events log, bench history
```

## Docs
- `HANDBOOK.md`: how it works and how to drive it (the flow, stages, agents, commands, state, troubleshooting).
- `SECURITY.md`: the five enforcement layers, the build-loop and save-point controls, and the known limits.
- `TELEPORT.md`: setting it up on a Mac, and what lives outside the repo.
- `CHANGELOG.md`: how it got here, version by version.

## Health
```bash
bash scripts/bench.sh          # structure, gates that actually fire, models that exist, no global copy
node scripts/gate-test.mjs     # the plugin and the sandbox, replayed for real
python3 scripts/state-test.py  # document parsing, routing, state, save points, deploys
bash scripts/bootstrap.sh      # tool checks plus the bench (use it on a new machine)
```

## Honest limits
- macOS only, and built against OpenCode 2.2.5: an OpenCode upgrade can break the plugin, so re-run the three suites
  after one. Apple marks `sandbox-exec` as deprecated; it still works, and the gate tests fail loudly if it stops.
- Proven on small projects (a two-step test project and one real milestone), used by one person.
- It is heavy for what it is: about 6,500 lines of routing and guardrail code. The guardrails were the point of the
  exercise.

## How it was built
By directing AI coding agents: every change was planned, tested and reviewed by an agent before it landed, and run end
to end on real models before each version was called done. The history here is squashed to one commit per version.

## Licence
MIT, see `LICENSE`.

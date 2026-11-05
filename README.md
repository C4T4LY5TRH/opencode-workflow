# opencode mini-project workshop

One harness. Many mini projects. A specialist team from idea to approved plan, then one command that builds the whole milestone on autopilot: `/go`.

## Start
```bash
cd ~/Projects/opencode
opencode                     # orchestrator is the default agent
/new "your idea"             # scaffold; the brainstormer drafts BRIEF.md and asks questions (answer in chat)
/go                          # lock the brief; architect, designer, planner, critic run; code prints the approval digest -> stop
/approve                     # you read the digest, open the mockups, approve (or /critique for another round)
/go                          # autopilot: tests, build (one step at a time), verify, review; stops at SHIP (/stop to stop early)
/ship                        # checklist; /ship yes commits, tags and records the milestone (/deploy, /publish, /undo follow)
```
The harness lives in this repo only (`.opencode/`). Outside this folder, opencode is plain opencode.
Changes to `.opencode/` apply on save; there is no install step.
Your Claude Code skills are deliberately hidden from opencode (see `TELEPORT.md` for the settings behind that).

## Docs
- `HANDBOOK.md` — how it works and how to drive it: the flow, stages, agents, commands, state, troubleshooting.
- `SECURITY.md` — the enforcement reference: the five layers, the build-loop and save-point controls, and the known limits.
- `TELEPORT.md` — move the harness to another machine.
- `docs/superpowers/specs/2026-10-27-harness-v4-front-half-design.md` — the v4 piece 1 design (`...-roadmap.md`: pieces 2-4).

## Layout
```
AGENTS.md            rules loaded in every session here (voice, flow, gates)
.opencode/           what opencode loads: opencode.json (models, permissions, policies), agents/, commands/, skills/, plugins/
rules/               the rulebook (agents load what a task needs: skill `rules`)
CHANGELOG.md        version history (v4)
scripts/             harness_state.py, harness_docs.py, next.py, checkpoint.py, deploy.py, status.py, approve.sh, new-project.sh, bench.sh, gate-test.mjs, state-test.py, bootstrap.sh
mini-projects/       one folder = one project = its own git repo; _template/ is the scaffold
docs/                audit evidence, specs and plans, history
.harness/            runtime state (gitignored): dashboard.html, plugin heartbeat, events log, bench history
```

## Commands (13)
```
/new "<idea>"     scaffold + first BRIEF.md draft   /status [slug]   where everything is (+ .harness/dashboard.html)
/brainstorm [topic|brief]  another round            /critique              one more critic round
/go [retry | cap <usd>]  next thing, or autopilot
/approve          you approve the documents         /review                REVIEW.md on demand
/ship [yes]        checklist; yes commits + tags     /research <q>          RESEARCH/ (cited)
/deploy [rollback|stop]  run the shipped milestone here   /publish [yes]  push to a private GitHub repo
/undo             back to the last save point
/stop             autopilot stops after this turn   (the slug is optional everywhere: none = current project)
```

## Health
```bash
bash scripts/bench.sh          # structure + gates actually fire + models exist + no global copy
node scripts/gate-test.mjs     # the plugin and sandbox, replayed for real
python3 scripts/state-test.py  # document parsing, routing, status
bash scripts/bootstrap.sh      # same as the bench, plus tool checks (use on a new machine)
```

## Voice
Caveman (`.opencode/skills/caveman/SKILL.md`). Payload (code, paths, errors) stays verbatim.

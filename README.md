# opencode mini-project workshop

One brain. Many mini projects. A specialist team from idea to approved plan, then one command that builds the whole milestone on autopilot: `/go`.

## Start
```bash
cd ~/Projects/opencode
opencode                     # orchestrator is the default agent
/new "your idea"             # scaffold; the brainstormer drafts BRIEF.md and asks questions (answer in chat)
/go                          # lock the brief; architect, designer, planner, critic run; code prints the approval digest -> stop
/approve                     # you read the digest, open the mockups, approve (or /critique for another round)
/go                          # autopilot: tests, build (3 steps at once), verify, review; stops at SHIP (/stop to stop early)
/ship                        # checklist; records the milestone; you commit
```
The harness lives in this repo only (`.opencode/`). Outside this folder, opencode is plain opencode.
Changes to `.opencode/` apply on save; there is no install step.
Your Claude Code skills are deliberately hidden from opencode (see `TELEPORT.md` for the settings behind that).

## Docs
- `HANDBOOK.md` — how it works and how to drive it: the flow, stages, agents, commands, state, troubleshooting.
- `AUDIT.md` — the 2026-10-23 security audit: what was broken, the evidence, what was fixed; §8b is the enforcement reference.
- `TELEPORT.md` — move the harness to another machine.
- `docs/superpowers/specs/2026-10-27-harness-v4-front-half-design.md` — the v4 piece 1 design (`...-roadmap.md`: pieces 2-4). `docs/history/` — the v1 record.

## Layout
```
AGENTS.md            rules loaded in every session here (voice, flow, gates)
.opencode/           what opencode loads: opencode.json (models, permissions, policies), agents/, commands/, skills/, plugins/
brain/               rules/, prompts/, CHANGELOG.md
scripts/             harness_state.py, harness_docs.py, next.py, status.py, approve.sh, new-project.sh, bench.sh, gate-test.mjs, state-test.py, bootstrap.sh
mini-projects/       one folder = one project = its own git repo; _template/ is the scaffold
docs/                audit evidence, specs and plans, history
.harness/            runtime state (gitignored): dashboard.html, plugin heartbeat, events log, bench history
```

## Commands (11)
```
/new "<idea>"     scaffold + first BRIEF.md draft   /status [slug]   where everything is (+ .harness/dashboard.html)
/brainstorm [topic|brief]  another round            /critique              one more critic round
/go [retry | cap <usd>]  next thing, or autopilot   /hunt [focus]          BUGHUNT.md (hunter -> skeptic -> referee)
/approve          you approve the documents         /review                REVIEW.md on demand
/ship             checklist; you commit             /research <q>          RESEARCH/ (cited)
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

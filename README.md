# opencode mini-project workshop

One brain. Many mini projects. One command to drive them: `/go`.

## Start
```bash
cd ~/Projects/opencode
opencode                     # orchestrator is the default agent
/new "one line goal"         # scaffold
/go my-project               # plan -> stop
/approve my-project          # you read PLAN.md and approve it
/go my-project               # one step per /go, until the review says SHIP
/ship my-project             # checklist; you commit
```
The harness lives in this repo only (`.opencode/`). Outside this folder, opencode is plain opencode.
Changes to `.opencode/` apply on save; there is no install step.
Your Claude Code skills are deliberately hidden from opencode (see `TELEPORT.md` for the settings behind that).

## Docs
- `HANDBOOK.md` — how it works and how to drive it: the loop, agents, commands, state, gates, troubleshooting.
- `AUDIT.md` — the 2026-10-23 security audit: what was broken, the evidence, what was fixed.
- `TELEPORT.md` — move the harness to another machine.
- `docs/superpowers/specs/2026-10-25-harness-v3-design.md` — the v3 design. `docs/history/` — the v1 record.

## Layout
```
AGENTS.md            rules loaded in every session here (voice, flow, gates)
.opencode/           what opencode loads: opencode.json (models, permissions, policies), agents/, commands/, skills/, plugins/
brain/               rules/, prompts/, patterns/, anti-patterns/, evals/, proposals/, CHANGELOG.md
scripts/             harness_state.py, next.py, status.py, approve.sh, new-project.sh, bench.sh, gate-test.mjs, state-test.py, bootstrap.sh
mini-projects/       one folder = one project = its own git repo; _template/ is the scaffold
docs/                audit evidence, v3 spec and plan, history
.harness/            runtime state (gitignored): dashboard.html, plugin heartbeat, events log, bench history
```

## Commands (9)
```
/new "<goal>"     scaffold                          /status [slug|brain]   where everything is (+ .harness/dashboard.html)
/go <slug>        do the next thing, then stop      /critique <slug>       CRITIQUE.md (optional second opinion)
/approve <slug>   you approve PLAN.md (recorded)    /hunt <slug> [focus]   BUGHUNT.md (hunter -> skeptic -> referee)
/ship <slug>      checklist; you commit             /review <slug>         REVIEW.md on demand
/research <q>     RESEARCH/ (cited)
```

## Health
```bash
bash scripts/bench.sh          # structure + gates actually fire + models exist + no global copy
node scripts/gate-test.mjs     # the plugin and sandbox, replayed for real
python3 scripts/state-test.py  # plan parsing, routing, status
bash scripts/bootstrap.sh      # same as the bench, plus tool checks (use on a new machine)
```

## Voice
Caveman (`.opencode/skills/caveman/SKILL.md`). Payload (code, paths, errors) stays verbatim.

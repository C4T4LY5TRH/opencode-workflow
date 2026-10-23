# opencode mini-project workshop

One brain. Many mini projects. Forever evolving. Free models only.

## Start
```bash
cd ~/Projects/opencode
opencode                     # orchestrator is the default agent
/new "one line goal"         # purpose gate first
```
The harness lives in this repo only (`.opencode/`). Outside this folder, opencode is plain opencode.
Changes to `.opencode/` apply on save; there is no install step.
Your Claude Code skills are deliberately hidden from opencode (see `TELEPORT.md` for the two settings behind that).

## Docs
- `HANDBOOK.md` — how it works and how to drive it: agents, commands, gates, scripts, troubleshooting.
- `AUDIT.md` — the 2026-10-23 audit: what was broken, the evidence, what was fixed, what is next.
- `TELEPORT.md` — move the harness to another machine (repo bundle + the settings that live outside the repo).
- `docs/history/` — the v1 handbook and build journal (bugs A–K), kept as a record.

## Layout
```
AGENTS.md            rules loaded in every session here (voice, flow, gates)
.opencode/           what opencode loads: opencode.json, agents/, commands/, skills/, plugins/
brain/               rules/, prompts/, patterns/, anti-patterns/, evals/, proposals/, CHANGELOG.md
scripts/             new-project.sh, bench.sh/.py, gate-test.mjs, bootstrap.sh, html2md.py, snapshot.py
mini-projects/       one folder = one project = its own git repo; _template/ is the scaffold
docs/audit/          audit evidence + research
.harness/            runtime state (gitignored): plugin heartbeat, events log, bench history
```

## Daily loop
```
/new <goal>     scaffold (purpose gate)         /review <slug>  REVIEW.md (verdict)
/scope <slug>   SCOPE.md                        /blind <slug>   BLIND.md
/research <q>   RESEARCH/*.md (cited)           /grill <slug>   DEVIL.md
/plan <slug>    PLAN.md                         /whatif <slug>  WHATIF.md
/approve <slug> you approve PLAN.md (recorded)
/build <slug>   one step, verified              /ship <slug>    gates + you say yes
/learn <slug>   brain proposal                  /bench          harness health
/hunt <slug>    BUGHUNT.md (hunter -> skeptic)  /pr-review [target]  independent review (advisory)
```

## Health
```bash
bash scripts/bench.sh        # structure + gates actually fire + models exist + no global copy
bash scripts/bootstrap.sh    # same, plus tool checks (use on a new machine)
```

## Voice
Caveman (`.opencode/skills/caveman/SKILL.md`). Payload (code, paths, errors) stays verbatim.

# WORKSHOP RULES - ~/Projects/opencode

Global harness rules live in `~/.config/opencode/AGENTS.md` (caveman voice, gates, brain pointer).
This file = workshop only. Both are active.

## LAYOUT
- `harness/` = source of truth for agents, commands, skills, plugins, brain. Installed to `~/.config/opencode` by `harness/scripts/install.sh`.
- `mini-projects/<slug>/` = one project = one git repo. Never put project code here.
- `mini-projects/_template/` = project shape template. `new-project.sh` copies from it.

## RULES FOR THIS DIRECTORY
- New project -> `/new <one-line goal>`. Purpose gate: no goal, no scaffold.
- Each mini project is its own git repo. Never commit a project into the workshop repo.
- Workshop repo holds the harness only. Commit harness changes here, one logical change per commit.
- After changing anything in `harness/`: run `bash harness/scripts/install.sh` (it syncs + restarts the opencode service).
- After changing `~/.config/opencode` by hand: `opencode service restart` (opencode runs as a background service).
- `bash ~/.config/opencode/scripts/bench.sh` = harness + brain health. Run it before claiming the harness is fine.

## MONEY + KEYS
- Free tools only. If a task needs a paid API, stop and say so.
- Secrets never in this repo, never in a mini project, never in chat output.

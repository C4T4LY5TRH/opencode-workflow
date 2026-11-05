# TELEPORT — move the harness to another machine

The harness lives in this repo (`.opencode/`, `rules/`, `scripts/`, `AGENTS.md`). Nothing is installed into
`~/.config/opencode`, so moving it means moving the repo and then re-applying three small settings that live
**outside** the repo (two of them are optional; the Anthropic key is not). `scripts/bootstrap.sh` checks all of it and prints the fix for anything missing.

The round trip has not been tried on v4 yet (11 agents + 13 commands, branch `main`, the only branch). The plan: `git bundle` → `git clone` into a
folder under the home dir → `bash scripts/bootstrap.sh` all OK, `bash scripts/bench.sh` failed 0,
`node scripts/gate-test.mjs` and `python3 scripts/state-test.py` all passed (incl. the OS sandbox cases) from the clone,
with no runtime state, approvals or test debris carried over. Piece 2 added nothing outside the repo. Piece 3 adds two things `/deploy` makes that a clone does not carry over: the app home `apps/<slug>/` (releases, `shared/` data, logs; inside the repo folder but git-ignored) and, outside the repo, one LaunchAgent per deployed app, `~/Library/LaunchAgents/local.opencode-harness.<slug>.plist`. Playwright's Chromium is used by the researcher and the inspector.

## What travels, and what does not
| Travels (in the repo) | Does NOT travel (set it up again) |
|---|---|
| `.opencode/` agents, commands, skills, plugins, config + policies | service env `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` |
| `rules/`, `scripts/`, `mini-projects/_template/`, docs | policy hiding `~/.agents` skills, in `~/.config/opencode/opencode.json` |
| full git history | opencode's saved approvals (kept empty on purpose, so start clean) |
| | **your Anthropic API key** (opencode's auth store; v4 needs it for the Opus architect and designer, the Opus reviewer, the Sonnet orchestrator, inspector, brainstormer, planner, critic, builder and qa, and the Haiku researcher) |
| | `.harness/` runtime state, incl. the dashboard and bench history |
| | deployed apps: `apps/<slug>/` (git-ignored; copy `apps/<slug>/shared/` if the data matters) and their LaunchAgents `local.opencode-harness.*`; run `/deploy <slug>` again on the new machine (it makes both) |
| | your mini projects (each is its own repo) and their `/approve` records and step state (`.harness/` is gitignored: re-`/approve` after moving) |
| | `.archive/` backups, your local `CLAUDE.md` (Claude Code notes, gitignored) |
| | macOS (the agent-shell sandbox uses `/usr/bin/sandbox-exec`), node, python3, opencode itself, Playwright's Chromium |

## On this machine
```bash
cd ~/Projects/opencode
git status --short                             # must be empty: a bundle carries committed files only
bash scripts/bench.sh                          # must say passed N/N, failed 0
git bundle create ~/opencode.bundle main   # one file: main (v4) with its full history; add --tags for the tags
```
Move `~/opencode.bundle` to the other machine (AirDrop, USB, anything). Mini projects are separate repos:
copy any you want (`mini-projects/<slug>/`) or push them to a remote you own.

## On the new machine
1. On a **Mac** (agent shells run in macOS `sandbox-exec`; elsewhere every agent shell command is refused), install
   opencode (verified on **2.2.5**; the platform facts were read in 2.1.3 and re-checked for 2.2.0 and 2.2.5; other versions: see the last rule below), Node 22+, python3.
   Once: `npx playwright install chromium`.
2. Restore:
   ```bash
   git clone -b main ~/opencode.bundle ~/Projects/opencode   # not inside /tmp: the sandbox lets agents write temp dirs
   cd ~/Projects/opencode
   ```
3. Store your Anthropic API key. **You type this yourself**; agents are policy-denied from `opencode auth`:
   ```bash
   opencode auth login        # choose Anthropic, paste the API key
   opencode auth list         # must show an Anthropic line
   ```
   Without it the Claude agents fail on their first call. Then the two optional settings (skip if you want opencode to
   see your Claude Code skills):
   ```bash
   opencode service set env OPENCODE_DISABLE_CLAUDE_CODE_SKILLS 1 && opencode service restart
   ```
   and, for each skill folder in `~/.agents/skills`, add a policy to `~/.config/opencode/opencode.json`:
   ```json
   "policies": [{ "action": "integration.use", "resource": "skill:<folder-name>", "effect": "deny" }]
   ```
4. Check everything: `bash scripts/bootstrap.sh`. It verifies the tools and `sandbox-exec`, refuses a workshop inside a
   temp dir or a harness copy in `~/.config/opencode`, warns about the Anthropic key and the two settings above, then runs the bench
   (its `opencode models` call loads the plugins, so `plugins-alive` is green on the first run).
5. Start it: `cd ~/Projects/opencode && opencode`. For each project you copied over, read its approval digest (`/status <slug>`) and `/approve <slug>`
   again before `/go`.

## Rules
- Do NOT copy `~/.config/opencode` between machines, and never put harness files there. A global copy merges with
  the workshop one and plugins fail with "Duplicate plugin ID". `bootstrap.sh` fails loudly if it finds one.
- Do NOT approve "always allow" in the opencode prompt for broad commands (`bash *`, `python3 *`, `rm *`).
  Saved approvals override every `ask` for every agent, and they are what silently disabled the gates before the audit.
- Models live in ONE place: `.opencode/opencode.json`, `agent.<name>.model`. Agent files carry no `model:` line
  (it would silently override opencode.json; the bench check `models-one-place` fails if one comes back). Claude model
  IDs come from `opencode models | grep anthropic` (v4 uses `anthropic/claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5`). If the bench's `models-resolve` fails on the new machine (a free model, if you add one, differs in availability between days and regions),
  change that agent's entry in `opencode.json`.
- If the other machine runs a different opencode version, read the platform notes in
  `docs/audit/research/`, re-run `bash scripts/bench.sh`, and run one real project before trusting the gates.
  The platform facts were read from the 2.1.3 source (`git clone --depth 1 --branch v2.1.3 https://github.com/anomalyco/opencode`); the 2.2.0 diff of every cited line is in the v4 spec, section 14; the 2.2.5 check is in `docs/superpowers/journal/2026-11-04-piece4-build-journal.md` (session 1).

# TELEPORT — move the harness to another machine

The harness lives in this repo (`.opencode/`, `brain/`, `scripts/`, `AGENTS.md`). Nothing is installed into
`~/.config/opencode`, so moving it means moving the repo and then re-applying three small settings that live
**outside** the repo (two of them are optional; the Anthropic key is not). `scripts/bootstrap.sh` checks all of it and prints the fix for anything missing.

Round trip verified 2026-10-25 (v3, 9 agents + 9 commands, branch `harness-v3`): `git bundle` → `git clone` into a
folder under the home dir → `bash scripts/bootstrap.sh` all OK, `bash scripts/bench.sh` failed 0,
`node scripts/gate-test.mjs` and `python3 scripts/state-test.py` all passed (incl. the OS sandbox cases) from the clone,
with no runtime state, approvals or test debris carried over.

## What travels, and what does not
| Travels (in the repo) | Does NOT travel (set it up again) |
|---|---|
| `.opencode/` agents, commands, skills, plugins, config + policies | service env `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` |
| `brain/`, `scripts/`, `mini-projects/_template/`, docs | policy hiding `~/.agents` skills, in `~/.config/opencode/opencode.json` |
| full git history | opencode's saved approvals (kept empty on purpose, so start clean) |
| | **your Anthropic API key** (opencode's auth store; v3 needs it for the orchestrator, planner, builder, reviewer, hunter and brain) |
| | `.harness/` runtime state, incl. rule-usage telemetry (`rule-usage.json`); copy it if you want `/status brain`'s decay history |
| | your mini projects (each is its own repo) and their `/approve` records and step state (`.harness/` is gitignored: re-`/approve` after moving) |
| | `.archive/` backups, your local `CLAUDE.md` (Claude Code notes, gitignored) |
| | macOS (the agent-shell sandbox uses `/usr/bin/sandbox-exec`), node, python3, opencode itself, Playwright's Chromium |

## On this machine
```bash
cd ~/Projects/opencode
git status --short                             # must be empty: a bundle carries committed files only
bash scripts/bench.sh                          # must say passed N/N, failed 0
git bundle create ~/harness-v3.bundle harness-v3   # one file: the v3 branch with its full history
# want v2.2 and main too? use --all instead of harness-v3
```
Move `~/harness-v3.bundle` to the other machine (AirDrop, USB, anything). Mini projects are separate repos:
copy any you want (`mini-projects/<slug>/`) or push them to a remote you own.

## On the new machine
1. On a **Mac** (agent shells run in macOS `sandbox-exec`; elsewhere every agent shell command is refused), install
   opencode (verified on **2.1.3**; other versions: see the last rule below), Node 22+, python3.
   Once: `npx playwright install chromium`.
2. Restore:
   ```bash
   git clone -b harness-v3 ~/harness-v3.bundle ~/Projects/opencode   # not inside /tmp: the sandbox lets agents write temp dirs
   cd ~/Projects/opencode             # stays on harness-v3 until it is merged into main
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
5. Start it: `cd ~/Projects/opencode && opencode`. For each project you copied over, read its PLAN.md and `/approve <slug>`
   again before `/go`.

## Rules
- Do NOT copy `~/.config/opencode` between machines, and never put harness files there. A global copy merges with
  the workshop one and plugins fail with "Duplicate plugin ID". `bootstrap.sh` fails loudly if it finds one.
- Do NOT approve "always allow" in the opencode prompt for broad commands (`bash *`, `python3 *`, `rm *`).
  Saved approvals override every `ask` for every agent, and they are what silently disabled the gates before the audit.
- Models live in ONE place: `.opencode/opencode.json`, `agent.<name>.model`. Agent files carry no `model:` line
  (it would silently override opencode.json; the bench check `models-one-place` fails if one comes back). Claude model
  IDs come from `opencode models | grep anthropic`. The checking roles (critic, skeptic, researcher) use free models,
  which differ in availability between days and regions: if the bench's `models-resolve` fails on the new machine,
  change that agent's entry in `opencode.json` (`brain/NOTES-pending-claude-key.md` lists alternatives).
- If the other machine runs a different opencode version, read `AUDIT.md` section 2 and the platform notes in
  `docs/audit/research/`, re-run `bash scripts/bench.sh`, and run one real project before trusting the gates.
  The platform facts were read from the 2.1.3 source: `git clone --depth 1 --branch v2.1.3 https://github.com/anomalyco/opencode`.

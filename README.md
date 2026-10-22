# opencode mini-project workshop

One brain. Many mini projects. Forever evolving.

## Docs
- `HANDBOOK.md` - build journal + full how-to: every agent, command, skill, plugin, gate, script, with examples
- `TELEPORT.md` - move this harness to another machine: pack / unpack / verify

## Layout
- `AGENTS.md` - workshop rules (global rules live in `~/.config/opencode/AGENTS.md`; both apply)
- `harness/`  - source of truth for agents, commands, skills, plugins, brain
- `harness/brain/` - the brain: rules, prompts, patterns, anti-patterns, evals, changelog
- `mini-projects/` - each child folder = its own git repo (one project = one repo)
- `mini-projects/_template/` - the project shape template (single source of truth for scaffold)
- `harness/scripts/install.sh` - installs harness into `~/.config/opencode` (global) + restarts the service

## Install / update
```bash
bash harness/scripts/install.sh     # syncs to ~/.config/opencode + restarts the opencode service
opencode debug agents    # verify
opencode debug paths
opencode debug config
bash ~/.config/opencode/scripts/bench.sh   # brain + harness structural bench
```

## Ops gotchas (learned the hard way -> brain/rules/060-ops.md)
- opencode runs as a **background service**. Config/plugin/agent changes need `opencode service restart`
  (install.sh does it for you).
- Headless `opencode run` cannot answer "ask" permissions -> they auto-reject. Keep happy paths on allow-listed commands.
- Server cwd can differ from session cwd. Never resolve project paths from `process.cwd()`.

## Daily loop
```
/new <goal>      -> scaffold (purpose gate)
/scope           -> SCOPE.md (IN / OUT / CUT LINE)
/research <q>    -> RESEARCH/*.md (cited)
/plan            -> PLAN.md (steps + done-when)   [human approves]
/build           -> one step, verified
/review          -> REVIEW.md
/blind           -> BLIND.md (blind spots)
/grill /whatif   -> attack the plan
/ship            -> gates + human confirm
/learn           -> brain rule proposals   [human approves]
/evolve          -> prune + version bump
/bench           -> did the brain get better?
```

## Voice
Caveman. See `harness/skills/caveman/SKILL.md`. Payload (code, paths, errors) stays verbatim.

## Skills (7, on demand)
`caveman` voice - `browser` playwright driving - `visual-review` see-and-fix - `html2md` page -> markdown
- `spec` spec-quality writing - `verify` prove it works - `brain` the rules index

## Helper scripts (free, no installs)
- `python3 ~/.config/opencode/scripts/html2md.py <url> [-o out.md]` - clean markdown from a page
- `python3 ~/.config/opencode/scripts/snapshot.py <url> [-o shot.png] [--text]` - screenshot (+ optional md)
- `bash ~/.config/opencode/scripts/bench.sh` - harness + brain health (27 checks)

## Config hygiene
`install.sh` backs up to ONE place: `~/.config/opencode/.backups/<timestamp>/` (last 5 runs kept).
No `.bak` files next to live files, ever.

## Models
Free tier only for now. Switch instructions: `harness/brain/NOTES-pending-claude-key.md`.

## Browser / visual
Playwright MCP (free, local). `npx playwright install chromium` once.
- `/browse <url>` -> snapshot + screenshot, report what you SAW
- `/html2md <url>` -> clean markdown for cheap ingestion

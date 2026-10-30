# NOTE - model setup

All agent models live in ONE place: `.opencode/opencode.json` -> `agent.<name>.model` (v3).
Agent files carry no `model:` line: a `model:` line in an agent `.md` silently wins over opencode.json
(spec §14.1 fact 2), and the bench check `models-one-place` fails if one comes back.

Current (v4, 2026-10-30). Claude for the hard roles (Anthropic API key, `opencode auth login`), a free
OpenCode Zen model for one checking role (skeptic):
- orchestrator: anthropic/claude-haiku-5-5 (runs the /go chains; fallback Sonnet if it handles them poorly)
- brainstormer: anthropic/claude-sonnet-5-5 (v4, new)
- architect: anthropic/claude-opus-5-5 (v4, new: the one Opus role, the hardest decisions)
- planner: anthropic/claude-sonnet-5-5
- builder: anthropic/claude-sonnet-5-5
- hunter: anthropic/claude-sonnet-5-5
- reviewer: anthropic/claude-sonnet-5-5 (was opencode/flint-40b-free until the 2026-10-25 live run, where the free
  usage limit stalled /go's review; then Haiku, unsteady on identical code (v4 spec §14.1); Sonnet since 2026-10-30)
- skeptic: opencode/deepseek-v4.1-flash-free (fixture-test winner; a different family from the hunter on purpose)
- critic: anthropic/claude-sonnet-5-5 (was opencode/nemotron-3-ultra-free, which disappeared on 2026-10-29)
- researcher: anthropic/claude-haiku-5-5 (was opencode/nemotron-3.5-super-vl-free until the 2026-10-30 acceptance
  run, where its free usage limit failed the brainstorm's research step; Haiku also reads screenshots)
- brain: anthropic/claude-sonnet-5-5 (was opencode/glm-5.3-flash-free, same free-limit stall in /ship; then Haiku;
  Sonnet since 2026-10-30, with the reviewer)

Families: Claude designs, builds and hunts; a non-Claude model verifies bugs (skeptic), so that checker does not share
the builder's blind spots. Since 2026-10-25 the reviewer and brain are Claude (free limits stalled the loop;
Haiku first, Sonnet since 2026-10-30 because the Haiku reviewer was unsteady), since v4 the critic is Claude Sonnet
(its free model disappeared; v4 spec §3), and since the v4 acceptance run the researcher is Claude Haiku (free
limit): those trades were the human's call.

Free models come and go without notice (minimax-m3.1 and longcat-2.5 disappeared during the v2 audit).
`bash scripts/bench.sh` checks every model in opencode.json against `opencode models` (`models-resolve`).
Run it first when an agent fails with "Model unavailable".

To change a model:
1. Edit `agent.<name>.model` in `.opencode/opencode.json`. Use an ID from `opencode models`.
2. `bash scripts/bench.sh` -> `models-resolve` passes.
3. `opencode debug agents` -> the agent shows the new model.

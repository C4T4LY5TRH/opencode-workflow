# NOTE - model setup

All agent models live in ONE place: `.opencode/opencode.json` -> `agent.<name>.model` (v3).
Agent files carry no `model:` line: a `model:` line in an agent `.md` silently wins over opencode.json
(spec §14.1 fact 2), and the bench check `models-one-place` fails if one comes back.

Current (v3, 2026-10-25). Claude for the hard roles (Anthropic API key, `opencode auth login`), free
OpenCode Zen models for the checking roles:
- orchestrator: anthropic/claude-haiku-5-5
- planner: anthropic/claude-sonnet-5-5
- builder: anthropic/claude-sonnet-5-5
- hunter: anthropic/claude-sonnet-5-5
- reviewer: anthropic/claude-haiku-5-5 (was opencode/flint-40b-free until the 2026-10-25 live run, where the free
  usage limit stalled /go's review)
- skeptic: opencode/deepseek-v4.1-flash-free (fixture-test winner; a different family from the hunter on purpose)
- critic: opencode/nemotron-3-ultra-free
- researcher: opencode/nemotron-3.5-super-vl-free (vision, for screenshots)
- brain: anthropic/claude-haiku-5-5 (was opencode/glm-5.3-flash-free; same free-limit stall in /ship)

Families: Claude builds and hunts; non-Claude models critique and verify bugs, so those checkers do not share the
builder's blind spots. Since 2026-10-25 the reviewer and brain are Claude Haiku (free limits stalled the loop);
that trade was the human's call (spec §3).

Free models come and go without notice (minimax-m3.1 and longcat-2.5 disappeared during the v2 audit).
`bash scripts/bench.sh` checks every model in opencode.json against `opencode models` (`models-resolve`).
Run it first when an agent fails with "Model unavailable".

To change a model:
1. Edit `agent.<name>.model` in `.opencode/opencode.json`. Use an ID from `opencode models`.
2. `bash scripts/bench.sh` -> `models-resolve` passes.
3. `opencode debug agents` -> the agent shows the new model.

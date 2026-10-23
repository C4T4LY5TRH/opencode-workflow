# NOTE - model setup

Current: free OpenCode Zen models only. Assigned per agent in `.opencode/agents/*.md` (`model:`).
Verified responding on 2026-10-23 (`opencode run --model ...`):
- orchestrator / architect / coder / brain: opencode/big-pickle
- scoper: opencode/glm-5.3-flash-free
- reviewer: opencode/deepseek-v4.1-flash-free
- critic: opencode/nemotron-3-ultra-free
- devil: opencode/mimo-v2.6-flash-free
- whatif: opencode/nemotron-3.5-lightning-free
- researcher: opencode/beam-free
- visual-review: opencode/nemotron-3.5-super-vl-free (vision)
- code-reviewer: opencode/flint-40b-free (least reliable: returned "Endpoint is unavailable" once; fallback mimo-v2.6-flash-free)
- bug-hunter: opencode/nemotron-3-ultra-free
- bug-skeptic: opencode/deepseek-v4.1-flash-free (keep it a different family from bug-hunter)

Free models come and go without notice (minimax-m3.1 and longcat-2.5 disappeared during the
audit). `bash scripts/bench.sh` checks every agent model against `opencode models`. Run it first
when an agent fails with "Model unavailable".

SWITCH to a paid key later:
1. `opencode auth login` (or export the provider key).
2. Change the `model:` line in the agent files you want to upgrade (orchestrator, architect,
   coder, brain are the highest-value roles). Use current model IDs from `opencode models`.
3. `bash scripts/bench.sh` -> confirm every model resolves.
Keep the critique roles (reviewer, critic, devil) on different model families than the coder,
so they do not echo its blind spots.

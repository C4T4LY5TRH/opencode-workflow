# NOTE - model setup is temporary

Current: free models only (OpenCode Zen free tier).
Free models in use:
- orchestrator / architect / coder / brain: opencode/big-pickle
- scoper / devil: opencode/glm-5.3-flash-free
- researcher: opencode/flint-40b-free
- reviewer / critic: opencode/minimax-m3.1-flash-free
- visual-review: opencode/nemotron-3.5-super-vl-free (vision)
- whatif: opencode/longcat-2.5-preview-free

PLAN: user adds own Anthropic (Claude) API key within 72h.

SWITCH (4 lines in ~/.config/opencode/opencode.json -> agent.<name>.model, or frontmatter model field of each agent file):
- orchestrator -> anthropic/claude-sonnet-4-5
- architect   -> anthropic/claude-sonnet-4-5
- coder       -> anthropic/claude-sonnet-4-5
- brain       -> anthropic/claude-sonnet-4-5
- reviewer/critic -> anthropic/claude-haiku-4-5 (cheap)

Steps to switch:
1. opencode auth login  (or export ANTHROPIC_API_KEY)
2. edit agent model fields (or add "agent": {...} overrides in opencode.json)
3. opencode debug config  -> confirm model resolved
4. run /bench to compare baseline vs new brain

Free tier stays as fallback for cheap roles (researcher, whatif) - cheaper, and diversity of models catches more blind spots.

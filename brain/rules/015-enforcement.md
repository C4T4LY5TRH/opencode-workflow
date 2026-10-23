# 015-enforcement

- Gates live in CODE (permission rules + safety-gate plugin), not only in prompt text.
  Prompt text alone gets bypassed by a smart model. Assume it will look for a loophole.
- When a tool refuses, REPORT the refusal. Never work around it. Workaround = bug.
- Each agent owns its output files. Coder never writes PLAN/SCOPE/REVIEW/BLIND.
- opencode server may run from a different cwd than the session. Resolve paths from
  the session/project dir, never from process.cwd().
- A PLUGIN THAT FAILS TO COMPILE IS SILENTLY SKIPPED. Your gates just vanished and
  nothing says so. So: every plugin writes a load heartbeat, and the bench fails on
  a load failure newer than the newest heartbeat. Never trust a gate you have not seen fire.
- A BROKEN FRONTMATTER SILENTLY DROPS THE AGENT/COMMAND. One missing newline = agent gone.
  Bench checks frontmatter shape and duplicate YAML keys.
- The hook's `agent` field DOES carry the subagent's own id in opencode 2.1.3 (verified in source).
  Still gate by FILE ROLE + per-agent permission rules first; use `agent` only as an extra check.
- A LOG SCAN MUST MATCH THE EVENT, NOT A SUBSTRING. The opencode log records every shell
  command you run. A naive "does the log contain 'failed to load plugin'" check counts your
  own diagnostic grep as a plugin failure. Match level=WARN AND message="failed to load plugin".
- A GATE THAT EXISTS IS NOT A GATE THAT FIRES. Test the block, not the file: scripts/gate-test.mjs
  replays real tool calls at the plugin. A gate checked only for presence passed for weeks while dead.

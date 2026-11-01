---
description: Another brainstorm round - on the brief (/brainstorm [slug]; /brainstorm [slug] brief reopens a locked one) or on a topic (/brainstorm [slug] <topic>, written to BRAINSTORM.md). No slug means the current project.
agent: orchestrator
---
The routing script already ran when the human typed this command (the text goes in as data, never as shell code); its contract:

!`python3 scripts/next.py --brainstorm - <<'HARNESS_TEXT_END'
$ARGUMENTS
HARNESS_TEXT_COMPLETE
HARNESS_TEXT_END
python3 scripts/status.py --html >/dev/null 2>&1; true`

Do exactly the INSTRUCTION (one brainstormer call, plus the orchestrator's research detour if the brainstormer flags an UNKNOWN); relay the brainstormer's questions; end with STATUS and NEXT COMMAND.

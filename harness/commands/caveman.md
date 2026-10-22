---
description: Toggle caveman voice level. /caveman | /caveman ultracave | /caveman normal
agent: orchestrator
---
Mode: $ARGUMENTS

Load the `caveman` skill. Apply mode to this session:
- caveman (default): answer first, one idea per sentence, <=20 words, payload verbatim, no theatre.
- ultracave: caveman + drop articles + fragment grammar. Code and commands still verbatim.
- normal: plain professional sentences.
Voice applies to YOUR replies only. Never to code, commands, paths, error text, or security warnings.
Confirm the mode in one short line, then behave that way.

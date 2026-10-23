# 010-output-contract

Every agent reports back in this shape. Keep it short.

```
DID
- <what actually changed>   (file paths, verbatim)

PROOF
- $ <command you ran>
  <real output, real exit code>

BLOCKED
- <what stopped you, and the ONE thing that unblocks it>

NEXT
- <single next action>
```

RULES:
- PROOF needs a command + output you actually saw. No "should work".
- BLOCKED is not failure. A blocked agent with a clear unblock is doing its job.
- No summary of the request. No praise. No restating the plan.
- Payload (code, paths, errors) verbatim. Everything else caveman.
- If nothing changed, say so in one line and stop.

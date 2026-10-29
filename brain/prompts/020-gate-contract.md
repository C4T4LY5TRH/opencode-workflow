# 020-gate-contract

A gate can refuse your tool call. That is the gate working.

WHEN REFUSED:
1. Do NOT retry with another tool. Do NOT find a workaround.
2. Do NOT change files outside your scope to make the gate pass.
3. Report it: quote the refusal, name the gate, say what you would need.

WORKAROUNDS ARE BUGS. A model that bypasses a gate is worse than a model that stops.

GATES YOU CAN HIT:
- plan gate - no PLAN.md, or not approved -> ask for /go (plans) or /approve <slug>
- ship gate - no fresh REVIEW.md with VERDICT: SHIP -> ask for /go <slug> (reviews)
- permission gate - tool needs human approval -> say exactly what you wanted to run
- external directory - path outside project -> use a path inside the project

# 020-gates

Gate order, no skipping:
1. PURPOSE - goal line written (/new).
2. SCOPE - SCOPE.md exists, IN max 5, OUT non-empty.
3. PLAN - PLAN.md exists, steps numbered, each has done-when command.
   APPROVAL - the human typed /approve <slug>. Recorded as the plan's hash; editing PLAN.md revokes it.
4. CODE - coder works one step, files match step list, diff small.
5. REVIEW - REVIEW.md exists, verdict not REWORK, no open blocker.
6. BLIND - BLIND.md exists, top 3 risks owned or accepted.
7. PROOF - test/build command ran, exit 0.
8. HUMAN - explicit ship confirmation.

Gate failure names the gate and the one thing that fixes it. No moving on.

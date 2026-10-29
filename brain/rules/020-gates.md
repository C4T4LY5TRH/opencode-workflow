# 020-gates

The v3 loop: /new, /go (plan), /approve, /go (steps, review), /ship. Gate order, no skipping:
1. PURPOSE - goal line in BRIEF.md (/new).
2. PLAN - PLAN.md has a SCOPE (IN max 5, OUT non-empty) and numbered STEPS, each with one exact `done when` check.
3. APPROVAL - the human typed /approve <slug>. Records the plan hash + steps. Editing PLAN.md revokes it.
4. CODE - plan gate: no code write by the edit/write/patch tools or shell redirects without an approved, unchanged plan
   (programs the builder runs are limited by the sandbox, not this gate). One step per /go.
5. STEP DONE - only when the plugin sees the step's exact check pass. The builder's word is not proof.
   2 failed checks on a step -> STUCK, the human decides.
6. REVIEW - REVIEW.md with `VERDICT: SHIP` (blind spots are a section of it). Max 2 review->fix rounds.
7. SHIP - /ship's first status line is the freshness check for the human's commit: recorded SHIP verdict + live
   REVIEW.md + matching tree hash. Code changed after the review = stale = review again. The plugin ship gate
   stops an agent's plain git commit; agents cannot write .git at all.
8. HUMAN - the human commits, pushes and publishes.

- Write tools reach only mini-projects/<slug>/, brain/proposals/ and the workshop RESEARCH/. No symlinks.
- Push and publish are human-only. The `policies` deny is a speed bump; the sandbox withholds the credentials.

Gate failure names the gate and the one thing that fixes it. No moving on.

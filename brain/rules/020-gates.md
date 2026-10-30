# 020-gates

The v4 loop: /new (idea, brainstorm) -> /go (lock the brief, then the automatic chain) -> /approve or /critique ->
/go per step -> /ship. `scripts/next.py` computes the stage from the files and the state. Gate order, no skipping:
1. PURPOSE - the idea is the GOAL of BRIEF.md (/new). No idea, no project.
2. BRIEF LOCK - /go locks BRIEF.md: right format, no open questions, at least one [MUST] feature. Only the
   brainstormer writes it. `/brainstorm <slug> brief` reopens a locked brief; /go locks it again.
3. DESIGN CHAIN - ARCHITECTURE.md (R1 with its spike, every MUST in a milestone), PLAN.md for the current milestone
   (step 1 of M1 proves R1), one critic round, every serious point answered in the file it targets. Each file must
   pass its parser; the parser's message goes back to the agent that wrote it.
4. APPROVAL - the human typed /approve <slug>: ONE hash over BRIEF + ARCHITECTURE (+ DESIGN) + PLAN. Any edit
   revokes it. /approve names every gap it refuses on. /critique asks for one more round instead.
5. CODE - plan gate: no code write (edit/write/patch tools, shell redirects) unless the documents are approved and
   unchanged and the plan's milestone is not shipped (programs the builder runs are limited by the sandbox, not
   this gate). One step per /go.
6. STEP DONE - only when the plugin sees the step's exact check pass. The builder's word is not proof.
   2 failed checks -> STUCK, the human decides. A failed spike (a step with `proves`) -> REARCHITECT instead.
7. REVIEW - REVIEW.md with `VERDICT: SHIP` (blind spots are a section of it). Max 2 review->fix rounds.
8. SHIP - /ship's first status line is the freshness check for the human's commit: recorded SHIP verdict + live
   REVIEW.md + matching tree hash. Then trusted code records the milestone as shipped; the next /go plans the next
   one. The plugin ship gate stops an agent's plain git commit; agents cannot write .git at all.
9. HUMAN - the human commits, pushes and publishes.

Limits, all in code:
- 2 failed attempts per automatic stage -> STUCK. `/go <slug> retry` (or /approve) clears the count.
- 16 delegations per human turn (circuit breaker); one at a time, never in the background.
- One chain per project: `.harness/lock`, freed when the orchestrator's turn ends, expires after 30 minutes.
  /approve and /ship refuse while it is fresh (they would judge files the chain is still writing).
- Only human-typed commands move a stage on (/go, /approve, /critique, /ship). No agent locks, approves or ships.
- An approved v3 project (plan hash, no ARCHITECTURE.md) keeps the v3 loop.
- Write tools reach only mini-projects/<slug>/, brain/proposals/ and the workshop RESEARCH/. No symlinks.
- Push and publish are human-only. The `policies` deny is a speed bump; the sandbox withholds the credentials.

Gate failure names the gate and the one thing that fixes it. No moving on.

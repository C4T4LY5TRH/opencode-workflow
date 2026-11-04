# 020-gates

The v4 loop: /new (idea, brainstorm) -> /go (lock the brief, then the automatic chain) -> /approve or /critique ->
/go (autopilot: tests, build, verify, review) -> /ship. `scripts/next.py` computes the stage from the files and the state. Gate order, no skipping:
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
   this gate). Each builder writes only its own step's files.
6. STEP DONE - only when the plugin sees the step's exact check pass. The builder's word is not proof.
   2 failed checks -> STUCK, the human decides. A failed spike (a step with `proves`) -> REARCHITECT instead.
7. REVIEW - REVIEW.md with `VERDICT: SHIP` (blind spots are a section of it). Max 2 review->fix rounds.
8. SHIP - /ship's first status line is the freshness check: recorded SHIP verdict + live REVIEW.md + matching tree
   hash. `/ship yes` then commits, tags and records the milestone (trusted code); the next /go plans the next one.
   Agents cannot write .git at all.
9. HUMAN - the human pushes and publishes (/publish), runs the app (/deploy) and can /undo to the last save point.

Limits, all in code:
- 2 failed attempts per automatic stage -> STUCK. `/go <slug> retry` (or /approve) clears the count.
- 16 delegations per human turn (circuit breaker); one delegation open at a time, never in the background.
- Autopilot stops at a cost cap ($10 per milestone, `/go cap <usd>`) and at a turn cap (3 x steps + 10); `/stop` ends it.
- One chain per project: `.harness/lock`, freed when the orchestrator's turn ends, expires after 30 minutes.
  /approve and /ship refuse while it is fresh (they would judge files the chain is still writing).
- Only human-typed commands move a stage on (/go, /approve, /critique, /ship). No agent locks, approves or ships.
- Write tools reach only mini-projects/<slug>/ and the workshop RESEARCH/. No symlinks.
- Push and publish are human-only. The `policies` deny is a speed bump; the sandbox withholds the credentials.

Gate failure names the gate and the one thing that fixes it. No moving on.

# fabricated-completion

- name: fabricated completion (report before work)
- symptom: an agent's report says `DID: PLAN.md` but the file does not exist; NEXT says "write PLAN.md".
  The model filled the report template instead of calling the write tool, then stopped.
- cause: a free model treated the report's NEXT slot as permission to defer the actual work.
- fix: (1) every agent prompt says "do the work first, report after; DID lists only files you
  actually wrote this turn"; (2) every file-producing command makes the orchestrator `ls` the file
  after the handoff and sends the worker back once if it is missing.
- source: harness v2 end-to-end test, 2026-10-23 (architect on big-pickle). After the fix the same
  flow produced PLAN.md -> src/hello.js -> REVIEW.md (VERDICT: SHIP).
- seen again: 2026-10-24, `/hunt` live test. The orchestrator (big-pickle) is the referee and writes BUGHUNT.md
  itself, so no second agent checks it. It reported `DID: wrote BUGHUNT.md` with a pasted `ls` PROOF, and made
  neither tool call. Fixed by naming the tool calls in the command ("call the write tool (a real tool call; text in
  your reply is not a file) ... then call the shell tool with `ls`"). The next run wrote and listed the file.
  Lesson: when the same agent writes and verifies, spell out both as tool calls.

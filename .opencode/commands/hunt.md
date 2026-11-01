---
description: Bug hunt on a project (/hunt [slug] [focus]; no slug means the current project) — Hunter, then Skeptic, then rule-based Referee. Writes BUGHUNT.md.
agent: orchestrator
---
The human typed: "$ARGUMENTS". If its first word is the name of a project under mini-projects/, that is <slug> and the rest is <focus> (it may be empty); otherwise <slug> is the current project and all of it is <focus>. The current project, resolved by code (the focus text is never in a shell line):

!`python3 scripts/harness_state.py resolve ""`

If <slug> is the current project and that printed no slug, relay what it printed and stop. Start with step 1 at once; do not inspect the project yourself.

1. **Hunter** — use the subagent tool to launch `hunter` with only this target text: "mini-projects/<slug>: its uncommitted
   changes (run git with workdir mini-projects/<slug>); if there are none, the whole project. Focus: <focus>". Do not suggest where bugs might be.
2. **Skeptic** — when the hunter finishes, launch `skeptic` with the hunter's full BUG-* blocks (not the leads). Add no commentary of your own.
3. **Referee** — apply these rules mechanically. Do not re-argue any verdict:
   - CONFIRMED + hunter confidence HIGH + skeptic `Severity: unchanged` → **Verified bugs**
   - CONFIRMED with confidence MEDIUM, or with a changed or missing skeptic severity line, or UNPROVEN →
     **Probable — needs repro**. For a changed severity show `severity: <hunter's> → <skeptic's> — <skeptic's why>`
   - REFUTED → **Dismissed** (one line each, with the skeptic's reason)
   - Hunter's leads → **Leads** (unchanged)
4. **Persist** — call the write tool (a real tool call; text in your reply is not a file) with path
   mini-projects/<slug>/BUGHUNT.md and the four sections, in that order, as content. First line:
   `# BUGHUNT — <slug> — <today's date>`; end with the hunter's Coverage block. Then call the shell tool with
   `ls mini-projects/<slug>/BUGHUNT.md`. If ls fails, call the write tool again once. Never say the file exists unless ls showed it.
5. Show the four sections. Do not fix anything until the human chooses which bugs to fix.

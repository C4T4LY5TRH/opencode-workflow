---
description: Bug hunt on a project — Hunter, then Skeptic, then rule-based Referee. Writes BUGHUNT.md.
agent: orchestrator
---
Project: $1   Focus (optional): $2
If no project slug is given: ask the human for one. Stop. Otherwise start with step 1 at once; do not inspect the project yourself.

1. **Hunter** — use the subagent tool to launch `hunter` with only this target text: "mini-projects/$1: its uncommitted
   changes (run git with workdir mini-projects/$1); if there are none, the whole project. Focus: $2". Do not suggest where bugs might be.
2. **Skeptic** — when the hunter finishes, launch `skeptic` with the hunter's full BUG-* blocks (not the leads). Add no commentary of your own.
3. **Referee** — apply these rules mechanically. Do not re-argue any verdict:
   - CONFIRMED + hunter confidence HIGH + skeptic `Severity: unchanged` → **Verified bugs**
   - CONFIRMED with confidence MEDIUM, or with a changed or missing skeptic severity line, or UNPROVEN →
     **Probable — needs repro**. For a changed severity show `severity: <hunter's> → <skeptic's> — <skeptic's why>`
   - REFUTED → **Dismissed** (one line each, with the skeptic's reason)
   - Hunter's leads → **Leads** (unchanged)
4. **Persist** — call the write tool (a real tool call; text in your reply is not a file) with path
   mini-projects/$1/BUGHUNT.md and the four sections, in that order, as content. First line:
   `# BUGHUNT — $1 — <today's date>`; end with the hunter's Coverage block. Then call the shell tool with
   `ls mini-projects/$1/BUGHUNT.md`. If ls fails, call the write tool again once. Never say the file exists unless ls showed it.
5. Show the four sections. Do not fix anything until the human chooses which bugs to fix.

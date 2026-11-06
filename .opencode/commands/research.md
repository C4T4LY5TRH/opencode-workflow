---
description: Gather facts with citations, read docs pages, or look at a rendered page. Writes RESEARCH/*.md.
agent: orchestrator
---
Topic / question / URL: $ARGUMENTS

Where it goes: if the first word is the name of an existing project under mini-projects/, the file goes in mini-projects/<slug>/RESEARCH/ (the rest is the question). Otherwise it goes in the workshop-root RESEARCH/.

Delegate: @researcher answer this. Give it the exact RESEARCH/ folder to write into.
- A docs or article page (static): fetch it into <folder>/<topic>.md with webfetch (markdown is its default) or a playwright snapshot, then read it back.
- A page that needs JavaScript, or "what does this page look like": open it with playwright, snapshot AND screenshot, report what is visible (SAW / BROKEN / MISSING / FIX LIST). A local app: use the dev server URL.
Every claim needs a URL. Record dead ends.
After: key findings in 5 bullets max + the list of UNKNOWNS. Handoff check: run `ls` on the file; never say it exists unless ls shows it.

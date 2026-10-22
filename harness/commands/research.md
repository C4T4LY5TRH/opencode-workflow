---
description: Gather facts with citations. Writes RESEARCH/*.md.
agent: orchestrator
---
Topic / question: $ARGUMENTS

Delegate: @researcher answer this. Write into RESEARCH/ of the current project.
Use html2md skill for static docs pages, playwright for JS pages.
Every claim needs URL. Dead ends recorded.
After: give the key findings in 5 bullets max + list of UNKNOWNS.

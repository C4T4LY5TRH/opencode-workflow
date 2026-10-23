---
description: Fetch a page and convert it to clean markdown for cheap ingestion.
agent: orchestrator
---
URL: $ARGUMENTS

Delegate: @researcher use the html2md skill to fetch this page into RESEARCH/<topic>.md of the current project, then read it back.
After: the key content in <=10 bullets. Keep the file full.
If the page needs JS (empty result), say so and use /browse instead.

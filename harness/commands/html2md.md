---
description: Fetch a page and convert it to clean markdown for cheap ingestion.
agent: orchestrator
---
URL: $ARGUMENTS

Use the `html2md` skill. Write result to RESEARCH/<topic>.md in the current project (or ./ if no project).
Then read the markdown and give the key content in <=10 bullets. Keep the file full.
If page needs JS (empty result), say so and use /browse instead.

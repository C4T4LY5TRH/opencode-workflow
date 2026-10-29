---
name: html2md
description: Convert a web page (or local HTML) to clean readable markdown for cheap agent ingestion. Use for docs, articles, any static page.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "true"
---
# html2md

Script, from the workshop root: `python3 scripts/html2md.py <url|file>` (exactly that spelling; it prints the markdown).
Save it with the write tool: an agent shell with no project workdir is read-only, so `-o` cannot write there.

What it does (stdlib only, no installs):
- fetch with browser-like UA
- drop script/style/nav/footer/header/aside/form/svg/noscript
- keep h1-h6, p, ul/ol/li, pre/code, a (keep text + url), table rows, blockquote, hr
- collapse blank lines, strip nav junk
- if `pandoc` on PATH -> uses pandoc for better tables/markdown, else internal converter

## When to use
- docs page, blog post, API reference, changelog, README on web
- save to `RESEARCH/<topic>.md` then read the file (cheaper than reading raw HTML)

## When NOT to use
- page needs JS/login -> use `browser` skill + playwright snapshot instead
- huge index pages -> narrow URL first

## Rules
- Keep source URL as first line: `<!-- source: <url> fetched: <date> -->`
- Do not edit content meaning. Code blocks verbatim.
- If output looks truncated or empty, page is JS-driven -> switch to browser skill.

---
description: Open a page in a real browser, get structure snapshot + screenshot.
agent: orchestrator
---
URL: $ARGUMENTS

Delegate: @visual-review open this URL, snapshot it AND take a screenshot, then report what is actually visible.
If it is a local app, use the dev server URL (check package.json scripts).
Report: SAW / BROKEN (checklist) / MISSING vs PLAN / FIX LIST (smallest first).

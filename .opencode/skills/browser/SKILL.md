---
name: browser
description: Drive a real browser via Playwright MCP - navigate, snapshot text structure, screenshot to SEE the page, fill forms, read console and network. Use for JS-heavy pages, UI checks, scraping.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "true"
---
# Browser (Playwright MCP)

Tools are namespaced `playwright_*`. If a name differs, list available tools and adapt.

Two agents use a browser; each gets only part of the tools.
- Researcher: `navigate`, `snapshot`, `take_screenshot` (no `filename`), `click`, `type`, `wait_for`, `close`, `resize`.
- Designer: everything except `evaluate`, `run_code`, `run_code_unsafe`, `route`, `file_upload`, `drop`, `install`. Pages only on
  its own project's localhost port. Screenshots only as `mini-projects/<slug>/design/shots/<name>.png` (the `filename` argument).
- Builders and every other agent: no browser.

Tools:
- `playwright_browser_navigate` {url}
- `playwright_browser_snapshot` - accessibility/text snapshot of current page (cheap to read)
- `playwright_browser_take_screenshot` - PNG you can actually LOOK at
- `playwright_browser_resize` {width,height} - phone and laptop widths
- `playwright_browser_click` / `_type` / `_wait_for` {text|time} / `_close`; the designer also has hover, form filling, key presses, `_console_messages`, `_network_requests`

## Loop that works
1. navigate -> 2. wait_for (load/text) -> 3. snapshot for TEXT -> 4. screenshot for PIXELS -> 5. close/leave tab

## Rules
- Snapshot = what page says. Screenshot = what page looks like. Never report visuals from snapshot alone.
- Screenshot needs a rendered tab. Wait for content before shooting.
- Read console + network before blaming a page for being broken.
- If page needs auth, ask human. Never guess credentials.
- Read data from the snapshot (it is text), not from screenshot pixels.
- Use `browser_snapshot` result, not page memory, when quoting text.

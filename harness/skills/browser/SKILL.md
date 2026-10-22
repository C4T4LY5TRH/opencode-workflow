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

Core tools:
- `playwright_browser_navigate` {url}
- `playwright_browser_snapshot` - accessibility/text snapshot of current page (cheap to read)
- `playwright_browser_take_screenshot` - PNG you can actually LOOK at
- `playwright_browser_resize` {width,height} - test viewport sizes
- `playwright_browser_click` / `_hover` / `_type` / `_fill` / `_select_option` / `_press_key`
- `playwright_browser_evaluate` {function} - run JS in page, return JSON
- `playwright_browser_console_messages` / `_network_requests` - diagnostics
- `playwright_browser_tabs` (list/switch) , `playwright_browser_wait_for` {text|time}
- `playwright_browser_resize` for mobile width check

## Loop that works
1. navigate -> 2. wait_for (load/text) -> 3. snapshot for TEXT -> 4. screenshot for PIXELS -> 5. evaluate for data (tables, JSON in page) -> 6. close/leave tab

## Rules
- Snapshot = what page says. Screenshot = what page looks like. Never report visuals from snapshot alone.
- Screenshot needs a rendered tab. Wait for content before shooting.
- Read console + network before blaming a page for being broken.
- If page needs auth, ask human. Never guess credentials.
- Extract structured data with `evaluate`, not by reading screenshot text.
- Use `browser_snapshot` result, not page memory, when quoting text.

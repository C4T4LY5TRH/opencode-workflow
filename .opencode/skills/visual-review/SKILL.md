---
name: visual-review
description: See-and-fix loop for UI - screenshot the rendered page, list what is visually broken, give smallest fixes. Use after building UI or when checking a page.
license: MIT
compatibility: opencode
metadata:
  opencode/slash: "true"
---
# Visual review (see, don't guess)

## Loop
1. Start app (check package.json scripts / dev server). Get URL.
2. Navigate. Wait for content.
3. Snapshot (text truth) + Screenshot (pixel truth). LOOK at the image.
4. Check at 2 widths: 1440 and 390.
5. Report, fix (builder), re-screenshot. Loop until clean.

## What counts as BROKEN
- Text overflowing / clipped / overlapping
- Unreadable contrast, invisible text on bg
- Broken or missing image, icon, font
- Button without label, link that looks like text
- Misalignment, inconsistent spacing, ragged grid
- Raw markdown / JSON / placeholder text visible in UI
- Horizontal scrollbar on mobile
- Content jumping (no fixed size, no reserved space)
- Dead hover/focus state, invisible cursor

## What is NOT broken (do not report as bug)
- Taste preference with no stated rule
- Missing feature not in PLAN

## Output (exact)
```
# VISUAL — <url> @ <widths>
## SAW
## BROKEN
- [ ] <element> — <what is wrong>
## MISSING vs PLAN
- <plan item> — visible? yes/no
## FIX LIST (smallest first)
```

Report only what you SAW. If screenshot failed, say so. No invention.

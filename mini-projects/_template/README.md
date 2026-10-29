# {{SLUG}}

{{GOAL}}

## How this project moves through the harness
One command drives it: `/go {{SLUG}}`. It does the next thing and stops. The gates check for the files below, so
they appear only when their agent writes them.

| Step | Command | Writes |
|---|---|---|
| purpose | `/new` | `BRIEF.md` (this scaffold) |
| plan | `/go {{SLUG}}` | `PLAN.md` (scope + numbered steps, each with a check) |
| approve | `/approve {{SLUG}}` | you read PLAN.md and approve it (recorded) |
| build | `/go {{SLUG}}`, once per step | code; a step is done when its check passes |
| review | `/go {{SLUG}}` after the last step | `REVIEW.md` (verdict and blind spots) |
| ship | `/ship {{SLUG}}` | a commit, after you say yes |

`/status {{SLUG}}` shows where it is. `NOTES.md` is the running log. `LEARNINGS.md` is what this project teaches the
brain (`/ship` drafts a proposal from it).

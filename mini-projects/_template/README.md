# {{SLUG}}

{{GOAL}}

## How this project moves through the harness
Each step writes one file. The gates check for those files, so they appear only when their agent writes them.

| Step | Command | Writes |
|---|---|---|
| purpose | `/new` | `BRIEF.md` (this scaffold) |
| scope | `/scope {{SLUG}}` | `SCOPE.md` |
| research (optional) | `/research <question>` | `RESEARCH/*.md` |
| plan | `/plan {{SLUG}}` | `PLAN.md` — you approve it |
| build | `/build {{SLUG}}` | code, one step at a time |
| review | `/review {{SLUG}}` | `REVIEW.md` |
| blind spots | `/blind {{SLUG}}` | `BLIND.md` |
| ship | `/ship {{SLUG}}` | a commit, after you say yes |

`NOTES.md` is the running log. `LEARNINGS.md` is what this project teaches the brain (`/learn {{SLUG}}`).

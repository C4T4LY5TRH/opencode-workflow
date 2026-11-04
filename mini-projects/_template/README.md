# {{SLUG}}

{{GOAL}}

## How this project moves through the harness
Answer the brainstormer in chat, then `/go {{SLUG}}` does the next thing and stops. The gates check for the files
below, so they appear only when their agent writes them.

| Step | Command | Writes |
|---|---|---|
| idea | `/new` | `BRIEF.md` (a first draft with questions; this scaffold until then) |
| brainstorm | answer in chat, or `/brainstorm {{SLUG}} [topic]` | `BRIEF.md` (rounds until you are happy), `BRAINSTORM.md` for a topic |
| design | `/go {{SLUG}}` | locks the brief, then `ARCHITECTURE.md`, `PLAN.md` (one milestone) and a `CRITIQUE.md` round with its answers |
| decide | `/approve {{SLUG}}` or `/critique {{SLUG}}` | you read the digest: approve it (recorded) or ask for one more critic round |
| build | `/go {{SLUG}}`, once per step | code; a step is done when its check passes (step 1 spikes the riskiest part) |
| review | `/go {{SLUG}}` after the last step | `REVIEW.md` (verdict and blind spots) |
| ship | `/ship {{SLUG}}`, then `/ship {{SLUG}} yes` | a checklist, then the milestone commit and tag (you never commit by hand; `/publish` pushes); the next `/go` plans the next milestone |

`/status {{SLUG}}` shows where it is. `NOTES.md` is the running log. `LEARNINGS.md` is what this project taught.

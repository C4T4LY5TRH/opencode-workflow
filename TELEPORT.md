# TELEPORT — moving this harness to another machine

Built and tested. Read this before you copy anything.

## The short answer

**Do NOT copy `~/.config/opencode` and ask an agent to rebuild it.** That is slow, lossy,
and it re-derives something that is already exact.

**The repo IS the portable artifact.** It has zero machine-specific paths, full git history,
and one script rebuilds the live install on any machine.

```
ON THE OLD MACHINE                MOVE THIS FILE             ON THE NEW MACHINE
--------------------              -------------             -------------------
bash harness/scripts/              harness-teleport-*.tar.gz    bash harness/scripts/
     teleport.sh pack      --->   (244 KB)          --->         teleport.sh unpack <file>
                                                          then
                                                          bash harness/scripts/install.sh
                                                          bash ~/.config/opencode/scripts/bench.sh
```

## Why not copy ~/.config/opencode

That directory holds two different things:

| Thing | Belongs to | Copy it? |
|---|---|---|
| `agents/ commands/ skills/ plugins/ brain/ scripts/ opencode.json AGENTS.md` | **this harness** | yes — but get it from the repo, not from the live dir |
| `cli.json service.json themes tui.json` | opencode itself | no — opencode regenerates these |
| `brain/.plugins-alive` `brain/.hook-payload.json` `brain/SESSIONS.log` `brain/evals/last-run.json` | runtime state of THIS machine | no — stale heartbeats would make the bench lie |
| `.backups/<timestamp>/` | install history | no |

Copying the live dir drags machine-local state and opencode's own files into a new machine.
The repo has none of that: it is pure source.

## What the bundle contains

`harness-teleport-<timestamp>.tar.gz`, ~244 KB:

- every git-tracked file of the workshop repo
- the full `.git` directory → the target repo is a real clone with all history
- untracked-but-intentional files (e.g. a `HANDBOOK.md` you edited but have not committed)

**Not** included, by design:

- `mini-projects/<your-projects>/` → your project work stays yours. The `_template/` is
  included because it is harness source.
- `.playwright-mcp/` → browser scratch
- the live install `~/.config/opencode` → rebuilt by `install.sh`
- opencode's state `~/.local/share/opencode` → not yours, not portable
- secrets → none exist in the repo. If you add a Claude key, it goes in opencode's auth
  store on each machine, never in git.

## The three commands

### 1. Pack (on the old machine)

```bash
cd ~/Projects/opencode
bash harness/scripts/teleport.sh pack
```

Output:

```
bundle: ~/Projects/opencode/harness-teleport-20261022-121457.tar.gz
size:   244K
files:  81
git:    included (full history)
```

Options:
- `pack <name>.tar.gz` → custom output path
- `pack <name>.tar.gz --no-git` → files only, no history (smaller, not a clone)

### 2. Unpack (on the new machine)

```bash
# move the .tar.gz across however you like (scp, cloud drive, USB, airdrop)
bash harness/scripts/teleport.sh unpack ~/Downloads/harness-teleport-20261022-121457.tar.gz
```

Defaults to `$HOME/Projects/opencode`. Pass a second argument for a different path.

### 3. Verify before installing

```bash
bash harness/scripts/teleport.sh verify ~/Projects/opencode
```

Checks the 20 files that must exist and the 5 counts that must match:

```
  agents=11 (want 11)  commands=17 (want 17)  skills=7 (want 7)  plugins=3 (want 3)  rules=8 (want 8)

BUNDLE OK - ~/Projects/opencode is ready to install
```

### 4. Install

```bash
cd ~/Projects/opencode
bash harness/scripts/install.sh
```

This syncs `harness/` → `~/.config/opencode`, writes `workspace.txt` (points at wherever you
unpacked it — the path is not hardcoded), backs up the old copy to `.backups/<ts>/`, and
restarts the opencode service so the new plugins and agents load.

### 5. Prove it

```bash
bash ~/.config/opencode/scripts/bench.sh
```

Expect `passed 27 / 27   failed 0`.

## Prerequisites on the new machine

| Need | Why | Command |
|---|---|---|
| opencode | the whole harness runs inside it | install the same version — `opencode --version` |
| node + npx | Playwright MCP server + `snapshot.py` | `brew install node` |
| python3 | `bench.py`, `html2md.py` | macOS ships it; Linux: `apt install python3` |
| chromium | `/browse`, `/html2md` on JS pages, `snapshot.py` | `npx playwright install chromium` |
| git | the bundle is built from tracked files | `brew install git` |

Auth: **not needed** for the free models — this machine runs the whole harness with zero
authenticated integrations. If you add your own Anthropic key, do it per machine:

```bash
opencode auth login
```

Never put the key in the repo. The bundle does not contain it.

## Verified round trip

This was tested end to end, not assumed:

| Step | Result |
|---|---|
| pack | 244 KB, 81 files, `.git` included |
| unpack to a fresh path | tree identical, `git log` shows all 5 commits |
| `git status` in the unpacked repo | clean (byte-for-byte match) |
| `teleport.sh verify` | all 20 files PASS, all 5 counts correct |
| `install.sh` into an empty config dir | all 6 dirs + 2 files synced, `workspace.txt` written to the NEW path |
| bench against the fresh install | 25/26 — the 1 fail is `plugins-alive`, correct: opencode had not run with that config dir yet |

### The bug this round trip found

`install.sh` **died on any genuinely fresh machine**. The backup-prune step ran
`ls -1dt "$BACKUPS"/*/` — when `.backups/` is empty the glob matches nothing, `ls` exits 1,
and `set -euo pipefail` killed the script right there. On this machine it never fired because
a legacy backup directory already existed.

Impact: on a new machine the install would stop **before** writing `workspace.txt` and
**before** restarting the service. The gates would be missing. Silent, and only on the one
machine you have never tested on.

*Fix:* glob-safe listing that never lets the prune abort the install, plus a test proving an
empty `.backups/` no longer stops it and that 8 backups still prune down to the 5 newest.

## If you prefer plain git

A remote is cleaner than a tarball for machines you sync often:

```bash
# on the old machine
git remote add origin git@github.com:you/opencode-harness.git
git push -u origin main

# on the new machine
git clone git@github.com:you/opencode-harness.git ~/Projects/opencode
cd ~/Projects/opencode
bash harness/scripts/install.sh
```

Same result, no bundle file to move. The bundle wins when there is no remote, no network, or
you want a point-in-time snapshot including uncommitted work.

## What is NOT portable

| Thing | Why | Fix on the new machine |
|---|---|---|
| mini projects | your work, not the harness | copy them separately, or push their own repos |
| the Claude/Anthropic key | secret, never in git | `opencode auth login` |
| opencode's session DB | machine-local runtime | nothing — it regenerates |
| playwright browser cache | 300 MB download | `npx playwright install chromium` |
| the absolute path of the repo | `workspace.txt` is written by `install.sh` from wherever you unpacked | automatic |

## One-line version

```bash
# old machine
bash harness/scripts/teleport.sh pack
# new machine
bash harness/scripts/teleport.sh unpack <bundle> && cd ~/Projects/opencode && \
  bash harness/scripts/install.sh && bash ~/.config/opencode/scripts/bench.sh
```

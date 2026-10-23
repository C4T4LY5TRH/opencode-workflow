# AUDIT — opencode one-man harness

Date: 2026-10-23 · Auditor: Claude (Opus) · Target commit: `d5a104a` (branch `harness-v2`)
Platform: OpenCode **v2.1.3** (installed binary `~/.opencode/bin/opencode`), macOS, free models only.

> **This is the actionable report.** Findings → fixes → tests → phased plan.
> Evidence lives in `docs/audit/evidence/`, platform facts in `docs/audit/research/`, the prior agent self-review in `docs/audit/REVIEW-agents-2026-10-22.md`. A reader-friendly web version of this report is linked at the end.

---

## 1. Verdict

**The design is good. The enforcement is not real yet, and the harness is installed in the wrong place.**

The architecture you asked for — one brain, many projects, planning≠building≠reviewing, gates in code, caveman voice, free tools, forever-evolving — is sound and mostly built. But every load-bearing safety claim fails in practice, and I proved it by running the real harness:

- The ship gate ("no commit without review") is skipped by one `&&`. **Proven live:** a `git commit` went through in a project with no `REVIEW.md` (`docs/audit/evidence/l7/live-probes-summary.txt`, probe 14b).
- The plan gate and ship gate are **no-ops in every new project**, because the scaffold ships the files the gates look for.
- A worker with `webfetch` denied **exfiltrated to the network anyway**, via Code Mode `fetch()` (probe 07, returned `200`).
- A long tool output was **silently cut in half before the model read it** (probe 01 / 03: a 40-step file became 20 steps).
- The permission config + 105 saved "always-allow" approvals (104 shell + 1 webfetch) resolve `rm -rf ~`, `git -C . reset --hard` and arbitrary `bash -c`/`python3`/`zsh` to **allow** for the coding agents. **Proven live:** `zsh -c '…'` ran with no prompt at the workshop root (probe 13c).
- `install.sh` — the command the docs tell you to run after every change — **deletes runtime state and any file you added by hand**, and it is the reason `SESSIONS.log` and the brain heartbeat vanish.

None of this is a design flaw. It is the predictable result of writing gates as prompt text and thin regexes on top of a permission model whose exact rules (last-match-wins, `**` is not special, saved approvals, Code Mode) were not yet known when the harness was built. Now they are known (`docs/audit/research/L0-config.md`, `docs/audit/research/L0-plugins.md`), and the fixes are concrete.

**Do not teleport this to your other machine yet** — you were right to hold off; the bundle ships every bug below. **Do move the install into `~/Projects/opencode` and delete the global copy** — that is both your stated preference and the correct call.

**Headline numbers**
- Safety-gate behavioural bench: **68 / 127** of real attack/– cases behave as a gate should (`docs/audit/evidence/l2/baseline-results.txt`). 59 wrong.
- Effective-permission matrix (`docs/audit/evidence/permission-matrix.txt`): destructive commands = **allow** for `coder`/`build` once saved approvals apply.
- 3 commands dead (`/map`, `/html2md`, `/evolve`-apply), 1 model missing (`whatif`), 1 model delisted (`reviewer`/`critic`).
- `brain-log` session logging: **never ran once** (wrong API).

---

## 2. Scope & method

**In scope:** the whole harness — `harness/{agents,commands,skills,plugins,brain,scripts}`, `opencode.json`, `AGENTS.md`, the project template, the docs (`README`, `HANDBOOK`, `TELEPORT`), and the live install in `~/.config/opencode`. Also: the fit against your original brief and against OpenCode v2.1.3's real behaviour.

**Method (9 layers):**
| Layer | What | Evidence |
|---|---|---|
| L0 | OpenCode v2.1.3 source ground truth (plugin API, permission eval, config discovery) | `docs/audit/research/L0-plugins.md`, `docs/audit/research/L0-config.md` |
| L1 | Brief & docs vs reality | §7 drift table |
| L2 | Gate plugins run in Node against 127 table-driven cases; fixes retested the same way | `docs/audit/evidence/l2/` |
| L3 | Effective per-agent permission matrix from OpenCode's *resolved* rules + the 105 saved DB approvals | `docs/audit/evidence/permission-matrix.txt` |
| L4 | command→agent→permission→file workflow trace + reference-design comparison | `docs/audit/research/L4-references.md` |
| L5 | `install.sh`/`new-project.sh`/`bench.py`/`teleport.sh` run against throwaway dirs | ledger |
| L6 | the learning loop, end to end | §6 |
| L7 | **8 live scenarios through the real `opencode run`** in a sandbox project | `docs/audit/evidence/l7/` |
| L8 | independent reviewer: refute my top findings + hunt for ones I missed | `docs/audit/research/L8-review.md` |

Everything destructive ran in throwaway dirs or a disposable `mini-projects/_audit-sandbox` (now deleted). The real service was never restarted; the real DB was read-only. Live findings are marked **[LIVE]**; source-derived ones **[SRC]**; Node-reproduced ones **[TEST]**.

---

## 3. Findings

Severity: **P0** a safety/gate claim is false in practice or data is lost · **P1** a feature is broken or a security hole needs a precondition · **P2** robustness/security hardening · **P3** polish. Each finding: evidence → impact → fix → how the fix is tested.

### P0 — safety claims false in practice / data loss

#### P0-1 — Ship gate bypassed by any command chaining **[LIVE]**
`harness/plugins/safety-gate.ts:198` — `if (/^\s*git\s+(commit|tag)\b/.test(cmd))`. Anchored to the whole string.
**Proven:** `git status --short && git commit --allow-empty -m …` committed in a project with no `REVIEW.md`/`BLIND.md` (probe 14b). Plain `git commit` is blocked (probe 14); one `&&` defeats it. `docs/audit/evidence/l2` also shows `cd sub && git commit`, `git -C . commit`, `FOO=1 git commit`, `sh -c 'git commit'`, `(git commit)` all bypass — 14 of 17 commit forms.
**Impact:** the gate the whole harness exists for does nothing against the way agents normally run commands.
**Fix:** this gate should not be a regex over shell text at all (see §5 target: the ship gate reads project state + verdict). As an interim, OpenCode already splits compound commands with tree-sitter and matches each sub-command separately — so a **`policies` rule** `{"action":"tool.use","resource":"shell:git commit*","effect":"deny"}` plus a plugin check keyed on the parsed sub-command catches every form. **Test:** `docs/audit/evidence/l2` S-group must go 17/17.

#### P0-2 — Scaffold ships the gate files, so gates are no-ops in every project **[LIVE+TEST]**
`harness/scripts/new-project.sh:38` copies the template, which contains `PLAN.md SCOPE.md REVIEW.md BLIND.md`. The plan gate (`:224 if (!isDoc && !has("PLAN.md"))`) and ship gate (`:199-205`) only check *existence*.
**Proven:** in a freshly scaffolded project, `has("PLAN.md")` is true from step zero (probe 01 saw them; `docs/audit/evidence/l2` SV01/P10). The behavioural baseline only ever "passed" because its tests used hand-made dirs, not scaffolds.
**Trap:** `bench.py:264` *requires* those four files in the template, so the bug is encoded in the bench — delete them from the template and the bench fails too. Fix both.
**Fix:** template ships **no** gate files; `new-project.sh` creates only `BRIEF.md`/`AGENTS.md`/`README.md`/`NOTES.md`/`LEARNINGS.md`. Gate files appear only when their owning agent writes them. Update `bench.py:264`. **Test:** `gate-test` asserts a fresh scaffold has no `PLAN/SCOPE/REVIEW/BLIND.md`.

#### P0-3 — `install.sh` deletes runtime state and anything you added by hand **[TEST]**
`harness/scripts/install.sh:49-55` removes every file in the config dir that is not in source. Confirmed in a sandbox: it deleted `SESSIONS.log`, `.plugins-alive`, `evals/last-run.json`, **and user-created `agents/*.md`, `skills/*`, `plugins/*.ts`, `brain/proposals/*`**. Only `opencode.json` + `AGENTS.md` are backed up (`:62-68`).
**Impact:** silent data loss on the exact command the docs say to run after every edit. Under the *global* install this also wipes anything else you keep in `~/.config/opencode`.
**Fix:** the migration to a project-local install (§5) **deletes `install.sh` entirely** — with the harness living in `~/Projects/opencode/.opencode/`, OpenCode loads it directly and hot-reloads on save (`docs/audit/research/L0-config.md` §6). No sync, no stale-cleanup, no drift. Runtime files move to a gitignored `.harness/` outside the watched config tree.

#### P0-4 — `quiet-output` silently truncates what the model reads **[LIVE]**
`harness/plugins/quiet-output.ts:48` hooks `execute.after` with **no tool filter**; `:19` truncates at 3000 chars keeping only "error-like" lines.
**Proven:** reading a 40-step file, the model received **20 steps** with the middle replaced by `… [quiet-output] 2050 chars hidden, 81 lines dropped, 0 error-like lines kept …` (probe 01). This hits `read` of `PLAN.md`/`REVIEW.md` and, per L8, **`subagent` return values** — so the orchestrator routes and gates on mangled worker reports (a dropped `VERDICT: REWORK` line vanishes).
**Impact:** the worst failure mode in an agent harness — a confident, wrong action on corrupted input, with no error. Also redundant: OpenCode already truncates at 2000 lines/50 KiB and **spills the full text to disk** (`docs/audit/research/L0-plugins.md` §7), and does it *after* this plugin, so the plugin only makes things worse.
**Fix:** **delete `quiet-output.ts`.** OpenCode's native truncation is safe (keeps head, saves full output, tells the model to page). **Test:** `gate-test` asserts a long `read` is not mutated by any plugin.

#### P0-5 — Code Mode `fetch()` exfiltrates past `webfetch: deny`; unsafe browser tool reachable by all **[LIVE]**
Every agent has Code Mode `execute` enabled (nobody denies `execute`), and Code Mode scripts get a global `fetch()` with any method/body, **no permission check, no plugin hook** (`docs/audit/research/L0-plugins.md` §2).
**Proven:** `coder` (which has `webfetch: deny`) ran `execute({code:"await fetch('https://example.com')"})` and got `200` (probe 07). Separately, while hunting for a way around a shell denial, an agent discovered via Code Mode `search()` the Playwright tool **`browser_run_code_unsafe`** ("executes arbitrary JavaScript in the Playwright server process, RCE-equivalent") — reachable by every agent because `tools: {"playwright_*": false}` is **dead config** in v2 (`docs/audit/research/L0-config.md` §4).
**Impact:** the single biggest security hole. Any agent reading an untrusted web page (researcher) or a poisoned file can POST your data out, regardless of `webfetch`/`curl` rules, and can reach an RCE-equivalent browser tool.
**Fix:** (1) deny `execute` for all agents (`policies` + per-agent) → turns Code Mode off, which also forces MCP tools to be **direct, hooked and permissioned**; (2) set `mcp.playwright.codemode: false`; (3) deny `playwright_browser_run_code_unsafe`, `playwright_browser_file_upload`, `playwright_browser_install` in `policies`; (4) run Playwright `--isolated` and pin its version. **Test:** live re-run of probe 07 must fail with permission denied.

#### P0-6 — Permission order + saved approvals resolve destructive commands to **allow** **[LIVE+TEST]**
OpenCode uses **last-match-wins** (`docs/audit/research/L0-config.md` §1). In `opencode.json` the specific denies (`rm -rf /`, `rm -rf ~`, …) are listed **before** the broad `"rm -rf *": "ask"`, so the broad `ask` wins and shadows them. Agent-level `"*"` rules shadow all global rules. Then 105 **saved "always-allow" approvals** in the DB (`rm *`, `bash *`, `zsh *`, `python3 *`, `curl *`, `git -C *`, `webfetch *`, …) turn every `ask` into `allow`.
**Proven:** the effective matrix (`docs/audit/evidence/permission-matrix.txt`) shows `rm -rf ~`, `git -C . reset --hard`, `bash -c 'rm -rf ~'` = **allow** for `coder`/`build`. Live: `zsh -c '…'` executed with no prompt at the workshop root but was rejected inside a fresh project (probe 13c vs 13b) — proving the saved approvals are doing it. L8 confirms what passes **both** the config layer and the plugin regex today: `git -C . reset --hard`, `git -C . push --force`, `rm -rf $HOME`, `rm --recursive --force /`, `find / -delete`.
**Impact:** the "dangerous command block … no way through" claim is false. The coding agents can hard-reset, force-push via `-C`, and delete your home dir.
**Fix:** (1) **clear the dangerous saved approvals** (`scripts/approvals.sh` wrapping `opencode api permission.saved.list/remove`); (2) reorder rules generic-first, specific-deny-last; (3) move hard stops into **`policies`** (deny beats agent rules *and* saved approvals, `docs/audit/research/L0-config.md` §1, verified against source); (4) deny the `-C`/long-flag/`$HOME` variants. **Test:** matrix re-run shows all destructive rows = deny for every agent; `gate-test` D-group 38/38.

### P1 — broken features / conditional security holes

#### P1-1 — `/map` is dead **[LIVE]** · `harness/commands/map.md:7` tells the orchestrator to delegate to `explore`, but `orchestrator.md:18-29` has no `explore` in its subagent allow-list. Live: the orchestrator could not spawn it and did the work itself (probe 01/02). **Fix:** add `explore: allow`, or (better, §5) make `/map` a direct read-only agent.

#### P1-2 — Models missing **[LIVE]** · `whatif` → `opencode/longcat-2.5-preview-free` does not exist; live error `Model unavailable` (probe 09). `reviewer`/`critic` → `minimax-m3.1-flash-free` is **no longer listed** by `opencode models` (still answered when called, but fragile). `NOTES-pending-claude-key.md` lists outdated Claude IDs. **Fix:** reassign to current free models (available: `beam-free`, `big-pickle`, `deepseek-v4.1-flash-free`, `flint-40b-free`, `glm-5.3-flash-free`, `mimo-v2.6-flash-free`, `nemotron-3-ultra-free`, `nemotron-3.5-lightning-free`, `nemotron-3.5-super-vl-free`); add a bench check that every agent `model:` resolves against `opencode models`.

#### P1-3 — Ship gate checks existence, not verdict · `safety-gate.ts:199-205` passes on any `REVIEW.md`, including the template's `VERDICT: TODO` and a real `VERDICT: REWORK`. **Fix:** the state-based ship gate (§5) reads the recorded verify + approval, not a filename.

#### P1-4 — `brain-log` session logging never ran once **[SRC, confirmed by absent file]** · `brain-log.ts:74` calls `ctx.event.subscribe(cb)` — but in v2 `subscribe()` returns an **AsyncIterable** and ignores the callback (`docs/audit/research/L0-plugins.md` §5). The event names (`file.edited`, `session.idle`, `session.error`) also don't exist in v2. So `SESSIONS.log` has never been written (and `install.sh` deletes it anyway). The context-pointer half **does** work. **Fix:** rebuild on the real API: `for await (const e of ctx.event.subscribe())` filtering `session.execution.*` / `session.step.ended`; write to `.harness/events.jsonl`.

#### P1-5 — `/html2md` and `/evolve`-apply and `/learn`-apply are dead · The orchestrator can't run `python3` or edit files, and no command delegates `/html2md` to an agent that can (probe 03: shell denied, degraded to loophole-hunting). `/evolve` and `/learn` have no agent allowed to apply approved rule changes (orchestrator `edit: deny`; the `brain` agent's write permission contradicts its own "never write" contract). **Fix:** route `/html2md` and `/research` file-writing to the `researcher`; make rule promotion a **human-typed** `/brain-apply` that runs a script (humans are trusted), never an agent write to `brain/rules/`.

#### P1-6 — The gate/session model is internally incoherent (deeper than REVIEW P1-8) **[TEST]** · Because `**/PLAN.md` does not match a bare `PLAN.md` (`**` is literal, `docs/audit/research/L0-config.md` §1): in a session **rooted in the project**, the plan gate fires, but `architect/scoper/reviewer/critic` **cannot write their own** `PLAN/SCOPE/REVIEW/BLIND.md` (bare name misses `**/X.md` → `"*": deny`) while **`coder` CAN overwrite them**. In a session **at the workshop root**, owners can write but the plan gate is **off** (`IN_PROJECT` false, `safety-gate.ts:123`). The two modes are mutually exclusive — the harness cannot be correct in either. **Fix:** fix file ownership by role in the plugin (not by edit-glob), and resolve the gated project from the **target path**, not the session dir, so it works from root or nested (§5).

#### P1-7 — Installed globally; deviates from your brief & approved schema **[LIVE]** · Your brief and the schema you approved put the harness in the workshop's `.opencode/`. It is in `~/.config/opencode`, so the orchestrator, caveman voice, gates and permissions apply to **every** OpenCode session anywhere under your home dir (a second recorded session did unrelated "JankyBorders" work under these rules). Also `~/.opencode` (the binary's dir) is loaded as a project config for every session under `$HOME` — a drop-in code-execution surface. **Fix:** §5 migration.

#### P1-8 — Core rules likely never loaded **[SRC]** · `instructions: ["AGENTS.md","brain/rules/000-core.md"]` with a **relative** path resolves only between the session dir and its git root (`docs/audit/research/L0-config.md` §5d). The workshop root has no `brain/`, so `000-core.md` — the always-on rules — is never injected in workshop or project sessions. **Fix:** put core rules in `AGENTS.md` (auto-walked to `$HOME`) and/or use an absolute instructions path.

#### P1-9 — No shared state; approval & handoff live only in chat · `/grill` and `/whatif` write nothing (devil/whatif have `edit: deny`, orchestrator too) — their output is chat-only, so `architect`/`critic` never see it. Plan "approval" is a chat sentence the gate never checks. The coder infers "the NEXT step" from `PLAN.md` with no status markers, so it repeats/skips steps across sessions. **Fix:** durable `.harness/state.json` per project (§5): records approval (with plan hash), current step + status, verify results; agents hand off through it and through persisted `DEVIL.md`/`WHATIF.md`.

### P2 — hardening

- **P2-1 — Command injection surface.** `new.md:9` interpolates `$ARGUMENTS` into a shell string; and in v2 any `` !`cmd` `` in a command body runs **with no permission check** *after* `$ARGUMENTS` substitution (`docs/audit/research/L0-config.md` §7) — so `` !`…` `` typed into arguments executes. **Fix:** pass the goal via env/stdin to `new-project.sh`; never put `` !`…` `` where arguments land.
- **P2-2 — install.sh fragility.** Running the *installed* copy aborts (`cp … are identical`); only 2 files backed up. (Moot after §5 removes `install.sh`.)
- **P2-3 — Scripts.** `snapshot.py:54` ignores `--wait-for` (fixed 1500 ms); `@playwright/mcp@latest` and `npx -y playwright@latest` are **unpinned** (supply-chain). **Fix:** implement or rename the flag; pin versions.
- **P2-4 — Brain injection / self-modification.** `brain.md` may `edit` `brain/**` though its own prompt and rule `040` say "never auto-apply"; and `coder` can plant a **persistent cross-session prompt injection** via `echo >> <cfg>/brain/rules/x.md` (shell redirect evades its own `external_directory: deny`; the plugin whitelists the brain dir), which `brain-log` then injects into every future session (L8 B4). **Fix:** `brain/rules/` writable only by human-run scripts; plugin denies all agent writes under `brain/`, `.opencode/`, `scripts/`, `.git/`.
- **P2-5 — Destructive-regex gaps & false positives.** Misses `rm --recursive --force`, `--no-preserve-root`, `"$HOME"`, `find -delete`, `git checkout -- .`, `git restore .`, `chmod 0777`, `wget|sh`, `bash <(curl …)`; **false-positives** on `grep 'git reset --hard'` and a commit message mentioning `rm -rf /` (`docs/audit/evidence/l2`). **Fix:** `policies` resources are matched against parsed sub-commands, avoiding both classes; keep the plugin list only as defence-in-depth.
- **P2-6 — Secret exfil / cosmetic read-denies.** `read` denies on `.env`/`.ssh`/`.pem` are cosmetic: `cat .env` is **allow for all 11 agents** (shell `cat *`), and `grep`/`glob` run under their own action so read-denies don't apply (L8 B6). `curl --data @.env` is allowed (researcher `curl *`; coder/build saved `curl *`) (L8 B5). **Fix:** the shell sandbox (§5) denies reads of secret globs at the OS level — prototype proved `cat .env` blocked while `.env.example` and runtime still work (`docs/audit/evidence/sandbox-prototype.sb`); plus `policies` deny on `curl --data/-d/-F/-T/--upload`.
- **P2-7 — Bench blind spots.** The bench passes 27/27 **with a dead gate regex and a nonexistent model** (sandbox-confirmed); treats any file in `rules/` as a rule (a `.DS_Store` fails it); and **overwrites `last-run.json` at the end of its own run**, so `/bench`'s "compare with last run" can never work. **Fix:** add behavioural gate-firing checks (§5 `gate-test`); filter `*.md`; write run history to `.harness/evals/history/`.
- **P2-8 — PROOF contract unsatisfiable for 6/11 agents** (devil/whatif/critic/scoper/architect/reviewer have no runnable artifact), which **invites fabricated proof** and undermines "verify before claim" (L8 B3). **Fix:** role-specific report contract — `PROOF` only where a command exists; analysis agents report `BASIS` instead.
- **P2-9 — Reviewer can't verify.** `reviewer` allows only `npm test*`/`pnpm test*` — no `npm run`, `python3`, `pytest`, `bash`, `git log` — so it structurally cannot run most acceptance commands, making "no open blocker" rest on unverified reasoning. The `/ship` checklist also asks the orchestrator to check staged files and "nothing pushed", which its permissions can't do. **Fix:** widen reviewer's allow-list (inside the sandbox); move the mechanical ship checks into the plugin.
- **P2-10 — Dead `tools` config & persistent browser.** `tools: {"playwright_*": false}` is dead → Playwright on for all agents; the default profile is **persistent on disk** (cookies/logins survive across agent sessions). **Fix:** `--isolated`; deny via `policies` (P0-5).

### P3 — polish
`harness/tools/` is empty and meaningless (v2 has no file-based tools; `docs/audit/research/L0-plugins.md` §8) — delete. `.DS_Store` ships into the live config — exclude. Doc drift: "gate contract inlined in every agent" (actually 2/11), "no agent-to-agent channel" (v2 has parent↔child via `sessionID`), teleport "byte for byte" (ships untracked files + every bug). Legacy config keys dropped silently: `subagent_depth` → `experimental.subagent_depth`, `compaction.prune` (remove), `small_model` → `agents.title.model`. Duplicate `.DS_Store` in `.gitignore`. Count drift across HANDBOOK/README/baseline. `NOTES-pending-claude-key.md` stale.

---

## 4. Reconciliation with the prior reviews

Your agents' `REVIEW.md` (now `docs/audit/REVIEW-agents-2026-10-22.md`) and the second-opinion notes were **~85% right**. Verified against source + live:

| Their claim | My verdict |
|---|---|
| P0-1 `&&` ship bypass | **Confirmed, live** (probe 14b). Wider: `-C`, `sh -c`, subshell, env-prefix too. |
| P0-2 template ships gate files | **Confirmed, live + the bench encodes it** (`bench.py:264`). |
| P0-3 install deletes brain state | **Confirmed.** Nuance: `SESSIONS.log` is doubly dead — `install.sh` wipes it **and** `brain-log` never wrote it (P1-4). The second opinion's "heartbeat comes back" is right; the log does not. |
| P1-1 `/map` dead · P1-2 whatif model · P1-3 verdict · P1-5 quiet-output eats reads · P1-8 glob misses root file | **All confirmed** (several live). |
| P1-5 "promote to P0" | **Agree — it's P0-4 here** (confirmed live, and it eats subagent returns too). |
| P2-1/3/4/5/6/7/9/10 | Confirmed. |
| 2nd-opinion: Bug F (agent-field gating impossible) | **Refuted for v2.1.3** — the hook's `agent` field *does* carry the subagent's id (`docs/audit/research/L0-plugins.md` §3). Agent-aware gating is viable. |
| 2nd-opinion: `_template/.gitignore` exists (REVIEW P2-8 half-wrong) | **Confirmed** — it exists. |
| 2nd-opinion: "loses workspace pointer" | **Refuted** — install aborts but keeps `workspace.txt`. |
| 2nd-opinion: `harness/tools` is in the handbook (line 717) | **Confirmed** — buried, not absent; still delete it. |
| 2nd-opinion: `mini-projects/REVIEW.md` duplicate | **No longer present** — only the root `REVIEW.md` existed at audit time. |
| Their top rec: "a gate-fires test would have caught the P0s" | **Strongly agree — it's the single highest-value fix.** Built as `gate-test` in §5. |

**What both reviews missed** (because they lacked the platform facts / couldn't run it): Code Mode `fetch()` exfiltration and the unsafe Playwright tool (P0-5), saved approvals neutralising every `ask` (P0-6), the global-install blast radius (P1-7), core rules never loading (P1-8), the session-model incoherence (P1-6), and that the sandbox must not be the primary control (§5).

---

## 5. Target architecture & the fix

**One principle: state changes and safety live in code, not in model obedience.** Humans are trusted (typed commands, `` !`…` `` scripts). Agents are not (sandboxed shell, Code Mode off, writes confined by a plugin). Plugins are trusted code.

### 5.1 Move to a project-local install
```
~/Projects/opencode/                 workshop git repo
  AGENTS.md                          merged global+workshop rules + core rules (auto-loaded for any session under here)
  .opencode/                         ← what OpenCode loads & hot-reloads (no install.sh, no sync)
    opencode.json                    models (per-agent), permissions (ordered), policies (hard stops), mcp, instructions (absolute), compaction, experimental.subagent_depth
    agents/  commands/  skills/  plugins/
  brain/   scripts/   sandbox/       data + tooling (not auto-loaded)
  .harness/  (gitignored)            runtime: events.jsonl, rule-usage.json, plugins-alive
  mini-projects/<slug>/              each its own repo; .harness/state.json (workflow state)
    _template/                       NO gate files
```
Verified: a session inside a nested `mini-projects/<slug>` **does** pick up the workshop `.opencode/` (walk-up discovery, `docs/audit/research/L0-config.md` §5c). This removes `install.sh`, the sync/drift/data-loss class (P0-3, P2-2), and the global blast radius (P1-7). **Delete the global `~/.config/opencode` harness files** (keep `tui.json`/`service.json`) or OpenCode errors on duplicate plugin IDs.

### 5.2 Four enforcement layers (defence in depth)
1. **`policies`** (hard denies for all agents; beat agent rules *and* saved approvals): destructive git/rm/dd/mkfs/chmod/`curl --data`, opaque wrappers (`bash -c`, `eval`, bare shells reading stdin → kills `curl|sh`), `sudo`, `git config --global`, `launchctl`/`osascript`/`defaults`, `execute:*` (Code Mode off), `opencode *` (agents must not drive the API/approvals), edits under `.opencode/ .harness/ brain/ scripts/ .git/`, and the unsafe Playwright tools.
2. **Per-agent permissions**, deny-by-default, with root *and* `**/` patterns, correct ordering.
3. **`harness-gate.ts` plugin** — the real gates: resolve the project from the **target path**; ownership by **role** (not edit-glob); plan gate reads `.harness/state.json` (approved plan hash matches current `PLAN.md`); ship gate reads recorded verify + verdict; confine writes (edit/write/**patch patchText**/shell redirects) to the project; block Code Mode.
4. **`sandbox/oc-shell` via `ctx.shell.hook("create.before")`** — wrap agent shell in macOS `sandbox-exec` (prototype in `docs/audit/evidence/sandbox-prototype.sb`: blocks writes/`.env` reads outside the project incl. via `python3`/`node`/`cd`, allows runtimes + `/tmp`), and **scrub secret env vars**. This is defence-in-depth for shell only — **not** the primary control, because it does not cover Code Mode or the edit/write tools (L8). Human `` !`…` `` scripts are not wrapped.

### 5.3 Workflow state (fixes P0-1, P1-3, P1-6, P1-9)
`.harness/state.json` per project, written **only** by `scripts/state.py` (human-typed commands) and the plugin:
- `/approve` (human types it) hashes `PLAN.md` and records approval; editing the plan after revokes it.
- `/build` injects the exact next step; step status is tracked; the coder never guesses.
- a step is "done" only when its `done-when` command is re-run and exits 0 (recorded).
- the ship gate reads the recorded verdict + approval, not filenames.
- `/grill`→`DEVIL.md`, `/whatif`→`WHATIF.md` are persisted so later agents see them.

### 5.4 Fix the plugins & loop
Delete `quiet-output.ts` (P0-4). Rebuild `brain-log.ts` on the real event API + rule-usage counting into `.harness/rule-usage.json` (makes decay measurable — fixes P1-4, L6). Add `scripts/gate-test.mjs` (the Node harness in `docs/audit/evidence/l2/`) wired into the bench, asserting every gate **fires** — the single highest-value fix, and the one both prior reviews called for.

---

## 6. The learning loop (L6)

Today the loop can't run: most agents can't write `LEARNINGS.md`; `SESSIONS.log` is dead; `patterns/`/`anti-patterns/` are empty (the build's own 11 bugs never went through the brain's mechanism); "decay after 3 unused projects" has nothing counting usage; the bench is structural only. **After §5:** rule-usage telemetry makes decay real; every promoted rule ships with a behavioural eval; `/bench` compares against kept history; `/learn` and `/evolve` show pass-rates before/after — "I learn from my setup, my setup learns from me" becomes measurable, not aspirational.

---

## 7. Doc/brief drift (L1) — corrections to make

HANDBOOK/README/baseline/NOTES overstate what's enforced ("deny = no way through", "gate contract in every agent", "no agent channel", teleport "byte for byte"), and counts disagree (v1.5/v1.6, 25/27 checks, "12 files"). These get rewritten to match the fixed harness in the implementation phase, with every claim tied to a test.

---

## 8. Phased implementation plan

Done on `harness-v2`, each phase committed separately, `gate-test` + a live re-probe after each. **Nothing merges to `main` until the live re-probes pass.**

- **Phase 0 — stop the bleeding (fast, no redesign):** clear dangerous saved approvals; reorder permissions + add `policies` hard stops; disable Code Mode (`execute` deny) + `mcp.playwright.codemode:false` + deny unsafe Playwright tools; delete `quiet-output.ts`. → kills P0-4/5/6 and most of P2-5/6/10 immediately.
- **Phase 1 — migrate to project-local:** build `.opencode/`, fix `instructions`/paths/legacy keys, delete the global harness + `install.sh` + `teleport.sh` (rebuilt later), add `bootstrap.sh`. → P0-3, P1-7, P1-8.
- **Phase 2 — real gates + state:** `harness-gate.ts` (target-path project resolution, role ownership, state-based plan/ship gates), `.harness/state.json` + `state.py` + `/approve`, sandbox shell wrapper + env scrub. → P0-1, P0-2, P1-3, P1-6, P1-9, P2-1/4.
- **Phase 3 — gate-test + bench:** `gate-test.mjs` wired in (127 cases → green), model-resolves check, `*.md` filter, run history. → P2-7, regression safety.
- **Phase 4 — workflow repair:** fix `/map` `/html2md` `/evolve` `/learn`, reassign models, role-specific report contract, widen reviewer. → P1-1/2/5, P2-8/9.
- **Phase 5 — brain loop:** rebuild `brain-log.ts`, rule-usage telemetry, eval-per-rule. → P1-4, L6.
- **Phase 6 — docs + teleport redo + final verification:** rewrite docs to match; rebuild `teleport` from tracked files only, verified by a real round-trip into a sandbox; full live end-to-end project; `/doctor`-style check.

Each fix carries its test (named inline above). The plan is written so your own harness, once Phase 2 lands, can drive the later phases through `/plan`→`/build`.

---

## 8a. Implementation status (2026-10-23, branch `harness-v2`)

| Finding | Status | Verified by |
|---|---|---|
| P0-1 chained-commit bypass | **Fixed** — commit/tag/merge/cherry-pick/revert matched anywhere in a chain; `bash -c`/`sh -c`/`eval` denied by policy | `gate-test` s1–s7; policy matrix |
| P0-2 scaffold ships gate files | **Fixed** — template has no gate files; bench `template-clean` | live scaffold of `v2sandbox`; bench |
| P0-3 install.sh data loss | **Fixed by removal** — project-local install, no sync step; global copy archived | bench `no-global-harness`; workshop-only agent check |
| P0-4 quiet-output truncation | **Fixed** — plugin deleted | live: 160-line file read in full |
| P0-5 Code Mode exfil + unsafe browser tool | **Fixed** — `permission.execute: deny` (a policy deny alone did NOT hide the tool — caught live), unsafe Playwright tools denied, `codemode:false`, `--isolated`, pinned | live re-run: `execute` absent from coder's toolset; bench `code-mode-off` |
| P0-6 rule order + saved approvals | **Fixed** — 105 saved approvals removed via API (backed up); rules reordered; hard stops in `policies` | `docs/audit/evidence/permission-matrix-after.txt`: every destructive row = deny for every agent |
| P1-1 `/map` dead | **Fixed** | live: orchestrator → explore returned the tree |
| P1-2 broken models | **Fixed** — all 11 on models that answered a live ping (reviewer/critic/whatif were dead) | bench `models-resolve`; live reviewer + critic ALIVE |
| P1-3 verdict not checked | **Fixed** — ship gate requires `VERDICT: SHIP` | `gate-test` s9 |
| P1-4 brain-log dead | **Fixed** — rebuilt on the AsyncIterable event API; **v2.2:** rule-usage telemetry (L6) added, `scripts/rule-report.py` + `/evolve` show DECAY, every rule maps to an eval | plugin loads (heartbeat); events land in `.harness/events.jsonl`; `gate-test` t1–t3, d1–d2; bench `rules-have-evals`; live: a rule read landed in `rule-usage.json` |
| P1-5 `/html2md` `/evolve` `/learn` dead | **Fixed** — html2md via researcher; learn/evolve write proposals, human applies | command bodies + agent permissions |
| P1-6 ownership incoherence | **Fixed** — root + `**/` patterns; plan gate keyed on target project | permission matrix (architect-only PLAN.md, root and nested); `gate-test` p1–p4 |
| P1-7 global install | **Fixed** | outside-dir run is plain opencode; workshop has 16 agents |
| P1-8 core rules not loaded | **Fixed** — absolute `instructions` path + rules in `AGENTS.md` | config parse shows the absolute path |
| P1-9 no persisted handoff | **Fixed (v2.2)** — DEVIL.md/WHATIF.md persisted, /plan reads them; human-typed `/approve` records the PLAN.md hash in the project's `.harness/state.json`, the plan gate checks it, agents cannot write it | `gate-test` a1–a8, h1–h3; live: unapproved write refused, `/approve` via the command endpoint, approved write ok, PLAN.md edit revoked it, forged state refused |
| P2-1 argument injection | **Fixed** in `new-project.sh` (goal handled as data) | hostile-goal test: nothing executed |
| P2-3 snapshot flag / unpinned | **Fixed** — `--wait-for` waits for a selector; versions pinned | code |
| P2-4 brain self-modification | **Fixed** — brain writes `brain/proposals/` only; top-level edit deny | permission matrix |
| P2-5 regex gaps + false positives | **Fixed** — destructive moved to policies; plugin false positives gone | `gate-test` n1–n3 |
| P2-6 secret exfil via shell | **Fixed (v2.2)** — curl uploads denied by policy; every agent shell runs in a macOS sandbox (no `.env`/key/credential-store reads, writes only in the project, never `.harness/` or `.git/hooks|config`, secret env vars removed); `python3`/`node` now allow for the coder. Shell only: grep/glob tools and the Playwright MCP server are not covered | `gate-test` x1–x13 (real `sandbox-exec`; a disabled sandbox fails 9 of them); live: `cat .env` and an out-of-project `python3` write refused, in-project `node` write ok, token scrubbed, `/new` with a hostile goal stored it as text |
| P2-7 bench blind spots | **Fixed** — gates-fire, models-resolve, history + regression diff | bench 22/22 |
| P2-8 PROOF contract | **Fixed** — builders PROOF, analysts BASIS | agent files |
| P2-9 reviewer can't verify | **Fixed** — test runners allowed for reviewer | permission matrix (`npm test` = allow) |
| P2-10 dead tools config | **Fixed** | config parse |

**End-to-end proof (live, 2026-10-23):** a fresh project went scope → plan → build → review through
the real harness on free models: `SCOPE.md` → `PLAN.md` (1 step) → `src/hello.js` (plan gate passed
only because PLAN.md existed) → `node src/hello.js Ada` printed `hello Ada` → `REVIEW.md` with
`VERDICT: SHIP`. The first attempt failed in an instructive way: the architect *reported* writing
PLAN.md without ever calling the write tool ("fabricated completion"). Fixed with a write-before-report
rule in every agent and a file-exists handoff check in every producing command; recorded as
`brain/anti-patterns/fabricated-completion.md`.

**After the audit (same day):** the review kit (3 agents, 2 commands, 2 skills) was installed and hardened (`brain/CHANGELOG.md` v2.1).
Two findings came out of it that the audit missed: "read-only" allow-list entries can write or execute (`git diff --output=FILE`,
`rg --pre CMD`; now denied in `policies`, which also closes it for the original agents), and opencode also reads your Claude Code
skills (now switched off; the settings live outside the repo, see `TELEPORT.md`). Also fixed: the bench could be satisfied by the
gate test faking the plugin heartbeat, and the teleport procedure was never tested until the round trip above. The bench is now
24 checks; the gate test 25 cases. All test sessions and sandboxes created during the audit were deleted afterwards.

**Backlog closed (v2.2, 2026-10-24):** the follow-ups this audit left open are done, each with tests and a live run
through opencode 2.1.3 (`HANDBOOK.md` §14, `brain/CHANGELOG.md` v2.2): recorded plan approval via a human-typed
`/approve` (P1-9); an OS sandbox for every agent shell, with `python3`/`node` now allowed for the coder (P2-6); rule-usage
telemetry plus an eval per rule (L6); the `/hunt` referee now also requires the skeptic's severity to be unchanged; `/hunt`
writes `BUGHUNT.md`. Bench 26 checks; gate test 56 cases.

**Still open:**
1. Merge `harness-v2` into `main`, after you have run real projects through it and are happy with it.
2. Known limits, by design (`HANDBOOK.md` §4): the sandbox covers shell only (grep/glob tools and the Playwright MCP server
   are outside it), it is macOS-only, and network stays open.

---

## 9. Appendix — evidence
- `docs/audit/evidence/l2/` — gate bench: `run-gate.mjs`, `cases.json` (127), `baseline-results.txt` (68/127), `run-misc.mjs`.
- `docs/audit/evidence/l7/live-probes-summary.txt` — the 8 live `opencode run` scenarios + run scripts.
- `docs/audit/evidence/permission-matrix.txt` — effective permissions per agent incl. saved approvals.
- `docs/audit/evidence/sandbox-prototype.sb` — working macOS write/read confinement profile.
- `docs/audit/research/L0-plugins.md`, `docs/audit/research/L0-config.md` — OpenCode v2.1.3 source ground truth.
- `docs/audit/research/L4-references.md` — reference-design comparison & improvement menu.
- `docs/audit/research/L8-review.md` — independent verification + extra findings.
- `docs/audit/REVIEW-agents-2026-10-22.md` — your agents' prior self-review.

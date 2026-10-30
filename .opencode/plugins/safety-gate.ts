/**
 * safety-gate - defence-in-depth gates inside the opencode plugin layer.
 *
 * This is the SECOND layer. The FIRST layer is `policies` + per-agent permission
 * rules in opencode.json (a policy `deny` beats agent rules AND saved approvals;
 * see docs/audit/research/L0-config.md). This plugin adds the checks that the
 * permission layer cannot express:
 *   - ship gate: no AGENT `git commit`/`git tag` unless the recorded review says SHIP and is fresh
 *     (the project's code still hashes to what it was when REVIEW.md was written);
 *     matched by text anywhere in a command chain. The human's own commit is not seen here (/ship's status
 *     line is its freshness check), and agent.sb denies every agent write under .git anyway (R25 keeps this)
 *   - recording (execute.after): the current plan step's check result and the REVIEW.md verdict go
 *     into the project's .harness/state.json (spec section 7); this plugin is the only writer
 *   - plan gate: no code write in a mini project unless the human approved its current documents. The state
 *     library decides (`harness_state.py approved`, spec H1/H24): v4 = one hash over BRIEF + ARCHITECTURE
 *     (+ DESIGN) + PLAN and the plan's milestone not yet shipped; v3 mode = PLAN.md's hash. Any edit revokes it
 *   - approval is human-only: agents cannot write .harness/ or run approve.sh
 *   - write confinement: no edit/write/patch/shell-redirect outside the project; and, for EVERY session
 *     (workshop root too), the write tools may only write inside an existing mini-projects/<slug>/, brain/proposals/ or
 *     the workshop RESEARCH/, never through a symlink (checked on the real path, not the path text)
 *   - delegations (spec 7.2 rules 7-8): at most 16 delegation calls per human turn for each calling session
 *     (circuit breaker), one at a time per session and never in the background, and when a session whose
 *     delegation completed ends its turn, every mini-projects/<slug>/.harness/lock (the /go chain lock) is deleted.
 *     Turns come from ctx.event (spec 14 f)
 *   - OS sandbox: every shell runs through scripts/sandbox/agent-shell, which puts
 *     agent shells (AGENT=1) in a macOS sandbox that may write only the project the
 *     command runs in, nothing with no project (shell create.before hook; covers shell only, not edit/write)
 *
 * v2 plugin API: export default { id, setup }. Throwing in execute.before
 * rejects the tool call (docs/audit/research/L0-plugins.md).
 *
 * Paths resolve from THIS file's location (project-local install), never from
 * ~/.config/opencode or process.cwd().
 */

import { spawn, spawnSync } from "node:child_process"
import { appendFileSync, existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, realpathSync, renameSync, statSync, unlinkSync, writeFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

// .opencode/plugins/safety-gate.ts -> workshop root is two dirs up from .opencode
const PLUGIN_DIR = path.dirname(fileURLToPath(import.meta.url))
const WORKSHOP = path.resolve(PLUGIN_DIR, "..", "..")
const RUNTIME = path.join(WORKSHOP, ".harness")
const ALIVE_FILE = path.join(RUNTIME, "plugins-alive")
const SANDBOX_SHELL = path.join(WORKSHOP, "scripts", "sandbox", "agent-shell")
const STATE_PY = path.join(WORKSHOP, "scripts", "harness_state.py") // read-only verbs only (approved, review)
// Dashboard regeneration. A test run (HARNESS_TEST) must never write the real .harness/dashboard.html, so it
// spawns only the copy of status.py that the test names in HARNESS_TEST_STATUS_PY (and nothing if it names none).
const STATUS_PY = process.env.HARNESS_TEST
  ? process.env.HARNESS_TEST_STATUS_PY || ""
  : path.join(WORKSHOP, "scripts", "status.py")

/** Project docs: writing them never counts as "code" for the plan gate. Must agree with DOC_FILES in scripts/harness_state.py. */
const GATED_FILES = ["PLAN.md", "REVIEW.md", "CRITIQUE.md"]
const V4_DOCS = ["BRIEF.md", "ARCHITECTURE.md", "BRAINSTORM.md", "DESIGN.md"] // spec H15
const DOC_FILES = [...GATED_FILES, ...V4_DOCS, "BUGHUNT.md", "NOTES.md", "LEARNINGS.md", "AGENTS.md", "README.md"]
/** Files only one role may write (the edit denies are case-sensitive, so a different-case spelling is refused). */
const ALIAS_GUARDED = [...GATED_FILES, ...V4_DOCS, "BUGHUNT.md"]
const DOC_DIRS = ["RESEARCH"] // /research runs before a plan exists
const WRITE_TOOLS = new Set(["edit", "write", "patch", "multiedit"])

/** The tool id of a delegation in execute.before/after (spec 14 fact c; agent permissions still say `task:`). */
const DELEGATION_TOOL = "subagent"
/** Delegations one session may make in one human turn (spec 7.2 rule 7, H23). */
const BREAKER_CAP = 16
const TURN_START = "session.execution.started"
const TURN_END = new Set(["session.execution.succeeded", "session.execution.failed", "session.execution.interrupted"])

/** Harness state (approval). Only scripts/approve.sh, run by the human's /approve, writes it. */
const isHarnessState = (absTarget: string) => absTarget.toLowerCase().split(path.sep).includes(".harness")

/** Run a read-only harness_state.py verb; its stdout, or null on any failure. */
function stateCli(verb: string, proj: string, timeout = 20000): string | null {
  const r = spawnSync("python3", [STATE_PY, verb, proj], { encoding: "utf8", timeout })
  return r.status === 0 ? r.stdout.trim() : null
}

/** Are the project's documents, as they are now, the ones the human approved? The state library answers (H1:
 *  never re-implemented here); a failed or slow call reads as "no", so the gate fails closed. */
const planApproved = (proj: string) => stateCli("approved", proj) === "yes"

/** Regenerate .harness/dashboard.html in a detached child: never blocks and never throws into a tool call. */
function refreshDashboard() {
  if (!STATUS_PY) return
  try {
    const child = spawn("python3", [STATUS_PY, "--html"], { detached: true, stdio: "ignore" })
    child.on("error", () => {}) // a missing python3 is an async 'error' event; unhandled it would crash the host
    child.unref()
  } catch {
    // the dashboard is a convenience
  }
}

const stateFile = (proj: string) => path.join(proj, ".harness", "state.json")

/** The project's state object, or null when there is none or it is unreadable (then nothing is recorded). */
function readState(proj: string): any | null {
  try {
    const state = JSON.parse(readFileSync(stateFile(proj), "utf8"))
    return state && typeof state === "object" && !Array.isArray(state) ? state : null
  } catch {
    return null
  }
}

/** Atomic write (tmp + rename), like harness_state.save(). */
function writeState(proj: string, state: any) {
  const tmp = `${stateFile(proj)}.tmp`
  writeFileSync(tmp, JSON.stringify(state, null, 2) + "\n")
  renameSync(tmp, stateFile(proj))
}

const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, "Z")
const normCmd = (cmd: string) => cmd.trim().replace(/\s+/g, " ")
const lastLines = (text: string, n: number) => text.replace(/\r\n/g, "\n").replace(/\n+$/, "").split("\n").slice(-n).join("\n")

/** git subcommands that create a commit/tag and so must pass the ship gate. */
const COMMIT_VERBS = "commit|tag|merge|cherry-pick|revert|rebase|am"

/** Match a commit-creating git command anywhere in a chain (fixes the &&/-C/env-prefix/subshell bypass). */
function isCommitOrTag(cmd: string): boolean {
  for (let seg of cmd.split(/[;&|]+|\n/)) {
    seg = seg.trim().replace(/^[("'\s]+/, "") // strip leading ( " ' and space (subshells)
    seg = seg.replace(/^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+/, "") // strip leading ENV=val
    if (new RegExp(`^(?:/\\S+/)?git\\s+(?:-[A-Za-z]\\S*\\s+\\S+\\s+|--\\S+\\s+)*(?:${COMMIT_VERBS})\\b`).test(seg))
      return true
  }
  return false
}

/** Paths named inside an apply-patch blob. */
function patchTargets(patchText: string): string[] {
  const out: string[] = []
  for (const m of patchText.matchAll(/^\*\*\* (?:Add File|Update File|Delete File|Move to):\s*(.+)$/gm)) {
    out.push(m[1].trim())
  }
  return out
}

export default {
  id: "safety-gate",
  setup: async (ctx: any) => {
    try {
      // scripts/gate-test.mjs sets HARNESS_TEST so a test run cannot fake the "opencode loaded me" heartbeat
      if (!process.env.HARNESS_TEST) {
        if (!existsSync(RUNTIME)) mkdirSync(RUNTIME, { recursive: true })
        appendFileSync(ALIVE_FILE, `safety-gate loaded ${new Date().toISOString()}\n`)
      }
    } catch {
      // ignore
    }

    const location = ctx?.location
    const SESSION_DIR: string =
      location?.directory ?? location?.project?.directory ?? process.env.OPENCODE_PROJECT_DIR ?? process.cwd()

    /** nearest ancestor that holds mini-projects/ */
    const miniRoot = (() => {
      let dir = SESSION_DIR
      for (let i = 0; i < 8; i++) {
        if (existsSync(path.join(dir, "mini-projects"))) return path.join(dir, "mini-projects")
        const parent = path.dirname(dir)
        if (parent === dir) break
        dir = parent
      }
      return null
    })()

    const filePath = (input: any): string => {
      if (!input || typeof input !== "object") return ""
      const f = input.path ?? input.filePath ?? input.file
      return typeof f === "string" ? f : ""
    }

    const resolveTarget = (p: string): string => {
      if (!p) return ""
      if (p.startsWith("~/")) return path.join(process.env.HOME || "", p.slice(2))
      return path.resolve(SESSION_DIR, p) // always normalised (a/../b), absolute or not: projectOf walks parents
    }

    /** The mini project a TARGET path lives in (a direct child of mini-projects/). */
    const projectOf = (absTarget: string, root: string | null = miniRoot): string | null => {
      if (!root) return null
      let dir = absTarget
      for (let i = 0; i < 12; i++) {
        if (path.dirname(dir) === root) return dir
        const parent = path.dirname(dir)
        if (parent === dir) break
        dir = parent
      }
      return null
    }

    const sessionProject = (): string | null => {
      if (miniRoot && path.dirname(SESSION_DIR) === miniRoot) return SESSION_DIR
      return projectOf(SESSION_DIR)
    }

    const has = (proj: string | null, file: string) => Boolean(proj && existsSync(path.join(proj, file)))

    const outsideProject = (absTarget: string): boolean => {
      if (absTarget === "/dev/null" || absTarget === "/dev/stdout" || absTarget === "/dev/stderr") return false
      if (absTarget.startsWith("/tmp/") || absTarget === "/tmp" || absTarget.startsWith("/var/tmp/")) return false
      const proj = sessionProject()
      if (!proj) return false // workshop-root session: plugin does not confine (harness work)
      return path.relative(proj, absTarget).startsWith("..")
    }

    const shellWriteTargets = (cmd: string): string[] => {
      const out: string[] = []
      const add = (raw: string) => {
        const t = raw.replace(/^["']|["']$/g, "")
        if (t) out.push(resolveTarget(t))
      }
      for (const m of cmd.matchAll(/>>?\s*("|')?([^\s"'|;&]+)/g)) add(m[2])
      for (const m of cmd.matchAll(/\b(?:cp|mv|install)\s+(?:-[A-Za-z-]+\s+)*\S+\s+(\S+)/g)) add(m[1])
      for (const m of cmd.matchAll(/\b(?:mkdir|touch|tee)\s+(?:-[A-Za-z-]+\s+)*(\S+)/g)) add(m[1])
      return out
    }

    /** Throws unless this write may happen: harness state is off limits, code needs an approved plan. */
    const checkWrite = (absTarget: string, root: string | null = miniRoot) => {
      if (isHarnessState(absTarget)) {
        throw new Error(
          `SAFETY GATE: approval. ${absTarget} is harness state. Agents never write .harness/; the human records approval by typing /approve <slug>.`,
        )
      }
      // plan gate keyed on the project the TARGET lives in (works from workshop root or nested)
      const proj = projectOf(absTarget, root)
      if (!proj) return
      // case-insensitive disk: "review.md" would create the file the reviewer must later write as REVIEW.md
      // (and slip past the case-sensitive edit denies); only the exact spelling of a guarded file is allowed
      const base = path.basename(absTarget)
      const alias = ALIAS_GUARDED.find((f) => f.toLowerCase() === base.toLowerCase())
      if (alias && alias !== base && path.dirname(absTarget) === proj) {
        throw new Error(
          `SAFETY GATE: write confinement. ${base} is a different-case spelling of a project file (${alias}). Use the exact name.`,
        )
      }
      if (DOC_FILES.includes(path.basename(absTarget))) return
      if (DOC_DIRS.includes(path.relative(proj, absTarget).split(path.sep)[0])) return
      if (!has(proj, "PLAN.md")) {
        throw new Error(
          "SAFETY GATE: plan gate. No PLAN.md in project. Code cannot be written before a plan exists. Run /go <slug> to get one, the human approves with /approve <slug>.",
        )
      }
      if (!planApproved(proj)) {
        throw new Error(
          `SAFETY GATE: plan gate. ${path.basename(proj)} has no current approval: it was never approved, a plan document (BRIEF, ARCHITECTURE, DESIGN, PLAN) changed after /approve, or its milestone has shipped. /go ${path.basename(proj)} shows what is next; the human approves with /approve ${path.basename(proj)}.`,
        )
      }
    }

    const real = (p: string) => realpathSync.native(p)
    const lexists = (p: string) => {
      try {
        lstatSync(p)
        return true
      } catch {
        return false
      }
    }

    /**
     * The real (on-disk) spelling of a write-tool target, or a throw. The write tools follow symlinks and the
     * permission layer, the policies and the checks below only see path text, so: the target may not be a
     * symlink, and no existing component below the workshop root may be a symlink or a different-case alias
     * (macOS is case-insensitive: ".HARNESS" is ".harness"). The workshop itself may be spelled any way that
     * reaches it (this machine has ~/Projects/opencode and .../projects/opencode).
     */
    const realTarget = (target: string): string => {
      const refuse = (why: string) => {
        throw new Error(`SAFETY GATE: write confinement. ${target} ${why}. Write a plain file inside the mini project.`)
      }
      if (!miniRoot) refuse("is not inside a workshop")
      let ws = ""
      try {
        ws = real(path.dirname(miniRoot as string))
      } catch {
        refuse("cannot be checked (workshop root unreadable)")
      }
      let anc = target
      while (!lexists(anc) && path.dirname(anc) !== anc) anc = path.dirname(anc)
      if (anc === target && lstatSync(target).isSymbolicLink()) refuse("is a symlink")
      // the workshop root in the target's own spelling: the HIGHEST ancestor that resolves to it, so a link
      // inside the workshop that points back at the workshop shows up in the relative part below
      let top = ""
      for (let dir = anc; ; dir = path.dirname(dir)) {
        try {
          if (real(dir) === ws) top = dir
        } catch {
          // unreadable component: cannot be the workshop
        }
        if (path.dirname(dir) === dir) break
      }
      if (!top) refuse("is outside the workshop")
      let ancReal = ""
      try {
        ancReal = real(anc)
      } catch {
        refuse("passes a broken symlink")
      }
      if (ancReal !== path.join(ws, path.relative(top, anc))) refuse("passes through a symlink or a different-case alias")
      return path.join(ws, path.relative(top, target))
    }

    /** Write tools, every agent, every session dir: only an existing mini project (not _template), brain/proposals/ or the workshop RESEARCH/. */
    const confine = (realTgt: string) => {
      const ws = real(path.dirname(miniRoot as string))
      const mini = path.join(ws, "mini-projects")
      const parts = path.relative(mini, realTgt).split(path.sep)
      const inProject =
        parts.length >= 2 && parts[0] !== ".." && parts[0] !== "" && parts[0] !== "_template" &&
        (() => {
          try {
            return statSync(path.join(mini, parts[0])).isDirectory()
          } catch {
            return false
          }
        })()
      const prop = path.relative(path.join(ws, "brain", "proposals"), realTgt)
      const inProposals = prop !== "" && !prop.startsWith("..") && !path.isAbsolute(prop)
      // /research without a project writes the workshop-root RESEARCH/ folder (exactly that name, same real-path rules)
      const rsh = path.relative(path.join(ws, "RESEARCH"), realTgt)
      const inResearch = rsh !== "" && !rsh.startsWith("..") && !path.isAbsolute(rsh)
      if (!inProject && !inProposals && !inResearch) {
        throw new Error(
          `SAFETY GATE: write confinement. ${realTgt} is outside every mini project. Agents write only inside an existing mini-projects/<slug>/ (the brain: brain/proposals/; research: RESEARCH/). Harness files, scripts, rules and config are the human's.`,
        )
      }
      // a session started inside a project stays in that project
      const sp = sessionProject()
      if (sp) {
        let spReal = sp
        try {
          spReal = real(sp)
        } catch {
          // a missing session project: the relative check below refuses
        }
        if (path.relative(spReal, realTgt).startsWith("..")) {
          throw new Error(`SAFETY GATE: write outside project blocked. Target: ${realTgt}\nWrite inside the current mini project only.`)
        }
      }
      return mini
    }

    // Delegations, per CALLING session (event.sessionID). `turnCalls`: the agents a session asked for in this turn,
    // in order (the breaker). `running`: its delegation still open (R8: two calls in one model response would
    // otherwise run at the same time, spec 14 d). `delegated`: sessions whose delegation really ran (an execute.after
    // with status completed). Only their turn end frees the /go lock: execute.before fires for any tool name a model
    // emits, so a worker child that TRIES `subagent` reaches checkDelegation too, but with subagent_depth 1 its
    // call never completes (spec 14 c) — and its own turn end must not free the lock mid-chain (spec 14 f: root only).
    // The event bus is global, so turn events of sessions not in these maps are ignored.
    const turnCalls = new Map<string, string[]>()
    const running = new Map<string, string>()
    const delegated = new Set<string>()

    const checkDelegation = (event: any) => {
      const sid = String(event?.sessionID ?? "")
      const agent = typeof event?.input?.agent === "string" && event.input.agent ? event.input.agent : "unknown"
      if (event?.input?.background) {
        // a background call returns at once (its after clears `running`) and its completion wakes the parent in a
        // new busy period (a fresh count, and a turn end that frees the lock while the child still writes)
        throw new Error("SAFETY GATE: one delegation at a time. Background delegations are not allowed; call it in the foreground.")
      }
      const calls = turnCalls.get(sid) ?? []
      turnCalls.set(sid, calls)
      const busy = running.get(sid)
      if (busy !== undefined) {
        throw new Error(`SAFETY GATE: one delegation at a time. Wait for the running @${busy} to finish, then call the next one.`)
      }
      if (calls.length >= BREAKER_CAP) {
        const counts = new Map<string, number>()
        for (const a of calls) counts.set(a, (counts.get(a) ?? 0) + 1)
        const who = [...counts].map(([a, n]) => `${a}×${n}`).join(", ")
        throw new Error(
          `SAFETY GATE: circuit breaker. ${calls.length} delegations in this turn (${who}). Stop and tell the human; their next message resets it.`,
        )
      }
      calls.push(agent)
      running.set(sid, agent)
    }

    /** Delete every mini-projects/<slug>/.harness/lock: plain files only, never through a symlinked slug or .harness. */
    const clearLocks = () => {
      if (!miniRoot) return
      let slugs: string[] = []
      try {
        slugs = readdirSync(miniRoot)
      } catch {
        return
      }
      for (const slug of slugs) {
        try {
          const dir = path.join(miniRoot, slug)
          const lock = path.join(dir, ".harness", "lock")
          if (lstatSync(dir).isDirectory() && lstatSync(path.dirname(lock)).isDirectory() && lstatSync(lock).isFile()) unlinkSync(lock)
        } catch {
          // no lock here, or it cannot be removed: next.py's 30-minute expiry is the fallback
        }
      }
    }

    /** A human turn starts or ends (spec 14 f): reset that session's count; at the end also free the /go lock (P7). */
    const onTurnEvent = (e: any) => {
      const sid = e?.data?.sessionID
      if (typeof sid !== "string" || !turnCalls.has(sid)) return
      if (e.type === TURN_START) {
        turnCalls.set(sid, [])
        running.delete(sid)
      } else if (TURN_END.has(e.type)) {
        turnCalls.delete(sid)
        running.delete(sid) // the turn is over, so nothing it started is still running
        if (delegated.delete(sid)) clearLocks()
      }
    }

    // Not awaited: the loop runs for the life of the plugin and never throws into the host. If the stream fails
    // or ends while the plugin is still loaded, subscribe once more; if that ends too, say so in the heartbeat file.
    let unloading = false
    void (async () => {
      for (let attempt = 0; attempt < 2 && !unloading; attempt++) {
        try {
          for await (const e of ctx.event.subscribe()) {
            try {
              onTurnEvent(e)
            } catch {
              // one bad event never stops the loop
            }
          }
        } catch {
          // no event stream (or it failed): retried once below
        }
      }
      if (unloading || process.env.HARNESS_TEST) return
      try {
        appendFileSync(ALIVE_FILE, `safety-gate event loop stopped ${new Date().toISOString()}: circuit-breaker resets and /go lock clean-up are off until opencode restarts\n`)
      } catch {
        // ignore
      }
    })()

    // OS sandbox. The wrapper sandboxes only agent shells; the writable root is the project the
    // command runs in, else the session's project. No project (or _template): the workshop's .harness/, which
    // agent.sb never lets anyone write, so the shell is read-only (temp dirs and tool caches aside).
    await ctx.shell.hook("create.before", async (invocation: any) => {
      const cwd = resolveTarget(invocation.cwd || SESSION_DIR) // a relative workdir is resolved after this hook
      const proj = projectOf(cwd) ?? sessionProject()
      let root = proj && path.basename(proj) !== "_template" ? proj : null
      if (!root && miniRoot) {
        root = path.join(path.dirname(miniRoot), ".harness")
        try {
          mkdirSync(root, { recursive: true }) // the wrapper refuses a missing root
        } catch {
          // the wrapper refuses below
        }
      }
      let real = ""
      try {
        real = root ? realpathSync.native(root) : "" // the on-disk spelling: right whether or not the sandbox matches paths without case (this Mac's does, seen 2026-10-29)
      } catch {
        // missing root: the wrapper refuses to run unsandboxed
      }
      invocation.env.HARNESS_REAL_SHELL = invocation.shell
      invocation.env.HARNESS_SANDBOX_ROOT = real
      invocation.shell = SANDBOX_SHELL
    })

    await ctx.tool.hook("execute.before", async (event: any) => {
      const tool = String(event?.tool ?? "")
      const input = event?.input

      if (tool === DELEGATION_TOOL) return checkDelegation(event)

      if (tool === "shell") {
        const cmd = typeof input?.command === "string" ? input.command : ""

        if (isCommitOrTag(cmd)) {
          // the project the commit runs in (its workdir; no workdir = the session dir). Not parsed: git -C, cd;
          // the sandbox denies every agent write under .git, so such a commit fails anyway
          const proj = projectOf(resolveTarget(input?.workdir || SESSION_DIR))
          if (!proj) {
            throw new Error("SAFETY GATE: ship gate. This commit runs outside a mini project. Run git commit with workdir mini-projects/<slug>; the gate checks that project's review.")
          }
          if (!has(proj, "REVIEW.md")) {
            throw new Error("SAFETY GATE: ship gate. REVIEW.md missing. Run /go first; the review comes before any commit.")
          }
          const slug = path.basename(proj)
          // one read-only call: REVIEW.md as it reads now (a human may have edited it) and the tree hash now
          let live: any = null
          try {
            live = JSON.parse(stateCli("review", proj) ?? "null")
          } catch {
            // fails closed below
          }
          if (!live) throw new Error("SAFETY GATE: ship gate. cannot read the review or compute the tree hash, so freshness is unknown.")
          if (typeof live.verdict !== "string") {
            throw new Error(`SAFETY GATE: ship gate. review is missing: REVIEW.md has no VERDICT line. Run /go ${slug} to review.`)
          }
          // the recorded review (written by this plugin when REVIEW.md was written) must agree with the file
          const review = readState(proj)?.review
          if (live.verdict !== "SHIP" || (review && typeof review.verdict === "string" && review.verdict !== "SHIP")) {
            throw new Error(
              `SAFETY GATE: ship gate. review verdict is "${review?.verdict ?? live.verdict}", not SHIP. Fix the findings and re-review (/go ${slug}) before committing.`,
            )
          }
          if (!review || typeof review.verdict !== "string") {
            throw new Error(`SAFETY GATE: ship gate. review is missing: no recorded verdict for ${slug}. Run /go ${slug} to review.`)
          }
          if (review.tree_sha256 !== live.tree_sha256) {
            throw new Error(`SAFETY GATE: ship gate. review is stale: code changed since REVIEW.md; run /go ${slug} to review again.`)
          }
        }

        if (/approve\.sh/.test(cmd)) {
          throw new Error("SAFETY GATE: approval. Only the human approves a plan, by typing /approve <slug>.")
        }

        const targets = shellWriteTargets(cmd)
        const bad = targets.find((p) => outsideProject(p))
        if (bad) {
          throw new Error(
            `SAFETY GATE: shell write outside project blocked. Path: ${bad}\nWrite inside the current mini project only.`,
          )
        }
        for (const t of targets) checkWrite(t)
        return
      }

      if (WRITE_TOOLS.has(tool)) {
        // every path this call writes: the single path, or each path named in a patch blob
        const raws =
          tool === "patch" && typeof input?.patchText === "string" ? patchTargets(input.patchText) : [filePath(input)]
        for (const raw of raws) {
          if (!raw) continue
          const target = realTarget(resolveTarget(raw)) // real spelling: symlinks and case aliases refused
          const mini = confine(target)
          checkWrite(target, mini) // harness state + plan gate, on the real path
        }
      }
    })

    /** Record a shell run of the current step's check: exit 0 -> done, anything else -> a failed attempt. */
    const recordStep = (event: any) => {
      const input = event.input
      const cmd = typeof input?.command === "string" ? input.command : ""
      const dir = resolveTarget(input?.workdir || SESSION_DIR)
      const proj = projectOf(dir)
      if (!proj || dir !== proj) return // only a run at the project root counts; a subdirectory is "anything else"
      const state = readState(proj)
      if (!Array.isArray(state?.steps)) return
      const cur = state.steps.find((s: any) => s && typeof s === "object" && !s.done_at)
      if (!cur || typeof cur.check !== "string" || normCmd(cmd) !== normCmd(cur.check)) return
      const out = event.result?.output
      if (event.status !== "error" && out?.status === "running") return // background run: no result yet
      const exit = out?.exit ?? event.result?.metadata?.exit
      if (event.status !== "error" && exit === 0 && out?.timeout !== true) {
        cur.done_at = nowIso()
      } else {
        const text = event.status === "error" ? String(event.error?.message ?? event.error ?? "tool error") : String(out?.output ?? "")
        cur.attempts = (Number.isInteger(cur.attempts) ? cur.attempts : 0) + 1
        cur.last_failure = lastLines(text, 40)
      }
      writeState(proj, state)
      refreshDashboard()
    }

    /** Record the verdict of a REVIEW.md that was just written; no verdict line removes the record. */
    const recordReview = (proj: string) => {
      const info = JSON.parse(stateCli("review", proj, 5000) ?? "null") // short: spawnSync blocks the event loop
      const state = readState(proj) // read after the (slow) call to keep the read-write window short
      if (!state) return
      if (info && typeof info.verdict === "string" && typeof info.tree_sha256 === "string") {
        state.review = { tree_sha256: info.tree_sha256, verdict: info.verdict, at: nowIso() }
      } else {
        delete state.review // no verdict, or the CLI failed: the tree hash ignores REVIEW.md, so an old SHIP would stay "fresh"
      }
      writeState(proj, state)
      refreshDashboard()
    }

    await ctx.tool.hook("execute.after", async (event: any) => {
      try {
        if (event?.tool === DELEGATION_TOOL) {
          const sid = String(event?.sessionID ?? "")
          running.delete(sid) // any status (R8)
          if (event?.status === "completed" && turnCalls.has(sid)) delegated.add(sid) // it really delegated
          return
        }
        if (event?.tool === "shell") return recordStep(event)
        if (event?.status !== "completed" || !WRITE_TOOLS.has(String(event?.tool))) return
        const input = event.input
        const raws = event.tool === "patch" && typeof input?.patchText === "string" ? patchTargets(input.patchText) : [filePath(input)]
        for (const raw of raws) {
          const target = resolveTarget(raw)
          const proj = target ? projectOf(target) : null
          if (proj && target === path.join(proj, "REVIEW.md")) recordReview(proj)
        }
      } catch {
        // recording never breaks a tool call
      }
    })

    // opencode runs this before it closes the event stream on unload, so a normal unload is not reported as a stop
    return () => {
      unloading = true
    }
  },
}

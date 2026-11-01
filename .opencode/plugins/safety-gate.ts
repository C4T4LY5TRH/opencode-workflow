/**
 * safety-gate - defence-in-depth gates inside the opencode plugin layer.
 *
 * This is the SECOND layer. The FIRST is `policies` + per-agent permission rules in opencode.json (a policy `deny`
 * beats agent rules AND saved approvals; docs/audit/research/L0-config.md). This plugin adds what that layer cannot say:
 *   - ship gate: no AGENT commit or tag (matched anywhere in a command chain) unless the recorded review says SHIP and
 *     the code still hashes as it did then. The human's commit is not seen here (/ship's status line checks it), and
 *     agent.sb denies every agent write under .git anyway (R25 keeps this)
 *   - plan gate: no code write in a mini project unless the human approved its current documents; the state library
 *     decides (`harness_state.py approved`, spec H1/H24) and any edit revokes it. Approval is human-only: agents
 *     cannot write .harness/ or run approve.sh
 *   - write confinement: no write outside the session's project; the write tools, in EVERY session, only inside an
 *     existing mini-projects/<slug>/ or the workshop RESEARCH/, checked on the real path
 *   - write scope: a builder child writes only its step's files; qa and the designer only their own
 *   - recording (execute.after, piece 2 spec 6.3): step checks, the acceptance run and the REVIEW/QA/VISUAL verdicts
 *     go into .harness/state.json through one write queue
 *   - delegations (spec 7.2 rules 7-8): a circuit breaker per turn, at most 3 open, never in the background; a
 *     delegating turn's end frees the /go locks, and its tool calls keep its project's lock fresh (turns: spec 14 f)
 *   - the autopilot loop (piece 2 spec 3.2): the plugin sends /go <slug> and nothing else, ever
 *   - cost (spec 9.3 fact 7) and the browser (fact 6): see onCost and checkBrowser
 *   - OS sandbox: every shell runs through scripts/sandbox/agent-shell, which puts agent shells (AGENT=1) in a macOS
 *     sandbox that may write only the project the command runs in (shell create.before; not edit/write)
 *
 * v2 plugin API: export default { id, setup }. Throwing in execute.before rejects the tool call
 * (docs/audit/research/L0-plugins.md). Paths resolve from THIS file's location, never ~/.config/opencode or cwd.
 */

import { execFile, spawn } from "node:child_process"
import { appendFileSync, existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, realpathSync, renameSync, statSync, unlinkSync, writeFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

// .opencode/plugins/safety-gate.ts -> workshop root is two dirs up from .opencode
const PLUGIN_DIR = path.dirname(fileURLToPath(import.meta.url))
const WORKSHOP = path.resolve(PLUGIN_DIR, "..", "..")
const RUNTIME = path.join(WORKSHOP, ".harness")
const ALIVE_FILE = path.join(RUNTIME, "plugins-alive")
const SANDBOX_SHELL = path.join(WORKSHOP, "scripts", "sandbox", "agent-shell")
const SCRIPTS = path.join(WORKSHOP, "scripts")
// Dashboard regeneration. A test run (HARNESS_TEST) must never write the real .harness/dashboard.html, so it
// spawns only the copy of status.py that the test names in HARNESS_TEST_STATUS_PY (and nothing if it names none).
const STATUS_PY = process.env.HARNESS_TEST
  ? process.env.HARNESS_TEST_STATUS_PY || ""
  : path.join(WORKSHOP, "scripts", "status.py")

/** Project docs: writing them never counts as "code" for the plan gate. Must agree with DOC_FILES in scripts/harness_state.py. */
const GATED_FILES = ["PLAN.md", "REVIEW.md", "CRITIQUE.md"]
const V4_DOCS = ["BRIEF.md", "ARCHITECTURE.md", "BRAINSTORM.md", "DESIGN.md", "QA.md", "VISUAL.md"] // spec H15, piece 2 spec 4
// README.md is product code (piece 2 spec 8 gap ii): a step that lists it writes it under the plan gate
const DOC_FILES = [...GATED_FILES, ...V4_DOCS, "BUGHUNT.md", "NOTES.md", "LEARNINGS.md", "AGENTS.md"]
/** Files only one role may write (the edit denies are case-sensitive, so a different-case spelling is refused). */
const ALIAS_GUARDED = [...GATED_FILES, ...V4_DOCS, "BUGHUNT.md"]
const DOC_DIRS = ["RESEARCH", "design"] // /research and the designer's mockups come before a plan is approved; checkScope still holds builders
const WRITE_TOOLS = new Set(["edit", "write", "patch", "multiedit"])

/** The tool id of a delegation in execute.before/after (spec 14 fact c; agent permissions still say `task:`). */
const DELEGATION_TOOL = "subagent"
/** Delegations one session may make in one human turn (spec 7.2 rule 7, H23). */
const BREAKER_CAP = 16
/** Delegations one session may have open at once (piece 2 spec 6.3: one builder per ready step, up to 3). */
const MAX_OPEN = 3
const TURN_START = "session.execution.started"
const TURN_OK = "session.execution.succeeded"
const TURN_END = new Set([TURN_OK, "session.execution.failed", "session.execution.interrupted"])
/** spec 9.3 fact 7: the one event that carries cost to a plugin; its data.cost is the session's RUNNING total. */
const COST_EVENT = "session.usage.updated"
/** spec 9.3 fact 6: the Playwright MCP's tools (input `url`, `filename`). It writes files outside the agent sandbox. */
const MCP_PREFIX = "playwright_"
const MCP_NAV_TOOL = "playwright_browser_navigate"
const MCP_SHOT_TOOL = "playwright_browser_take_screenshot"
const SLUG_RE = /^[a-z0-9-][a-z0-9_-]*$/ // as approve.sh; `cap` and `retry` are /go words, never a slug the loop sends

/** Is `p` strictly below `dir` (compare real paths)? */
function inside(dir: string, p: string): boolean {
  const rel = path.relative(dir, p)
  return rel !== "" && !rel.startsWith("..") && !path.isAbsolute(rel)
}

/** Harness state (approval). Only scripts/approve.sh, run by the human's /approve, writes it. */
const isHarnessState = (absTarget: string) => absTarget.toLowerCase().split(path.sep).includes(".harness")

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

/** The one bridge to the state library (H1: never re-implemented here), asynchronous so the host is not blocked.
 *  Read-only; null on any failure, so every gate that asks fails closed. */
const PY_FACTS = [
  "import json, os, sys",
  "sys.dont_write_bytecode = True",
  "sys.path.insert(0, sys.argv[1])",
  "import harness_docs as d, harness_state as h",
  "mode, p = sys.argv[2], sys.argv[3]",
  "def text(name):",
  "    try:",
  "        with open(os.path.join(p, name), encoding='utf-8', errors='replace') as fh:",
  "            return fh.read()",
  "    except OSError:",
  "        return None",
  "if mode == 'approved':",
  "    out = {'approved': bool(h.approved(p))}",
  "elif mode == 'tests':", // the tests hash and QA.md's '- run:' line, '' when none
  "    t = text('QA.md')",
  "    out = {'tests': h.tests_sha256(p), 'run': d.parse_qa(t)['run'] if t is not None else ''}",
  "elif mode == 'milestone':",
  "    arch = h.docs(p)['arch']",
  "    out = {'milestone': h.current_milestone(p, h._state_or_empty(p), arch) if arch else None}",
  "else:",
  "    out = {'tree': h.tree_sha256(p)}",
  "if mode == 'qa':",
  "    t = text('QA.md')",
  "    out['verdict'] = d.parse_qa(t)['verdict'] if t is not None else None",
  "if mode == 'visual':",
  "    t = text('VISUAL.md')",
  "    out['verdict'] = d.parse_visual(t) if t is not None else None",
  "if mode == 'review':",
  "    out['verdict'] = h.review_verdict(p)",
  "print(json.dumps(out))",
].join("\n")

function pyFacts(mode: "approved" | "tree" | "tests" | "qa" | "visual" | "review" | "milestone", proj: string): Promise<any | null> {
  return new Promise((resolve) => {
    try {
      execFile("python3", ["-c", PY_FACTS, SCRIPTS, mode, proj], { encoding: "utf8", timeout: 20000 }, (err, stdout) => {
        if (err) return resolve(null)
        try {
          resolve(JSON.parse(String(stdout).trim()))
        } catch {
          resolve(null)
        }
      })
    } catch {
      resolve(null)
    }
  })
}

/** Are the project's documents, as they are now, the ones the human approved? (spec H1/H24) */
const planApproved = async (proj: string) => (await pyFacts("approved", proj))?.approved === true

const stateFile = (proj: string) => path.join(proj, ".harness", "state.json")
const isObj = (v: any) => Boolean(v) && typeof v === "object" && !Array.isArray(v)
const isStr = (v: any): v is string => typeof v === "string"
const stepsOf = (st: any): any[] => (Array.isArray(st?.steps) ? st.steps.filter(isObj) : [])
/** The milestone of the recorded (approved) steps: qa, verify and visual are recorded with it (T7-R8). */
const msOf = (st: any): string | undefined => {
  const m = stepsOf(st)[0]?.milestone
  return isStr(m) ? m : undefined
}

/** The project's state object, or null when there is none or it is unreadable (then nothing is recorded). */
function readState(proj: string): any | null {
  try {
    const state = JSON.parse(readFileSync(stateFile(proj), "utf8"))
    return isObj(state) ? state : null
  } catch {
    return null
  }
}

let tmpNo = 0
/** Atomic write (temp + rename in the same folder), like harness_state.save(). O_EXCL ("wx") never follows a planted link. */
function writeAtomic(file: string, text: string) {
  const tmp = `${file}.${process.pid}.${++tmpNo}.tmp`
  writeFileSync(tmp, text, { flag: "wx" })
  renameSync(tmp, file)
}

/** Every state.json write of this plugin, one job at a time. next.py writes the same file from its own process, so
 *  the job reads it right before `mutate` (false: write nothing) and writes at once, never from an earlier copy. */
let writeChain: Promise<unknown> = Promise.resolve()
function queueWrite(proj: string, mutate: (state: any) => boolean | void): Promise<boolean> {
  const job = writeChain.then(() => {
    const file = stateFile(proj)
    let raw = ""
    let state: any = null
    try {
      raw = readFileSync(file, "utf8")
      state = JSON.parse(raw)
    } catch {
      return false // no state, or unreadable: nothing is recorded
    }
    if (!isObj(state) || mutate(state) === false) return false
    writeAtomic(`${file}.bak`, raw) // first the last good copy (it parsed), as harness_state.save()
    writeAtomic(file, JSON.stringify(state, null, 2) + "\n")
    return true
  })
  const safe = job.catch(() => false)
  writeChain = safe
  return safe
}

const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, "Z")
const normCmd = (cmd: string) => cmd.trim().replace(/\s+/g, " ")
const lastLines = (text: string, n: number) => text.replace(/\r\n/g, "\n").replace(/\n+$/, "").split("\n").slice(-n).join("\n")

/** harness_docs.norm_path: './Src//A.js' -> 'src/a.js'; lowercase (this Mac is case-insensitive); a trailing '/' (a
 *  folder) is kept. */
function normPath(p: string): string {
  const s = p.trim().replace(/\\/g, "/").toLowerCase()
  const folder = s.endsWith("/") || s.endsWith("/.")
  let n = s ? path.posix.normalize(s) : ""
  if (n.length > 1) n = n.replace(/\/+$/, "")
  if (n === ".") return ""
  return folder && !n.endsWith("/") ? n + "/" : n
}

/** harness_docs.paths_overlap: equal, or one is a folder ('/') that holds the other. 'src' (no slash) is a file. */
function pathsOverlap(a: string, b: string): boolean {
  const x = normPath(a)
  const y = normPath(b)
  return x === y || (x.endsWith("/") && y.startsWith(x)) || (y.endsWith("/") && x.startsWith(y))
}

/** next.py's .harness/snapshot.json: the steps of the turn it issued, their attempts then, and its kind/stage; null
 *  when unreadable. */
function readSnap(proj: string): { steps: number[]; kind: string; stage: string; attempts: any } | null {
  try {
    const snap = JSON.parse(readFileSync(path.join(proj, ".harness", "snapshot.json"), "utf8"))
    if (!isObj(snap) || !Array.isArray(snap.steps)) return null
    return { steps: snap.steps.filter((n: any) => Number.isInteger(n)), kind: String(snap.kind ?? ""), stage: String(snap.stage ?? ""),
      attempts: isObj(snap.attempts) ? snap.attempts : {} }
  } catch {
    return null
  }
}

/** A delegation description / child session title (CHILD_TIE "title"): `<slug>: step <n>`, `<slug>: tests`, ... */
const TITLE_RE = /^([a-z0-9-][a-z0-9_-]*): (?:(step|research step|testfix step) (\d+)|(tests|verify|visual|review|fix))(?=$|[\s\p{P}])/u
function parseTitle(title: string): { slug: string; kind: string; n: number | null } | null {
  const m = TITLE_RE.exec(title.trim())
  if (!m) return null
  return { slug: m[1], kind: m[2] ? m[2].split(" ")[0] : m[4], n: m[3] ? Number(m[3]) : null }
}

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

/** Every path a write-tool call writes: its one path, or each path named in an apply-patch blob. */
function writePaths(tool: string, input: any): string[] {
  const raws = tool === "patch" && isStr(input?.patchText)
    ? [...input.patchText.matchAll(/^\*\*\* (?:Add File|Update File|Delete File|Move to):\s*(.+)$/gm)].map((m) => m[1].trim())
    : [input?.path ?? input?.filePath ?? input?.file]
  return raws.filter((p): p is string => isStr(p) && p !== "")
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

    const sessionProject = () => projectOf(SESSION_DIR)

    const has = (proj: string | null, file: string) => Boolean(proj && existsSync(path.join(proj, file)))

    const outsideProject = (absTarget: string): boolean => {
      if (absTarget === "/dev/null" || absTarget === "/dev/stdout" || absTarget === "/dev/stderr") return false
      if (absTarget.startsWith("/tmp/") || absTarget === "/tmp" || absTarget.startsWith("/var/tmp/")) return false
      const proj = sessionProject()
      if (!proj) return false // workshop-root session: plugin does not confine (harness work)
      return path.relative(proj, absTarget).startsWith("..")
    }

    /** Paths a shell command writes (best effort: redirects, cp/mv/install, mkdir/touch/tee), resolved against the
     *  command's workdir. What this misses (sed -i, programs) the sandbox and the after-turn file check (next.py) see. */
    const shellWriteTargets = (full: string, base: string): string[] => {
      // a heredoc body is data, not redirects: `cat >> a.py <<'EOF'` + code with `>=` named files "=" (T15 live)
      const cmd = full.replace(/<<-?\s*(['"]?)(\w+)\1[^\n]*\n[\s\S]*?\n[ \t]*\2[ \t]*(?=\n|$)/g, (m) => m.slice(0, m.indexOf("\n")))
      const out: string[] = []
      const add = (raw: string, dir = false) => {
        const t = raw.replace(/^["']|["']$/g, "")
        if (t) out.push((t.startsWith("~/") ? resolveTarget(t) : path.resolve(base, t)) + (dir ? path.sep : ""))
      }
      for (const m of cmd.matchAll(/>>?\s*("|')?([^\s"'|;&]+)/g)) add(m[2])
      for (const m of cmd.matchAll(/\b(?:cp|mv|install)\s+(?:-[A-Za-z-]+\s+)*\S+\s+(\S+)/g)) add(m[1])
      for (const m of cmd.matchAll(/\b(mkdir|touch|tee)\s+(?:-[A-Za-z-]+\s+)*(\S+)/g)) add(m[2], m[1] === "mkdir") // a made folder ends in '/'
      return out
    }

    /** Throws unless this write may happen: harness state is off limits, code needs an approved plan. */
    const checkWrite = async (absTarget: string, root: string | null = miniRoot) => {
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
      if (DOC_FILES.includes(base)) return
      if (DOC_DIRS.includes(path.relative(proj, absTarget).split(path.sep)[0])) return
      if (!has(proj, "PLAN.md")) {
        throw new Error(
          "SAFETY GATE: plan gate. No PLAN.md in project. Code cannot be written before a plan exists. Run /go <slug> to get one, the human approves with /approve <slug>.",
        )
      }
      if (!(await planApproved(proj))) {
        throw new Error(
          `SAFETY GATE: plan gate. ${path.basename(proj)} has no current approval: it was never approved, a plan document (BRIEF, ARCHITECTURE, DESIGN, PLAN) changed after /approve, or its milestone has shipped. /go ${path.basename(proj)} shows what is next; the human approves with /approve ${path.basename(proj)}.`,
        )
      }
    }

    const real = (p: string) => realpathSync.native(p)
    /** lstat (a symlink is never followed), or null when the path is missing or unreadable. */
    const lst = (p: string) => {
      try {
        return lstatSync(p)
      } catch {
        return null
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
      while (!lst(anc) && path.dirname(anc) !== anc) anc = path.dirname(anc)
      if (anc === target && lst(target)?.isSymbolicLink()) refuse("is a symlink")
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

    /** Write tools, every agent, every session dir: only an existing mini project (not _template) or the workshop RESEARCH/. */
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
      // /research without a project writes the workshop-root RESEARCH/ folder (exactly that name, same real-path rules)
      if (!inProject && !inside(path.join(ws, "RESEARCH"), realTgt)) {
        throw new Error(
          `SAFETY GATE: write confinement. ${realTgt} is outside every mini project. Agents write only inside an existing mini-projects/<slug>/ (research: RESEARCH/). Harness files, scripts, rules and config are the human's.`,
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

    // CHILD_TIE = "title" (spec 9.3): a child's title is its delegation's description. After a restart the maps are
    // empty, so ctx.session.get recovers the title and per-step scope survives (Review Focus 3).
    type Tie = { proj: string | null; kind: string | null; n: number | null }
    const stepOf = new Map<string, Tie>()
    const parentOf = new Map<string, string>()
    const rootProj = new Map<string, string>() // a calling session -> the project its delegations name (`<slug>:`)

    const projDir = (slug: string): string | null =>
      miniRoot && lst(path.join(miniRoot, slug))?.isDirectory() ? path.join(miniRoot, slug) : null
    const samePath = (a: string, b: string) => {
      try {
        return real(a).toLowerCase() === real(b).toLowerCase()
      } catch {
        return false
      }
    }
    const onCreated = (data: any) => {
      const sid = data?.sessionID
      const parent = data?.parentID
      if (!isStr(sid) || !isStr(parent) || !parent) return // a root session is no child
      parentOf.set(sid, parent)
      const t = parseTitle(isStr(data.title) ? data.title : "")
      stepOf.set(sid, { proj: t ? projDir(t.slug) : null, kind: t?.kind ?? null, n: t?.n ?? null })
    }
    /** ctx.session.get (Session.Info: title, parentID, location.directory), at most 2 s; null when it fails. */
    const sessionInfo = async (sid: string): Promise<any | null> => {
      const get = ctx?.session?.get
      if (typeof get !== "function") return null
      let timer: any
      try {
        const late = new Promise((r) => {
          timer = setTimeout(() => r(null), 2000)
          timer.unref?.()
        })
        return (await Promise.race([Promise.resolve(get.call(ctx.session, { sessionID: sid })), late])) ?? null
      } catch {
        return null
      } finally {
        clearTimeout(timer)
      }
    }
    const tieOf = async (sid: string): Promise<Tie | null> => {
      const known = stepOf.get(sid)
      if (known) return known
      const s = await sessionInfo(sid) // untied when unknown: the narrowest rule applies
      if (s && isStr(s.parentID) && s.parentID) onCreated({ sessionID: sid, parentID: s.parentID, title: s.title })
      return stepOf.get(sid) ?? null
    }
    /** Is sid a root session of THIS instance's directory? Every instance sees every session's events, so only the
     *  session's own instance may end its loop on what it did not see. Unknown: no. */
    const homeOf = new Map<string, string>() // session -> its directory, from session.created
    const ownRoot = async (sid: string) => {
      if (parentOf.has(sid)) return false
      let dir = homeOf.get(sid)
      if (dir === undefined) {
        const s = await sessionInfo(sid)
        if (!s || (isStr(s.parentID) && s.parentID)) return false
        dir = s.location?.directory
      }
      return isStr(dir) && dir === SESSION_DIR
    }

    /** The project whose /go lock a session's tool calls keep alive: its own tie, else its parent's delegations. */
    const lockProject = (sid: string): string | null =>
      stepOf.get(sid)?.proj ?? rootProj.get(sid) ?? rootProj.get(parentOf.get(sid) ?? "") ?? null

    /** Rewrite the lock's `at` (nothing else), so next.py's 30-minute expiry only frees a crash leftover. Never through
     *  a symlinked .harness or lock; an unreadable lock is left alone (/go retry clears it). `refreshedFor` remembers
     *  the root whose turn last refreshed each project's lock (cleared at that root's next turn start). */
    const refreshedFor = new Map<string, string>()
    const refreshLock = (sid: string) => {
      const proj = lockProject(sid)
      if (!proj) return
      const lock = path.join(proj, ".harness", "lock")
      try {
        if (!lst(path.dirname(lock))?.isDirectory() || !lst(lock)?.isFile()) return
        const old = JSON.parse(readFileSync(lock, "utf8"))
        const at = nowIso()
        if (!isObj(old)) return
        refreshedFor.set(proj, rootOf(sid)) // this root's turn keeps it alive: its end without a delegation may free it
        if (old.at === at) return
        old.at = at
        writeAtomic(lock, JSON.stringify(old))
      } catch {
        // no lock, or it cannot be read: nothing to refresh
      }
    }

    /** Throws unless this builder, qa or designer may write `target` in `proj` (spec 4, 6.3); other agents: the gates
     *  above only. The batch next.py issued caps every tie, because a title is written by a model. */
    const checkScope = async (event: any, target: string, proj: string) => {
      const agent = String(event?.agent ?? "")
      if (agent !== "builder" && agent !== "qa" && agent !== "designer") return
      const rel = path.relative(proj, target).split(path.sep).join("/") + (target.endsWith(path.sep) ? "/" : "")
      const fits = (allowed: string[]) => allowed.some((a) => pathsOverlap(rel, a))
      const refuse = (why: string) => {
        throw new Error(`SAFETY GATE: step scope. ${why}`)
      }
      if (agent === "qa") {
        const qa = ["tests/acceptance/", "QA.md"]
        if (!fits(qa)) refuse(`qa may write only: ${qa.join(", ")}.`)
        return
      }
      if (agent === "designer") {
        const own = (await planApproved(proj)) ? ["VISUAL.md", "design/shots/"] : ["DESIGN.md", "design/mockups/"]
        if (!fits(own)) refuse(`The designer may write only: ${own.join(", ")}.`)
        return
      }
      const slug = path.basename(proj)
      const tie = await tieOf(String(event?.sessionID ?? ""))
      if (tie?.proj && !samePath(tie.proj, proj)) {
        refuse(tie.kind === "step" ? `Step ${tie.n} may write only its own project's files.` : `This builder may not write in ${slug}.`)
      }
      const steps = stepsOf(readState(proj))
      const filesOf = (ss: any[]) => [...new Set(ss.flatMap((s: any) => (Array.isArray(s.files) ? s.files.filter(isStr) : [])))]
      const snap = readSnap(proj)
      if (tie?.kind === "step" && tie.n !== null && (!snap || snap.steps.includes(tie.n))) {
        const files = filesOf(steps.filter((s: any) => s.n === tie.n))
        if (!fits([...files, `requests/step${tie.n}.md`])) {
          refuse(`Step ${tie.n} may write only: ${files.join(", ") || "(no files)"}. Write requests/step${tie.n}.md if you need more.`)
        }
        return
      }
      if (tie?.kind === "fix" && (!snap || snap.kind === "FIX" || snap.stage === "FIX")) {
        const files = filesOf(steps)
        if (!fits(files)) refuse(`A fix round may write only the milestone's step files: ${files.join(", ") || "(none)"}.`)
        return
      }
      // untied, or tied outside the batch: the batch's step files and their requests, never its test, QA or
      // research paths; no snapshot, nothing (Review Focus 3)
      if (!snap) refuse(`This builder is not tied to a step and ${slug} has no batch snapshot, so it may write nothing. The human runs /go ${slug}.`)
      const allowed = [...filesOf(steps.filter((s: any) => snap!.steps.includes(s.n))), ...snap!.steps.map((n) => `requests/step${n}.md`)]
      if (!fits(allowed)) refuse(`This builder is not tied to a step; it may write only this batch's files: ${allowed.join(", ") || "(none)"}.`)
    }

    // Delegations per CALLING session. `turnCalls`: this turn's agents (the breaker). `running`: open calls by call
    // id, at most MAX_OPEN; one the host moved to the background (L124) keeps its slot and the /go lock until its
    // child ends. `delegated`: sessions whose delegation completed; only their turn end frees the lock, because a
    // worker child that tries `subagent` reaches checkDelegation too but its call never completes (spec 14 c, f).
    const turnCalls = new Map<string, string[]>()
    const running = new Map<string, Map<string, { agent: string; bg: string | null }>>()
    /** Frees the open calls of `sid` that `drop` picks; a session with none left leaves `running`. */
    const freeSlots = (sid: string, drop: (call: string, slot: { bg: string | null }) => boolean) => {
      const open = running.get(sid)
      for (const [k, s] of open ?? []) if (drop(k, s)) open!.delete(k)
      if (open && !open.size) running.delete(sid)
    }
    const bgChild = new Map<string, { parent: string; call: string }>()
    const delegated = new Set<string>()
    const turnSeen = new Map<string, number>() // session -> when this plugin saw its turn start (Review Focus 3: no /go otherwise)
    let anon = 0

    // Cost (spec 9.3 fact 7): the rise of a session's running total since its last event goes to the project its
    // root's turn names (`rootProj`, from the turn's first delegation; until then the root's own cost waits in
    // `unbilled`). A session never seen created (made before a restart) only sets its baseline: nothing counts twice.
    const spent = new Map<string, number>()
    const unbilled = new Map<string, number>()
    const rootOf = (sid: string) => {
      let s = sid
      for (let i = 0; i < 8 && parentOf.has(s); i++) s = parentOf.get(s)!
      return s
    }
    const addCost = async (proj: string, usd: number) => {
      const now = await pyFacts("milestone", proj) // the current milestone, from the state library (H1)
      if (!now) return
      const ms = now.milestone ?? null
      const num = (v: any) => (typeof v === "number" && Number.isFinite(v) ? v : 0)
      await queueWrite(proj, (st) => {
        const c = isObj(st.cost) ? st.cost : {}
        const old = isStr(c.milestone) ? c.milestone : null
        const reset = ms !== null && old !== null && old !== ms // only two KNOWN milestones that differ start afresh
        st.cost = { ...c, milestone: ms ?? old, usd: (reset ? 0 : num(c.usd)) + usd, project_usd: num(c.project_usd) + usd }
      })
    }
    const onCost = (data: any) => {
      const sid = data?.sessionID
      const total = data?.cost
      if (!isStr(sid) || typeof total !== "number" || !Number.isFinite(total)) return
      const prev = spent.get(sid)
      spent.set(sid, total)
      if (prev === undefined || total <= prev) return
      const root = rootOf(sid)
      const proj = rootProj.get(root)
      if (proj) void addCost(proj, total - prev)
      else if (turnSeen.has(root)) unbilled.set(root, (unbilled.get(root) ?? 0) + total - prev) // a turn without a delegation counts nowhere
    }

    const checkDelegation = (event: any) => {
      const sid = String(event?.sessionID ?? "")
      const agent = typeof event?.input?.agent === "string" && event.input.agent ? event.input.agent : "unknown"
      if (event?.input?.background) {
        // a background call returns at once (its after frees the slot) and its completion wakes the parent in a
        // new busy period (a fresh count, and a turn end that frees the lock while the child still writes)
        throw new Error("SAFETY GATE: background delegation. Background delegations are not allowed; call it in the foreground.")
      }
      if (isStr(event?.input?.sessionID) && event.input.sessionID) {
        // a continued child keeps its old title and fires no session.created, so its step tie would be stale
        throw new Error("SAFETY GATE: start a new delegation; continuing an earlier one is not allowed.")
      }
      const calls = turnCalls.get(sid) ?? []
      turnCalls.set(sid, calls)
      const open = running.get(sid) ?? new Map()
      if (open.size >= MAX_OPEN) {
        throw new Error(`SAFETY GATE: at most ${MAX_OPEN} delegations at once. Wait for one to finish.`)
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
      open.set(isStr(event?.id) && event.id ? event.id : `anon-${++anon}`, { agent, bg: null }) // no id: held to the turn end
      running.set(sid, open)
      const named = /^([a-z0-9-][a-z0-9_-]*):\s/.exec(String(event?.input?.description ?? ""))
      const proj = named ? projDir(named[1]) : null
      if (proj && !rootProj.has(sid)) { // the turn's first delegation names its project (and pays its cost so far)
        rootProj.set(sid, proj)
        const owed = unbilled.get(sid)
        unbilled.delete(sid)
        if (owed) void addCost(proj, owed)
      }
    }

    /** A delegation's execute.after: frees its slot, unless the host moved it to the background (L124). */
    const endDelegation = (event: any) => {
      const sid = String(event?.sessionID ?? "")
      const id = String(event?.id ?? "")
      const open = running.get(sid)
      let out = event?.result?.output
      if (isStr(out)) {
        try {
          out = JSON.parse(out)
        } catch {
          // plain text output
        }
      }
      const meta = event?.result?.metadata
      const child = String((isObj(out) && out.sessionID) || meta?.sessionID || "")
      const status = (isObj(out) && out.status) || meta?.status
      if (event?.status === "completed" && turnCalls.has(sid)) delegated.add(sid) // it really delegated
      if (event?.status === "completed" && status === "running" && child && open?.has(id)) {
        open.get(id)!.bg = child // the child still runs: its slot and the lock stay until its turn ends
        bgChild.set(child, { parent: sid, call: id })
        return
      }
      freeSlots(sid, (call) => call === id)
    }

    /** Every mini-projects/<slug>/ holding a .harness/lock: plain files only, never through a symlinked slug or .harness. */
    const lockedProjects = (): string[] => {
      let slugs: string[] = []
      try {
        slugs = miniRoot ? readdirSync(miniRoot) : []
      } catch {
        return []
      }
      return slugs.map((slug) => path.join(miniRoot!, slug)).filter((dir) =>
        lst(dir)?.isDirectory() && lst(path.join(dir, ".harness"))?.isDirectory() && lst(path.join(dir, ".harness", "lock"))?.isFile())
    }
    const unlinkLock = (dir: string) => {
      try {
        unlinkSync(path.join(dir, ".harness", "lock"))
      } catch {
        // it cannot be removed: next.py's 30-minute expiry is the fallback
      }
    }
    const clearLocks = () => lockedProjects().forEach(unlinkLock)
    /** Was this lock taken by the turn of `sid` that started at `startedAt`? Yes when this instance refreshed it during
     *  that turn (`refreshedFor`: the turn's first builder ran, then Esc). Otherwise next.py's lock records no session,
     *  only `at` (whole seconds), written by the /go template just before the turn starts: so `at` within the minute
     *  before the start (or the second after). Either way no other open turn of this instance may delegate for that
     *  project. A lock refreshed for another root carries a later `at` and another `refreshedFor`. Unreadable: not ours. */
    const LOCK_LEAD_MS = 60_000
    const lockTakenBy = (dir: string, sid: string, startedAt: number) => {
      if (refreshedFor.get(dir) !== sid) { // refreshed by this root's own turn (its first builder ran): ours, any `at`
        try {
          const at = Date.parse(JSON.parse(readFileSync(path.join(dir, ".harness", "lock"), "utf8"))?.at)
          if (!Number.isFinite(at) || at < startedAt - LOCK_LEAD_MS || at > startedAt + 1000) return false
        } catch {
          return false
        }
      }
      return ![...rootProj].some(([other, proj]) => other !== sid && samePath(proj, dir))
    }

    /** A note in the session's workshop .harness/plugins-alive (the human reads it when the loop did not go on). */
    const note = (text: string) => {
      try {
        const file = path.join(path.dirname(miniRoot!), ".harness", "plugins-alive")
        mkdirSync(path.dirname(file), { recursive: true })
        appendFileSync(file, `safety-gate ${nowIso()}: ${text}\n`)
      } catch {
        // a note is a convenience
      }
    }

    /** The autopilot loop (spec 3.2), on a root's turn end, before the locks are freed. The plugin may only ever send
     *  /go <slug>: into the session whose turn ended, for the ONE locked project whose autopilot is on with `continue`
     *  (next.py sets it on each turn it issues; it is cleared here first, so one turn continues once). A failed or
     *  interrupted turn ends the loop; two candidates send nothing (Review Focus 2). */
    const isGoing = (st: any) => isObj(st?.autopilot) && st.autopilot.on === true && st.autopilot.continue === true
    const endLoop = (st: any) => {
      if (!isGoing(st)) return false
      st.autopilot.continue = false
    }
    const continueLoop = (sid: string, ok: boolean) => {
      const going = lockedProjects().filter((dir) => isGoing(readState(dir)))
      if (!ok) {
        for (const dir of going) void queueWrite(dir, endLoop)
        return
      }
      const slugs = going.map((dir) => path.basename(dir))
      if (slugs.length > 1) return note(`autopilot: ${slugs.join(", ")} all hold a lock with continue set; nothing sent. /go <slug> resumes one.`)
      const slug = slugs[0]
      if (!slug || !SLUG_RE.test(slug) || slug === "cap" || slug === "retry") return
      void queueWrite(going[0], endLoop)
        .then((wrote) => {
          if (wrote && typeof ctx?.session?.command === "function") {
            return ctx.session.command({ sessionID: sid, name: "go", text: slug, delivery: "queue" })
          }
        })
        .catch(() => note(`autopilot: sending /go ${slug} failed; /go ${slug} resumes it.`))
    }

    /** Turn and session events (spec 14 f): reset a session's count at its turn start; at a delegating turn's end run
     *  the loop, then free the /go locks (P7). Also cost events and the session tree. */
    const onTurnEvent = (e: any) => {
      if (e?.type === "session.created") {
        const sid = e.data?.sessionID
        if (isStr(sid) && !spent.has(sid)) spent.set(sid, 0) // made while this plugin runs: its total starts at 0
        if (isStr(sid) && isStr(e.data?.location?.directory)) homeOf.set(sid, e.data.location.directory)
        return onCreated(e.data)
      }
      if (e?.type === COST_EVENT) return onCost(e.data)
      const sid = e?.data?.sessionID
      if (typeof sid !== "string") return
      const ended = TURN_END.has(e.type)
      if (e.type === TURN_START) {
        turnSeen.set(sid, Date.now())
        for (const [proj, root] of refreshedFor) if (root === sid) refreshedFor.delete(proj) // only this turn's refreshes count
      }
      const startedAt = ended ? turnSeen.get(sid) : undefined
      const seen = ended && turnSeen.delete(sid)
      if (ended || e.type === TURN_START) unbilled.delete(sid)
      if (seen && !delegated.has(sid)) {
        // a root turn of this instance that completed no delegation (a model error, Esc while the first builder runs)
        // ends the loop, so a later turn cannot resume it, and frees the lock its own /go took (lockTakenBy)
        void ownRoot(sid).then((own) => {
          if (!own) return
          continueLoop(sid, false)
          for (const dir of lockedProjects()) if (lockTakenBy(dir, sid, startedAt!)) unlinkLock(dir)
        })
      }
      const bg = ended ? bgChild.get(sid) : undefined
      if (bg) { // a backgrounded child is done: its parent's slot is free
        bgChild.delete(sid)
        freeSlots(bg.parent, (call) => call === bg.call)
      }
      if (!turnCalls.has(sid)) return
      freeSlots(sid, (_, s) => !s.bg) // a turn's start or end closes every slot, except a backgrounded one
      if (e.type === TURN_START) {
        turnCalls.set(sid, [])
      } else if (ended) {
        if (running.has(sid)) {
          // a backgrounded child still writes: the lock stays and no /go goes out (fact 8); the turn its completion
          // starts by itself ends later, and that end may continue the loop
          turnCalls.set(sid, [])
          return
        }
        turnCalls.delete(sid)
        rootProj.delete(sid)
        if (delegated.delete(sid)) {
          if (seen) continueLoop(sid, e.type === TURN_OK) // never for a turn whose start this plugin did not see
          clearLocks()
        }
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

    /** The browser (spec 9.3 fact 6, ruling C5+). The Playwright MCP writes outside the agent sandbox and resolves a
     *  relative filename against the WORKSHOP (its cwd), so only the designer saves a file, a screenshot into its own
     *  project's design/shots/, and it opens only http://127.0.0.1|localhost:<its project's port>. Other agents browse
     *  as their permissions allow and take screenshots inline only. */
    const checkBrowser = async (event: any, tool: string) => {
      const input = event?.input
      const file = isStr(input?.filename) ? input.filename : "" // raw, as the MCP uses it: " " is a file named " "
      const designer = event?.agent === "designer"
      if (file && !(designer && tool === MCP_SHOT_TOOL)) {
        throw new Error("SAFETY GATE: browser file. Only the designer saves a browser file (a screenshot, into its project's design/shots/). Take it without a filename.")
      }
      const opens = tool === MCP_NAV_TOOL || (isObj(input) && "url" in input) // navigate, browser_tabs new, ...
      if (!designer || (!opens && !file)) return
      const sid = String(event?.sessionID ?? "")
      await tieOf(sid) // the designer child's title `<slug>: visual` names its project
      const proj = lockProject(sid) ?? sessionProject()
      const port = proj ? readState(proj)?.port : undefined
      if (opens) {
        let url: URL | null = null
        try {
          url = new URL(isStr(input?.url) ? input.url : "")
        } catch {
          // not a URL: refused below
        }
        if (!url || url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname) || !Number.isInteger(port) || url.port !== String(port)) {
          throw new Error(`SAFETY GATE: designer browser. Only http://127.0.0.1:${Number.isInteger(port) ? port : "<port>"} of this project.`)
        }
      }
      if (!file) return
      let inShots = false
      try { // the real path, as for the write tools: no symlink, no case alias
        inShots = inside(path.join(real(proj!), "design", "shots"), realTarget(path.resolve(path.dirname(miniRoot!), file)))
      } catch {
        // no project, outside the workshop, or through a link: refused below
      }
      if (!inShots) {
        throw new Error(`SAFETY GATE: designer browser. Screenshots go only into mini-projects/${proj ? path.basename(proj) : "<slug>"}/design/shots/.`)
      }
    }

    await ctx.tool.hook("execute.before", async (event: any) => {
      const tool = String(event?.tool ?? "")
      const input = event?.input
      refreshLock(String(event?.sessionID ?? "")) // any tool call, refused or not: the turn is alive

      if (tool === DELEGATION_TOOL) return checkDelegation(event)
      if (tool.startsWith(MCP_PREFIX)) return await checkBrowser(event, tool)

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
          const live = await pyFacts("review", proj)
          if (!isStr(live?.tree)) throw new Error("SAFETY GATE: ship gate. cannot read the review or compute the tree hash, so freshness is unknown.")
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
          if (review.tree_sha256 !== live.tree) {
            throw new Error(`SAFETY GATE: ship gate. review is stale: code changed since REVIEW.md; run /go ${slug} to review again.`)
          }
        }

        if (/approve\.sh/.test(cmd)) {
          throw new Error("SAFETY GATE: approval. Only the human approves a plan, by typing /approve <slug>.")
        }

        const targets = shellWriteTargets(cmd, resolveTarget(input?.workdir || SESSION_DIR))
        const bad = targets.find((p) => outsideProject(p))
        if (bad) {
          throw new Error(
            `SAFETY GATE: shell write outside project blocked. Path: ${bad}\nWrite inside the current mini project only.`,
          )
        }
        for (const t of targets) {
          await checkWrite(t)
          const proj = projectOf(t)
          if (proj) await checkScope(event, t, proj)
        }
        return
      }

      if (WRITE_TOOLS.has(tool)) {
        for (const raw of writePaths(tool, input)) {
          const target = realTarget(resolveTarget(raw)) // real spelling: symlinks and case aliases refused
          const mini = confine(target)
          await checkWrite(target, mini) // harness state + plan gate, on the real path
          const proj = projectOf(target, mini)
          if (proj) await checkScope(event, target, proj)
        }
      }
    })

    /** A shell run, verbatim at the project root, of a step check or the acceptance run (spec 6.3). Steps open:
     *  only a builder's run of a batch step counts (a reviewer running an unbuilt step's check must not charge it),
     *  and qa's failing acceptance run pins the tests hash and the command. All done: verify.* for the current tree.
     *  qa and verify belong to the steps' milestone (T7-R8): another milestone's record is replaced, never extended. */
    const recordCheck = async (event: any) => {
      const input = event.input
      const cmd = typeof input?.command === "string" ? input.command : ""
      const dir = resolveTarget(input?.workdir || SESSION_DIR)
      const proj = projectOf(dir)
      if (!proj || dir !== proj) return // only a run at the project root counts; a subdirectory is "anything else"
      const out = event.result?.output
      if (event.status !== "error" && out?.status === "running") return // background run: no result yet
      const seen = readState(proj) // to decide what this run is; the write re-reads inside the queue
      if (!Array.isArray(seen?.steps)) return
      const steps = stepsOf(seen)
      const run = normCmd(cmd)
      const matching = steps.filter((s: any) => isStr(s.check) && normCmd(s.check) === run)
      const pinned = isObj(seen.qa) && seen.qa.milestone === msOf(seen) && isStr(seen.qa.run) && seen.qa.run === run // VERIFY: the one seen failing
      const exit = out?.exit ?? event.result?.metadata?.exit
      const code: number | null = event.status !== "error" && Number.isInteger(exit) && out?.timeout !== true ? exit : null
      const agent = String(event.agent ?? "")
      const open = !steps.every((s: any) => s.done_at)
      // TESTS: qa's failing run of QA.md's command as written now; the state library reads it with the tests hash
      const facts = open && agent === "qa" && code !== null && code !== 0 ? await pyFacts("tests", proj) : null
      const isAcceptance = isStr(facts?.run) && facts.run !== "" && normCmd(facts.run) === run
      if (!matching.length && !isAcceptance && !pinned) return
      let wrote = false

      if (open) {
        if (isAcceptance) { // the tests fail first (W4)
          const tests = facts.tests
          if (isStr(tests)) {
            wrote = await queueWrite(proj, (st) => {
              const ms = msOf(st)
              st.qa = { ...(isObj(st.qa) && st.qa.milestone === ms ? st.qa : {}), failed_first_at: nowIso(), tests_sha256: tests, run, milestone: ms }
            })
          }
        }
        const tie = agent === "builder" ? await tieOf(String(event.sessionID ?? "")) : null
        const snap = readSnap(proj)
        const inBatch = (n: number) => !snap || snap.steps.includes(n) // only steps of the issued batch are credited
        const mine = tie?.kind === "step" && tie.proj && samePath(tie.proj, proj) && inBatch(tie.n!)
        const pick = (agent !== "builder" ? [] : mine ? matching.filter((s: any) => s.n === tie!.n) : matching.length === 1 ? matching : [])
          .filter((s: any) => inBatch(s.n))
        if (pick.length === 1 && !pick[0].done_at) {
          const n = pick[0].n
          const text = event.status === "error" ? String(event.error?.message ?? event.error ?? "tool error") : String(out?.output ?? "")
          wrote = (await queueWrite(proj, (st) => {
            const s = stepsOf(st).find((x) => x.n === n)
            if (!s || s.done_at || !isStr(s.check) || normCmd(s.check) !== run) return false
            if (code === 0) {
              s.done_at = nowIso()
            } else {
              const was = Number.isInteger(s.attempts) ? s.attempts : 0
              const base = snap?.attempts[String(n)] // at most one failed attempt per step per turn (final review I1)
              if (!Number.isInteger(base) || was <= base) s.attempts = was + 1
              s.last_failure = `exit ${code ?? "none"}\n${lastLines(text, 40)}`
            }
          })) || wrote
        }
      } else {
        if (code === null) return // no exit code (refused, errored, timed out): not a result; verify stays pending
        const ns = matching.length === 1 ? [String(matching[0].n)] : []
        const tree = (await pyFacts("tree", proj))?.tree
        if (isStr(tree) && (ns.length || pinned)) {
          wrote = await queueWrite(proj, (st) => {
            let v = isObj(st.verify) ? st.verify : {}
            if (v.tree_sha256 !== tree || v.milestone !== msOf(st)) { // a new tree or milestone: older results count no more
              v = { tree_sha256: tree, milestone: msOf(st), checks: {} }
              if (isObj(st.qa) && st.qa.verdict_tree_sha256 !== tree) {
                delete st.qa.verdict
                delete st.qa.verdict_tree_sha256
              }
            }
            v.checks = isObj(v.checks) ? v.checks : {}
            for (const n of ns) v.checks[n] = code
            if (pinned) v.acceptance = code
            st.verify = v
          })
        }
      }
      if (wrote) refreshDashboard()
    }

    /** A REVIEW.md, QA.md or VISUAL.md just written: its verdict with the tree it judged, or no record without a
     *  verdict line (the tree hash ignores these files, so an old SHIP would stay "fresh"). qa.verdict stays a string
     *  (what harness_state reads). A SHIP review resets the fix rounds. */
    const recordDoc = async (proj: string, kind: "review" | "qa" | "visual") => {
      const f = await pyFacts(kind, proj)
      const ok = isStr(f?.tree) && isStr(f?.verdict)
      const wrote = await queueWrite(proj, (st) => {
        const ms = msOf(st) // qa and visual belong to the steps' milestone (T7-R8)
        if (kind === "qa") {
          const mine = isObj(st.qa) && st.qa.milestone === ms ? st.qa : null
          if (!ok && !mine) return false
          st.qa = { ...mine, milestone: ms, verdict: ok ? f.verdict : undefined, verdict_tree_sha256: ok ? f.tree : undefined }
          return
        }
        if (!ok) {
          delete st[kind]
          return
        }
        st[kind] = kind === "review" ? { tree_sha256: f.tree, verdict: f.verdict, at: nowIso() } : { verdict: f.verdict, tree_sha256: f.tree, milestone: ms }
        if (kind === "review" && f.verdict === "SHIP") st.fix_rounds = 0
      })
      if (wrote) refreshDashboard()
    }
    const DOC_OWNER = new Map<string, ["review" | "qa" | "visual", string | null]>([
      ["REVIEW.md", ["review", null]], ["QA.md", ["qa", "qa"]], ["VISUAL.md", ["visual", "designer"]],
    ])

    await ctx.tool.hook("execute.after", async (event: any) => {
      try {
        if (event?.tool === DELEGATION_TOOL) return endDelegation(event)
        if (event?.tool === "shell") return await recordCheck(event)
        if (event?.status !== "completed" || !WRITE_TOOLS.has(String(event?.tool))) return
        for (const raw of writePaths(event.tool, event.input)) {
          const target = resolveTarget(raw)
          const proj = projectOf(target)
          const doc = proj && path.dirname(target) === proj ? DOC_OWNER.get(path.basename(target)) : undefined
          if (doc && (!doc[1] || event.agent === doc[1])) await recordDoc(proj!, doc[0]) // a verdict counts only from its owner
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

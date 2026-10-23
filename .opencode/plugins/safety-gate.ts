/**
 * safety-gate - defence-in-depth gates inside the opencode plugin layer.
 *
 * This is the SECOND layer. The FIRST layer is `policies` + per-agent permission
 * rules in opencode.json (a policy `deny` beats agent rules AND saved approvals;
 * see docs/audit/research/L0-config.md). This plugin adds the checks that the
 * permission layer cannot express:
 *   - ship gate: no `git commit`/`git tag` unless REVIEW.md + BLIND.md exist
 *     (matched anywhere in a command chain, not just at the start)
 *   - plan gate: no code write in a mini project unless the human approved its
 *     current PLAN.md (/approve records the plan's sha256 in .harness/state.json;
 *     any later edit to PLAN.md changes the hash and revokes the approval)
 *   - approval is human-only: agents cannot write .harness/ or run approve.sh
 *   - write confinement: no edit/write/patch/shell-redirect outside the project
 *   - OS sandbox: every shell runs through scripts/sandbox/agent-shell, which puts
 *     agent shells (AGENT=1) in a macOS sandbox that may write only the project the
 *     command runs in (shell create.before hook; covers shell only, not edit/write)
 *
 * v2 plugin API: export default { id, setup }. Throwing in execute.before
 * rejects the tool call (docs/audit/research/L0-plugins.md).
 *
 * Paths resolve from THIS file's location (project-local install), never from
 * ~/.config/opencode or process.cwd().
 */

import { createHash } from "node:crypto"
import { appendFileSync, existsSync, mkdirSync, readFileSync, realpathSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

// .opencode/plugins/safety-gate.ts -> workshop root is two dirs up from .opencode
const PLUGIN_DIR = path.dirname(fileURLToPath(import.meta.url))
const WORKSHOP = path.resolve(PLUGIN_DIR, "..", "..")
const RUNTIME = path.join(WORKSHOP, ".harness")
const ALIVE_FILE = path.join(RUNTIME, "plugins-alive")
const SANDBOX_SHELL = path.join(WORKSHOP, "scripts", "sandbox", "agent-shell")

/** Project docs: writing them never counts as "code" for the plan gate. */
const GATED_FILES = ["PLAN.md", "SCOPE.md", "REVIEW.md", "BLIND.md", "DEVIL.md", "WHATIF.md"]
const DOC_FILES = [...GATED_FILES, "BUGHUNT.md", "NOTES.md", "LEARNINGS.md", "BRIEF.md", "AGENTS.md", "README.md"]
const DOC_DIRS = ["RESEARCH"] // /research runs before /plan
const WRITE_TOOLS = new Set(["edit", "write", "patch", "multiedit"])

/** Harness state (approval). Only scripts/approve.sh, run by the human's /approve, writes it. */
const isHarnessState = (absTarget: string) => absTarget.split(path.sep).includes(".harness")
const sha256 = (file: string) => createHash("sha256").update(readFileSync(file)).digest("hex")

/** Is the project's PLAN.md, as it is now, the one the human approved? */
function planApproved(proj: string): boolean {
  try {
    const state = JSON.parse(readFileSync(path.join(proj, ".harness", "state.json"), "utf8"))
    return state?.plan_sha256 === sha256(path.join(proj, "PLAN.md"))
  } catch {
    return false
  }
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
      if (path.isAbsolute(p)) return p
      return path.resolve(SESSION_DIR, p)
    }

    /** The mini project a TARGET path lives in (a direct child of mini-projects/). */
    const projectOf = (absTarget: string): string | null => {
      if (!miniRoot) return null
      let dir = absTarget
      for (let i = 0; i < 12; i++) {
        if (path.dirname(dir) === miniRoot) return dir
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
    const checkWrite = (absTarget: string) => {
      if (isHarnessState(absTarget)) {
        throw new Error(
          `SAFETY GATE: approval. ${absTarget} is harness state. Agents never write .harness/; the human records approval by typing /approve <slug>.`,
        )
      }
      // plan gate keyed on the project the TARGET lives in (works from workshop root or nested)
      const proj = projectOf(absTarget)
      if (!proj) return
      if (DOC_FILES.includes(path.basename(absTarget))) return
      if (DOC_DIRS.includes(path.relative(proj, absTarget).split(path.sep)[0])) return
      if (!has(proj, "PLAN.md")) {
        throw new Error(
          "SAFETY GATE: plan gate. No PLAN.md in project. Code cannot be written before a plan exists. Run /plan, the human approves with /approve, then /build.",
        )
      }
      if (!planApproved(proj)) {
        throw new Error(
          `SAFETY GATE: plan gate. PLAN.md in ${path.basename(proj)} is not approved, or changed after approval. The human reads PLAN.md and types /approve ${path.basename(proj)}.`,
        )
      }
    }

    // OS sandbox. The wrapper sandboxes only agent shells; the writable root is the project the
    // command runs in, else the session's project, else all of mini-projects/ (workshop root).
    await ctx.shell.hook("create.before", async (invocation: any) => {
      const cwd = resolveTarget(invocation.cwd || SESSION_DIR) // a relative workdir is resolved after this hook
      const root = projectOf(cwd) ?? sessionProject() ?? miniRoot
      let real = ""
      try {
        real = root ? realpathSync.native(root) : "" // sandbox paths are case-sensitive; macOS dirs may not be
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

      if (tool === "shell") {
        const cmd = typeof input?.command === "string" ? input.command : ""

        if (isCommitOrTag(cmd)) {
          const proj = sessionProject()
          if (!has(proj, "REVIEW.md")) {
            throw new Error("SAFETY GATE: ship gate. REVIEW.md missing. Run /review first. No commit without review.")
          }
          if (!has(proj, "BLIND.md")) {
            throw new Error("SAFETY GATE: ship gate. BLIND.md missing. Run /blind first. No commit without blind spot check.")
          }
          // verdict must be SHIP, not REWORK / FIX FIRST / TODO (AUDIT.md P1-3)
          let verdict = ""
          try {
            const m = readFileSync(path.join(proj!, "REVIEW.md"), "utf8").match(/VERDICT:\s*([A-Za-z ]+)/i)
            verdict = (m?.[1] ?? "").trim().toUpperCase()
          } catch {
            // ignore
          }
          if (verdict !== "SHIP") {
            throw new Error(
              `SAFETY GATE: ship gate. REVIEW.md verdict is "${verdict || "missing"}", not SHIP. Fix the findings and re-review before committing.`,
            )
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
        targets.forEach(checkWrite)
        return
      }

      if (WRITE_TOOLS.has(tool)) {
        // every path this call writes: the single path, or each path named in a patch blob
        const raws =
          tool === "patch" && typeof input?.patchText === "string" ? patchTargets(input.patchText) : [filePath(input)]
        for (const raw of raws) {
          if (!raw) continue
          const target = resolveTarget(raw)
          if (outsideProject(target)) {
            throw new Error(
              `SAFETY GATE: write outside project blocked. Target: ${target}\nWrite inside the current mini project only.`,
            )
          }
          checkWrite(target)
        }
      }
    })
  },
}

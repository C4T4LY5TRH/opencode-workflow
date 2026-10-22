/**
 * safety-gate - hard gates. Blocks what must never happen.
 *
 * v2 plugin API: export default { id, setup }
 * hooks: ctx.tool.hook("execute.before", cb)  -> throwing rejects the tool call.
 *
 * NOTE 1: the opencode server may run from a different cwd than the session
 *   (it can run as a background service). Session/project dir MUST come from
 *   ctx.location, never from process.cwd().
 *
 * NOTE 2: a plugin that fails to compile is SILENTLY skipped -> gates vanish.
 *   So: heartbeat file on setup + bench check + log scan. Never assume.
 */

import { appendFileSync, existsSync, readdirSync, statSync } from "node:fs"
import path from "node:path"

const DANGEROUS: { re: RegExp; msg: string }[] = [
  {
    re: /\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rf][a-zA-Z]*\s+(\/(?:\s|$)|~(?:\/)?(?:\s|$)|\/\*|~\/\*|\/Users\b|\/System\b|\/private\b|\/var\b|\/etc\b)/,
    msg: "recursive delete of a system or home path blocked.",
  },
  { re: /\bgit\s+push\b[^|;&]*(--force|-f)\b/, msg: "git push --force blocked." },
  { re: /\bgit\s+reset\s+--hard\b/, msg: "git reset --hard blocked." },
  { re: /\bgit\s+clean\b[^|;&]*-[a-zA-Z]*f/, msg: "git clean -f blocked." },
  { re: /\bgit\s+checkout\s+\.\s*$/m, msg: "git checkout . blocked (loses work)." },
  { re: /\bDROP\s+(TABLE|DATABASE)\b/i, msg: "DROP blocked." },
  { re: /:\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:/, msg: "fork bomb blocked." },
  { re: /\bcurl\b[^|]*\|\s*(sudo\s+)?(ba|z|d)?sh\b/, msg: "curl | sh blocked." },
  { re: /\bchmod\s+(-R\s+)?777\b/, msg: "chmod 777 blocked." },
  { re: /\bmkfs\b/, msg: "mkfs blocked." },
  { re: /\bdd\s+[^|;&]*of=\/dev\//, msg: "dd to device blocked." },
]

/** Files owned by other agents. Coder must not write them. */
const GATED_FILES = ["PLAN.md", "SCOPE.md", "REVIEW.md", "BLIND.md"]

/** Project docs: writing them never requires a plan. Everything else is code. */
const DOC_FILES = [...GATED_FILES, "NOTES.md", "LEARNINGS.md", "BRIEF.md", "AGENTS.md", "README.md"]

const WRITE_TOOLS = new Set(["edit", "write", "patch", "apply_patch", "multiedit"])

const CONFIG_DIR = process.env.OPENCODE_CONFIG_DIR ?? path.join(process.env.HOME || "", ".config", "opencode")
const ALIVE_FILE = path.join(CONFIG_DIR, "brain", ".plugins-alive")

export default {
  id: "safety-gate",
  setup: async (ctx: any) => {
    // heartbeat: proves this plugin actually loaded (see NOTE 2)
    try {
      if (!existsSync(path.dirname(ALIVE_FILE))) {
        const { mkdirSync } = await import("node:fs")
        mkdirSync(path.dirname(ALIVE_FILE), { recursive: true })
      }
      appendFileSync(ALIVE_FILE, `safety-gate loaded ${new Date().toISOString()}\n`)
    } catch {
      // ignore
    }

    const location = ctx?.location
    const SESSION_DIR: string =
      location?.directory ?? location?.project?.directory ?? process.env.OPENCODE_PROJECT_DIR ?? process.cwd()
    const BRAIN_DIR = path.join(CONFIG_DIR, "brain")

    /** nearest ancestor that holds mini-projects/ */
    const miniRoot = (() => {
      let dir = SESSION_DIR
      for (let i = 0; i < 6; i++) {
        const candidate = path.join(dir, "mini-projects")
        if (existsSync(candidate)) return candidate
        const parent = path.dirname(dir)
        if (parent === dir) break
        dir = parent
      }
      return null
    })()

    const listProjects = (): string[] => {
      if (!miniRoot) return []
      try {
        return readdirSync(miniRoot)
          .map((name) => path.join(miniRoot, name))
          .filter((dir) => {
            try {
              return statSync(dir).isDirectory()
            } catch {
              return false
            }
          })
      } catch {
        return []
      }
    }

    /** The project we are working in. */
    const projectDir = (): string => {
      // session is the workshop root -> the workshop IS the working area
      if (existsSync(path.join(SESSION_DIR, "mini-projects"))) return SESSION_DIR
      // session sits directly inside mini-projects/ -> that IS the project
      if (miniRoot && path.dirname(SESSION_DIR) === miniRoot) return SESSION_DIR
      // session dir already looks like a project
      const markers = ["PLAN.md", "SCOPE.md", "BRIEF.md", "AGENTS.md"]
      if (markers.some((f) => existsSync(path.join(SESSION_DIR, f)))) return SESSION_DIR
      const projects = listProjects()
      if (projects.length === 0) return SESSION_DIR
      const withPlan = projects.filter((dir) => existsSync(path.join(dir, "PLAN.md")))
      if (withPlan.length === 1) return withPlan[0]
      const sorted = projects
        .map((dir) => {
          let m = 0
          try {
            m = statSync(dir).mtimeMs
          } catch {}
          return { dir, m }
        })
        .sort((a, b) => b.m - a.m)
      return sorted[0]?.dir ?? SESSION_DIR
    }

    const has = (file: string) => existsSync(path.join(projectDir(), file))

    /** true when the session is inside a mini project (not the workshop root) */
    const IN_PROJECT = Boolean(miniRoot && path.dirname(SESSION_DIR) === miniRoot)

    const shellCommand = (input: any): string => {
      if (!input || typeof input !== "object") return ""
      const c = input.command ?? input.cmd ?? input.script
      return typeof c === "string" ? c : ""
    }

    const filePath = (input: any): string => {
      if (!input || typeof input !== "object") return ""
      const f = input.filePath ?? input.file ?? input.path
      return typeof f === "string" ? f : ""
    }

    /** absolute write targets inside a shell command */
    const writeTargets = (cmd: string): string[] => {
      const targets: string[] = []
      const push = (raw: string) => {
        const t = raw.replace(/^["']|["']$/g, "")
        if (!t) return
        if (t.startsWith("~/")) targets.push(path.join(process.env.HOME || "", t.slice(2)))
        else if (t.startsWith("/")) targets.push(t)
      }
      // redirection targets: > path, >> path
      const redirect = />>?\s*("|')?([^\s"'|;&]+)/g
      for (const m of cmd.matchAll(redirect)) push(m[2])
      // cp / mv destination
      const copy = /\b(?:cp|mv)\s+(?:-[a-zA-Z-]+\s+)*([^\s]+)\s+([^\s]+)/g
      for (const m of cmd.matchAll(copy)) push(m[2])
      // mkdir / touch / tee path
      const create = /\b(?:mkdir|touch|tee)\s+(?:-[a-zA-Z-]+\s+)*([^\s]+)/g
      for (const m of cmd.matchAll(create)) push(m[1])
      return targets
    }

    const outsideProject = (target: string): boolean => {
      const proj = projectDir()
      if (!path.isAbsolute(target)) return false
      if (!path.relative(proj, target).startsWith("..")) return false
      if (!path.relative(BRAIN_DIR, target).startsWith("..")) return false
      // harmless sinks
      if (target === "/dev/null" || target === "/dev/stdout" || target === "/dev/stderr") return false
      if (target.startsWith("/tmp/") || target === "/tmp" || target.startsWith("/var/tmp/")) return false
      return true
    }

    await ctx.tool.hook("execute.before", async (event: any) => {
      const tool = String(event?.tool ?? "")
      try {
        const marker = path.join(CONFIG_DIR, "brain", ".hook-payload.json")
        if (!existsSync(marker)) {
          const { writeFileSync } = await import("node:fs")
          writeFileSync(
            marker,
            JSON.stringify({ keys: Object.keys(event ?? {}), agent: event?.agent, tool, sessionID: event?.sessionID }, null, 2),
          )
        }
      } catch {
        // ignore
      }
      const agent = String(event?.agent ?? "")
      const input = event?.input

      // 1. destructive shell
      if (tool === "bash" || tool === "shell") {
        const cmd = shellCommand(input)
        for (const rule of DANGEROUS) {
          if (rule.re.test(cmd)) {
            throw new Error(
              `SAFETY GATE: ${rule.msg}\nCommand was: ${cmd.slice(0, 200)}\nDo it yourself in a terminal if you really mean it.`,
            )
          }
        }

        // 2. ship gate - no commit without review + blind spot sheet
        if (/^\s*git\s+(commit|tag)\b/.test(cmd)) {
          if (!has("REVIEW.md")) {
            throw new Error("SAFETY GATE: ship gate. REVIEW.md missing. Run /review first. No commit without review.")
          }
          if (!has("BLIND.md")) {
            throw new Error("SAFETY GATE: ship gate. BLIND.md missing. Run /blind first. No commit without blind spot check.")
          }
        }

        // 3. no shell writes outside the project (blocks gate workarounds)
        const bad = writeTargets(cmd).find((p) => outsideProject(p))
        if (bad) {
          throw new Error(
            `SAFETY GATE: shell write outside project blocked. Path: ${bad}\nProject: ${projectDir()}\nWrite inside the project only.`,
          )
        }
      }

      // 4. plan gate - no code edits without an approved PLAN.md
      //    File-role based (not agent based): project docs are always allowed,
      //    everything else counts as code and needs a plan first.
      //    Only applies INSIDE a mini project. The workshop root is the tooling
      //    itself (harness/, README, AGENTS.md) - no plan needed there.
      if (WRITE_TOOLS.has(tool) && IN_PROJECT) {
        const base = filePath(input) ? path.basename(filePath(input)) : ""
        const isDoc = DOC_FILES.includes(base)
        if (!isDoc && !has("PLAN.md")) {
          throw new Error(
            "SAFETY GATE: plan gate. No PLAN.md in project. Code cannot be written before a plan exists. Run /plan, get human approval, then /build.",
          )
        }
      }

      // 6. no writes outside the project tree
      if (WRITE_TOOLS.has(tool)) {
        const target = filePath(input)
        if (target && path.isAbsolute(target) && outsideProject(target)) {
          throw new Error(
            `SAFETY GATE: write outside project blocked. Target: ${target}\nProject: ${projectDir()}\nWrite inside the project only.`,
          )
        }
      }
    })
  },
}

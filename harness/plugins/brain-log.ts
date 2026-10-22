/**
 * brain-log - keeps the brain alive across sessions.
 *
 * 1. Injects a tiny brain pointer into every request context (so the brain is
 *    never lost after compaction).
 * 2. Appends a compact session log to brain/SESSIONS.log.
 *
 * v2 plugin API: ctx.session.hook("context", cb), ctx.event.subscribe(cb)
 */

import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs"
import path from "node:path"

const CONFIG_DIR = process.env.OPENCODE_CONFIG_DIR || path.join(process.env.HOME || "", ".config", "opencode")
const BRAIN = path.join(CONFIG_DIR, "brain")
const LOG = path.join(BRAIN, "SESSIONS.log")
const ALIVE_FILE = path.join(BRAIN, ".plugins-alive")
const ROOT = process.env.OPENCODE_PROJECT_DIR || process.cwd()

const POINTER = [
  "## BRAIN ACTIVE",
  "Rules live in ~/.config/opencode/brain/rules/. Load with the `brain` skill when a rule matters.",
  "Core rules (always): verify before claim - no scope creep - ask when unsure - small diff - cite sources.",
  "Gates: plan -> build -> review + blind -> ship (human confirms).",
].join("\n")

function brainRuleIndex(): string {
  const dir = path.join(BRAIN, "rules")
  if (!existsSync(dir)) return ""
  try {
    return readdirSync(dir)
      .filter((f) => f.endsWith(".md"))
      .sort()
      .map((f) => {
        const body = readFileSync(path.join(dir, f), "utf8")
        const title = body.split("\n").find((l) => l.startsWith("# ")) ?? ""
        return `- ${f} ${title.replace(/^#\s*/, "")}`.trim()
      })
      .join("\n")
  } catch {
    return ""
  }
}

export default {
  id: "brain-log",
  setup: async (ctx: any) => {
    // heartbeat: proves this plugin actually loaded (a plugin that fails to compile is silent)
    try {
      if (!existsSync(path.dirname(LOG))) mkdirSync(path.dirname(LOG), { recursive: true })
      appendFileSync(ALIVE_FILE, `brain-log loaded ${new Date().toISOString()}\n`)
    } catch {
      // ignore
    }

    // 1. brain pointer + rule index on every request context
    try {
      await ctx.session.hook("context", async (event: any) => {
        try {
          if (!Array.isArray(event?.system)) return
          const index = brainRuleIndex()
          const text = index ? `${POINTER}\n${index}` : POINTER
          event.system.push({ type: "text", text })
        } catch {
          // ignore
        }
      })
    } catch {
      // ignore
    }

    // 2. session log
    try {
      await ctx.event.subscribe(async (event: any) => {
        try {
          const type = String(event?.type ?? "")
          if (type !== "file.edited" && type !== "session.idle" && type !== "session.error") return
          if (!existsSync(BRAIN)) mkdirSync(BRAIN, { recursive: true })
          const time = new Date().toISOString()
          const data = event?.data ?? {}
          const detail =
            type === "file.edited"
              ? `edited: ${data?.filePath ?? data?.path ?? "?"}`
              : type === "session.error"
                ? `error: ${String(data?.message ?? "").slice(0, 200)}`
                : `idle: ${data?.sessionID ?? ""}`
          appendFileSync(LOG, `${time} | ${type} | ${detail}\n`)
        } catch {
          // ignore
        }
      })
    } catch {
      // ignore
    }
  },
}

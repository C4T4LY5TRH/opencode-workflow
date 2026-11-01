/**
 * brain-log - injects the rule index into every request and records a compact session log.
 *
 * 1. Injects a brain pointer + rule index into every request context
 *    (survives compaction; re-injected on the next primary step after it).
 * 2. Appends a compact session log to .harness/events.jsonl using the REAL v2
 *    event API: ctx.event.subscribe() returns an AsyncIterable, so we iterate it
 *    with `for await`; the v1 callback form never ran (see
 *    docs/audit/research/L0-plugins.md section 5).
 *
 * Paths resolve from THIS file's location, never from ~/.config/opencode.
 */

import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const PLUGIN_DIR = path.dirname(fileURLToPath(import.meta.url))
const WORKSHOP = path.resolve(PLUGIN_DIR, "..", "..")
const BRAIN = path.join(WORKSHOP, "brain")
const RULES = path.join(BRAIN, "rules")
const RUNTIME = path.join(WORKSHOP, ".harness")
const LOG = path.join(RUNTIME, "events.jsonl")
const ALIVE_FILE = path.join(RUNTIME, "plugins-alive")

const POINTER = [
  "## BRAIN ACTIVE",
  `Rules live in ${RULES}. Load with the \`brain\` skill when a rule matters.`,
  "Core rules (always): verify before claim - no scope creep - ask when unsure - small diff - cite sources.",
  "Gates: approved plan -> steps with passing checks -> fresh SHIP review -> ship (human commits).",
].join("\n")

function brainRuleIndex(): string {
  if (!existsSync(RULES)) return ""
  try {
    return readdirSync(RULES)
      .filter((f) => f.endsWith(".md"))
      .sort()
      .map((f) => {
        const body = readFileSync(path.join(RULES, f), "utf8")
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
    try {
      if (!existsSync(RUNTIME)) mkdirSync(RUNTIME, { recursive: true })
      appendFileSync(ALIVE_FILE, `brain-log loaded ${new Date().toISOString()}\n`)
    } catch {
      // ignore
    }

    // 1. brain pointer + rule index on every primary request
    try {
      await ctx.session.hook("context", async (event: any) => {
        try {
          if (!Array.isArray(event?.system)) return
          const index = brainRuleIndex()
          event.system.push({ type: "text", text: index ? `${POINTER}\n${index}` : POINTER })
        } catch {
          // ignore
        }
      })
    } catch {
      // ignore
    }

    // 2. session log via the real AsyncIterable event stream (do NOT await the loop)
    try {
      const stream = ctx.event.subscribe()
      void (async () => {
        try {
          for await (const e of stream) {
            try {
              const type = String(e?.type ?? "")
              if (
                type !== "session.execution.succeeded" &&
                type !== "session.execution.failed" &&
                type !== "session.execution.interrupted" &&
                type !== "session.step.ended"
              )
                continue
              const data = e?.data ?? {}
              const files = Array.isArray(data?.files) ? data.files : undefined
              const rec = {
                t: new Date().toISOString(),
                type,
                sessionID: data?.sessionID,
                files: files && files.length ? files.slice(0, 20) : undefined,
                error: data?.error?.message ? String(data.error.message).slice(0, 200) : undefined,
              }
              appendFileSync(LOG, JSON.stringify(rec) + "\n")
            } catch {
              // ignore one event
            }
          }
        } catch {
          // stream closed on unload
        }
      })()
    } catch {
      // ignore
    }
  },
}

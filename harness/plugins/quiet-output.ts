/**
 * quiet-output - shrink noisy tool output before the model reads it.
 *
 * Our own "Blocks" implementation. Does not touch prompts, does not touch code.
 * Only rewrites already-produced output when it is huge and mostly noise.
 */

import { appendFileSync, existsSync, mkdirSync } from "node:fs"
import path from "node:path"

const MAX = 3000
const HEAD = 1200
const TAIL = 900
const NOISE = /(error|failed|failure|exception|panic|warning|\bE\d{3}\b)/i

const CONFIG_DIR = process.env.OPENCODE_CONFIG_DIR ?? path.join(process.env.HOME || "", ".config", "opencode")
const ALIVE_FILE = path.join(CONFIG_DIR, "brain", ".plugins-alive")

function truncate(text: string): string {
  if (text.length <= MAX) return text
  const head = text.slice(0, HEAD)
  const tail = text.slice(text.length - TAIL)
  const middle = text.slice(HEAD, text.length - TAIL)
  const lines = middle.split("\n")
  const keep = lines.filter((l) => NOISE.test(l)).slice(0, 40)
  const dropped = lines.length - keep.length
  return [
    head,
    "",
    `... [quiet-output] ${middle.length} chars hidden, ${dropped} lines dropped, ${keep.length} error-like lines kept ...`,
    ...keep,
    "",
    tail,
  ].join("\n")
}

export default {
  id: "quiet-output",
  setup: async (ctx: any) => {
    // heartbeat: proves this plugin actually loaded (a plugin that fails to compile is silent)
    try {
      if (!existsSync(path.dirname(ALIVE_FILE))) mkdirSync(path.dirname(ALIVE_FILE), { recursive: true })
      appendFileSync(ALIVE_FILE, `quiet-output loaded ${new Date().toISOString()}\n`)
    } catch {
      // ignore
    }

    await ctx.tool.hook("execute.after", async (event: any) => {
      try {
        const result = event?.result
        if (!result) return

        if (typeof result.output === "string") {
          result.output = truncate(result.output)
          return
        }

        if (typeof result.content === "string") {
          result.content = truncate(result.content)
          return
        }

        if (Array.isArray(result.content)) {
          for (const part of result.content) {
            if (part && typeof part === "object" && typeof part.text === "string") {
              part.text = truncate(part.text)
            }
          }
        }
      } catch {
        // never break a session over cosmetics
      }
    })
  },
}

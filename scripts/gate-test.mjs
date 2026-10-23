// gate-test: prove the harness plugins FIRE, not just that they exist.
// Builds a throwaway workshop fixture, loads the real plugins with a fake opencode
// ctx, replays the cases in scripts/gate-cases.json, exits non-zero on any miss.
//
//   node scripts/gate-test.mjs        (Node 22+ runs the .ts plugin directly)
//
// Scope: what the PLUGIN owns (ship gate, plan gate + approval, write confinement),
// scripts/approve.sh (the only writer of the approval the plan gate reads), and the
// OS sandbox for agent shells (shell hook + scripts/sandbox/, run for real; macOS),
// brain-log's rule-usage telemetry, and the decay verdict of scripts/rule-report.py.
// Destructive commands are the policy layer's job; scripts/bench.py checks those.
import { spawnSync } from "node:child_process"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

process.env.HARNESS_TEST = "1" // the plugin must not write its load heartbeat during tests
const HERE = path.dirname(fileURLToPath(import.meta.url))
const PLUGIN = path.resolve(HERE, "..", ".opencode", "plugins", "safety-gate.ts")
const spec = JSON.parse(fs.readFileSync(path.join(HERE, "gate-cases.json"), "utf8"))

// The fixture lives in the workshop (gitignored), not in the temp dir: the sandbox lets agents
// write temp dirs, so sandbox cases there would pass for the wrong reason.
const root = fs.realpathSync.native(fs.mkdtempSync(path.resolve(HERE, "..", ".gate-test-")))
process.on("exit", () => fs.rmSync(root, { recursive: true, force: true })) // also after a crash
for (const rel of spec.fixture) {
  const p = path.join(root, rel)
  fs.mkdirSync(path.dirname(p), { recursive: true })
  // REVIEW.md needs a real verdict: good/ ships, rework/ does not
  let body = "x\n"
  if (rel.endsWith("REVIEW.md")) body = rel.includes("/rework/") ? "## VERDICT: REWORK\n" : "## VERDICT: SHIP\n"
  fs.writeFileSync(p, body)
}

// approve.sh resolves the workshop from its own location, so a copy in the fixture approves fixture projects.
const APPROVE = path.join(root, "scripts", "approve.sh")
fs.mkdirSync(path.dirname(APPROVE), { recursive: true })
fs.copyFileSync(path.resolve(HERE, "approve.sh"), APPROVE)
const human = { ...process.env }
delete human.AGENT
delete human.OPENCODE_SESSION_ID
const approve = (slug, env = human) => spawnSync("bash", [APPROVE, slug], { env, encoding: "utf8" })
for (const proj of spec.approve) {
  const r = approve(path.basename(proj))
  if (r.status !== 0) throw new Error(`approve.sh failed for ${proj}: ${r.stderr}`)
}
for (const proj of spec.edit_after_approve) fs.appendFileSync(path.join(root, proj, "PLAN.md"), "step added later\n")

let fail = 0
const report = (id, ok, expect, got, note) => {
  if (!ok) fail++
  console.log(`${ok ? "PASS" : "FAIL"} ${id.padEnd(5)} expect=${expect.padEnd(5)} got=${got.padEnd(5)} ${note}`)
}

// the script itself: refuses agent shells (opencode sets AGENT=1 + OPENCODE_SESSION_ID there) and missing plans
const stateOf = (slug) => path.join(root, "mini-projects", slug, ".harness", "state.json")
const scriptCases = [
  ["h1", approve("unapproved", { ...human, AGENT: "1" }), "unapproved", "approve.sh refuses an agent shell (AGENT=1)"],
  ["h2", approve("unapproved", { ...human, OPENCODE_SESSION_ID: "ses_x" }), "unapproved", "approve.sh refuses an agent shell (session id)"],
  ["h3", approve("bare"), "bare", "approve.sh refuses a project without PLAN.md"],
]
for (const [id, r, slug, note] of scriptCases) {
  const got = r.status !== 0 && !fs.existsSync(stateOf(slug)) ? "block" : "allow"
  report(id, got === "block", "block", got, note)
}

const plugin = (await import(pathToFileURL(PLUGIN).href)).default
const hooksFor = new Map()
async function hooks(session) {
  if (hooksFor.has(session)) return hooksFor.get(session)
  const h = {}
  await plugin.setup({
    location: { directory: path.join(root, session) },
    tool: { hook: async (n, cb) => { h[n] = cb } },
    shell: { hook: async (n, cb) => { h[`shell.${n}`] = cb } },
    session: { hook: async () => {} },
    event: { subscribe: () => ({ async *[Symbol.asyncIterator]() {} }) },
  })
  hooksFor.set(session, h)
  return h
}

for (const c of spec.cases) {
  const h = await hooks(c.session)
  const input = JSON.parse(JSON.stringify(c.input).replaceAll("$ROOT", root))
  let got = "allow"
  try {
    await h["execute.before"]({ tool: c.tool, input, agent: "coder", sessionID: "s", id: "t", messageID: "m" })
  } catch {
    got = "block"
  }
  report(c.id, got === c.expect, c.expect, got, c.note)
}
// sandbox: run each command the way opencode would after the shell hook (AGENT=1 marks agent shells)
for (const c of spec.sandbox) {
  const h = await hooks(c.session)
  const env = { ...human, HOME: path.join(root, "home"), HARNESS_TEST_TOKEN: "x" }
  const inv = { command: c.command, cwd: c.cwd ?? path.join(root, c.session), timeout: 0, shell: "/bin/zsh", env }
  if (!h["shell.create.before"]) {
    report(c.id, false, c.expect, "nohook", c.note)
    continue
  }
  await h["shell.create.before"](inv)
  if (c.agent) inv.env.AGENT = "1"
  const r = spawnSync(inv.shell, ["-c", inv.command], {
    cwd: path.resolve(root, c.session, c.cwd ?? ""), env: inv.env, encoding: "utf8",
  })
  const got = r.status === 0 ? "allow" : "block"
  report(c.id, got === c.expect, c.expect, got, c.note)
}

// Tools that resolve paths from their own file location run as COPIES inside the fixture,
// so they read and write the fixture's .harness/, never the real one.
const REPO = path.resolve(HERE, "..")
const copyIn = (rel) => fs.cpSync(path.join(REPO, rel), path.join(root, rel), { recursive: true })
const okCase = (id, ok, note) => report(id, ok, "ok", ok ? "ok" : "wrong", note)

// brain-log telemetry: replay tool calls through execute.after, then read the fixture's rule-usage.json
copyIn(".opencode/plugins/brain-log.ts")
const brainLog = (await import(pathToFileURL(path.join(root, ".opencode/plugins/brain-log.ts")).href)).default
const afterFor = new Map()
for (const call of spec.telemetry.calls) {
  if (!afterFor.has(call.session)) {
    const h = {}
    await brainLog.setup({
      location: { directory: path.join(root, call.session) },
      tool: { hook: async (n, cb) => { h[n] = cb } },
      session: { hook: async () => {} },
      event: { subscribe: () => ({ async *[Symbol.asyncIterator]() {} }) },
    })
    afterFor.set(call.session, h)
  }
  const input = JSON.parse(JSON.stringify(call.input).replaceAll("$ROOT", root))
  await afterFor.get(call.session)["execute.after"]?.({
    tool: call.tool, input, status: call.status, agent: "coder", sessionID: "s", id: "t", messageID: "m",
  })
}
let usage = {}
try {
  usage = JSON.parse(fs.readFileSync(path.join(root, ".harness", "rule-usage.json"), "utf8"))
} catch {}
const t = spec.telemetry
okCase("t1", Object.entries(t.expect_rules).every(([r, n]) => usage.rules?.[r]?.count === n),
  "telemetry: rule reads counted (read tool + shell cat)")
okCase("t2", t.not_counted.every((r) => !usage.rules?.[r]), "telemetry: a failed read is not counted")
okCase("t3", JSON.stringify(Object.keys(usage.projects ?? {}).sort()) === JSON.stringify([...t.expect_projects].sort()),
  "telemetry: projects recorded from paths and session dir, never _template")

// rule-report: decay verdicts on a crafted usage file
for (const rel of ["scripts/rule-report.py", "brain/rules", "brain/evals/bench.yaml", ".opencode/opencode.json"]) copyIn(rel)
fs.writeFileSync(path.join(root, ".harness", "rule-usage.json"), JSON.stringify(spec.decay.usage))
const rep = spawnSync("python3", [path.join(root, "scripts", "rule-report.py")], { encoding: "utf8" })
const line = (rule) => rep.stdout.split("\n").find((l) => l.startsWith(rule)) ?? ""
okCase("d1", rep.status === 0 && spec.decay.decay.every((r) => line(r).includes("DECAY")),
  "rule-report: unused for 3+ new projects -> DECAY")
okCase("d2", rep.status === 0 && spec.decay.keep.every((r) => line(r) && !line(r).includes("DECAY")),
  "rule-report: recently used or always-on rules are kept")

const total = spec.cases.length + scriptCases.length + spec.sandbox.length + 5
console.log(`\ngate-test: ${total - fail}/${total} passed`)
process.exit(fail ? 1 : 0)

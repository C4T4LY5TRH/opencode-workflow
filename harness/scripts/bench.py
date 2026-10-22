#!/usr/bin/env python3
"""Structural bench: does the harness still look right?

Behavioural evals (in brain/evals/bench.yaml) still need a real task by hand.
This script checks structure + prints the manual checklist.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

CONFIG = os.environ.get("OPENCODE_CONFIG_DIR", os.path.expanduser("~/.config/opencode"))
BRAIN = os.path.join(CONFIG, "brain")
RULES = os.path.join(BRAIN, "rules")
AGENTS = ["orchestrator", "scoper", "architect", "researcher", "visual-review", "coder",
          "reviewer", "critic", "devil", "whatif", "brain"]
COMMANDS = ["new", "scope", "research", "plan", "build", "review", "grill", "whatif",
            "blind", "ship", "learn", "evolve", "bench", "caveman", "browse", "html2md", "map"]
SKILLS = ["caveman", "browser", "visual-review", "html2md", "spec", "brain", "verify"]

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


# --- rules
rule_files = sorted(f for f in os.listdir(RULES)) if os.path.isdir(RULES) else []
check("core-rules-present", "core rule file exists",
      os.path.isfile(os.path.join(RULES, "000-core.md")))

ids = [f.split("-")[0] for f in rule_files]
check("rules-numbered", "rule ids unique", len(ids) == len(set(ids)), ",".join(ids))

too_long = []
for f in rule_files:
    n = len(read(os.path.join(RULES, f)).splitlines())
    if n > 40:
        too_long.append(f"{f}:{n}")
check("rules-small", "every rule <= 40 lines", not too_long, ",".join(too_long))

skill_index = read(os.path.join(CONFIG, "skills", "brain", "SKILL.md"))
referenced = set(re.findall(r"\b(\d{3})-([a-z0-9-]+)\b", skill_index))
missing = []
for num, slug in referenced:
    if not any(f.startswith(num + "-") for f in rule_files):
        missing.append(f"{num}-{slug}")
check("rules-linked", "brain skill index matches rule files", not missing, ",".join(missing))

# --- frontmatter is well formed (a broken one silently drops the agent/command)
bad_fm = []
for folder, ext in (("agents", ".md"), ("commands", ".md")):
    d = os.path.join(CONFIG, folder)
    if not os.path.isdir(d):
        continue
    for f in os.listdir(d):
        if not f.endswith(ext):
            continue
        body = read(os.path.join(d, f))
        if not body.startswith("---\n") or "\n---\n" not in body[4:]:
            bad_fm.append(f"{folder}/{f}")
check("frontmatter-valid", "every agent/command has valid frontmatter", not bad_fm, ",".join(bad_fm))

# --- no duplicate keys inside agent frontmatter (YAML strict mode rejects them)
dup_agents = []
for f in os.listdir(os.path.join(CONFIG, "agents")) if os.path.isdir(os.path.join(CONFIG, "agents")) else []:
    if not f.endswith(".md"):
        continue
    body = read(os.path.join(CONFIG, "agents", f))
    fm = body[4:].split("\n---\n")[0] if body.startswith("---\n") else ""
    seen = set()
    for line in fm.split("\n"):
        st = line.strip()
        if not st or st.startswith("#") or ":" not in st:
            continue
        indent = len(line) - len(line.lstrip())
        key = st.split(":", 1)[0].strip().strip('"')
        if indent == 0:
            if key in seen:
                dup_agents.append(f"{f}:{key}")
            seen.add(key)
check("frontmatter-no-dupes", "no duplicate top-level keys in agent frontmatter", not dup_agents, ",".join(dup_agents))

# --- agents / commands / skills
agent_files = [f[:-3] for f in os.listdir(os.path.join(CONFIG, "agents"))] if os.path.isdir(os.path.join(CONFIG, "agents")) else []
check("agents-present", "11 custom agents exist",
      all(a in agent_files for a in AGENTS),
      ",".join(a for a in AGENTS if a not in agent_files))

cmd_files = [f[:-3] for f in os.listdir(os.path.join(CONFIG, "commands"))] if os.path.isdir(os.path.join(CONFIG, "commands")) else []
check("commands-present", "17 commands exist",
      all(c in cmd_files for c in COMMANDS) and len(cmd_files) >= 17,
      f"found {len(cmd_files)}")

skill_ok = []
for s in SKILLS:
    p = os.path.join(CONFIG, "skills", s, "SKILL.md")
    body = read(p)
    if not body or "name:" not in body or "description:" not in body:
        skill_ok.append(s)
check("skills-present", "7 skills with valid frontmatter", not skill_ok, ",".join(skill_ok))

# --- gates intact (semantics, not substring)
cfg_path = os.path.join(CONFIG, "opencode.json")
try:
    cfg = json.loads(read(cfg_path))
except Exception:
    cfg = {}
perms = cfg.get("permission", cfg.get("permissions", {})) or {}


def perm(action, resource):
    v = perms.get(action)
    if isinstance(v, dict):
        return v.get(resource)
    return v


required = [
    ("shell", "rm -rf /", "deny"),
    ("shell", "rm -rf /Users*", "deny"),
    ("shell", "git push --force*", "deny"),
    ("shell", "git reset --hard*", "deny"),
    ("shell", "git clean -*", "deny"),
    ("read", "*.env", "deny"),
    ("read", "**/.ssh/**", "deny"),
    ("edit", "**/.git/**", "deny"),
    ("external_directory", "*", "deny"),
]
bad_gates = [f"{a}:{r} expected {e} got {perm(a, r)}" for a, r, e in required if perm(a, r) != e]
check("gates-intact", "permission rules keep their intended effect", not bad_gates, "; ".join(bad_gates))

soft = [("shell", "rm -rf *", "ask"), ("shell", "npm publish*", "ask"), ("shell", "git push*", "ask")]
bad_soft = [f"{a}:{r} expected {e} got {perm(a, r)}" for a, r, e in soft if perm(a, r) != e]
check("gates-soft-ask", "soft-danger commands ask the human, not silently pass", not bad_soft, "; ".join(bad_soft))

# --- rule files are well formed (title + at least one bullet)
malformed = []
for f in rule_files:
    body = read(os.path.join(RULES, f))
    lines = [l for l in body.splitlines() if l.strip()]
    if not lines or not lines[0].startswith("# "):
        malformed.append(f"{f}:no-title")
    elif not any(re.match(r"^(-|\d+\.)\s+\S", l.strip()) for l in lines[1:]):
        malformed.append(f"{f}:no-rules")
check("rules-shaped", "every rule has a title and at least one rule line", not malformed, ",".join(malformed))

# --- orphan rule files (exist but not in the brain skill index)
orphans = []
for f in rule_files:
    stem = f[:-3]
    if stem not in skill_index:
        orphans.append(stem)
check("rules-no-orphans", "every rule file is listed in the brain skill index", not orphans, ",".join(orphans))

# --- brain folders exist
missing_dirs = [d for d in ("patterns", "anti-patterns", "evals") if not os.path.isdir(os.path.join(BRAIN, d))]
check("brain-folders", "brain has patterns/ anti-patterns/ evals/", not missing_dirs, ",".join(missing_dirs))

plugin_files = os.listdir(os.path.join(CONFIG, "plugins")) if os.path.isdir(os.path.join(CONFIG, "plugins")) else []
check("plugins-present", "3 plugins installed",
      all(p in plugin_files for p in ["safety-gate.ts", "quiet-output.ts", "brain-log.ts"]),
      ",".join(plugin_files))

# --- plugins ACTUALLY loaded (a plugin that fails to compile is silently skipped -> gates vanish)
alive = read(os.path.join(BRAIN, ".plugins-alive"))
not_alive = [p for p in ("safety-gate", "quiet-output", "brain-log") if f"{p} loaded" not in alive]
if not alive.strip():
    # no heartbeat at all = opencode has never run with this config dir yet.
    # Distinct from "loaded then broke". Say which one it is.
    check("plugins-alive", "all 3 plugins reported a load heartbeat", False,
          "no heartbeat file yet - opencode has not run with this config dir (start it once, or run install.sh)")
else:
    check("plugins-alive", "all 3 plugins reported a load heartbeat", not not_alive, ",".join(not_alive))

# --- no plugin load failure AFTER the last successful heartbeat
#     (old failures in the log are history; only a failure newer than the
#      newest heartbeat means a plugin is currently broken)
log_dir = os.path.expanduser("~/.local/share/opencode/log")
failures = []  # (timestamp, target)
try:
    logs = sorted(
        (os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith(".log")),
        key=lambda p: os.path.getmtime(p),
    )
    for lg in logs[-2:]:
        for line in read(lg).splitlines():
            # ONLY real plugin-load warnings count. A shell command that merely
            # mentions the phrase (e.g. a diagnostic grep) is logged as
            # "spawning process" and must NOT be counted as a failure.
            if 'message="failed to load plugin"' not in line:
                continue
            if 'level=WARN' not in line:
                continue
            ts = line.split(" ")[0].strip().replace("timestamp=", "")
            target = ""
            for part in line.split():
                if part.startswith("target="):
                    target = part[len("target="):]
            failures.append((ts, target))
except Exception:
    pass

heartbeats = []
for line in alive.splitlines():
    parts = line.split(" loaded ")
    if len(parts) == 2 and parts[1].strip():
        heartbeats.append(parts[1].strip())
newest_beat = heartbeats[-1] if heartbeats else ""
if not newest_beat:
    # No heartbeat = opencode has never run with this config dir. There is no
    # reference point, so old log entries from another config dir are history,
    # not failures. The plugins-alive check above already flags this state.
    check("plugins-no-load-failures", "no plugin load failure after the last heartbeat", True,
          "no heartbeat yet - opencode has not run with this config dir")
else:
    recent_failures = []
    for ts, target in failures:
        if ts > newest_beat:
            recent_failures.append(f"{ts} {target}")
    check("plugins-no-load-failures", "no plugin load failure after the last heartbeat",
          not recent_failures, "; ".join(recent_failures[-3:]))

# --- changelog
ch = read(os.path.join(BRAIN, "CHANGELOG.md"))
check("changelog-current", "brain changelog has version", bool(re.search(r"##\s*v", ch)))

# --- prompt fragments exist and are referenced by agents
PROMPTS_DIR = os.path.join(BRAIN, "prompts")
prompt_files = sorted(f for f in os.listdir(PROMPTS_DIR)) if os.path.isdir(PROMPTS_DIR) else []
check("prompts-present", "brain has prompt fragments", len(prompt_files) >= 2, ",".join(prompt_files))

agent_bodies = ""
for a in agent_files:
    agent_bodies += read(os.path.join(CONFIG, "agents", a + ".md"))
unref = [f for f in prompt_files if f != "000-index.md" and f not in agent_bodies]
check("prompts-linked", "every prompt fragment is used by an agent", not unref, ",".join(unref))

# --- agents report with the shared contract
missing_contract = [a for a in AGENTS if "010-output-contract" not in read(os.path.join(CONFIG, "agents", a + ".md"))]
check("agents-report-contract", "all agents use the output contract", not missing_contract, ",".join(missing_contract))

# --- project template materialised (one source of truth)
workspace = ""
try:
    with open(os.path.join(CONFIG, "workspace.txt"), "r", encoding="utf-8") as fh:
        workspace = fh.read().strip()
except Exception:
    pass
TEMPLATE = os.path.join(workspace, "mini-projects", "_template") if workspace else ""
tpl_required = ["AGENTS.md", "BRIEF.md", "SCOPE.md", "PLAN.md", "REVIEW.md", "BLIND.md", "NOTES.md", "LEARNINGS.md"]
missing_tpl = [f for f in tpl_required if not (TEMPLATE and os.path.isfile(os.path.join(TEMPLATE, f)))]
check("template-materialised", "mini-project template holds the real scaffold", not missing_tpl, ",".join(missing_tpl))

# --- workshop rules live in the workshop root
check("workshop-rules", "workshop AGENTS.md exists",
      os.path.isfile(os.path.join(workspace, "AGENTS.md")) if workspace else False)

# --- hygiene: no scattered .bak files, backups live in one place
stray = [f for f in os.listdir(CONFIG) if ".bak-" in f]
check("config-hygiene", "no scattered .bak files in the config dir", not stray, ",".join(stray))
check("backups-one-place", "backups live in .backups/",
      os.path.isdir(os.path.join(CONFIG, ".backups")))

# --- teleport tooling exists (moving this harness to another machine)
teleport = os.path.join(CONFIG, "scripts", "teleport.sh")
check("teleport-tooling", "teleport.sh is installed", os.path.isfile(teleport),
      "" if os.path.isfile(teleport) else "run install.sh")

# --- version
m = re.search(r"##\s*v(\d+\.\d+)", ch)
version = m.group(1) if m else "0.0"

# --- source and installed copy are in sync
#     (editing harness/ without running install.sh = the live harness is stale)
src_version = ""
src_root = ""
try:
    with open(os.path.join(CONFIG, "workspace.txt"), "r", encoding="utf-8") as fh:
        src_root = fh.read().strip()
except Exception:
    pass
if src_root:
    src_ch = read(os.path.join(src_root, "harness", "brain", "CHANGELOG.md"))
    ms = re.search(r"##\s*v(\d+\.\d+)", src_ch)
    src_version = ms.group(1) if ms else ""
    if src_version and src_version != version:
        check("install-in-sync", "installed harness matches the source tree",
              False, f"source v{src_version} vs installed v{version} - run install.sh")
    else:
        check("install-in-sync", "installed harness matches the source tree", True)
else:
    check("install-in-sync", "installed harness matches the source tree", False, "no workspace.txt")

passed = sum(1 for r in results if r["ok"])
failed = len(results) - passed

print(f"BRAIN BENCH  v{version}  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
print(f"passed {passed} / {len(results)}   failed {failed}\n")
for r in results:
    mark = "PASS" if r["ok"] else "FAIL"
    print(f"  [{mark}] {r['id']:22} {r['desc']}" + (f"   -> {r['detail']}" if r["detail"] and not r["ok"] else ""))

print("\nBEHAVIOURAL EVALS (manual - need a real task):")
evals = read(os.path.join(BRAIN, "evals", "bench.yaml"))
for cid, desc in re.findall(r"-\s*id:\s*(\S+)\s*\n\s*desc:\s*\"?([^\"\n]+)", evals):
    if not cid.startswith("behavioural"):
        continue
    print(f"  [MANUAL] {cid:20} {desc.strip()}")

out = {
    "version": version,
    "at": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "failed": failed,
    "results": results,
}
path = os.path.join(BRAIN, "evals", "last-run.json")
try:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nlast run saved: {path}")
except Exception as exc:
    print(f"(could not save last run: {exc})")

sys.exit(1 if failed else 0)

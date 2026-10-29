#!/usr/bin/env python3
"""Rule report: how often each brain rule is used, and which evals check it.

Usage data: .harness/rule-usage.json, written by the brain-log plugin. A rule counts as
used when an agent reads its file; each mini project is stamped when first touched.
Decay (rule 040): a rule not used while 3 or more new projects started is a delete
candidate. Rules loaded on every request via `instructions` never decay.
Evals: the `rules:` map at the end of brain/evals/bench.yaml.

  python3 scripts/rule-report.py           the table /status brain shows
  python3 scripts/rule-report.py --check   exit 1 if a rule has no eval or names an unknown one (bench)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSHOP = os.path.dirname(HERE)
RULES = os.path.join(WORKSHOP, "brain", "rules")
EVALS = os.path.join(WORKSHOP, "brain", "evals", "bench.yaml")
USAGE = os.path.join(WORKSHOP, ".harness", "rule-usage.json")
CONFIG = os.path.join(WORKSHOP, ".opencode", "opencode.json")
DECAY_AFTER = 3  # new projects without a use


def read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


rules = sorted(f for f in os.listdir(RULES) if re.match(r"^\d{3}-.+\.md$", f)) if os.path.isdir(RULES) else []
yaml = read(EVALS)
eval_ids = set(re.findall(r"^\s*- id:\s*(\S+)", yaml, re.M))
rule_map = {}
if "\nrules:" in yaml:
    for name, ids in re.findall(r"^\s+(\d{3}-[\w-]+\.md):\s*\[([^\]]*)\]", yaml.split("\nrules:", 1)[1], re.M):
        rule_map[name] = [i.strip() for i in ids.split(",") if i.strip()]

problems = {r: "NO EVAL" for r in rules if not rule_map.get(r)}
for r, ids in rule_map.items():
    unknown = [i for i in ids if i not in eval_ids]
    if unknown:
        problems[r] = "UNKNOWN EVAL " + ",".join(unknown)

if "--check" in sys.argv:
    for r, why in sorted(problems.items()):
        print(f"{r}: {why}")
    print(f"rules-have-evals: {len(rules) - len(problems)}/{len(rules)} rules mapped to existing evals")
    sys.exit(1 if problems else 0)

try:
    usage = json.loads(read(USAGE)) if read(USAGE) else {}
except ValueError:
    usage = {}
used = usage.get("rules", {})
projects = usage.get("projects", {})
since = usage.get("since", "")
always_on = {r for r in rules if r in read(CONFIG)}  # loaded via `instructions` on every request

print(f"RULE REPORT  usage since {since[:10] or 'never (no data yet)'}; {len(projects)} projects seen")
print(f"{'rule':24} {'uses':>4}  {'last used':10}  {'new projects since':>18}  {'status':24} evals")
for r in rules:
    u = used.get(r, {})
    since_use = sum(1 for t in projects.values() if t > (u.get("last") or since))
    if r in problems:
        status = problems[r]
    elif r in always_on:
        status = "keep (always loaded)"
    elif not usage:
        status = "no data yet"
    elif since_use >= DECAY_AFTER:
        status = "DECAY: propose delete"
    else:
        status = "keep"
    last = "always" if r in always_on else (u.get("last", "")[:10] or "never")
    print(f"{r:24} {u.get('count', 0):>4}  {last:10}  {since_use:>18}  {status:24} {', '.join(rule_map.get(r, []))}")

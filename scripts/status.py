#!/usr/bin/env python3
"""/status text (stdlib only).

usage: python3 scripts/status.py [slug | <slug> --check <FILE>]

  (none)   one line per project and the bench result
  <slug>   one project in detail: every step, the failure text, the review
  <slug> --check <FILE>   run one document's format check, print OK or ERROR: <message> (read-only; the one form
           an agent shell may run besides `<slug>`)

Run from command templates. It only reads the project state. Nothing here can raise into a caller: a bad project becomes a message.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import harness_state as hs  # noqa: E402
import next as nx  # noqa: E402  (the one routing map: next_command; the approval digest)

REVIEW_LINES = 12


# --- gathering ---------------------------------------------------------------------------

def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def project_slugs(workshop):
    root = os.path.join(workshop, "mini-projects")
    try:
        names = os.listdir(root)
    except OSError:
        return []
    return sorted(n for n in names if not n.startswith(("_", ".")) and os.path.isdir(os.path.join(root, n)))


def _goal(proj):
    m = re.search(r"^##\s+GOAL[^\n]*\n+([^\n#][^\n]*)", _read(os.path.join(proj, "BRIEF.md")), re.M)
    return m.group(1).strip() if m else ""


def _deploy_line(slug, state):
    """deploy.py's line (spec 7.2: read from <APPS_HOME>/<slug>/deploys.json), None when there is nothing to say."""
    try:
        import deploy as dp  # here: a test's copy of status.py may sit without deploy.py beside it
    except ImportError:
        return None
    return dp.status_line(slug, bool(state.get("milestones_shipped")))


def info(workshop, slug):
    """Everything shown about one project. Never raises: a project that cannot be read gets an `error`."""
    proj = os.path.join(workshop, "mini-projects", slug)
    d = {"slug": slug, "error": None, "steps": [], "review": None, "approved_at": None, "goal": _goal(proj),
         "findings": [], "status": slug, "autopilot": False, "cost": 0, "project_cost": 0, "batch": ""}
    try:
        ph = hs.stage(proj)
        rnd = hs.fix_running(proj)  # F3: a fix round is issued but not yet judged: FIX, not STUCK (the last round)
        if rnd and ph["stage"] == "STUCK":
            ph = {**ph, "stage": "FIX"}
        elif ph["stage"] != "FIX":
            rnd = None
        d.update(stage=ph["stage"], step=ph["step"], done=ph["done"], total=ph["total"], reason=ph["reason"],
                 milestone=ph["milestone"], at=ph["at"], problem=ph["error"],
                 batch=", ".join(f"{i['kind']} {i['n']}" for i in ph["batch"]))
        try:
            state = hs.load(proj)
        except hs.StateError:
            state = {}
            d["error"] = hs.unreadable_reason(proj)
        # the running cost and autopilot (spec 3.2), never the cap (B3); the STATUS line is next.py's, the one format
        cost = state.get("cost") or {}
        d.update(status=nx.status_line(slug, ph, state), autopilot=bool((state.get("autopilot") or {}).get("on")),
                 cost=hs.milestone_cost(state, ph["milestone"]),
                 project_cost=cost.get("project_usd") or 0)
        d["fix_round"] = f"FIX round {rnd}/{hs.FIX_LIMIT}" if rnd else None
        d["fix_running"] = f"{d['fix_round']} running" if rnd else None
        d["steps"] = [s for s in state.get("steps", []) if isinstance(s, dict)]
        d["approved_at"] = state.get("approved_at")
        vr = state.get("visual_runs")
        d["visual_runs"] = (vr.get(ph["milestone"]) or 0) if isinstance(vr, dict) and ph.get("milestone") else 0
        blk = state.get("checkpoint_block")  # spec 4.2: a save point that waits for the human, and the scan notes
        d["blocked"] = f"save point blocked: {hs.block_reason(blk, slug)}" if blk else None
        d["scan_notes"] = state.get("scan_notes") or []
        d["deploy"] = _deploy_line(slug, state)
        rev = state.get("review")
        if isinstance(rev, dict) and rev.get("verdict") and ph["stage"] in ("REVIEW", "FIX", "SHIP", "STUCK") and not ph["step"]:
            d["review"] = rev["verdict"] + (" (stale: code changed since)" if ph["stage"] == "REVIEW" else "")
            if ph["stage"] != "REVIEW":
                lines = [l.rstrip() for l in _read(os.path.join(proj, "REVIEW.md")).splitlines() if l.strip()]
                d["findings"] = lines[:REVIEW_LINES]
        if ph["stage"] in ("REVIEW", "STUCK") and not d["problem"]:
            d["problem"] = hs.review_problem(proj)  # a lens missing from ## Hunt: why no verdict was recorded
    except Exception as exc:  # one broken project must not hide the others
        d.update(stage="?", step=None, done=0, total=0, reason="", milestone=None, at=None, problem=None,
                 error=f"could not read this project ({exc.__class__.__name__})")
    d["next"] = (f"wait for {d['fix_round']} to finish, then /status {slug}"
                 if d.get("fix_running") else nx.next_command(slug, d["stage"], d["at"], d["reason"]))
    d["digest"] = nx.digest(workshop, slug) if d["stage"] == "DECIDE" else None
    return d


def bench_line(workshop):
    files = sorted(glob.glob(os.path.join(workshop, ".harness", "bench-history", "*.json")))
    if not files:
        return "bench: not run yet"
    try:
        with open(files[-1], "r", encoding="utf-8") as fh:
            run = json.load(fh)
        return f"bench: {int(run['passed'])} passed, {int(run['failed'])} failed ({str(run['at'])[:10]})"
    except (OSError, ValueError, KeyError, TypeError):
        return "bench: last result unreadable"


# --- text --------------------------------------------------------------------------------

def _progress(d):
    if d["stage"] in ("BUILD", "STUCK") and d["step"]:
        return f"step {d['step'].get('n')}/{d['total']}"
    return f"{d['done']}/{d['total']} steps done" if d["total"] else "no steps yet"


def _autopilot(d):
    return f"autopilot {'on' if d['autopilot'] else 'off'}"


def _costs(d, milestone="this milestone", project="this project", sep=", "):
    return f"${d['cost']:.2f} {milestone}{sep}${d['project_cost']:.2f} {project}"


def _detail(d):
    out = [f"STATUS: {d['status']}  {_autopilot(d)}", f"{d['slug']}  {d['stage']}  {_progress(d)}"]
    if d["goal"]:
        out.append(f"goal: {d['goal']}")
    if d["milestone"]:
        out.append(f"milestone: {d['milestone']}")
    if d["batch"]:
        out.append(f"batch: {d['batch']}")
    out.append(f"cost: {_costs(d)}")
    if d.get("visual_runs"):
        out.append(f"visual runs: {d['visual_runs']}/{hs.VISUAL_RUN_CAP}")
    out.append(d["error"] or d.get("fix_running") or d["reason"])
    if d.get("blocked"):
        out.append(d["blocked"])
    if d.get("scan_notes"):
        out.append(f"scan notes: {', '.join(d['scan_notes'])}")
    if d["problem"] and d["stage"] != "DECIDE":
        out.append(f"problem: {d['problem']}")
    if d["approved_at"]:
        out.append(f"approved: {d['approved_at']}")
    if d.get("deploy"):
        out.append(d["deploy"])
    cur = next((s for s in d["steps"] if not s.get("done_at")), None)
    for s in d["steps"]:
        mark = "✓" if s.get("done_at") else ("→" if s is cur else "·")
        out.append(f"  {mark} {s.get('n')}. {s.get('title')}")
        if s is cur:
            out.append(f"      check: {s.get('check')}")
            if s.get("attempts") and s.get("last_failure"):
                out.append(f"      failed {s['attempts']} time(s); last failure:")
                out.extend("        " + l for l in nx._tail(s["last_failure"]))
    if d["review"]:
        out.append(f"review: {d['review']}")
        out.extend("  " + l for l in d["findings"])
    if d["digest"]:
        out.extend(["", d["digest"], ""])
    out.append(f"next: {d['next']}")
    return "\n".join(out)


def text(workshop, slug=None):
    if slug:
        if not hs.SLUG_RE.fullmatch(slug) or slug not in project_slugs(workshop):
            return f"no project mini-projects/{slug}. Try /status for the list.\n"
        return _detail(info(workshop, slug)) + "\n"
    out = [bench_line(workshop)]
    slugs = project_slugs(workshop)
    if not slugs:
        out.append("no projects yet: /new \"<goal>\"")
    for s in slugs:
        d = info(workshop, s)
        run = f"  {_autopilot(d)}  {_costs(d, 'milestone', 'project', ' / ')}" if d["autopilot"] or d["project_cost"] else ""
        out.append(f"{s:<16} {d['stage']:<11} {_progress(d):<16} next: {d['next']}{run}")
        if d["error"] or d["stage"] == "STUCK" or d.get("fix_running"):
            out.append(f"{'':<16} {d['error'] or d.get('fix_running') or d['reason']}")
    return "\n".join(out) + "\n"


# --- CLI ---------------------------------------------------------------------------------

CHECK_USAGE = "ERROR: usage: status.py <slug> --check <" + "|".join(hs.DOC_NAMES) + ">"


def check(workshop, slug, name):
    """`<slug> --check <FILE>`: OK or ERROR: <message>. Validates both arguments before reading anything; read-only."""
    if not hs.SLUG_RE.fullmatch(slug or "") or slug not in project_slugs(workshop) or name not in hs.DOC_NAMES:
        return CHECK_USAGE + "\n"
    try:
        err = hs.check_file(os.path.join(workshop, "mini-projects", slug), name)
    except Exception as exc:  # the answer must stay one line
        err = f"could not check {name} ({exc.__class__.__name__})"
    return ("OK" if err is None else "ERROR: " + " ".join(err.split())) + "\n"


def main(argv):
    workshop = os.path.dirname(HERE)
    args = argv[1:]
    if len(args) == 3 and args[1] == "--check":
        sys.stdout.write(check(workshop, args[0].strip(), args[2].strip()))
        return 0
    if len(args) > 1:
        sys.stdout.write("usage: /status [project]\n")
        return 0
    try:
        sys.stdout.write(text(workshop, args[0].strip() if args else None))
    except Exception as exc:  # /status must never show a traceback
        print(f"status: could not finish ({exc.__class__.__name__}: {exc})", file=sys.stdout)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

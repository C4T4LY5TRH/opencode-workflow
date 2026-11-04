#!/usr/bin/env python3
"""/status text and the read-only dashboard (stdlib only).

usage: python3 scripts/status.py [slug | --html | <slug> --check <FILE>]

  (none)   one line per project and the bench result
  <slug>   one project in detail: every step, the failure text, the review
  --html   write .harness/dashboard.html (self-refreshing, read-only), print nothing
  <slug> --check <FILE>   run one document's format check, print OK or ERROR: <message> (read-only; the one form
           an agent shell may run besides `<slug>`)

Run from command templates and from the safety-gate plugin. It only reads the project state, except that
--html writes the one dashboard file. Nothing here can raise into a caller: a bad project becomes a message.
"""
import glob
import html as _html
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import harness_state as hs  # noqa: E402
import next as nx  # noqa: E402  (the one routing map: next_command; the approval digest)

SLUG_RE = re.compile(r"[a-z0-9-][a-z0-9_-]*")  # same rule as approve.sh and next.py
TEXT_FAILURE_LINES = 10
REVIEW_LINES = 12
REFRESH_SECONDS = 5
esc = _html.escape


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
         "findings": [], "updated": None, "status": slug, "autopilot": False, "cost": 0, "project_cost": 0, "batch": ""}
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
                 cost=(cost.get("usd") or 0) if cost.get("milestone") == ph["milestone"] else 0,
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
        mtimes = [os.path.getmtime(p) for p in (os.path.join(proj, ".harness", "state.json"),
                  os.path.join(proj, "PLAN.md"), os.path.join(proj, "REVIEW.md")) if os.path.exists(p)]
        d["updated"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(max(mtimes))) if mtimes else None
    except Exception as exc:  # one broken project must not hide the others
        d.update(stage="?", step=None, done=0, total=0, reason="", milestone=None, at=None, problem=None,
                 error=f"could not read this project ({exc.__class__.__name__})")
    d["next"] = (f"wait for {d['fix_round']} to finish, then /status {slug}"
                 if d.get("fix_running") else nx.next_command(slug, d["stage"], d["at"]))
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
                out.extend("        " + l for l in str(s["last_failure"]).splitlines()[-TEXT_FAILURE_LINES:])
    if d["review"]:
        out.append(f"review: {d['review']}")
        out.extend("  " + l for l in d["findings"])
    if d["digest"]:
        out.extend(["", d["digest"], ""])
    out.append(f"next: {d['next']}")
    return "\n".join(out)


def text(workshop, slug=None):
    if slug:
        if not SLUG_RE.fullmatch(slug) or slug not in project_slugs(workshop):
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


# --- html --------------------------------------------------------------------------------

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2024;--dim:#5d6670;--line:#dde1e6;--bar:#e3e7ec;--fill:#2f6fd6;--bad:#b3261e;--ok:#1b7a43}
@media (prefers-color-scheme: dark){:root{--bg:#14171a;--card:#1d2125;--ink:#e6e9ec;--dim:#98a2ad;--line:#2f353b;--bar:#2b3137;--fill:#5b9bff;--bad:#ff8a80;--ok:#5fd18c}}
body{margin:0;padding:16px;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
main{max-width:960px;margin:0 auto}h1{font-size:20px;margin:0 0 4px}
.meta{color:var(--dim);margin:0 0 16px}.meta span{margin-right:16px;display:inline-block}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:0 0 12px}
.card h2{font-size:17px;margin:0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.badge{font-size:12px;border:1px solid var(--line);border-radius:4px;padding:1px 7px}
.STUCK{color:var(--bad);border-color:var(--bad)}.SHIP,.DONE{color:var(--ok);border-color:var(--ok)}
.goal,.dim{color:var(--dim);margin:2px 0}.err{color:var(--bad);margin:6px 0}
progress{width:100%;height:10px;margin:8px 0;accent-color:var(--fill)}
ul{list-style:none;padding:0;margin:6px 0}li{margin:2px 0}li.cur{font-weight:600}
pre{background:var(--bar);padding:8px;border-radius:4px;overflow:auto;max-height:12em;font-size:13px;margin:4px 0}
code{font-family:ui-monospace,monospace;font-size:13px}
"""


def _card(d):
    h = [f'<section class="card"><h2>{esc(d["slug"])} <span class="badge {esc(d["stage"])}">{esc(d["stage"])}</span>'
         f' <span class="dim">{esc(_progress(d))}</span></h2>']
    if d["goal"]:
        h.append(f'<p class="goal">{esc(d["goal"])}</p>')
    h.append(f'<progress value="{d["done"]}" max="{max(d["total"], 1)}"></progress>')
    h.append(f'<p class="{"err" if d["error"] else "dim"}">{esc(d["error"] or d.get("fix_running") or d["reason"])}</p>')
    if d.get("blocked"):
        h.append(f'<p class="err">{esc(d["blocked"])}</p>')
    run = [_autopilot(d), _costs(d, sep=" · ")] + ([f"batch: {d['batch']}"] if d["batch"] else [])
    h.append(f'<p class="dim">{esc(" · ".join(run))}</p>')
    cur = next((s for s in d["steps"] if not s.get("done_at")), None)
    if d["steps"]:
        h.append("<ul>")
        for s in d["steps"]:
            mark = "✓" if s.get("done_at") else ("→" if s is cur else "·")
            h.append(f'<li{" class=cur" if s is cur else ""}>{mark} {esc(str(s.get("n")))}. {esc(str(s.get("title")))}')
            if s is cur:
                h.append(f'<br><code>{esc(str(s.get("check")))}</code>')
                if s.get("attempts") and s.get("last_failure"):
                    h.append(f'<div class="err">failed {esc(str(s["attempts"]))} time(s); last failure:</div>'
                             f'<pre>{esc(str(s["last_failure"]))}</pre>')
            h.append("</li>")
        h.append("</ul>")
    if d["review"]:
        h.append(f'<p>review: <b>{esc(d["review"])}</b></p>')
        if d["findings"]:
            h.append("<pre>" + esc("\n".join(d["findings"])) + "</pre>")
    facts = [f"approved {d['approved_at']}" if d["approved_at"] else "not approved", f"updated {d['updated']}" if d["updated"] else ""]
    h.append(f'<p class="dim">{esc(" · ".join(f for f in facts if f))} · next: <code>{esc(d["next"])}</code></p></section>')
    return "".join(h)


def html(workshop):
    slugs = project_slugs(workshop)
    cards = "".join(_card(info(workshop, s)) for s in slugs) or '<p class="dim">no projects yet: /new "&lt;goal&gt;"</p>'
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="{REFRESH_SECONDS}">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>Harness dashboard</title>'
            f"<style>{CSS}</style></head><body><main><h1>Harness dashboard</h1>"
            f'<p class="meta"><span>{esc(bench_line(workshop))}</span>'
            f"<span>read-only, refreshes every {REFRESH_SECONDS} s</span></p>{cards}</main></body></html>\n")


def write_html(workshop):
    dest = os.path.join(workshop, ".harness", "dashboard.html")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = f"{dest}.{os.getpid()}.tmp"  # per-process name: two regenerations can overlap
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(html(workshop))
    os.replace(tmp, dest)


# --- CLI ---------------------------------------------------------------------------------

CHECK_USAGE = "ERROR: usage: status.py <slug> --check <" + "|".join(hs.DOC_NAMES) + ">"


def check(workshop, slug, name):
    """`<slug> --check <FILE>`: OK or ERROR: <message>. Validates both arguments before reading anything; read-only."""
    if not SLUG_RE.fullmatch(slug or "") or slug not in project_slugs(workshop) or name not in hs.DOC_NAMES:
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
        if args == ["--html"]:
            write_html(workshop)
        else:
            sys.stdout.write(text(workshop, args[0].strip() if args else None))
    except Exception as exc:  # /status must never show a traceback
        print(f"status: could not finish ({exc.__class__.__name__}: {exc})", file=sys.stderr if args == ["--html"] else sys.stdout)
        return 1 if args == ["--html"] else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""Recorded project state for harness v3 (stdlib only).

Library: parse_plan, load, save, approve, tree_sha256, review_verdict, phase.
CLI (run from command templates only, never from an agent shell):
  harness_state.py approve <project-dir>   record the human's approval of PLAN.md
  harness_state.py tree <project-dir>      print the project's tree hash
  harness_state.py review <project-dir>    print {"tree_sha256", "verdict"} for REVIEW.md as it is now (read-only)

State lives in <project>/.harness/state.json; its shape is spec section 7. Only trusted code writes it.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

RETRY_LIMIT = 2  # failed checks per step before STUCK
FIX_LIMIT = 2    # review -> fix rounds before STUCK
DOC_FILES = {"PLAN.md", "REVIEW.md", "CRITIQUE.md", "BUGHUNT.md", "NOTES.md", "LEARNINGS.md",
             "BRIEF.md", "README.md", "AGENTS.md"}
DOC_DIRS = ("RESEARCH/", ".harness/")
WALK_SKIP = {".git", "node_modules"}
VERDICTS = ("SHIP", "FIX FIRST", "REWORK")
# Every harness git call runs OUTSIDE the sandbox, so a repo config must never run code: no core.fsmonitor, and no
# implicit bare repo (HEAD/objects/config planted at a project root, which git would otherwise read as a repo).
GIT = ("git", "-c", "core.fsmonitor=false", "-c", "safe.bareRepository=explicit")


class PlanError(ValueError):
    pass


class StateError(ValueError):
    pass


# --- plan parsing -------------------------------------------------------------------------

def parse_plan(text):
    """PLAN.md text -> [{"n", "title", "files", "check"}]. Raises PlanError naming what is wrong."""
    lines = [l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    start = next((i for i, l in enumerate(lines) if re.match(r"^##\s+STEPS\s*$", l, re.I)), None)
    if start is None:
        raise PlanError("PLAN.md has no '## STEPS' section")
    body = []
    for l in lines[start + 1:]:
        if re.match(r"^##\s", l):  # next section
            break
        body.append(l)

    blocks = []  # [number, title, [lines]]
    for l in body:
        m = re.match(r"^###\s+(\d+)\.\s+(.+)$", l)
        if m:
            blocks.append([int(m.group(1)), m.group(2).strip(), []])
        elif re.match(r"^###(\s|$)", l):
            raise PlanError(f"malformed step heading '{l}' (use '### <n>. <title>')")
        elif blocks:
            blocks[-1][2].append(l)
    if not blocks:
        raise PlanError("no steps found under '## STEPS' (each step is '### 1. <title>')")

    steps = []
    for idx, (n, title, rest) in enumerate(blocks, start=1):
        if n != idx:
            raise PlanError(f"step {n} ('{title}') is out of order: expected step {idx} (steps run 1..N with no gaps)")
        who = f"step {n} ('{title}')"
        files, checks = [], []
        for l in rest:
            m = re.match(r"^\s*[-*]\s*(files|done when)\s*:\s*(.*)$", l, re.I)
            if not m:
                continue
            if m.group(1).lower() == "files":
                files = [f.strip().strip("`").strip() for f in m.group(2).split(",")]
                files = [f for f in files if f]
            else:
                checks.append(m.group(2).strip())
        if not checks:
            raise PlanError(f"{who} has no 'done when:' line")
        if len(checks) > 1:
            raise PlanError(f"{who} has more than one 'done when:' line")
        raw = checks[0]
        m = re.fullmatch(r"`([^`]+)`", raw)
        if not m or not m.group(1).strip():
            raise PlanError(f"{who}: 'done when' needs exactly one command inside one pair of backticks, got: {raw or '(empty)'}")
        steps.append({"n": n, "title": title, "files": files, "check": m.group(1).strip()})
    return steps


# --- state file -----------------------------------------------------------------------------

def _state_path(proj):
    return os.path.join(proj, ".harness", "state.json")


def load(proj):
    """The state dict, {} when there is no file. Raises StateError when it cannot be read."""
    try:
        with open(_state_path(proj), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise StateError(f"cannot read state.json: {exc}")
    if not isinstance(data, dict):
        raise StateError("state.json is not a JSON object")
    _check_shape(data)
    return data


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check_shape(data):
    """Raise StateError when a field has the wrong type (a hand edit), so callers never hit a TypeError."""
    def need(ok, what):
        if not ok:
            raise StateError(f"state.json: bad {what}")
    for key in ("plan_sha256", "approved_at"):
        need(data.get(key) is None or isinstance(data[key], str), key)
    need(data.get("fix_rounds") is None or _is_int(data["fix_rounds"]), "fix_rounds")
    steps = data.get("steps", [])
    need(isinstance(steps, list), "steps")  # absent is fine, null is not
    for s in steps:
        need(isinstance(s, dict), "step entry")
        need(_is_int(s.get("n")), "step n")
        need(s.get("attempts") is None or _is_int(s["attempts"]), "step attempts")
        for key in ("title", "check", "done_at", "last_failure"):
            need(s.get(key) is None or isinstance(s[key], str), f"step {key}")
        need(s.get("files") is None or isinstance(s["files"], list), "step files")
    rev = data.get("review")
    need(rev is None or isinstance(rev, dict), "review")
    for key in ("tree_sha256", "verdict", "at"):
        need(rev is None or rev.get(key) is None or isinstance(rev[key], str), f"review {key}")


def save(proj, state):
    path = _state_path(proj)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def _plan_bytes(proj):
    try:
        with open(os.path.join(proj, "PLAN.md"), "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def approve(proj, now):
    """Parse PLAN.md and record the approval. A plan that does not parse records nothing. A changed plan drops
    the recorded review; the same plan re-approved keeps it (and resets attempts and fix rounds)."""
    raw = _plan_bytes(proj)
    if raw is None:
        raise PlanError("no PLAN.md")
    try:
        steps = parse_plan(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise PlanError("PLAN.md is not valid UTF-8")
    try:
        state = load(proj)
    except StateError:
        state = {}  # re-approving is how a corrupt state is repaired
    done = {(s.get("n"), s.get("title"), s.get("check")): s.get("done_at")
            for s in state.get("steps", []) if isinstance(s, dict) and s.get("done_at")}
    for s in steps:
        s["done_at"] = done.get((s["n"], s["title"], s["check"]))
        s["attempts"] = 0
        s["last_failure"] = None
    plan_sha = hashlib.sha256(raw).hexdigest()
    if state.get("plan_sha256") != plan_sha:
        state.pop("review", None)  # a new plan: the old review judged another plan
    state["plan_sha256"] = plan_sha
    state["approved_at"] = now
    state["steps"] = steps
    state["fix_rounds"] = 0
    save(proj, state)
    return state


# --- tree hash ----------------------------------------------------------------------------

def _is_doc(rel):
    return rel in DOC_FILES or rel.startswith(DOC_DIRS)


def _git_files(proj):
    """Files git sees, only when proj is itself a repo root (else a parent repo's ignore rules would hide them)."""
    try:
        top = subprocess.run([*GIT, "-C", proj, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, timeout=10)
        # samefile, not a string compare: macOS paths differ in case (projects/Projects) and symlinks
        if top.returncode != 0 or not os.path.samefile(top.stdout.strip(), proj):
            return None
        ls = subprocess.run([*GIT, "-C", proj, "ls-files", "-co", "--exclude-standard", "-z"],
                            capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if ls.returncode != 0:
        return None
    return [p.decode("utf-8", "surrogateescape") for p in ls.stdout.split(b"\0") if p]


def _walk_files(proj):
    out = []
    for dirpath, dirnames, filenames in os.walk(proj):
        dirnames[:] = [d for d in dirnames if d not in WALK_SKIP]
        for f in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, f), proj).replace(os.sep, "/"))
    return out


def tree_sha256(proj):
    """sha256 over the project's code files (docs and .harness/ excluded), stable for equal content."""
    rels = _git_files(proj)
    if rels is None:
        rels = _walk_files(proj)
    h = hashlib.sha256()
    for rel in sorted(set(rels)):
        if _is_doc(rel):
            continue
        try:
            with open(os.path.join(proj, rel), "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            continue  # deleted but still listed, a directory, a broken symlink
        h.update(f"{rel}\0{digest}\n".encode("utf-8", "surrogateescape"))
    return h.hexdigest()


# --- review + phase -----------------------------------------------------------------------

def review_verdict(proj):
    """SHIP / FIX FIRST / REWORK from REVIEW.md, else None."""
    try:
        with open(os.path.join(proj, "REVIEW.md"), "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    m = re.search(r"VERDICT:\s*[*`]*\s*([A-Za-z ]+)", text, re.I)
    verdict = " ".join(m.group(1).upper().split()) if m else ""
    return verdict if verdict in VERDICTS else None


def phase(proj):
    """Where the project is, computed from files and state (spec 7.4, first match wins)."""
    slug = os.path.basename(os.path.abspath(proj))

    def result(name, reason, step=None, done=0, total=0):
        return {"phase": name, "step": step, "done": done, "total": total, "reason": reason}

    raw = _plan_bytes(proj)
    if raw is None:
        return result("PLAN", "no PLAN.md yet: the planner writes it")
    try:
        state = load(proj)
    except StateError:
        return result("APPROVE", f"state unreadable: /approve {slug} again")
    steps = [s for s in state.get("steps", []) if isinstance(s, dict)]
    done = sum(1 for s in steps if s.get("done_at"))
    total = len(steps)
    if state.get("plan_sha256") != hashlib.sha256(raw).hexdigest():
        return result("APPROVE", f"plan not approved or changed: read PLAN.md, then /approve {slug}", None, done, total)
    if not steps:
        return result("APPROVE", f"no steps recorded: /approve {slug} again", None, done, total)

    cur = next((s for s in steps if not s.get("done_at")), None)
    if cur is not None:
        attempts = cur.get("attempts") or 0
        if attempts >= RETRY_LIMIT:
            return result("STUCK", f"step {cur.get('n')} failed its check {attempts} times: fix it by hand, then "
                                   f"/approve {slug} (resets attempts), then /go {slug}; or edit PLAN.md, then "
                                   f"/approve {slug}", cur, done, total)
        return result("BUILD", f"build step {cur.get('n')}: {cur.get('title')}", cur, done, total)

    rev = state.get("review")
    fresh = (isinstance(rev, dict) and rev.get("verdict") in VERDICTS
             and rev.get("tree_sha256") == tree_sha256(proj))
    if not fresh:
        return result("REVIEW", "no fresh review: the reviewer writes REVIEW.md", None, done, total)
    if rev["verdict"] == "SHIP":
        return result("SHIP", f"review is fresh and says SHIP: /ship {slug}", None, done, total)
    rounds = state.get("fix_rounds") or 0
    if rounds >= FIX_LIMIT:
        return result("STUCK", f"{rounds} fix rounds used and the review still says {rev['verdict']}: "
                               "read REVIEW.md, you decide", None, done, total)
    return result("FIX", f"review says {rev['verdict']}: the builder fixes the findings", None, done, total)


# --- CLI ----------------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3 or argv[1] not in ("approve", "tree", "review"):
        print("usage: harness_state.py approve|tree|review <project-dir>", file=sys.stderr)
        return 2
    cmd, proj = argv[1], os.path.abspath(argv[2])
    if cmd == "tree":
        print(tree_sha256(proj))
        return 0
    if cmd == "review":
        print(json.dumps({"tree_sha256": tree_sha256(proj), "verdict": review_verdict(proj)}))
        return 0
    # opencode marks every agent shell with AGENT=1 and OPENCODE_SESSION_ID; a command template has neither
    if os.environ.get("AGENT") == "1" or os.environ.get("OPENCODE_SESSION_ID"):
        print("REFUSED: approval comes only from the human typing /approve <slug>, never from an agent shell.",
              file=sys.stderr)
        return 3
    slug = os.path.basename(proj)
    try:
        state = approve(proj, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    except PlanError as exc:
        print(f"REFUSED: {exc}")
        return 1
    except OSError as exc:
        print(f"REFUSED: cannot write state: {exc}")
        return 1
    print(f"APPROVED: mini-projects/{slug}/PLAN.md (sha256 {state['plan_sha256'][:12]}, {len(state['steps'])} steps). "
          "Any edit to PLAN.md revokes this; /approve again after a change.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

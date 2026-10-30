#!/usr/bin/env python3
"""Recorded project state for the harness (v3 plans, v4 brief + architecture + plan; stdlib only).

Library: parse_plan, load, save, approve, approve_v3, approved, ship, lock_brief, lock_fresh, docs, check_file,
tree_sha256, review_verdict, phase, stage.
CLI (the writing verbs run from command templates only, never from an agent shell):
  harness_state.py approve <project-dir>   record the human's approval (v4: BRIEF + ARCHITECTURE + PLAN; v3: PLAN)
  harness_state.py ship <project-dir>      record the finished milestone (v4 only; a v3 project has none)
  harness_state.py approved <project-dir>  print yes/no: is the current plan approved (read-only)
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
from datetime import datetime, timedelta, timezone

sys.dont_write_bytecode = True  # the import below must not leave scripts/__pycache__ behind
import harness_docs as hd
from harness_docs import PlanError, parse_plan  # noqa: F401  (re-exported for hs.parse_plan / hs.PlanError)

RETRY_LIMIT = 2  # failed checks per step before STUCK
FIX_LIMIT = 2    # review -> fix rounds before STUCK
STAGE_LIMIT = 2  # failed chains per automatic stage before STUCK (v4)
DOC_FILES = {"PLAN.md", "REVIEW.md", "CRITIQUE.md", "BUGHUNT.md", "NOTES.md", "LEARNINGS.md",
             "BRIEF.md", "README.md", "AGENTS.md", "ARCHITECTURE.md", "BRAINSTORM.md", "DESIGN.md"}
DOC_DIRS = ("RESEARCH/", ".harness/")
WALK_SKIP = {".git", "node_modules"}
VERDICTS = ("SHIP", "FIX FIRST", "REWORK")
# Every harness git call runs OUTSIDE the sandbox, so a repo config must never run code: no core.fsmonitor, and no
# implicit bare repo (HEAD/objects/config planted at a project root, which git would otherwise read as a repo).
GIT = ("git", "-c", "core.fsmonitor=false", "-c", "safe.bareRepository=explicit")


class StateError(ValueError):
    pass


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
        for key in ("milestone", "proves"):
            need(s.get(key) is None or isinstance(s[key], str), f"step {key}")
        need(s.get("covers") is None or isinstance(s["covers"], list), "step covers")
    need(data.get("approved_sha256") is None or isinstance(data["approved_sha256"], str), "approved_sha256")
    brief = data.get("brief")
    need(brief is None or isinstance(brief, dict), "brief")
    if brief is not None:
        for key in ("locked_at", "sha256"):
            need(isinstance(brief.get(key), str), f"brief {key}")
        need(brief.get("reopened") is None or isinstance(brief["reopened"], bool), "brief reopened")
    shipped = data.get("milestones_shipped")
    need(shipped is None or (isinstance(shipped, list) and all(isinstance(m, str) for m in shipped)),
         "milestones_shipped")
    att = data.get("stage_attempts")
    need(att is None or (isinstance(att, dict) and all(_is_int(v) for v in att.values())), "stage_attempts")
    req = data.get("critique_requested")
    need(req is None or _is_int(req), "critique_requested")
    rv = data.get("revise")
    need(rv is None or isinstance(rv, dict), "revise")
    if rv is not None:
        need(rv.get("reason") in ("spike", "brief"), "revise reason")
        need(rv.get("step") is None or _is_int(rv["step"]), "revise step")
        need(isinstance(rv.get("arch_sha256"), str), "revise arch_sha256")
        need(rv.get("plan_sha256") is None or isinstance(rv["plan_sha256"], str), "revise plan_sha256")
        need(_is_int(rv.get("round")), "revise round")
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


def approve_v3(proj, now):
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


# --- v4: documents, brief lock, one approval, milestone ship ----------------------------------

DOC_NAMES = ("BRIEF.md", "ARCHITECTURE.md", "PLAN.md", "CRITIQUE.md", "DESIGN.md")


def _read_raw(proj, name):
    """The file's bytes, None when it is missing. Raises DocError when it cannot be read."""
    try:
        with open(os.path.join(proj, name), "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise hd.DocError(f"{name}: cannot read: {exc}")


def _decode(raw, name):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise hd.DocError(f"{name}: not valid UTF-8")


def _read(proj, name):
    """The file's text, None when it is missing. Raises DocError when it cannot be read as UTF-8."""
    raw = _read_raw(proj, name)
    return None if raw is None else _decode(raw, name)


def _file_sha(proj, name):
    try:
        with open(os.path.join(proj, name), "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _state_or_empty(proj):
    try:
        return load(proj)
    except StateError:
        return {}


def approval_sha256(proj):
    """The one approval hash (spec H1): BRIEF, ARCHITECTURE, DESIGN (only if it exists), PLAN. None when a
    required file is missing."""
    return _approval_from({n: _file_sha(proj, n) for n in ("BRIEF.md", "ARCHITECTURE.md", "DESIGN.md", "PLAN.md")})


def _approval_from(digests):
    """H1 formula over file digests (name -> sha256 or None/absent); approve() feeds it the digests of the very
    bytes it parsed, so a file changed between parse and hash cannot be approved unchecked."""
    h = hashlib.sha256()
    for name in ("BRIEF.md", "ARCHITECTURE.md", "DESIGN.md", "PLAN.md"):
        digest = digests.get(name)
        if digest is None:
            if name == "DESIGN.md":
                continue
            return None
        h.update(f"{name}\0{digest}\n".encode("utf-8"))
    return h.hexdigest()


def is_v3_mode(proj, state):
    """A project approved the v3 way: a recorded plan hash, and neither an architecture nor a brief lock."""
    return ("plan_sha256" in state and not os.path.exists(os.path.join(proj, "ARCHITECTURE.md"))
            and "brief" not in state)


def current_milestone(proj, state, arch):
    """The first milestone of ARCHITECTURE.md that has not shipped, or None when all have."""
    shipped = state.get("milestones_shipped") or []
    return next((m["id"] for m in arch["milestones"] if m["id"] not in shipped), None)


def docs(proj):
    """Every v4 document, parsed. Each is None when it is missing or invalid, with its message in errors[name].
    Never raises."""
    out = {"brief": None, "arch": None, "plan_steps": None, "plan_milestone": None, "critique": None,
           "errors": {}, "skipped": set(), "digests": {}, "texts": {}}
    errors, skipped, texts = out["errors"], out["skipped"], out["texts"]
    # one read per file: what is parsed here is what is hashed (digests) and what answers are read from (texts)
    for name in ("BRIEF.md", "ARCHITECTURE.md", "PLAN.md", "CRITIQUE.md", "DESIGN.md"):
        try:
            raw = _read_raw(proj, name)
            if raw is not None:
                out["digests"][name] = hashlib.sha256(raw).hexdigest()
                texts[name] = _decode(raw, name)
        except hd.DocError as exc:
            errors[name] = str(exc)
            continue
        if raw is None and name != "DESIGN.md":
            errors[name] = f"{name} does not exist yet"

    def attempt(name, fn):
        try:
            return fn()
        except hd.DocError as exc:
            errors[name] = str(exc)
            return None

    if "BRIEF.md" in texts:
        out["brief"] = attempt("BRIEF.md", lambda: hd.parse_brief(texts["BRIEF.md"]))
    if "ARCHITECTURE.md" in texts:
        if out["brief"] is None:
            errors["ARCHITECTURE.md"] = "ARCHITECTURE.md: not checked until BRIEF.md is valid"
            skipped.add("ARCHITECTURE.md")
        else:
            feats = out["brief"]["features"]
            out["arch"] = attempt("ARCHITECTURE.md", lambda: hd.parse_architecture(
                texts["ARCHITECTURE.md"], {f["id"] for f in feats}, {f["id"] for f in feats if f["priority"] == "MUST"}))
    if "PLAN.md" in texts:
        out["plan_milestone"] = hd.plan_milestone(texts["PLAN.md"])
        if out["arch"] is None:
            errors["PLAN.md"] = "PLAN.md: not checked until ARCHITECTURE.md is valid"
            skipped.add("PLAN.md")
        else:
            cm = current_milestone(proj, _state_or_empty(proj), out["arch"])
            if cm is not None:  # every milestone shipped: there is no plan to check
                out["plan_steps"] = attempt("PLAN.md", lambda: hd.check_plan(texts["PLAN.md"], out["arch"], cm))
    if "CRITIQUE.md" in texts:
        has_design = os.path.exists(os.path.join(proj, "DESIGN.md"))
        out["critique"] = attempt("CRITIQUE.md", lambda: hd.parse_critique(texts["CRITIQUE.md"], has_design))
    return out


def _critique_problem(d, state, cm):
    """(message or None, latest round or None): is there a usable critique round for milestone cm (P4, P13)?"""
    if "CRITIQUE.md" in d["errors"]:
        return d["errors"]["CRITIQUE.md"], None
    latest = d["critique"]["rounds"][-1]
    if cm is not None and latest["milestone"] != cm:
        return (f"CRITIQUE.md: no round for the current milestone {cm} "
                f"(add '## ROUND {latest['n'] + 1} — {cm}')"), latest
    req = state.get("critique_requested")
    if req is not None and latest["n"] <= req:
        return (f"CRITIQUE.md: no round newer than the request (the critic must add ROUND {latest['n'] + 1})"), latest
    return None, latest


def _revise_pending(d, state):
    """{file: message} for each condition of a recorded revise (H7, H20) not met yet: the architect revises, the
    planner redoes the plan, a critique round newer than the recorded one. stage(), approve() and check_file() all
    ask this one helper, so they cannot drift. Empty when there is no revise."""
    rv = state.get("revise")
    if not rv:
        return {}
    out, digests, crit = {}, d["digests"], d["critique"]
    if rv.get("arch_sha256") == digests.get("ARCHITECTURE.md"):
        out["ARCHITECTURE.md"] = "ARCHITECTURE.md is unchanged since the revise was recorded"
    if digests.get("PLAN.md") is not None and rv.get("plan_sha256") == digests["PLAN.md"]:
        out["PLAN.md"] = "PLAN.md is unchanged since the revise was recorded"
    if crit and crit["rounds"][-1]["n"] <= rv.get("round", 0):
        out["CRITIQUE.md"] = (f"CRITIQUE.md: no round newer than round {rv['round']} "
                              f"(the critic must add ROUND {crit['rounds'][-1]['n'] + 1})")
    return out


def _unanswered(proj, d, latest):
    """One message per serious point of the round that its target file does not answer."""
    out, cache = [], {}
    for pt in latest["points"]:
        if pt["severity"] != "serious":
            continue
        name = hd.ANSWER_FILE[pt["target"]]
        if name not in cache:
            cache[name] = {}
            if name == "ARCHITECTURE.md":
                cache[name] = d["arch"]["answers"] if d["arch"] else {}
            else:
                try:
                    text = d["texts"].get(name)
                    cache[name] = hd.parse_answers(text, name) if text is not None else {}
                except hd.DocError as exc:
                    out.append(str(exc))
        if pt["id"] not in cache[name]:
            out.append(f"{pt['id']} ({pt['target']}) unanswered in {name}")
    return out


def _open_questions(brief):
    """The one refusal text for a parsed brief with open questions (check, lock, stage), None when it has none."""
    if not brief or not brief["open_questions"]:
        return None
    qs = "; ".join(re.sub(r"^\s*[-*]\s*", "", q) for q in brief["open_questions"])
    return f"BRIEF.md has open questions; settle them before it locks: {qs}"


def check_file(proj, name):
    """The format error of one document in its context (state, the other files), or None when it is fine."""
    if name not in DOC_NAMES:
        return "unknown file"
    if name == "DESIGN.md":
        try:
            text = _read(proj, name)
            if text is None:
                return "DESIGN.md does not exist yet"
            hd.check_summary(text, name)
        except hd.DocError as exc:
            return str(exc)
        return None
    d = docs(proj)
    if name in d["errors"]:
        return d["errors"][name]
    if name == "BRIEF.md":
        return _open_questions(d["brief"])
    state = _state_or_empty(proj)
    if name == "CRITIQUE.md":
        cm = current_milestone(proj, state, d["arch"]) if d["arch"] else None
        problem = _critique_problem(d, state, cm)[0]
        if problem:
            return problem
    return _revise_pending(d, state).get(name)  # M1: a revise chain is not OK on what it must change


def lock_brief(proj, now):
    """Lock BRIEF.md as it is now. Refuses (nothing written) on a format error or open questions. Re-locking a
    changed brief once an architecture exists records a revise (H20)."""
    try:
        raw = _read_raw(proj, "BRIEF.md")
        if raw is None:
            return False, "BRIEF.md does not exist yet"
        text = _decode(raw, "BRIEF.md")
    except hd.DocError as exc:
        return False, str(exc)
    try:
        brief = hd.parse_brief(text)
    except hd.DocError as exc:
        return False, str(exc)
    questions = _open_questions(brief)
    if questions:
        return False, questions
    try:
        state = load(proj)
    except StateError as exc:
        return False, f"cannot lock the brief: {exc}"
    digest = hashlib.sha256(raw).hexdigest()  # the bytes that were parsed
    prev = state.get("brief")
    state["brief"] = {"locked_at": now, "sha256": digest}
    d = docs(proj)
    arch = d["digests"].get("ARCHITECTURE.md")
    if isinstance(prev, dict) and prev.get("sha256") != digest and arch is not None:
        crit = d["critique"]
        state["revise"] = {"reason": "brief", "arch_sha256": arch, "plan_sha256": d["digests"].get("PLAN.md"),
                           "round": crit["rounds"][-1]["n"] if crit else 0}
    save(proj, state)
    return True, f"BRIEF.md locked (sha256 {digest[:12]})"


def reopen_brief(proj):
    """Mark the lock reopened (H20): approval is refused until /go locks the brief again."""
    state = load(proj)
    if isinstance(state.get("brief"), dict):
        state["brief"]["reopened"] = True
        save(proj, state)


LOCK_MINUTES = 30  # H6, H19: a lock older than this is stale
TIME_FMT = "%Y-%m-%dT%H:%M:%SZ"


def lock_path(proj):
    return os.path.join(proj, ".harness", "lock")


def lock_fresh(proj):
    """The project lock next.py writes while a chain runs: None when there is none, else {"stage", "at", "fresh"}.
    fresh = written under LOCK_MINUTES ago; an unreadable or old lock is stale ("?" for what it does not hold)."""
    try:
        with open(lock_path(proj), "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return None
    out = {"stage": "?", "at": "?", "fresh": False}
    try:
        lock = json.loads(raw)
        out["stage"], out["at"] = str(lock["stage"]), str(lock["at"])
        age = datetime.now(timezone.utc) - datetime.strptime(out["at"], TIME_FMT).replace(tzinfo=timezone.utc)
        out["fresh"] = timedelta(0) <= age < timedelta(minutes=LOCK_MINUTES)
    except (ValueError, KeyError, TypeError):
        pass
    return out


def _running(proj, retry_cmd):
    """The refusal text while a chain runs (I2), else None: approve and ship judge files a chain may rewrite."""
    lock = lock_fresh(proj)
    if lock and lock["fresh"]:
        return (f"a chain is running (stage {lock['stage']} since {lock['at']}): wait until it has finished, then "
                f"{retry_cmd}")
    return None


def approve(proj, now):
    """The human's approval. v3-mode projects keep v3's PLAN-only approval; otherwise BRIEF + ARCHITECTURE +
    PLAN (+ DESIGN) are approved together, and every missing item is named in one refusal."""
    running = _running(proj, f"/approve {os.path.basename(os.path.abspath(proj))}")
    if running:
        raise PlanError(running)
    try:
        state = load(proj)
        unreadable = False
    except StateError:
        state, unreadable = {}, True  # re-approving is how a corrupt state is repaired
    if is_v3_mode(proj, state) or (unreadable and not os.path.exists(os.path.join(proj, "ARCHITECTURE.md"))):
        return approve_v3(proj, now)
    slug = os.path.basename(os.path.abspath(proj))
    d = docs(proj)
    errors = d["errors"]
    missing = []

    def note(msg):
        if msg and msg not in missing:
            missing.append(msg)

    def err(name):  # a file skipped because an earlier one failed is reported through that earlier one
        return None if name in d["skipped"] else errors.get(name)

    brief, cur = state.get("brief"), d["digests"].get("BRIEF.md")
    if cur is None:
        note(errors.get("BRIEF.md", "BRIEF.md does not exist yet"))
    elif not isinstance(brief, dict):
        note(f"BRIEF.md is not locked (/go {slug} locks it)")
        note(err("BRIEF.md"))
    elif brief.get("reopened"):
        note(f"BRIEF.md is reopened (/go {slug} re-locks it)")
    elif brief.get("sha256") != cur:
        note(f"BRIEF.md changed since it was locked (/go {slug} re-locks it)")
    else:
        note(err("BRIEF.md"))
    note(err("ARCHITECTURE.md"))
    cm = current_milestone(proj, state, d["arch"]) if d["arch"] else None
    if d["arch"] and cm is None:
        note("every milestone is shipped: there is nothing left to approve")
    note(err("PLAN.md"))
    for m in _revise_pending(d, state).values():  # I1: a revise runs its course (H7, H20) before DECIDE
        note(m)
    msg, latest = _critique_problem(d, state, cm)
    note(msg)
    if latest and (cm is None or latest["milestone"] == cm):
        for m in _unanswered(proj, d, latest):
            note(m)
    if missing or d["plan_steps"] is None:
        raise PlanError("; ".join(missing) or "PLAN.md is not valid for the current milestone")

    steps = d["plan_steps"]
    done = {(s.get("milestone"), s.get("n"), s.get("title"), s.get("check")): s.get("done_at")
            for s in state.get("steps", []) if isinstance(s, dict) and s.get("done_at")}
    for s in steps:
        s["milestone"] = cm
        s["done_at"] = done.get((cm, s["n"], s["title"], s["check"]))  # H12: a new milestone inherits nothing
        s["attempts"] = 0
        s["last_failure"] = None
    digest = _approval_from(d["digests"])
    if state.get("approved_sha256") != digest:
        state.pop("review", None)  # P10: the old review judged other documents
    state["approved_sha256"] = digest
    state.pop("plan_sha256", None)  # v3's key; the plugin's plan gate asks approved(), which reads approved_sha256
    state["approved_at"] = now
    state["steps"] = steps
    state["fix_rounds"] = 0
    state["stage_attempts"] = {}
    state["revise"] = None
    state["critique_requested"] = None
    save(proj, state)
    return state


def approved(proj):
    """Is the current plan approved? v3 mode: PLAN.md is the recorded one. v4: the approval hash is the recorded
    one and the plan's milestone has not shipped (H24). Read-only; any problem reads as not approved."""
    try:
        state = load(proj)
    except StateError:
        return False
    if is_v3_mode(proj, state):
        digest = _file_sha(proj, "PLAN.md")
        return digest is not None and state.get("plan_sha256") == digest
    digest = approval_sha256(proj)
    if digest is None or state.get("approved_sha256") != digest:
        return False
    try:
        text = _read(proj, "PLAN.md")
    except hd.DocError:
        return False
    milestone = hd.plan_milestone(text) if text else None
    return milestone is not None and milestone not in (state.get("milestones_shipped") or [])


def ship(proj, now):
    """Record the current milestone as shipped, only when every recorded step is done and the review is a fresh
    SHIP. Returns (recorded, one-line message). v3 projects have no milestone."""
    try:
        state = load(proj)
    except StateError as exc:
        return False, f"NOT RECORDED: {exc}"
    if is_v3_mode(proj, state):
        return True, "v3 project: no milestone to record"
    slug = os.path.basename(os.path.abspath(proj))
    running = _running(proj, f"/ship {slug}")
    if running:
        return False, f"NOT RECORDED: {running}"
    d = docs(proj)
    if d["arch"] is None:
        return False, "NOT RECORDED: " + d["errors"].get("ARCHITECTURE.md", "ARCHITECTURE.md is not valid")
    cm = current_milestone(proj, state, d["arch"])
    if cm is None:
        return False, "NOT RECORDED: every milestone is already shipped"
    if not approved(proj):
        return False, (f"NOT RECORDED: {cm} has no current approval (a document changed since /approve, or it was "
                       f"never typed): /approve {slug}")
    steps = [s for s in state.get("steps", []) if isinstance(s, dict)]
    if not steps or any(s.get("milestone") != cm for s in steps):
        return False, f"NOT RECORDED: the recorded steps are not for {cm}: /approve {slug}"
    if state.get("critique_requested") is not None:  # I1: /critique at SHIP (H26) runs before the milestone ships
        problem, latest = _critique_problem(d, state, cm)
        if problem:
            return False, f"NOT RECORDED: a critique round you asked for has not run: /go {slug}"
        unanswered = _unanswered(proj, d, latest)
        if unanswered:
            return False, (f"NOT RECORDED: the critique round you asked for is not answered "
                           f"({'; '.join(unanswered)}): /go {slug}")
    loop = _loop(proj, state, slug, steps)
    if loop["phase"] != "SHIP":
        return False, f"NOT RECORDED: {loop['phase']}: {loop['reason']}"
    try:  # /ship's checklist item 2 needs this section: the same test as its awk (case-sensitive, at a line start)
        blind = re.search(r"^## Blind spots", _read(proj, "REVIEW.md") or "", re.M)
    except hd.DocError:
        blind = None
    if not blind:
        return False, (f"NOT RECORDED: REVIEW.md has no '## Blind spots' section (what the review could not check): "
                       f"/review {slug}, then /ship {slug}")
    state["milestones_shipped"] = [*(state.get("milestones_shipped") or []), cm]
    state["critique_requested"] = None
    save(proj, state)
    nxt = current_milestone(proj, state, d["arch"])
    if nxt is None:
        return True, f"MILESTONE SHIPPED: {cm}. All milestones shipped."
    return True, f"MILESTONE SHIPPED: {cm}. Next: /go {slug} plans {nxt}."


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


def _result(name, reason, step=None, done=0, total=0):
    return {"phase": name, "step": step, "done": done, "total": total, "reason": reason}


def _loop(proj, state, slug, steps):
    """The BUILD / STUCK / REVIEW / FIX / SHIP part of the phase table, on the recorded steps (v3 phase() and v4
    stage() share it; ship() asks it whether the milestone may be recorded)."""
    done = sum(1 for s in steps if s.get("done_at"))
    total = len(steps)

    cur = next((s for s in steps if not s.get("done_at")), None)
    if cur is not None:
        attempts = cur.get("attempts") or 0
        if attempts >= RETRY_LIMIT:
            return _result("STUCK", f"step {cur.get('n')} failed its check {attempts} times: fix it by hand, then "
                                   f"/approve {slug} (resets attempts), then /go {slug}; or edit PLAN.md, then "
                                   f"/approve {slug}", cur, done, total)
        return _result("BUILD", f"build step {cur.get('n')}: {cur.get('title')}", cur, done, total)

    rev = state.get("review")
    fresh = (isinstance(rev, dict) and rev.get("verdict") in VERDICTS
             and rev.get("tree_sha256") == tree_sha256(proj))
    if not fresh:
        return _result("REVIEW", "no fresh review: the reviewer writes REVIEW.md", None, done, total)
    if rev["verdict"] == "SHIP":
        return _result("SHIP", f"review is fresh and says SHIP: /ship {slug}", None, done, total)
    rounds = state.get("fix_rounds") or 0
    if rounds >= FIX_LIMIT:
        return _result("STUCK", f"{rounds} fix rounds used and the review still says {rev['verdict']}: "
                               "read REVIEW.md, you decide", None, done, total)
    return _result("FIX", f"review says {rev['verdict']}: the builder fixes the findings", None, done, total)


def phase(proj):
    """Where the project is, computed from files and state (spec 7.4, first match wins)."""
    slug = os.path.basename(os.path.abspath(proj))

    result = _result
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

    return _loop(proj, state, slug, steps)


# --- v4 stage table ------------------------------------------------------------------------

# the order is "later than" for the revise rules (spec H5)
STAGES = ("BRAINSTORM", "ARCHITECT", "REARCHITECT", "DESIGN", "PLAN", "CRITIQUE", "ANSWER", "DECIDE",
          "BUILD", "STUCK", "REVIEW", "FIX", "SHIP", "DONE")
CHAIN_STAGES = ("ARCHITECT", "REARCHITECT", "DESIGN", "PLAN", "CRITIQUE", "ANSWER")


def _stage_result(stage, reason, step=None, done=0, total=0, milestone=None, error=None, v3=False, at=None):
    return {"stage": stage, "step": step, "done": done, "total": total, "reason": reason,
            "milestone": milestone, "error": error, "v3": v3, "at": at}


def stage(proj):
    """Where a v4 project is (spec 7.1, first match wins), computed from files and state. A pure read: it
    never writes. `at` is the chain stage a STUCK stands on (rule 5, P20); `error` is the parser feedback."""
    slug = os.path.basename(os.path.abspath(proj))
    try:
        state = load(proj)
    except StateError as exc:
        if not os.path.exists(os.path.join(proj, "ARCHITECTURE.md")):  # P5: a v3 project keeps v3's answer
            old = phase(proj)
            return _stage_result(old["phase"], old["reason"], old["step"], old["done"], old["total"], v3=True)
        return _stage_result("STUCK", f"the state file is unreadable ({exc}): delete "
                                      f"mini-projects/{slug}/.harness/state.json by hand, then /go {slug}")
    if is_v3_mode(proj, state):
        old = phase(proj)
        return _stage_result(old["phase"], old["reason"], old["step"], old["done"], old["total"], v3=True)

    d = docs(proj)
    errors = d["errors"]

    # row 3: the brief lock
    brief, cur = state.get("brief"), d["digests"].get("BRIEF.md")
    if not isinstance(brief, dict) or brief.get("reopened") or brief.get("sha256") != cur:
        error = errors.get("BRIEF.md") or _open_questions(d["brief"])
        if error is None:
            error = (f"BRIEF.md is reopened (/go {slug} re-locks it)" if isinstance(brief, dict) and brief.get("reopened")
                     else f"BRIEF.md is not locked (/go {slug} locks it)" if not isinstance(brief, dict)
                     else f"BRIEF.md changed since it was locked (/go {slug} re-locks it)")
        return _stage_result("BRAINSTORM", f"the brief is not locked: settle BRIEF.md with the brainstormer, then "
                                           f"/go {slug} locks it", error=error)

    attempts = state.get("stage_attempts") or {}

    def chain(name, reason, cm, step=None, error=None, done=0, total=0):
        """A chain-stage result, or STUCK once the stage has failed STAGE_LIMIT times (rule 5, P20)."""
        if attempts.get(name, 0) >= STAGE_LIMIT:
            return _stage_result("STUCK", f"stage {name} failed twice: fix the cause (e.g. switch the agent's model in "
                                          f"opencode.json), then /go {slug} retry", step, done, total, cm, error, at=name)
        return _stage_result(name, reason, step, done, total, cm, error)

    # row 4: a valid architecture
    arch = d["arch"]
    if arch is None:
        return chain("ARCHITECT", f"no valid ARCHITECTURE.md: /go {slug} runs the architect chain", None,
                     error=errors.get("ARCHITECTURE.md", "ARCHITECTURE.md is not valid"))

    # row 5: nothing left to do
    cm = current_milestone(proj, state, arch)
    if cm is None:
        return _stage_result("DONE", "every milestone is shipped: the project is done")

    steps = [s for s in state.get("steps", []) if isinstance(s, dict) and s.get("milestone") == cm]
    done_n, total_n = sum(1 for s in steps if s.get("done_at")), len(steps)

    def out(name, reason, step=None, error=None):
        return chain(name, reason, cm, step, error, done_n, total_n)

    # row 6: REARCHITECT (a recorded revise, or a failed spike not yet recorded)
    revise, pending = state.get("revise"), _revise_pending(d, state)
    if revise:
        spike = revise.get("step")
        if "ARCHITECTURE.md" in pending:
            why = "the brief changed" if revise.get("reason") == "brief" else "a spike failed"
            return out("REARCHITECT", f"{why}: /go {slug} lets the architect revise ARCHITECTURE.md",
                       next((s for s in steps if s.get("n") == spike), None) if spike else None,
                       pending["ARCHITECTURE.md"])
    else:
        failed = next((s for s in steps if s.get("proves") and (s.get("attempts") or 0) >= RETRY_LIMIT
                       and not s.get("done_at")), None)
        if failed is not None:
            return out("REARCHITECT", f"the spike for {failed['proves']} (step {failed['n']}) failed "
                                      f"{failed.get('attempts')} times: /go {slug} lets the architect revise "
                                      "ARCHITECTURE.md", failed, failed.get("last_failure"))

    # row 7: DESIGN, only once a designer agent exists in this workshop
    workshop = os.path.dirname(os.path.dirname(os.path.abspath(proj)))
    if (d["brief"]["ui"] and os.path.exists(os.path.join(workshop, ".opencode", "agents", "designer.md"))
            and "DESIGN.md" not in d["texts"]):
        return out("DESIGN", f"the project has a UI and no DESIGN.md: /go {slug} runs the designer",
                   error="DESIGN.md does not exist yet")

    # row 8: PLAN
    if d["plan_steps"] is None or "PLAN.md" in pending:
        error = errors.get("PLAN.md") or pending.get("PLAN.md") or "PLAN.md is not valid for the current milestone"
        return out("PLAN", f"/go {slug} runs the planner for {cm}", error=error)

    # row 9: CRITIQUE
    problem, latest = _critique_problem(d, state, cm)
    problem = problem or pending.get("CRITIQUE.md")
    if problem is not None:
        return out("CRITIQUE", f"/go {slug} runs the critic for {cm}", error=problem)

    # row 10: ANSWER
    unanswered = _unanswered(proj, d, latest)
    if unanswered:
        return out("ANSWER", f"/go {slug} has the authors answer the serious points of round {latest['n']}",
                   error="; ".join(unanswered))

    # row 11: DECIDE
    if not approved(proj):
        return _stage_result("DECIDE", f"read the approval digest (/status {slug}), then /approve {slug} or "
                                       f"/critique {slug}", None, done_n, total_n, cm)

    # row 12: the build loop on the recorded steps
    if not steps:
        return _stage_result("DECIDE", f"no steps recorded for {cm}: /approve {slug} again", None, 0, 0, cm)
    res = _loop(proj, state, slug, steps)
    return _stage_result(res["phase"], res["reason"], res["step"], res["done"], res["total"], cm)


# --- CLI ----------------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3 or argv[1] not in ("approve", "ship", "approved", "tree", "review"):
        print("usage: harness_state.py approve|ship|approved|tree|review <project-dir>", file=sys.stderr)
        return 2
    cmd, proj = argv[1], os.path.abspath(argv[2])
    if cmd == "tree":
        print(tree_sha256(proj))
        return 0
    if cmd == "review":
        print(json.dumps({"tree_sha256": tree_sha256(proj), "verdict": review_verdict(proj)}))
        return 0
    if cmd == "approved":
        print("yes" if approved(proj) else "no")
        return 0
    # opencode marks every agent shell with AGENT=1 and OPENCODE_SESSION_ID; a command template has neither
    if os.environ.get("AGENT") == "1" or os.environ.get("OPENCODE_SESSION_ID"):
        what = ("approval comes only from the human typing /approve <slug>" if cmd == "approve"
                else "shipping comes only from the human typing /ship <slug>")
        print(f"REFUSED: {what}, never from an agent shell.", file=sys.stderr)
        return 3
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = os.path.basename(proj)
    if cmd == "ship":
        # P17: only a project of THIS workshop (a direct child of its mini-projects/, never _template)
        proj = os.path.realpath(proj)
        workshop = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        slug = os.path.basename(proj)
        try:  # samefile, not a string compare: this workshop is reached as .../Projects/x and .../projects/x
            direct = os.path.samefile(os.path.dirname(proj), os.path.join(workshop, "mini-projects"))
        except OSError:
            direct = False
        if not direct or slug.startswith("_") or not os.path.isdir(proj):
            print("REFUSED: ship works on a project directly under this workshop's mini-projects/.")
            return 1
        try:
            ok, msg = ship(proj, now)
        except OSError as exc:
            print(f"REFUSED: cannot write state: {exc}")
            return 1
        print(msg)
        return 0 if ok else 1
    try:
        state = approve(proj, now)
    except PlanError as exc:
        print(f"REFUSED: {exc}")
        return 1
    except OSError as exc:
        print(f"REFUSED: cannot write state: {exc}")
        return 1
    if "approved_sha256" in state:
        design = " + DESIGN" if os.path.exists(os.path.join(proj, "DESIGN.md")) else ""
        print(f"APPROVED: mini-projects/{slug} {state['steps'][0]['milestone']} (BRIEF + ARCHITECTURE{design} + PLAN, "
              f"sha256 {state['approved_sha256'][:12]}, {len(state['steps'])} steps). "
              "Any edit to these files revokes this; /approve again after a change.")
        return 0
    print(f"APPROVED: mini-projects/{slug}/PLAN.md (sha256 {state['plan_sha256'][:12]}, {len(state['steps'])} steps). "
          "Any edit to PLAN.md revokes this; /approve again after a change.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

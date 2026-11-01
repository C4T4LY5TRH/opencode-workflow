#!/usr/bin/env python3
"""Recorded project state for the harness (brief + architecture + plan; stdlib only).

Library: parse_plan, load, save, approve, approved, ship, lock_brief, lock_fresh, docs, check_file,
tree_sha256, review_verdict, stage.
CLI (the writing verbs run from command templates only, never from an agent shell):
  harness_state.py approve <project-dir>   record the human's approval (BRIEF + ARCHITECTURE + PLAN)
  harness_state.py ship <project-dir>      record the finished milestone
  harness_state.py approved <project-dir>  print yes/no: is the current plan approved (read-only)
  harness_state.py tree <project-dir>      print the project's tree hash
  harness_state.py review <project-dir>    print {"tree_sha256", "verdict"} for REVIEW.md as it is now (read-only)

State lives in <project>/.harness/state.json; its shape is spec section 7. Only trusted code writes it.
"""
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.dont_write_bytecode = True  # the import below must not leave scripts/__pycache__ behind
import harness_docs as hd
from harness_docs import PlanError, parse_plan  # noqa: F401  (re-exported for hs.parse_plan / hs.PlanError)

RETRY_LIMIT = 2  # failed checks per step before STUCK
FIX_LIMIT = 2    # review -> fix rounds before STUCK
STAGE_LIMIT = 2  # failed chains per automatic stage before STUCK (v4)
MAX_PARALLEL = 3     # builder/researcher/qa calls in one batch
COST_CAP_USD = 10    # default milestone cost cap
PORT_BASE = 4800     # a project's preview port is PORT_BASE + its number
AUTOPILOT_STAGES = ("TESTS", "BUILD", "REVIEW", "FIX", "VERIFY")  # the stages the plugin may chain
# README.md is product code (it is in the tree hash); QA.md and VISUAL.md are agents' reports
DOC_FILES = {"PLAN.md", "REVIEW.md", "CRITIQUE.md", "BUGHUNT.md", "NOTES.md", "LEARNINGS.md",
             "BRIEF.md", "AGENTS.md", "ARCHITECTURE.md", "BRAINSTORM.md", "DESIGN.md", "QA.md", "VISUAL.md"}
DOC_DIRS = ("RESEARCH/", ".harness/", "requests/", "design/shots/")
WALK_SKIP = {".git", "node_modules"}
VERDICTS = ("SHIP", "FIX FIRST", "REWORK")
# T7-R9: with every step done no failing run can be recorded any more, so a test change then is the human's call
TESTS_CHANGED = ("acceptance tests or their run command changed after the build: revert them, or /go retry to accept "
                 "them as they are")
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


def turn_cap(total):
    """Autopilot turns allowed for a milestone of `total` steps."""
    return 3 * total + 10


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


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
        need(s.get("after") is None or isinstance(s["after"], list), "step after")
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
        need(rv.get("reason") in ("spike", "brief", "design"), "revise reason")
        need(rv.get("step") is None or _is_int(rv["step"]), "revise step")
        need(isinstance(rv.get("arch_sha256"), str), "revise arch_sha256")
        need(rv.get("plan_sha256") is None or isinstance(rv["plan_sha256"], str), "revise plan_sha256")
        need(_is_int(rv.get("round")), "revise round")
    rev = data.get("review")
    need(rev is None or isinstance(rev, dict), "review")
    for key in ("tree_sha256", "verdict", "at"):
        need(rev is None or rev.get(key) is None or isinstance(rev[key], str), f"review {key}")
    ap = data.get("autopilot")
    need(ap is None or isinstance(ap, dict), "autopilot")
    if ap is not None:
        for key in ("on", "continue"):
            need(ap.get(key) is None or isinstance(ap[key], bool), f"autopilot {key}")
        need(ap.get("milestone") is None or isinstance(ap["milestone"], str), "autopilot milestone")
        need(ap.get("turns") is None or _is_int(ap["turns"]), "autopilot turns")
    cost = data.get("cost")
    need(cost is None or isinstance(cost, dict), "cost")
    if cost is not None:
        need(cost.get("milestone") is None or isinstance(cost["milestone"], str), "cost milestone")
        for key in ("usd", "project_usd"):
            need(cost.get(key) is None or _is_num(cost[key]), f"cost {key}")
    need(data.get("cost_cap_usd") is None or _is_num(data["cost_cap_usd"]), "cost_cap_usd")
    need(data.get("port") is None or _is_int(data["port"]), "port")
    sf = data.get("scope_failure")
    need(sf is None or isinstance(sf, dict), "scope_failure")
    if sf is not None:
        need(isinstance(sf.get("paths"), list) and all(isinstance(p, str) for p in sf["paths"]), "scope_failure paths")
        need(sf.get("stage") is None or isinstance(sf["stage"], str), "scope_failure stage")
        sfs = sf.get("steps")
        need(isinstance(sfs, dict) and all(
            isinstance(v, dict) and _is_int(v.get("attempts")) and (v.get("done_at") is None or isinstance(v["done_at"], str))
            and (v.get("last_failure") is None or isinstance(v["last_failure"], str)) for v in sfs.values()),
            "scope_failure steps")
    need(data.get("stop_pending") is None or isinstance(data["stop_pending"], bool), "stop_pending")
    need(data.get("design_objection") is None or _is_int(data["design_objection"]), "design_objection")
    qa = data.get("qa")
    need(qa is None or isinstance(qa, dict), "qa")
    if qa is not None:
        for key in ("tests_sha256", "failed_first_at", "verdict", "run", "milestone"):
            need(qa.get(key) is None or isinstance(qa[key], str), f"qa {key}")
    ver = data.get("verify")
    need(ver is None or isinstance(ver, dict), "verify")
    if ver is not None:
        for key in ("tree_sha256", "milestone"):
            need(ver.get(key) is None or isinstance(ver[key], str), f"verify {key}")
        chk = ver.get("checks")
        need(chk is None or (isinstance(chk, dict) and all(_is_int(v) for v in chk.values())), "verify checks")
        need(ver.get("acceptance") is None or _is_int(ver["acceptance"]), "verify acceptance")
    vis = data.get("visual")
    need(vis is None or isinstance(vis, dict), "visual")
    if vis is not None:
        for key in ("verdict", "tree_sha256", "milestone"):
            need(vis.get(key) is None or isinstance(vis[key], str), f"visual {key}")


def save(proj, state):
    path = _state_path(proj)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:  # keep the last good copy: only a file that loads (parses, right shape) is copied, atomically
        with open(path, "r", encoding="utf-8") as fh:
            old = fh.read()
        data = json.loads(old)
        if not isinstance(data, dict):
            raise StateError("not an object")
        _check_shape(data)
        with open(path + ".bak.tmp", "w", encoding="utf-8") as fh:
            fh.write(old)
        os.replace(path + ".bak.tmp", path + ".bak")
    except (OSError, ValueError):  # StateError is a ValueError
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


V3_REFUSAL = "v3 project: not supported by v4; start it again with /new"


def is_v3_state(state):
    """A v3 project: a recorded plan hash and no v4 approval hash."""
    return "plan_sha256" in state and "approved_sha256" not in state


def _bak_loads(proj):
    """Does state.json.bak load (parses, right shape)? Only then is it worth offering as the way back."""
    try:
        with open(_state_path(proj) + ".bak", "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return False
        _check_shape(data)
        return True
    except (OSError, ValueError):
        return False


def unreadable_reason(proj):
    """The one STUCK message for an unreadable state.json (spec 8, M5); the restore half only when .bak loads."""
    slug = os.path.basename(os.path.abspath(proj))
    p = f"mini-projects/{slug}/.harness/state.json"
    restore = f"restore the last good copy (cp {p}.bak {p}) or " if _bak_loads(proj) else ""
    return f"state unreadable: {restore}delete .harness/state.json, then /go {slug}"


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


def _mockup_shas(proj, design_text):
    """{design/mockups/<name>.html: sha256 or None} for each SCREENS entry of a parseable DESIGN.md, in SCREENS
    order; {} when DESIGN.md does not parse (check_file reports that)."""
    try:
        screens = hd.parse_design(design_text)["screens"]
    except hd.DocError:
        return {}
    return {path: _file_sha(proj, path) for _, path in screens}


def approval_sha256(proj):
    """The one approval hash (spec H1): BRIEF, ARCHITECTURE, DESIGN (only if it exists) and each of its SCREENS
    mockups, PLAN. None when a required file is missing."""
    digests = {n: _file_sha(proj, n) for n in ("BRIEF.md", "ARCHITECTURE.md", "DESIGN.md", "PLAN.md")}
    try:
        design = _read(proj, "DESIGN.md")
    except hd.DocError:
        design = None
    digests.update(_mockup_shas(proj, design) if design else {})
    return _approval_from(digests)


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
        if name == "DESIGN.md":  # its mockups follow it, in SCREENS order (insertion order of the digests)
            for path, sha in digests.items():
                if path.startswith("design/mockups/"):
                    if sha is None:
                        return None
                    h.update(f"{path}\0{sha}\n".encode("utf-8"))
    return h.hexdigest()


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
    if "DESIGN.md" in texts:
        out["digests"].update(_mockup_shas(proj, texts["DESIGN.md"]))

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
                texts["ARCHITECTURE.md"], {f["id"] for f in feats}, {f["id"] for f in feats if f["priority"] == "MUST"},
                ui=out["brief"]["ui"]))
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


def design_objection(d, state):
    """The designer's reason when DESIGN.md objects to the stack and the architect has not seen it yet
    (state.design_objection unset), else None. Needs a valid architecture; DESIGN.md is parsed from d."""
    if d["arch"] is None or state.get("design_objection") is not None or "DESIGN.md" not in d["texts"]:
        return None
    try:
        fit = hd.parse_design(d["texts"]["DESIGN.md"])
    except hd.DocError:
        return None
    return fit["object_reason"] if fit["stack_fit"] == "object" else None


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
            design = hd.parse_design(text)
        except hd.DocError as exc:
            return str(exc)
        for _, path in design["screens"]:
            try:
                mock = _read(proj, path)
            except hd.DocError as exc:
                return str(exc)
            if mock is None:
                return f"DESIGN.md: mockup {path} does not exist yet"
            err = hd.check_mockup(mock)
            if err:
                return f"{path}: {err}"
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
    pending_spike = (state.get("revise") or {}).get("reason") == "spike"  # M9: never overwrite a failed spike's revise
    if isinstance(prev, dict) and prev.get("sha256") != digest and arch is not None and not pending_spike:
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
    """The project lock next.py writes while a chain runs: None when there is none, else {"stage", "at", "fresh",
    "unreadable"}. fresh = written under LOCK_MINUTES ago. A lock that cannot be decoded or parsed is a crash
    leftover: unreadable (not fresh, "?" for what it does not hold)."""
    try:
        with open(lock_path(proj), "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    out = {"stage": "?", "at": "?", "fresh": False, "unreadable": True}
    try:  # strict decoding: a lock with bytes that are not UTF-8 is a crash leftover, not a lock to trust
        lock = json.loads(raw.decode("utf-8"))
        stage, at = str(lock["stage"]), str(lock["at"])
        age = datetime.now(timezone.utc) - datetime.strptime(at, TIME_FMT).replace(tzinfo=timezone.utc)
    except (ValueError, KeyError, TypeError):  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        return out
    out.update(stage=stage, at=at, unreadable=False, fresh=timedelta(0) <= age < timedelta(minutes=LOCK_MINUTES))
    return out


LOCK_CRASH = "a chain lock is unreadable (crash leftover): /go retry clears it"
WAY_OUT = re.compile(r"/(?:go|approve|ship|new|status|review|critique|brainstorm|stop)\b[^.;]*$")


def _then(msg, cmd):
    """`msg` ending with the command that gets out (spec 6.4), added unless the message already ends with one."""
    return msg if WAY_OUT.search(msg) else f"{msg}. Next: {cmd}"


def _running(proj, retry_cmd):
    """The refusal text while a chain runs (I2), else None: approve and ship judge files a chain may rewrite."""
    lock = lock_fresh(proj)
    if lock and lock["unreadable"]:
        return LOCK_CRASH
    if lock and lock["fresh"]:
        return (f"a chain is running (stage {lock['stage']} since {lock['at']}): wait until it has finished, then "
                f"{retry_cmd}")
    return None


def approve(proj, now):
    """The human's approval: BRIEF + ARCHITECTURE + PLAN (+ DESIGN) are approved together, and every missing item
    is named in one refusal. An unreadable state or a v3 project is refused with its one message; nothing is written."""
    running = _running(proj, f"/approve {os.path.basename(os.path.abspath(proj))}")
    if running:
        raise PlanError(running)
    try:
        state = load(proj)
    except StateError:
        raise PlanError(unreadable_reason(proj))
    if is_v3_state(state):
        raise PlanError(V3_REFUSAL)
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
        out = "every milestone is shipped" in "; ".join(missing)
        raise PlanError(_then("; ".join(missing) or "PLAN.md is not valid for the current milestone",
                              f"/status {slug}" if out else f"/go {slug}"))

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
    state["approved_at"] = now
    state["steps"] = steps
    state["fix_rounds"] = 0
    state["stage_attempts"] = {}
    state["revise"] = None
    state["critique_requested"] = None
    _drop_turn_record(proj, state)
    save(proj, state)
    return state


def _drop_turn_record(proj, state):
    """A new approval or a shipped milestone ends the turn record: no file snapshot, no scope failure to give back."""
    state.pop("scope_failure", None)
    try:
        os.remove(os.path.join(proj, ".harness", "snapshot.json"))
    except OSError:
        pass


def _archive_requests(proj, milestone):
    """Move requests/step<n>.md and RESEARCH/step<n>.md under .harness/archive/m<N>/ (never delete), so a request of
    this milestone never applies to step n of the next one. A move that fails is skipped: the record is already kept."""
    for folder in ("requests", "RESEARCH"):
        try:
            names = sorted(os.listdir(os.path.join(proj, folder)))
        except OSError:
            continue
        for name in names:
            src = os.path.join(proj, folder, name)
            if not re.fullmatch(r"step\d+\.md", name) or not os.path.isfile(src):
                continue
            try:
                dest = os.path.join(proj, ".harness", "archive", milestone.lower(), folder)
                os.makedirs(dest, exist_ok=True)
                os.replace(src, os.path.join(dest, name))
            except OSError:
                pass


def approved(proj):
    """Is the current plan approved? The approval hash is the recorded
    one and the plan's milestone has not shipped (H24). Read-only; any problem reads as not approved."""
    try:
        state = load(proj)
    except StateError:
        return False
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
    SHIP. Returns (recorded, one-line message)."""
    try:
        state = load(proj)
    except StateError:
        return False, f"NOT RECORDED: {unreadable_reason(proj)}"
    if is_v3_state(state):
        return False, f"NOT RECORDED: {V3_REFUSAL}"
    slug = os.path.basename(os.path.abspath(proj))
    running = _running(proj, f"/ship {slug}")
    if running:
        return False, f"NOT RECORDED: {running}"
    d = docs(proj)
    if d["arch"] is None:
        return False, _then("NOT RECORDED: " + d["errors"].get("ARCHITECTURE.md", "ARCHITECTURE.md is not valid"),
                            f"/go {slug}")
    cm = current_milestone(proj, state, d["arch"])
    if cm is None:
        return False, _then("NOT RECORDED: every milestone is already shipped", f"/status {slug}")
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
    now_stage = stage(proj)  # one source of truth: record only when the stage table says SHIP
    if now_stage["stage"] != "SHIP":
        return False, _then(f"NOT RECORDED: stage is {now_stage['stage']}: {now_stage['reason']}", f"/go {slug}")
    try:  # /ship's checklist item 2 needs this section: the same test as its awk (case-sensitive, at a line start)
        blind = re.search(r"^## Blind spots", _read(proj, "REVIEW.md") or "", re.M)
    except hd.DocError:
        blind = None
    if not blind:
        return False, (f"NOT RECORDED: REVIEW.md has no '## Blind spots' section (what the review could not check): "
                       f"/review {slug}, then /ship {slug}")
    state["milestones_shipped"] = [*(state.get("milestones_shipped") or []), cm]
    state["critique_requested"] = None
    _drop_turn_record(proj, state)
    save(proj, state)
    _archive_requests(proj, cm)
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


def _hash_files(proj, keep):
    """sha256 over the project files whose relative path passes keep(rel), stable for equal content."""
    rels = _git_files(proj)
    if rels is None:
        rels = _walk_files(proj)
    h = hashlib.sha256()
    for rel in sorted(set(rels)):
        if not keep(rel):
            continue
        try:
            with open(os.path.join(proj, rel), "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            continue  # deleted but still listed, a directory, a broken symlink
        h.update(f"{rel}\0{digest}\n".encode("utf-8", "surrogateescape"))
    return h.hexdigest()


def tree_sha256(proj):
    """sha256 over the project's code files (docs and .harness/ excluded), stable for equal content."""
    return _hash_files(proj, lambda rel: not _is_doc(rel))


def tests_sha256(proj):
    """sha256 over the acceptance tests (tests/acceptance/), the same scheme as tree_sha256."""
    return _hash_files(proj, lambda rel: rel.lower().startswith("tests/acceptance/"))


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


# --- v4 stage table ------------------------------------------------------------------------

# the order is "later than" for the revise rules (spec H5)
STAGES = ("BRAINSTORM", "ARCHITECT", "REARCHITECT", "DESIGN", "PLAN", "CRITIQUE", "ANSWER", "DECIDE",
          "TESTS", "BUILD", "STUCK", "VERIFY", "REVIEW", "FIX", "SHIP", "DONE")
CHAIN_STAGES = ("ARCHITECT", "REARCHITECT", "DESIGN", "PLAN", "CRITIQUE", "ANSWER")


def _stage_result(stage, reason, step=None, done=0, total=0, milestone=None, error=None, at=None, batch=None):
    return {"stage": stage, "step": step, "done": done, "total": total, "reason": reason,
            "milestone": milestone, "error": error, "at": at, "batch": batch or []}


def stage(proj):
    """Where a v4 project is (spec 7.1, first match wins), computed from files and state. A pure read: it
    never writes. `at` is the chain stage a STUCK stands on (rule 5, P20); `error` is the parser feedback."""
    slug = os.path.basename(os.path.abspath(proj))
    try:
        state = load(proj)
    except StateError:
        return _stage_result("STUCK", unreadable_reason(proj))
    if is_v3_state(state):
        return _stage_result("STUCK", V3_REFUSAL)

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
                                          f"opencode.json), then /go retry", step, done, total, cm, error, at=name)
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
            why = {"brief": "the brief changed", "design": "the designer disagrees with the stack"}.get(
                revise.get("reason"), "a spike failed")
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
    if d["brief"]["ui"] and os.path.exists(os.path.join(workshop, ".opencode", "agents", "designer.md")):
        if "DESIGN.md" not in d["texts"]:
            return out("DESIGN", f"the project has a UI and no DESIGN.md: /go {slug} runs the designer",
                       error="DESIGN.md does not exist yet")
        bad = check_file(proj, "DESIGN.md")
        if bad:
            return out("DESIGN", f"DESIGN.md is not valid: /go {slug} runs the designer", error=bad)
        reason = design_objection(d, state)
        if reason:  # the first object goes back to the architect once; /go records revise + design_objection
            return out("ARCHITECT", f"the designer disagrees with the stack: /go {slug} sends it to the architect "
                                    f"once ({reason})", error=reason)

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
    res = _post_approval(proj, state, d, slug, cm, steps)
    n = attempts.get(res["stage"], 0)
    if res["stage"] in AUTOPILOT_STAGES and n >= STAGE_LIMIT:  # turns of this stage kept changing other files
        fail = state.get("scope_failure") or {}
        why = (f": files changed outside the turn's scope: {', '.join(fail['paths'][:10])}"
               if fail.get("stage") == res["stage"] and fail.get("paths") else "")
        return _stage_result("STUCK", f"stage {res['stage']} failed {n} times{why}. Fix the cause, then /go retry",
                             res["step"], done_n, total_n, cm)
    return res


# --- v4 build stages (spec 3.1 rows 9a-9l) ---------------------------------------------------

def ready_steps(steps, open_steps, limit=MAX_PARALLEL):
    """Steps that may start now, in step order: not done, every `after` done (default: the previous step), not held
    by an open request, and sharing no path or folder with a step already picked. A step whose `after` is not done
    blocks only itself."""
    done = {s.get("n") for s in steps if s.get("done_at")}
    picked, taken = [], []
    for i, s in enumerate(steps):
        if len(picked) >= limit:
            break
        if s.get("done_at") or s.get("n") in open_steps:
            continue
        after = s.get("after")
        need = [steps[i - 1].get("n")] if after is None and i > 0 else (after or [])
        if any(n not in done for n in need):
            continue
        files = [f for f in (s.get("files") or []) if isinstance(f, str)]
        if any(hd.paths_overlap(f, g) for f in files for g in taken):
            continue
        picked.append(s)
        taken.extend(files)
    return picked


def requests(proj, state):
    """Open builder requests of the not-done steps: {"step", "kind": RESEARCH | TEST-WRONG | STUCK, ...} (spec 5.6).
    RESEARCH stays open until RESEARCH/step<n>.md exists; TEST-WRONG until QA.md logs a revision for step<n>; a
    second TEST-WRONG for a test already revised is STUCK (for the human), as is a request file that does not parse."""
    try:
        qa_rev = hd.parse_qa(_read(proj, "QA.md") or "")["revisions"]
    except hd.DocError:
        qa_rev = []
    out = []
    for s in state.get("steps", []):
        if not isinstance(s, dict) or s.get("done_at"):
            continue
        n = s.get("n")
        try:
            text = _read(proj, f"requests/step{n}.md")
            if text is None:
                continue
            req = hd.parse_request(text)
        except (hd.DocError, hd.PlanError) as exc:
            out.append({"step": n, "kind": "STUCK", "why": str(exc)})
            continue
        if req["kind"] == "RESEARCH":
            if not os.path.exists(os.path.join(proj, "RESEARCH", f"step{n}.md")):
                out.append({"step": n, "kind": "RESEARCH", "question": req["question"]})
            continue
        test = hd.norm_path(req["test"])
        if any(r["step"] == n for r in qa_rev):
            continue
        if any(hd.norm_path(r["test"]) == test for r in qa_rev):
            out.append({"step": n, "kind": "STUCK", "test": req["test"],
                        "why": f"{req['test']} was already revised once and the builder still says it is wrong"})
        else:
            out.append({"step": n, "kind": "TEST-WRONG", "test": req["test"], "why": req["why"]})
    return out


def _of(state, key, cm):
    """The qa, verify or visual record of milestone cm, else {}: another milestone's record counts as absent (T7-R8),
    so every milestone fails its own acceptance tests first and is verified on its own."""
    rec = state.get(key)
    return rec if isinstance(rec, dict) and rec.get("milestone") == cm else {}


def _must(d, cm):
    """The MUST feature ids milestone cm covers: what its acceptance tests test (none: no TESTS, no acceptance run)."""
    covers = next((m["covers"] for m in d["arch"]["milestones"] if m["id"] == cm), [])
    return {f["id"] for f in d["brief"]["features"] if f["priority"] == "MUST"} & set(covers)


def _verify_gap(state, steps, tree, ui, cm, acceptance=True):
    """(kind, reason): "ok", "pending" (a result not recorded for this tree) or "failed" (a recorded failure).
    A failure outranks a gap; the reason names the first one of that kind. `acceptance`: the milestone has tests."""
    ver = _of(state, "verify", cm)
    if ver.get("tree_sha256") != tree:
        return "pending", "verify has not run for the current tree"
    gaps = []
    checks = ver.get("checks") or {}
    for s in steps:
        code = checks.get(str(s.get("n")))
        if code is None:
            gaps.append(("pending", f"step {s.get('n')} check was not run in VERIFY"))
        elif code != 0:
            gaps.append(("failed", f"step {s.get('n')} check exited {code} in VERIFY"))
    acc = ver.get("acceptance")
    if acc is None and acceptance:
        gaps.append(("pending", "the acceptance run was not recorded"))
    elif acc not in (None, 0):
        gaps.append(("failed", f"the acceptance run exited {acc}"))
    verdict = _of(state, "qa", cm).get("verdict")
    if verdict is None:
        gaps.append(("pending", "the QA verdict was not recorded"))
    elif verdict != "PASS":
        gaps.append(("failed", f"the QA verdict is {verdict}"))
    if ui:
        vis = _of(state, "visual", cm)
        if vis.get("tree_sha256") != tree or vis.get("verdict") is None:
            gaps.append(("pending", "the VISUAL verdict was not recorded for the current tree"))
        elif vis["verdict"] != "MATCH":
            gaps.append(("failed", f"the VISUAL verdict is {vis['verdict']}"))
    for kind in ("failed", "pending"):
        hit = next((g for g in gaps if g[0] == kind), None)
        if hit:
            return hit
    return "ok", "verify is fresh"


def verify_fresh(proj, state, ui=None):
    """(True, ...) when the recorded VERIFY covers the current tree: every step check and the acceptance run exited 0,
    the QA verdict is PASS and (ui projects) the VISUAL verdict is MATCH. Otherwise (False, the first gap)."""
    d = docs(proj)
    if ui is None:
        ui = bool(d["brief"] and d["brief"]["ui"])
    steps = [s for s in state.get("steps", []) if isinstance(s, dict)]
    cm = steps[0].get("milestone") if steps else None  # the recorded steps are the approved milestone's
    acceptance = not (d["brief"] and d["arch"]) or bool(_must(d, cm))  # unreadable docs: the run is still asked for
    kind, why = _verify_gap(state, steps, tree_sha256(proj), ui, cm, acceptance)
    return kind == "ok", why


def _post_approval(proj, state, d, slug, cm, steps):
    """Rows 9c-9l on the recorded steps of milestone cm (9a and 9b are rows 1-6 of stage())."""
    done_n, total_n = sum(1 for s in steps if s.get("done_at")), len(steps)
    pend = [s for s in steps if not s.get("done_at")]

    def res(name, reason, step=None, batch=None, error=None):
        return _stage_result(name, reason, step, done_n, total_n, cm, error, batch=batch)

    tree = tree_sha256(proj)
    arch, ui, must = d["arch"], d["brief"]["ui"], _must(d, cm)
    rev = state.get("review")
    rev_fresh = (isinstance(rev, dict) and rev.get("verdict") in VERDICTS and rev.get("tree_sha256") == tree)
    vkind, vwhy = _verify_gap(state, steps, tree, ui, cm, bool(must))
    reqs = requests(proj, state)
    rounds = state.get("fix_rounds") or 0

    cause = None  # why a fix round is due (only once every step is done)
    if not pend:
        if rev_fresh and rev["verdict"] != "SHIP":
            cause = f"review says {rev['verdict']}"
        elif vkind == "failed":
            cause = f"verify failed: {vwhy}"

    # 9c: a limit was hit
    cur = next((s for s in pend if (s.get("attempts") or 0) >= RETRY_LIMIT), None)
    if cur is not None:
        what = ("wrote outside its files" if str(cur.get("last_failure") or "").startswith("exit scope:")
                else "failed its check")
        return res("STUCK", f"step {cur.get('n')} {what} {cur.get('attempts')} times: fix it by hand, then "
                            f"/approve {slug} (resets attempts), then /go {slug}; or edit PLAN.md, then "
                            f"/approve {slug}", cur)
    stuck = next((r for r in reqs if r["kind"] == "STUCK"), None)
    if stuck is not None:
        return res("STUCK", f"step {stuck['step']}: {stuck['why']}: read requests/step{stuck['step']}.md and fix the "
                            f"test or the step by hand, then /go {slug}",
                   next((s for s in steps if s.get("n") == stuck["step"]), None))
    if cause is not None and rounds >= FIX_LIMIT:
        return res("STUCK", f"{rounds} fix rounds used and still: {cause}: read REVIEW.md and the verify output, "
                            "you decide")

    # 9d: the spike, alone, before any test is written
    spike = steps[0]
    if cm == arch["milestones"][0]["id"] and spike.get("proves") and not spike.get("done_at"):
        mine = [{"kind": "research" if r["kind"] == "RESEARCH" else "testfix", "n": r["step"]}
                for r in reqs if r["step"] == spike.get("n")]
        return res("BUILD", f"build the spike for {spike['proves']} (step {spike.get('n')}) before any test is written",
                   spike, mine or [{"kind": "step", "n": spike.get("n")}])

    # 9e: acceptance tests (only when the milestone covers a MUST feature)
    if must:
        qa = _of(state, "qa", cm)
        try:
            text = _read(proj, "QA.md")
            problem = "QA.md does not exist yet" if text is None else hd.check_qa(text, must)
        except hd.DocError as exc:
            problem = str(exc)
        if problem:
            return res("TESTS", f"{cm} has no valid QA.md: qa writes the acceptance tests", error=problem)
        if not qa.get("failed_first_at"):
            return res("TESTS", "no recorded failing run of the acceptance tests: qa runs them once")
        run_moved = qa.get("run") != " ".join(hd.parse_qa(text)["run"].split())  # the plugin pins the command it saw fail
        tests_moved = qa.get("tests_sha256") != tests_sha256(proj) and not any(r["kind"] == "TEST-WRONG" for r in reqs)
        if (run_moved or tests_moved) and not pend:
            return res("STUCK", TESTS_CHANGED)
        if run_moved:
            return res("TESTS", "the acceptance command changed since the recorded run: qa runs it once")
        if tests_moved:
            return res("TESTS", "the acceptance tests changed since the recorded run: qa runs them once")

    # 9f + 9g: requests first, then ready steps, at most MAX_PARALLEL in all
    items = [{"kind": "research" if r["kind"] == "RESEARCH" else "testfix", "n": r["step"]}
             for r in reqs][:MAX_PARALLEL]
    # a testfix may change the tests every step is judged by: it never shares a batch with builders
    ready = [] if any(i["kind"] == "testfix" for i in items) else ready_steps(
        steps, {r["step"] for r in reqs}, MAX_PARALLEL - len(items))
    batch = items + [{"kind": "step", "n": s.get("n")} for s in ready]
    if batch:
        first = ready[0] if ready else next((s for s in steps if s.get("n") == items[0]["n"]), None)
        return res("BUILD", "batch: " + ", ".join(f"{i['kind']} {i['n']}" for i in batch), first, batch)

    if pend:
        return res("STUCK", f"steps {', '.join(str(s.get('n')) for s in pend)} cannot start (each waits on a step "
                            f"that is not done): edit PLAN.md, then /approve {slug}")

    if cause is not None:  # 9i
        return res("FIX", f"{cause}: the builder fixes it (round {rounds + 1} of {FIX_LIMIT})")
    if vkind != "ok":  # 9j
        return res("VERIFY", f"{vwhy}: qa runs the project's checks" + (", then the designer compares" if ui else ""))
    if not rev_fresh:  # 9k
        return res("REVIEW", "no fresh review: the reviewer writes REVIEW.md")
    return res("SHIP", f"review is fresh and says SHIP: /ship {slug}")  # 9l


# --- the current project and the preview ports (spec 6.1) ---------------------------------

RESERVED_WORDS = ("cap", "retry")  # arguments of /go, never project names
SLUG_RE = re.compile(r"[a-z0-9-][a-z0-9_-]*")  # same rule as approve.sh
NO_CURRENT = "no current project: name one, e.g. /go <slug>"


def _is_project(workshop, slug):
    return (bool(SLUG_RE.fullmatch(slug)) and slug not in RESERVED_WORDS
            and os.path.isdir(os.path.join(workshop, "mini-projects", slug)))


def _current_path(workshop):
    return os.path.join(workshop, ".harness", "current")


def set_current(workshop, slug):
    """Remember `slug` as the project a command without a name means (<workshop>/.harness/current)."""
    path = _current_path(workshop)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(slug + "\n")
    os.replace(tmp, path)


def resolve_slug(workshop, arg):
    """(slug, "") or (None, error). An explicit name wins (and is remembered once it is a project), else the saved
    one; `cap` and `retry` are never names. The caller checks that an explicit name is a project."""
    arg = (arg or "").strip()
    if arg and arg not in RESERVED_WORDS:
        if _is_project(workshop, arg):
            try:
                set_current(workshop, arg)
            except OSError:
                pass  # a convenience: the command still runs
        return arg, ""
    try:
        with open(_current_path(workshop), "r", encoding="utf-8") as fh:
            saved = fh.read().strip()
    except (OSError, ValueError):
        saved = ""
    if not SLUG_RE.fullmatch(saved):
        return None, NO_CURRENT
    if not _is_project(workshop, saved):
        return None, f"{NO_CURRENT} ('{saved}' is gone)"
    return saved, ""


def resolve_command(workshop, text):
    """The slug a command template means, for `harness_state.py resolve`: (slug line, "") or (None, error). `text` is
    one project name, or empty for the current project."""
    parts = (text or "").split()
    if len(parts) > 1 or (parts and not _is_project(workshop, parts[0])):
        return None, (f"there is no project mini-projects/{parts[0]} (give one project name, or none for the current one)"
                      if len(parts) == 1 else "give one project name, or none for the current one")
    slug, err = resolve_slug(workshop, parts[0] if parts else None)
    return (None, err) if slug is None else (slug + "\n", "")


def assign_port(workshop, proj):
    """The project's preview port: the recorded one, else the lowest from PORT_BASE that no other project holds."""
    state = load(proj)
    if _is_int(state.get("port")):
        return state["port"]
    root, taken = os.path.join(workshop, "mini-projects"), set()
    try:
        names = sorted(os.listdir(root))
    except OSError:
        names = []
    for name in names:
        other = os.path.join(root, name)
        if name.startswith("_") or not os.path.isdir(other) or os.path.realpath(other) == os.path.realpath(proj):
            continue
        try:
            port = load(other).get("port")
        except (StateError, OSError):
            continue
        if _is_int(port):
            taken.add(port)
    port = PORT_BASE
    while port in taken:
        port += 1
    state["port"] = port
    save(proj, state)
    return port


def free_port(proj, port):
    """Stop a listener on `port` only when its working directory is inside `proj` (an unrelated service of the human's
    is left alone). Never raises."""
    try:
        root, me = os.path.realpath(proj).lower(), str(os.getpid())
        pids = subprocess.run(["lsof", "-nP", f"-iTCP:{int(port)}", "-sTCP:LISTEN", "-t"], capture_output=True,
                              text=True, timeout=10).stdout.split()
        for pid in sorted(set(pids)):
            if not pid.isdigit() or pid == me:
                continue
            out = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], capture_output=True, text=True,
                                 timeout=10).stdout
            cwd = next((l[1:] for l in out.splitlines() if l.startswith("n")), None)
            if cwd:
                cwd = os.path.realpath(cwd).lower()  # this Mac is case-blind: projects/ and Projects/ are one folder
                if cwd == root or cwd.startswith(root + os.sep):
                    os.kill(int(pid), signal.SIGTERM)
    except Exception:  # a preview port is a convenience: never fail a /go over it
        pass


# --- CLI ----------------------------------------------------------------------------------

def main(argv):
    if len(argv) in (3, 4) and argv[1] == "current":  # current <workshop> [slug]: read, or (human only) set
        workshop = os.path.abspath(argv[2])
        if len(argv) == 3:
            slug, _ = resolve_slug(workshop, None)
            print(slug or "")
            return 0 if slug else 1
        if os.environ.get("AGENT") == "1" or os.environ.get("OPENCODE_SESSION_ID"):
            print("REFUSED: the current project is set by the human's command, never from an agent shell.",
                  file=sys.stderr)
            return 3
        if not _is_project(workshop, argv[3]):
            print(f"REFUSED: there is no project mini-projects/{argv[3]}.", file=sys.stderr)
            return 1
        set_current(workshop, argv[3])
        return 0
    if len(argv) == 3 and argv[1] == "resolve":
        # resolve <text>: the project a command template names (sets the current project): human only
        if os.environ.get("AGENT") == "1" or os.environ.get("OPENCODE_SESSION_ID"):
            print("REFUSED: the current project is set by the human's command, never from an agent shell.",
                  file=sys.stderr)
            return 3
        out, err = resolve_command(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), argv[2])
        if out is None:
            print(err, file=sys.stderr)
            return 1
        sys.stdout.write(out)
        return 0
    if len(argv) != 3 or argv[1] not in ("approve", "ship", "approved", "tree", "review"):
        print("usage: harness_state.py approve|ship|approved|tree|review <project-dir> | current <workshop> [slug] | "
              "resolve <text>", file=sys.stderr)
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
    design = " + DESIGN" if os.path.exists(os.path.join(proj, "DESIGN.md")) else ""
    print(f"APPROVED: mini-projects/{slug} {state['steps'][0]['milestone']} (BRIEF + ARCHITECTURE{design} + PLAN, "
          f"sha256 {state['approved_sha256'][:12]}, {len(state['steps'])} steps). "
          "Any edit to these files revokes this; /approve again after a change.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

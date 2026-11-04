#!/usr/bin/env python3
"""Parsers for the v4 project documents (BRIEF, ARCHITECTURE, PLAN, CRITIQUE) and the answer lines.

Stdlib only, no imports from other harness modules. Every DocError message starts with the file name and
names the exact line or id, because it is fed back verbatim to the agent that wrote the file.
"""
import os
import posixpath
import re


class DocError(ValueError):
    pass


class PlanError(DocError):
    pass


ANSWER_FILE = {"architecture": "ARCHITECTURE.md", "brief": "ARCHITECTURE.md", "plan": "PLAN.md", "design": "DESIGN.md"}

# Separator between the parts of an ids line: em dash, en dash, or a spaced hyphen.
SEP = r"(?:\s*[—–]\s*|\s+-\s+)"


def _lines(text):
    return [l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]


def _norm(heading):
    h = re.sub(r"\s+", " ", heading.strip())
    return h.rstrip(":").strip().upper()


def sections(text):
    """'## ' headings (normalised) -> their lines. First occurrence wins."""
    out, cur = {}, None
    for l in _lines(text):
        m = re.match(r"^##(?!#)\s+(.*)$", l)
        if m:
            cur = _norm(m.group(1))
            if cur in out:
                cur = None  # a repeated heading never overrides the first
            else:
                out[cur] = []
        elif cur is not None:
            out[cur].append(l)
    return out


def check_summary(text, name):
    secs = sections(text)
    if not secs or next(iter(secs)) != "SUMMARY":
        raise DocError(f"{name}: the first '## ' section must be '## SUMMARY' (1 to 5 lines)")
    n = len([l for l in secs["SUMMARY"] if l.strip()])
    if n == 0:
        raise DocError(f"{name}: '## SUMMARY' is empty (write 1 to 5 lines)")
    if n > 5:
        raise DocError(f"{name}: '## SUMMARY' has {n} lines (the limit is 5)")


def _bullets(lines):
    return [l for l in lines if l.strip()]


def _ids(raw, prefix, who):
    """'F1, F3' / 'f1 f3' / 'none' -> ['F1', 'F3']. Raises DocError naming a bad token."""
    raw = raw.strip().strip("`").strip()
    if not raw or raw.lower().rstrip(".") == "none":
        return []
    out = []
    for tok in [t for t in re.split(r"[,\s]+", raw) if t]:
        if not re.fullmatch(rf"{prefix}\d+", tok, re.I):
            raise DocError(f"{who}: '{tok}' is not a {prefix}<n> id")
        out.append(tok.upper())
    return out


# --- paths ---------------------------------------------------------------------------------------

def norm_path(p):
    """'./Src//A.js' -> 'src/a.js'. Lowercase (this Mac is case-insensitive); a trailing '/' (a folder) is kept."""
    p = p.strip().replace("\\", "/").lower()
    folder = p.endswith("/") or p.endswith("/.")
    n = posixpath.normpath(p) if p else ""
    if n == ".":
        return ""
    return n + "/" if folder and not n.endswith("/") else n


def paths_overlap(a, b):
    """Equal after norm_path, or one is a folder ('/') that is a prefix of the other. 'src' (no slash) is a file."""
    a, b = norm_path(a), norm_path(b)
    return a == b or (a.endswith("/") and b.startswith(a)) or (b.endswith("/") and a.startswith(b))


# Paths no builder step may own: QA's tests, request/research files, designer and inspector output, harness state, the doc files.
HARNESS_OWNED = ("tests/acceptance/", "requests/", "RESEARCH/", "design/", ".harness/",
                 "BRIEF.md", "BRAINSTORM.md", "ARCHITECTURE.md", "DESIGN.md", "PLAN.md", "REVIEW.md",
                 "CRITIQUE.md", "BUGHUNT.md", "QA.md", "VISUAL.md")


# --- BRIEF.md ------------------------------------------------------------------------------------

# the '## ' sections of BRIEF.md in order: next.py's BRIEF_FORMAT is built from this; a test checks brainstormer.md
BRIEF_SECTIONS = ("SUMMARY", "GOAL", "FOR WHO / WHY", "WHERE IT RUNS", "FEATURES", "OPPORTUNITIES", "REALITY CHECK",
                  "DECISIONS", "OPEN QUESTIONS")


def parse_brief(text):
    name = "BRIEF.md"
    check_summary(text, name)
    secs = sections(text)
    if "WHERE IT RUNS" not in secs:
        raise DocError(f"{name}: no '## WHERE IT RUNS' section")
    ui = None
    for l in secs["WHERE IT RUNS"]:
        m = re.match(r"^\s*[-*]\s*ui\s*:\s*(yes|no)\s*\.?\s*$", l, re.I)
        if m:
            ui = m.group(1).lower() == "yes"
    if ui is None:
        raise DocError(f"{name}: '## WHERE IT RUNS' has no '- ui: yes' or '- ui: no' line")
    if "FEATURES" not in secs:
        raise DocError(f"{name}: no '## FEATURES' section")
    features, seen = [], set()
    for l in _bullets(secs["FEATURES"]):
        m = re.match(r"^\s*[-*]\s*(F\d+)\s*\[(MUST|SHOULD|LATER)\]\s*:?\s*(.*)$", l, re.I)
        if not m:
            raise DocError(f"{name}: FEATURES line is not '- F<n> [MUST|SHOULD|LATER] <text>': {l.strip()}")
        fid = m.group(1).upper()
        if fid in seen:
            raise DocError(f"{name}: feature id {fid} appears twice")
        seen.add(fid)
        features.append({"id": fid, "priority": m.group(2).upper(), "text": m.group(3).strip()})
    if not features:
        raise DocError(f"{name}: '## FEATURES' has no features (write '- F1 [MUST] <feature>')")
    if not any(f["priority"] == "MUST" for f in features):
        raise DocError(f"{name}: no feature is [MUST] (at least one is required)")
    if "OPEN QUESTIONS" not in secs:
        raise DocError(f"{name}: no '## OPEN QUESTIONS' section (write '- none' when there are none)")
    questions = []
    for l in _bullets(secs["OPEN QUESTIONS"]):
        s = re.sub(r"^\s*[-*]\s*", "", l).strip()
        s = s[:-1].strip() if s.endswith(".") else s
        if s and s.lower() != "none":
            questions.append(l.strip())
    return {"features": features, "ui": ui, "open_questions": questions}


# --- answers -------------------------------------------------------------------------------------

def parse_answers(text, name="file"):
    """'## CRITIQUE ANSWERS' -> {"C3": ("rejected", "needs /brainstorm")}."""
    out = {}
    for l in _bullets(sections(text).get("CRITIQUE ANSWERS", [])):
        if not re.match(r"^\s*[-*]\s*C\d+\b", l, re.I):
            continue
        m = re.match(rf"^\s*[-*]\s*(C\d+)\s*:\s*(fixed|rejected){SEP}(\S.*)$", l, re.I)
        if not m:
            raise DocError(f"{name}: CRITIQUE ANSWERS line is not '- C<n>: fixed|rejected — <reason>': {l.strip()}")
        out[m.group(1).upper()] = (m.group(2).lower(), m.group(3).strip())
    return out


# --- ## DEPLOY (spec 7.1) -------------------------------------------------------------------------

KNOWN_KINDS = ("service", "none")
PREVIEW_PORTS = (4800, 4899)  # assign_port hands these out; a deployed app must not sit on one


def parse_deploy(text):
    """ARCHITECTURE.md text -> {"kind", "build", "start", "port", "health", "data"}. Raises PlanError naming what is wrong."""
    name = "ARCHITECTURE.md"
    body = sections(text).get("DEPLOY")
    if body is None:
        raise PlanError(f"{name}: add a ## DEPLOY section (kind, build, start, port, health, data)")
    vals, last = {}, None
    for l in _bullets(body):
        m = re.match(r"^[-*]\s*(kind|build|start|port|health|data)\s*:\s*(.*)$", l, re.I)
        if m:
            last = m.group(1).lower()
            vals.setdefault(last, m.group(2).strip().strip("`").strip())
        elif last and re.match(r"^\s", l):  # an indented continuation: the value runs over two lines
            raise PlanError(f"{name}: DEPLOY {last} must be one line")
        else:
            last = None
    kind = vals.get("kind", "").lower()
    if not kind:
        raise PlanError(f"{name}: DEPLOY needs a '- kind: service | none' line")
    if kind not in KNOWN_KINDS:
        raise PlanError(f"{name}: DEPLOY kind {kind} has no adapter yet: use service or none, or add the adapter")
    out = {"kind": kind, "build": None, "start": None, "port": None, "health": None, "data": False}
    if kind == "none":
        return out
    for f in ("start", "port", "health"):
        if not vals.get(f):
            raise PlanError(f"{name}: DEPLOY kind service needs {f}")
    port_msg = f"{name}: DEPLOY port must be 1024-65535 and outside {PREVIEW_PORTS[0]}-{PREVIEW_PORTS[1]} (preview ports)"
    if not re.fullmatch(r"\d{1,5}", vals["port"]):
        raise PlanError(port_msg)
    port = int(vals["port"])
    if not 1024 <= port <= 65535 or PREVIEW_PORTS[0] <= port <= PREVIEW_PORTS[1]:
        raise PlanError(port_msg)
    if not vals["health"].startswith("/"):
        raise PlanError(f"{name}: DEPLOY health must be a path starting with /")
    data = vals.get("data", "no").lower()
    if data not in ("yes", "no"):
        raise PlanError(f"{name}: DEPLOY data must be yes or no")
    build = vals.get("build", "")
    out.update(build=None if build.lower() in ("", "none") else build, start=vals["start"], port=port,
               health=vals["health"], data=data == "yes")
    return out


# --- ARCHITECTURE.md -----------------------------------------------------------------------------

def parse_architecture(text, feature_ids, must_ids, ui=False):
    name = "ARCHITECTURE.md"
    check_summary(text, name)
    secs = sections(text)

    risks, rids = [], set()
    for l in _bullets(secs.get("RISKS", [])):
        if not re.match(r"^\s*[-*]\s*R\d+\b", l, re.I):
            continue
        m = re.match(rf"^\s*[-*]\s*(R\d+)\s*:\s*(.*?)(?:{SEP}test\s*:\s*(\S.*))?$", l, re.I)
        if not m:
            raise DocError(f"{name}: RISKS line is not '- R<n>: <risk> — test: <spike>': {l.strip()}")
        rid = m.group(1).upper()
        if rid in rids:
            raise DocError(f"{name}: risk id {rid} appears twice")
        if rid == "R1" and not m.group(3):
            raise DocError(f"{name}: R1 needs '— test: <smallest spike>': {l.strip()}")
        rids.add(rid)
        risks.append({"id": rid, "text": m.group(2).strip(), "test": (m.group(3) or "").strip()})
    if "R1" not in rids:
        raise DocError(f"{name}: RISKS has no R1 (write '- R1: <risk> — test: <smallest spike>')")

    for l in _bullets(secs.get("DECISIONS", [])):
        if re.match(r"^\s*[-*]\s*D\d+\b", l, re.I) and not re.match(
                rf"^\s*[-*]\s*D\d+\s*:\s*.+?{SEP}rejected\s*:\s*.+?{SEP}why\s*:\s*\S", l, re.I):
            raise DocError(f"{name}: DECISIONS line is not '- D<n>: <choice> — rejected: <x> — why: <y>': {l.strip()}")

    milestones, mids, owner = [], [], {}
    for l in _bullets(secs.get("MILESTONES", [])):
        if not re.match(r"^\s*[-*]\s*M\d+\b", l, re.I):
            continue
        m = re.match(rf"^\s*[-*]\s*(M\d+)\s*:\s*(.*?){SEP}covers\s*:\s*(.*)$", l, re.I)
        if not m:
            raise DocError(f"{name}: MILESTONES line is not '- M<n>: <title> — covers: F1, F2': {l.strip()}")
        mid = m.group(1).upper()
        if mid in mids:
            raise DocError(f"{name}: milestone id {mid} appears twice")
        covers = _ids(m.group(3), "F", f"{name}: milestone {mid}")
        for f in covers:
            if f not in feature_ids:
                raise DocError(f"{name}: milestone {mid} covers {f}, which is not a feature in BRIEF.md")
            if f in owner:
                raise DocError(f"{name}: feature {f} is in two milestones ({owner[f]} and {mid})")
            owner[f] = mid
        mids.append(mid)
        milestones.append({"id": mid, "title": m.group(2).strip(), "covers": covers})
    if not milestones:
        raise DocError(f"{name}: MILESTONES has no milestones (write '- M1: <title> — covers: F1')")
    for i, mid in enumerate(mids, start=1):
        if mid != f"M{i}":
            raise DocError(f"{name}: milestones must run M1..Mn with no gaps; expected M{i}, found {mid}")
    for f in sorted(must_ids):
        if f not in owner:
            raise DocError(f"{name}: MUST feature {f} is in no milestone")
    preview = None
    for l in secs.get("STACK", []):
        m = re.match(r"^\s*[-*]\s*preview\s*:\s*(\S.*)$", l, re.I)
        if m:
            preview = m.group(1).strip().strip("`").strip() or None
    if ui and preview is None:
        raise DocError(f"{name}: ui: yes needs a '- preview: <command>' line in STACK")
    deploy = parse_deploy(text)
    return {"risks": risks, "milestones": milestones, "preview": preview, "deploy": deploy,
            "answers": parse_answers(text, name), "feature_ids": set(feature_ids)}


# --- PLAN.md -------------------------------------------------------------------------------------

def parse_plan(text):
    """PLAN.md text -> [{"n", "title", "files", "check", "covers", "proves", "after", "design"}]. Raises PlanError naming what is wrong."""
    lines = _lines(text)
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
        files, checks, covers, proves, after, design = [], [], [], None, None, []
        for l in rest:
            m = re.match(r"^\s*[-*]\s*(files|done when|covers|proves|after|design)\s*:\s*(.*)$", l, re.I)
            if not m:
                continue
            key = m.group(1).lower()
            if key == "files":
                files = [f.strip().strip("`").strip() for f in m.group(2).split(",")]
                files = [f for f in files if f]
            elif key == "covers":
                try:
                    covers = _ids(m.group(2), "F", f"PLAN.md {who}")
                except DocError as exc:
                    raise PlanError(str(exc))
            elif key == "after":
                raw_after = m.group(2).strip().strip("`").strip()
                after = []
                if raw_after and raw_after.lower().rstrip(".") != "none":
                    toks = [t for t in re.split(r"[,\s]+", raw_after) if t]
                    # PL4: `after:` is parsed and ignored; a malformed token is not an error (yields [])
                    after = [int(t) for t in toks] if all(re.fullmatch(r"\d+", t) for t in toks) else []
            elif key == "design":
                design = [t.strip().strip("`").strip() for t in m.group(2).split(",")]
                design = [t for t in design if t and t.lower().rstrip(".") != "none"]
            elif key == "proves":
                try:
                    ids = _ids(m.group(2), "R", f"PLAN.md {who}")
                except DocError as exc:
                    raise PlanError(str(exc))
                proves = ids[0] if ids else None
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
        steps.append({"n": n, "title": title, "files": files, "check": m.group(1).strip(),
                      "covers": covers, "proves": proves, "after": after, "design": design})
    return steps


def plan_milestone(text):
    """First non-empty line of '## MILESTONE' ('M1: title') -> 'M1', or None."""
    for l in sections(text).get("MILESTONE", []):
        if l.strip():
            m = re.match(r"^\s*(M\d+)\s*:", l, re.I)
            return m.group(1).upper() if m else None
    return None


PLAN_DESIGN_SECTIONS = ("SUMMARY", "DIRECTION", "TOKENS", "COMPONENTS", "SCREENS", "ACCESSIBILITY")


def _design_name_ok(name, design):
    """F2: a step's `design:` entry is a DESIGN.md section, a SCREENS name, or a SCREENS mockup file that exists."""
    low = name.lower()
    if low in (h.lower() for h in PLAN_DESIGN_SECTIONS) or low in (n.lower() for n, _ in design["screens"]):
        return True
    path = norm_path(name)  # lowercases first: fine on this case-insensitive Mac, a known limit elsewhere
    if not path.startswith("design/mockups/") or ".." in path.split("/") or "\\" in name or name[0] in "/~":
        return False
    if path not in {norm_path(p) for _, p in design["screens"]}:  # only mockups the human approved (the SCREENS ones)
        return False
    base = os.path.realpath(os.path.join(design["proj"], "design", "mockups"))
    full = os.path.realpath(os.path.join(design["proj"], path))
    return full.startswith(base + os.sep) and os.path.isfile(full)


def check_plan(text, arch, milestone, design=None):
    """design: for a ui project, parse_design(...) plus {"proj": <project dir>}; None for any other project."""
    name = "PLAN.md"
    check_summary(text, name)
    got = plan_milestone(text)
    if got is None:
        raise DocError(f"{name}: no '## MILESTONE' section with a first line 'M<n>: <title>' (expected {milestone})")
    if got != milestone:
        raise DocError(f"{name}: the plan is for {got} but the current milestone is {milestone}")
    try:
        steps = parse_plan(text)
    except PlanError as exc:
        msg = str(exc)
        raise DocError(msg if msg.startswith("PLAN.md") else f"PLAN.md: {msg}")
    risk_ids = {r["id"] for r in arch["risks"]}
    for s in steps:
        for f in s["covers"]:
            if f not in arch["feature_ids"]:
                raise DocError(f"{name}: step {s['n']} covers {f}, which is not a feature in BRIEF.md")
        if s["proves"] is not None and s["proves"] not in risk_ids:
            raise DocError(f"{name}: step {s['n']} proves {s['proves']}, which is not a risk in ARCHITECTURE.md")
    owned = [norm_path(o) for o in HARNESS_OWNED]
    seen_checks = {}
    for s in steps:
        for f in s["files"]:
            if ".." in f.replace("\\", "/").split("/") or f[0] in "/~" or "\\" in f:
                raise DocError(f"{name}: step {s['n']} lists {f}: use a plain path inside the project "
                               "(no .., no absolute path)")
            if norm_path(f) in ("", ".", "/"):
                raise DocError(f"{name}: step {s['n']} lists {f}: name files or folders, not the whole project")
            if any(paths_overlap(f, o) for o in owned):
                raise DocError(f"{name}: step {s['n']} may not list {f} (owned by the harness or another agent)")
        key = " ".join(s["check"].split())
        if key in seen_checks:
            raise DocError(f"{name}: step {seen_checks[key]} and step {s['n']} share the check {s['check']}")
        seen_checks[key] = s["n"]
    if design is not None:
        if not any(s["design"] for s in steps):
            raise DocError(f"{name}: a UI milestone needs at least one step with a '- design:' line")
        for s in steps:
            for d in s["design"]:
                if not _design_name_ok(d, design):
                    raise DocError(f"{name}: step {s['n']} design: '{d}' is not in DESIGN.md or design/mockups/")
    if milestone == "M1" and steps[0]["proves"] != "R1":
        raise DocError(f"{name}: step 1 of M1 must have '- proves: R1'")
    covered = {f for s in steps for f in s["covers"]}
    want = next((m["covers"] for m in arch["milestones"] if m["id"] == milestone), None)
    if want is None:
        raise DocError(f"{name}: {milestone} is not a milestone in ARCHITECTURE.md")
    for f in want:
        if f not in covered:
            raise DocError(f"{name}: feature {f} belongs to {milestone} in ARCHITECTURE.md but no step covers it")
    return steps


# --- CRITIQUE.md ---------------------------------------------------------------------------------

def parse_critique(text, has_design):
    name = "CRITIQUE.md"
    check_summary(text, name)
    targets = ("brief", "architecture", "plan") + (("design",) if has_design else ())
    rounds, cur, last_c = [], None, 0
    for l in _lines(text):
        if re.match(r"^##(?!#)\s+ROUND\b", l, re.I):
            m = re.match(rf"^##\s+ROUND\s+(\d+){SEP}(M\d+)\s*$", l, re.I)
            if not m:
                raise DocError(f"{name}: round heading is not '## ROUND <n> — M<k>': {l.strip()}")
            n = int(m.group(1))
            if n != len(rounds) + 1:
                raise DocError(f"{name}: ROUND {n} is out of order: expected ROUND {len(rounds) + 1} (rounds run 1..N)")
            cur = {"n": n, "milestone": m.group(2).upper(), "points": []}
            rounds.append(cur)
        elif re.match(r"^##(?!#)\s", l):
            cur = None
        elif cur is not None and re.match(r"^\s*[-*]\s*C\d+\b", l, re.I):
            m = re.match(rf"^\s*[-*]\s*(C\d+)\s*\[(\w+)\]\s*\[(\w+)\]\s*(.*?)(?:{SEP}fix\s*:\s*(.*))?$", l, re.I)
            if not m:
                raise DocError(f"{name}: point is not '- C<n> [serious|minor] [target] <text> — fix: <fix>': {l.strip()}")
            cid, sev, tgt = m.group(1).upper(), m.group(2).lower(), m.group(3).lower()
            k = int(cid[1:])
            if k <= last_c:
                raise DocError(f"{name}: point {cid} is out of order or reused (ids increase across the file; last was C{last_c})")
            if sev not in ("serious", "minor"):
                raise DocError(f"{name}: point {cid} has severity '{sev}' (use serious or minor)")
            if tgt not in targets:
                extra = " (design needs a DESIGN.md)" if tgt == "design" else ""
                raise DocError(f"{name}: point {cid} has target '{tgt}' (use {'|'.join(targets)}){extra}")
            last_c = k
            cur["points"].append({"id": cid, "severity": sev, "target": tgt,
                                  "text": m.group(4).strip(), "fix": (m.group(5) or "").strip()})
    if not rounds:
        raise DocError(f"{name}: no '## ROUND 1 — M1' section")
    return {"rounds": rounds}


# --- DESIGN.md + mockups -------------------------------------------------------------------------

DESIGN_SECTIONS = ("SUMMARY", "DIRECTION", "TOKENS", "COMPONENTS", "SCREENS", "ACCESSIBILITY", "STACK FIT")


def parse_design(text):
    """DESIGN.md -> {"screens": [(name, path)], "stack_fit": "agree"|"object", "object_reason": str|None}."""
    name = "DESIGN.md"
    try:
        check_summary(text, name)
    except DocError as exc:
        raise PlanError(str(exc))
    secs = sections(text)
    for h in DESIGN_SECTIONS:
        if h not in secs:
            raise PlanError(f"{name}: no '## {h}' section")
    screens = []
    for l in _bullets(secs["SCREENS"]):
        m = re.match(r"^\s*[-*]\s*(.+?)\s*:\s*`?(\S+?)`?\s*$", l)
        path = norm_path(m.group(2)) if m else ""
        if not m or not path.startswith("design/mockups/") or ".." in path or not path.endswith(".html"):
            raise PlanError(f"{name}: SCREENS line is not '- <screen>: design/mockups/<name>.html': {l.strip()}")
        screens.append((m.group(1).strip(), m.group(2)))
    if not 1 <= len(screens) <= 6:
        raise PlanError(f"{name}: '## SCREENS' needs 1 to 6 entries, found {len(screens)}")
    fit = _bullets(secs["STACK FIT"])
    if len(fit) != 1:
        raise PlanError(f"{name}: '## STACK FIT' needs exactly one line: '- agree' or '- object: <why>'")
    m = re.match(r"^\s*[-*]\s*(agree\.?|object\s*:\s*(\S.*))\s*$", fit[0], re.I)
    if not m:
        raise PlanError(f"{name}: STACK FIT line is not '- agree' or '- object: <why>': {fit[0].strip()}")
    if m.group(2):
        return {"screens": screens, "stack_fit": "object", "object_reason": m.group(2).strip()}
    return {"screens": screens, "stack_fit": "agree", "object_reason": None}


_FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")


def check_mockup(text):
    """Error text if a mockup is not static HTML/CSS (script, outside URL), else None."""
    if re.search(r"<script", text, re.I):
        return "mockup has a <script tag (mockups are static HTML/CSS only)"
    for m in re.finditer(r"https?://([^/\s\"'<>)?#]*)", text, re.I):
        host = m.group(1).lower().rsplit("@", 1)[-1].split(":")[0]
        if host not in _FONT_HOSTS:
            return f"mockup loads {m.group(0)} (only fonts.googleapis.com and fonts.gstatic.com are allowed)"
    if re.search(r"(?:[\w-]+\s*=\s*[\"']?\s*|@import\s*[\"']?\s*|url\(\s*[\"']?\s*)//", text, re.I):
        return "mockup has a protocol-relative '//' URL (only Google Fonts links are allowed)"
    if re.search(r"javascript:", text, re.I):
        return "mockup has a javascript: URL (static HTML/CSS only)"
    if re.search(r"\son\w+\s*=", text, re.I):
        return "mockup has an inline event handler (static HTML/CSS only)"
    return None


# --- QA.md, VISUAL.md, requests ------------------------------------------------------------------

def parse_qa(text):
    """QA.md -> {"tests": {"F3": path}, "run": cmd or "", "verdict": "PASS"|"FAIL"|None, "revisions": [...]}."""
    secs = sections(text)
    tests = {}
    for l in secs.get("TESTS", []):
        m = re.match(r"^\s*[-*]\s*(F\d+)\s*:\s*`?(\S+?)`?(?:\s.*)?$", l, re.I)
        if m:
            tests[m.group(1).upper()] = m.group(2)
    run = ""
    for l in secs.get("RUN", []):
        m = re.match(r"^\s*[-*]\s*run\s*:\s*`([^`]+)`\s*$", l, re.I)
        if m and m.group(1).strip():
            run = m.group(1).strip()
            break
    verdict = None
    for l in secs.get("VERDICT", []):
        m = re.match(r"^\s*VERDICT\s*:\s*(PASS|FAIL)\s*$", l, re.I)
        if m:
            verdict = m.group(1).upper()
            break
    revisions = []
    for l in secs.get("REVISIONS", []):
        m = re.match(rf"^\s*[-*]\s*step\s*(\d+)\s*:\s*`?(\S+?)`?(?:{SEP}.*)?$", l, re.I)
        if m:
            revisions.append({"step": int(m.group(1)), "test": m.group(2)})
    return {"tests": tests, "run": run, "verdict": verdict, "revisions": revisions}


def check_qa(text, must_ids):
    """Error text (starts 'QA.md') or None."""
    name = "QA.md"
    try:
        check_summary(text, name)
    except DocError as exc:
        return str(exc)
    qa = parse_qa(text)
    for fid in sorted(must_ids):
        if fid not in qa["tests"]:
            return f"{name}: '## TESTS' has no line for MUST feature {fid} ('- {fid}: tests/acceptance/<file> — <what it proves>')"
    for fid, path in qa["tests"].items():
        n = norm_path(path)
        if not n.startswith("tests/acceptance/") or ".." in n or n.endswith("/"):
            return f"{name}: test for {fid} must be a file under tests/acceptance/, got {path}"
    runs = [l for l in sections(text).get("RUN", []) if re.match(r"^\s*[-*]\s*run\s*:", l, re.I)]
    if len(runs) != 1 or not qa["run"]:
        return f"{name}: '## RUN' needs exactly one '- run: `<command>`' line (one command in one pair of backticks)"
    return None


VISUAL_VERDICT_RE = re.compile(r"^\s*VERDICT\s*:\s*(MATCH|MINOR|FIX)\s*$", re.I)  # shared with harness_state.visual_items


def parse_visual(text):
    """VISUAL.md -> 'MATCH' | 'MINOR' | 'FIX' | None (from the first 'VERDICT: MATCH|MINOR|FIX' line)."""
    for l in _lines(text):
        m = VISUAL_VERDICT_RE.match(l)
        if m:
            return m.group(1).upper()
    return None


def parse_request(text):
    """requests/step<n>.md first line -> {"kind": "RESEARCH", "question"} | {"kind": "TEST-WRONG", "test", "why"}."""
    first = next((l.strip() for l in _lines(text) if l.strip()), "")
    m = re.match(r"^RESEARCH\s*:\s*(\S.*)$", first)
    if m:
        return {"kind": "RESEARCH", "question": m.group(1).strip()}
    m = re.match(rf"^TEST-WRONG\s*:\s*`?(\S+?)`?{SEP}(\S.*)$", first)
    if m:
        return {"kind": "TEST-WRONG", "test": m.group(1), "why": m.group(2).strip()}
    raise PlanError("request: the first line must be 'RESEARCH: <question>' or "
                    f"'TEST-WRONG: <test file> — <why it cannot pass>', got: {first or '(empty)'}")

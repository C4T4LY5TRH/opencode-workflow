#!/usr/bin/env python3
"""Trusted save points for a project (v4 piece 3, spec section 4): a secret scan, a structure check, and event-scoped
git commits. Python 3 stdlib only.

    python3 scripts/checkpoint.py commit <project> '<event json>'     prints one JSON result, exit 0
    python3 scripts/checkpoint.py undo '<project name or empty>'      /undo: shelve everything since the last save point

This module NEVER writes .harness/state.json: it prints a result and its caller records it. Every git call runs with the
project's hooks switched off and without fsmonitor / implicit bare repos (GIT_BASE), and only after own_repo() has shown
that <project> is itself a git repo root, so a project without its own .git can never stage the workshop repo.
"""
import fnmatch
import json
import os
import posixpath
import re
import subprocess
import sys
from datetime import datetime, timezone

SCAN_BLOCK_BYTES = 50 * 1024 * 1024
SCAN_NOTE_BYTES = 5 * 1024 * 1024
SCAN_NOTES_KEPT = 20  # the caller keeps this many in state.scan_notes
TEXT_SCAN_BYTES = 2 * 1024 * 1024  # whole-tree scans read blobs up to this size

# Trusted git: nothing a project's own config can run (spec 4.1). Identity is the only user config we rely on.
GIT_BASE = ["git", "-c", "core.fsmonitor=false", "-c", "safe.bareRepository=explicit", "-c", "core.hooksPath=/dev/null"]
FIXED_EXCLUSIONS = [":(exclude).review", ":(exclude)design/shots", ":(exclude).harness"]
LEAKY_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR",
             "GIT_NAMESPACE", "GIT_PREFIX", "GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS",
             "GIT_ICASE_PATHSPECS")  # *_PATHSPECS: an exclude pathspec read literally would match nothing

_B = "block"
_N = "note"

IDENTITY_MESSAGE = ('set your git name and email: git config --global user.email "you@example.com" '
                    'and git config --global user.name "Your Name"')

SCAFFOLD = (".gitignore", "AGENTS.md", "README.md", "NOTES.md", "LEARNINGS.md", "opencode.json", "RESEARCH/")
DEP_FOLDERS = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target", "Pods",
               "DerivedData"}

_TOKEN = r"[A-Za-z0-9_\-]"
LINE_RULES = [  # (rule, level, compiled pattern)
    ("private-key", _B, re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----")),
    ("github-token", _B, re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("api-key", _B, re.compile(r"\bsk-" + _TOKEN + r"{20,}")),
    ("aws-key", _B, re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack-token", _B, re.compile(r"\bxox[abpr]-[A-Za-z0-9\-]{10,}")),
    ("google-key", _B, re.compile(r"\bAIza[0-9A-Za-z_\-]{35}")),
    ("stripe-live", _B, re.compile(r"\bsk_live_[0-9A-Za-z]{10,}")),
]
# Every pattern is anchored on a literal or bounded, so a scan stays linear on a huge one-line file (no line cap).
ASSIGN_RE = re.compile(
    r"""(?i)(?:KEY|SECRET|TOKEN|PASSWORD)[A-Za-z0-9_.\-]{0,64}["']?\s*[:=]\s*["']?"""
    r"""([A-Za-z0-9+/=_\-.~!@#%^&*]{16,})""")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63}){0,8}\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d]|\.\d)")
HOME_RE = re.compile(r"/(?:Users|home)/[A-Za-z0-9._\-]{1,64}/")
DOC_NETS = (("192", "0", "2"), ("198", "51", "100"), ("203", "0", "113"))


# --- git ---------------------------------------------------------------------------------------

def _env():
    env = {k: v for k, v in os.environ.items() if k not in LEAKY_ENV}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(proj, *args, check=True, input=None):
    """Run one trusted git command in proj. Text output (undecodable bytes kept as surrogates). check=True raises
    subprocess.CalledProcessError on a non-zero exit."""
    return subprocess.run([*GIT_BASE, "-C", proj, *args], capture_output=True, text=True, encoding="utf-8",
                          errors="surrogateescape", env=_env(), check=check, input=input, timeout=300)


def own_repo(proj):
    """True when `git rev-parse --show-toplevel` is proj itself (samefile: macOS paths differ in case/symlinks)."""
    try:
        top = git(proj, "rev-parse", "--show-toplevel", check=False)
        return top.returncode == 0 and os.path.samefile(top.stdout.strip(), proj)
    except (OSError, subprocess.SubprocessError):
        return False


# --- allow file --------------------------------------------------------------------------------

def read_allow(proj):
    """[(path, line or None, rule)] from <proj>/.harness/scan-allow: `path:rule` or `path:line:rule`, `#` comments."""
    out = []
    try:
        with open(os.path.join(proj, ".harness", "scan-allow"), encoding="utf-8", errors="replace") as fh:
            raw = fh.read().splitlines()
    except OSError:
        return out
    for l in raw:
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        parts = l.rsplit(":", 2)
        if len(parts) == 3 and parts[1].strip().isdigit():
            out.append((parts[0].strip(), int(parts[1]), parts[2].strip()))
        else:
            path, _, rule = l.rpartition(":")
            if path and rule:
                out.append((path.strip(), None, rule.strip()))
    return out


def _allowed(allow, path, line, rule):
    for apath, aline, arule in allow or ():
        if arule != rule or (aline is not None and aline != line):
            continue
        if apath == path or fnmatch.fnmatchcase(path, apath):
            return True
    return False


# --- scanning ----------------------------------------------------------------------------------

def _finding(path, line, rule, level):
    return {"file": path, "line": line, "rule": rule, "level": level}


def _classes(v):
    return sum(bool(re.search(p, v)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))


def _ip_noted(m):
    a, b, c, d = (int(x) for x in m.groups())
    if max(a, b, c, d) > 255 or a == 127 or a == 0:
        return False
    return not any((str(a), str(b), str(c)) == n for n in DOC_NETS)


def _scan_line(path, n, text):
    out = []
    for rule, level, rx in LINE_RULES:
        if rx.search(text):
            out.append(_finding(path, n, rule, level))
    for m in ASSIGN_RE.finditer(text):
        v = m.group(1)
        if re.search(r"[A-Za-z]", v) and re.search(r"\d", v) and _classes(v) >= 2:
            out.append(_finding(path, n, "assigned-secret", _B))
            break
    if "@" in text and EMAIL_RE.search(text):
        out.append(_finding(path, n, "email", _N))
    if any(_ip_noted(m) for m in IPV4_RE.finditer(text)):
        out.append(_finding(path, n, "ipv4", _N))
    if HOME_RE.search(text):
        out.append(_finding(path, n, "home-path", _N))
    return out


def _scan_name(path, size=None):
    """Findings from a file's name, folder and size alone (line 0)."""
    out = []
    base = posixpath.basename(path)
    if base == ".env" or (base.startswith(".env.") and base != ".env.example"):
        out.append(_finding(path, 0, "env-file", _B))
    low = base.lower()
    if low.endswith((".pem", ".key", ".p12")) or low.startswith("id_rsa"):
        out.append(_finding(path, 0, "key-file", _B))
    if size is not None:
        if size > SCAN_BLOCK_BYTES:
            out.append(_finding(path, 0, "file-over-50mb", _B))
        elif size > SCAN_NOTE_BYTES:
            out.append(_finding(path, 0, "file-over-5mb", _N))
    return out


def _dep_note(path):
    parts = path.split("/")
    for i, p in enumerate(parts[:-1]):
        if p in DEP_FOLDERS:
            return _finding("/".join(parts[:i + 1]) + "/", 0, "dependency-folder", _N)
    return None


def _filter(findings, allow):
    seen, out = set(), []
    for f in findings:
        key = (f["file"], f["line"], f["rule"], f.get("commit"))
        if key in seen or _allowed(allow, f["file"], f["line"], f["rule"]):
            continue
        seen.add(key)
        out.append(f)
    return out


def _split(findings):
    return ([f for f in findings if f["level"] == "block"], [f for f in findings if f["level"] == "note"])


def scan_text(path, text, allow=()):
    """Findings for one file's name and its text (every line counts as added). {file, line, rule, level}."""
    out = _scan_name(path, len(text.encode("utf-8", "surrogateescape")))
    dep = _dep_note(path)
    if dep:
        out.append(dep)
    for n, l in enumerate(text.splitlines(), start=1):
        out += _scan_line(path, n, l)
    return _filter(out, allow)


def _unquote(p):
    if p.startswith('"') and p.endswith('"'):
        try:
            return p[1:-1].encode("latin-1", "backslashreplace").decode("unicode_escape").encode("latin-1").decode(
                "utf-8", "surrogateescape")
        except (UnicodeError, ValueError):
            return p[1:-1]
    return p


def _added_lines(diff_text):
    """[(path, line number, text)] for every added line of a -U0 unified diff, counting hunks so that content which
    looks like a '+++' header is never mistaken for one."""
    out, path, lines = [], None, diff_text.split("\n")
    i = 0
    while i < len(lines):
        l = lines[i]
        i += 1
        if l.startswith("diff --git "):
            path = None
        elif l.startswith("+++ "):
            name = l[4:].split("\t")[0]
            path = None if name == "/dev/null" else _unquote(name[2:] if name[:2] in ("b/", "a/") else name)
        elif l.startswith("@@") and path is not None:
            m = re.match(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", l)
            if not m:
                continue
            rem = int(m.group(1)) if m.group(1) is not None else 1
            add = int(m.group(3)) if m.group(3) is not None else 1
            n = int(m.group(2))
            while (rem > 0 or add > 0) and i < len(lines):
                body = lines[i]
                i += 1
                if body.startswith("\\"):
                    continue
                if body.startswith("-"):
                    rem -= 1
                elif body.startswith("+"):
                    add -= 1
                    out.append((path, n, body[1:]))
                    n += 1
                else:
                    break
    return out


def _blob_sizes(proj, oids):
    """{oid: size} of the blobs among oids. Keyed by oid: a name holding \\n or \\r never passes this line protocol."""
    if not oids:
        return {}
    r = git(proj, "cat-file", "--batch-check", check=False, input="".join(o + "\n" for o in oids))
    sizes = {}
    for line in r.stdout.split("\n"):
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob" and parts[2].isdigit():
            sizes[parts[0]] = int(parts[2])
    return sizes


def _git_bytes(proj, *args):
    """stdout of a trusted git command, decoded WITHOUT universal newlines: text mode turns a lone \\r into \\n, which
    cut a -U0 hunk short in _added_lines (the rest of the file went unscanned) and broke file names. A failure raises
    CalledProcessError with text output, as git() does, so callers can put it in a JSON message."""
    r = subprocess.run([*GIT_BASE, "-C", proj, *args], capture_output=True, env=_env(), timeout=300)
    out, err = (b.decode("utf-8", "surrogateescape") for b in (r.stdout, r.stderr))
    if r.returncode:
        raise subprocess.CalledProcessError(r.returncode, r.args, out, err)
    return out


def _scan_diff(proj, diff_args, allow, commit=None):
    files, meta = [], None  # [(path, new blob oid)] from `--raw -z`: ":<modes> <oid> <oid> <status>\0<path>\0"
    # T (typechange): a symlink replaced by a file holding a key
    raw = _git_bytes(proj, *diff_args, "--raw", "-z", "--no-abbrev", "--diff-filter=ACMRT", "--no-renames")
    for tok in raw.split("\0"):
        if meta is not None:
            files.append((tok, meta.split()[3]))
            meta = None
        elif tok.startswith(":"):
            meta = tok
    sizes = _blob_sizes(proj, sorted({o for _, o in files}))
    out, big = [], []
    for p, oid in files:
        out += _scan_name(p, sizes.get(oid))
        dep = _dep_note(p)
        if dep:
            out.append(dep)
        if sizes.get(oid, 0) > SCAN_BLOCK_BYTES:
            big.append(":(exclude,literal)" + p)
    # explicit prefixes: diff.mnemonicPrefix / noprefix / srcPrefix in a repo config would break the path parse
    # --text: binary-looking files (.gitattributes -diff/binary, a NUL byte) are diffed as text, else never scanned.
    # Memory: --text holds a file ~10x its size here (measured: 436 MB peak, 16 s for 40 MB of random bytes), so a file
    # over SCAN_BLOCK_BYTES stays out of the diff: it blocks by size, and if the human allows it, it goes unscanned.
    # Below that the cost is accepted (such a file already gets a file-over-5mb note; streaming would add weight).
    diff = _git_bytes(proj, "-c", "core.quotepath=off", *diff_args, "-U0", "--text", "--no-color", "--no-ext-diff",
                      "--no-textconv", "--no-renames", "--src-prefix=a/", "--dst-prefix=b/", "--diff-filter=ACMRT",
                      "--", *big)
    for p, n, text in _added_lines(diff):
        out += _scan_line(p, n, text)
    if commit:
        for f in out:
            f["commit"] = commit
    return out


def scan_staged(proj):
    """(blocks, notes) over the staged diff's added lines and the staged names and sizes."""
    allow = read_allow(proj)
    return _split(_filter(_scan_diff(proj, ["diff", "--cached"], allow), allow))


def _cat_blobs(proj, oids):
    """{oid: bytes} through one `git cat-file --batch` process."""
    if not oids:
        return {}
    p = subprocess.run([*GIT_BASE, "-C", proj, "cat-file", "--batch"], input="".join(o + "\n" for o in oids).encode(),
                       capture_output=True, env=_env(), timeout=300)
    data, pos, out = p.stdout, 0, {}
    while pos < len(data):
        nl = data.find(b"\n", pos)
        if nl < 0:
            break
        head = data[pos:nl].split()
        if len(head) != 3:
            pos = nl + 1
            continue
        size = int(head[2])
        out[head[0].decode()] = data[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
    return out


def scan_ref(proj, ref):
    """(blocks, notes) over a whole tree (deploy readiness): every committed file at `ref`."""
    allow = read_allow(proj)
    tree = git(proj, "ls-tree", "-r", "-l", "-z", ref).stdout
    entries, out = [], []
    for rec in tree.split("\0"):
        if not rec:
            continue
        meta, _, path = rec.partition("\t")
        parts = meta.split()
        if len(parts) < 4 or parts[1] != "blob":
            continue
        size = int(parts[3]) if parts[3].isdigit() else None
        out += _scan_name(path, size)
        dep = _dep_note(path)
        if dep:
            out.append(dep)
        if size is not None and size <= TEXT_SCAN_BYTES:
            entries.append((path, parts[2]))
    blobs = _cat_blobs(proj, sorted({o for _, o in entries}))
    for path, oid in entries:
        raw = blobs.get(oid, b"")
        for n, l in enumerate(raw.decode("utf-8", "replace").splitlines(), start=1):
            out += _scan_line(path, n, l)
    return _split(_filter(out, allow))


def scan_range(proj, rev_range):
    """(blocks, notes) over every commit of `rev_range` (None = all of HEAD): the publish check. Findings carry the
    short `commit` they came from."""
    allow = read_allow(proj)
    spec = [rev_range] if isinstance(rev_range, str) else list(rev_range or ["HEAD"])
    revs = git(proj, "rev-list", *spec).stdout.split()
    out = []
    for c in revs:
        # --diff-merges=first-parent: a merge is diffed against its first parent only (plain diff-tree prints nothing
        # for a merge; -m --first-parent still diffs every parent on git 2.39)
        out += _scan_diff(proj, ["diff-tree", "-r", "--root", "--diff-merges=first-parent", c], allow, commit=c[:12])
    return _split(_filter(out, allow))


# --- events ------------------------------------------------------------------------------------

def _state(proj):
    try:
        with open(os.path.join(proj, ".harness", "state.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _steps(proj, event):
    return [s for s in _state(proj).get("steps", []) if isinstance(s, dict)]


def _milestone(proj, event):
    m = event.get("milestone")
    if isinstance(m, str) and m:
        return m
    steps = _steps(proj, event)
    return steps[0].get("milestone") if steps and isinstance(steps[0].get("milestone"), str) else None


def _step(proj, event):
    for s in reversed(_steps(proj, event)):
        if s.get("n") == event.get("n"):
            return s
    return None


def event_files(proj, event):
    """The paths (as written, not yet resolved on disk) the event's commit may hold (spec 4.1 table)."""
    kind = event.get("kind")
    if kind == "approved":
        # the first approval also adopts the scaffold new-project.sh copied (Task 16: until `ship M1` it was in no
        # save point, so an /undo shelved the project's .gitignore, AGENTS.md and README.md); once tracked, never again.
        # CRITIQUE.md on every approval: the stage machine needs this milestone's round before the build loop, so an
        # /undo that shelved or reverted it sent /go back to a paid critic turn. BRAINSTORM.md holds the human's decisions.
        tracked = _tracked(proj)
        return ["BRIEF.md", "ARCHITECTURE.md", "DESIGN.md", "PLAN.md", "design/mockups/",
                "CRITIQUE.md", "BRAINSTORM.md",
                *(p for p in SCAFFOLD if not any(t == p or (p.endswith("/") and t.startswith(p)) for t in tracked))]
    if kind in ("tests", "testfix"):
        return ["tests/acceptance/", "QA.md"]
    if kind == "step":
        step = _step(proj, event) or {}
        files = [f for f in (event.get("files") or step.get("files") or []) if isinstance(f, str)]
        n = event.get("n")
        return [*files, f"requests/step{n}.md", f"RESEARCH/step{n}.md"]
    if kind == "qa":
        if str(event.get("verdict", "")).upper() != "PASS":
            return ["QA.md"]
        cm = _milestone(proj, event)
        files = [f for s in _steps(proj, event) if s.get("milestone") == cm
                 for f in s.get("files") or [] if isinstance(f, str)]
        return [*dict.fromkeys(files), "tests/", "QA.md"]
    if kind == "visual":
        return ["VISUAL.md"]
    if kind == "review":
        return ["REVIEW.md"]
    if kind == "ship":
        return ["."]
    return []


def _message(proj, event):
    """(subject, body or None) for the event, or (None, reason) when it cannot be named."""
    kind = event.get("kind")
    verdict = str(event.get("verdict", "")).upper()
    if kind == "approved":
        sha = str(event.get("sha12") or "")
        return (f"approved {sha}", None) if sha else (None, "approved event has no sha12")
    if kind in ("tests", "ship"):
        m = _milestone(proj, event)
        if not m:
            return None, f"{kind} event has no milestone"
        return (f"M{m.lstrip('Mm')} acceptance tests (red by design)" if kind == "tests" else f"ship {m}"), None
    if kind in ("step", "testfix") and not isinstance(event.get("n"), int):
        return None, f"{kind} event has no step number"
    if kind == "testfix":
        return f"tests revised for step {event['n']}", None
    if kind == "step":
        step = _step(proj, event) or {}
        title = event.get("title") or step.get("title") or "done"
        files = [f for f in (event.get("files") or step.get("files") or []) if isinstance(f, str)]
        return f"step {event['n']}: {title}", ("files: " + ", ".join(files) if files else None)
    if kind == "qa":
        if verdict == "PASS":
            k = event.get("fix_round")
            return (f"fix round {k} verified: QA PASS" if isinstance(k, int) and k > 0 else "verify: QA PASS"), None
        if verdict == "FAIL":
            return "verify: QA FAIL", None
        return None, "qa event verdict must be PASS or FAIL"
    if kind in ("visual", "review"):
        return (f"{kind}: {verdict}", None) if verdict else (None, f"{kind} event has no verdict")
    return None, f"unknown event kind: {kind!r}"


# --- staging -----------------------------------------------------------------------------------

def _tracked(proj):
    return [p for p in git(proj, "ls-files", "-z").stdout.split("\0") if p]


def _resolve(proj, rel, tracked):
    """`rel` spelled as it is on disk (or as git tracks it), or None when it is neither on disk nor tracked, or
    escapes the project. A trailing '/' (a folder) is kept."""
    if not rel or os.path.isabs(rel) or "\0" in rel:
        return None
    folder = rel.replace("\\", "/").endswith("/")
    norm = posixpath.normpath(rel.replace("\\", "/"))
    if norm == ".":
        return "."
    if norm == ".." or norm.startswith("../"):
        return None
    cur, actual = proj, []
    for part in norm.split("/"):
        try:
            names = os.listdir(cur)
        except OSError:
            names = []
        hit = part if part in names else next((n for n in names if n.lower() == part.lower()), None)
        if hit is None:
            actual = None
            break
        actual.append(hit)
        cur = os.path.join(cur, hit)
    if actual is not None:
        return "/".join(actual) + ("/" if folder and os.path.isdir(cur) else "")
    low = norm.lower()
    for t in tracked:
        if t.lower() == low:
            return t
        if t.lower().startswith(low + "/"):
            return t[:len(norm)] + "/"
    return None


def _stage(proj, paths):
    """Stage the event's paths. `git add` exits 1 when a NAMED path is ignored, even a tracked one, so the paths are
    split: tracked files go through `add -u` (modifications and deletions, no ignored-path refusal) and new files that
    are not ignored are listed by git itself and added by name. A named path that is ignored and untracked is skipped."""
    specs = [f":(literal){p}" for p in paths if p != "."]
    if "." in paths:
        git(proj, "add", "-A", "--", ".")
    if not specs:
        return
    tracked = git(proj, "ls-files", "-z", "--", *specs).stdout
    if tracked:
        git(proj, "add", "-u", "--pathspec-from-file=-", "--pathspec-file-nul", input="\0".join(specs) + "\0")
    new = [p for p in git(proj, "ls-files", "-o", "--exclude-standard", "-z", "--", *specs).stdout.split("\0") if p]
    if new:
        git(proj, "add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul",
            input="\0".join(f":(literal){p}" for p in new) + "\0")


def _busy(proj):
    """Why a commit must not happen now (mid-merge/rebase, detached HEAD), or None."""
    for name, what in (("MERGE_HEAD", "a merge"), ("CHERRY_PICK_HEAD", "a cherry-pick"), ("REVERT_HEAD", "a revert"),
                       ("rebase-merge", "a rebase"), ("rebase-apply", "a rebase")):
        p = git(proj, "rev-parse", "--git-path", name).stdout.strip()
        if p and os.path.exists(p if os.path.isabs(p) else os.path.join(proj, p)):
            return f"git is in the middle of {what}; finish or abort it, then /go"
    if git(proj, "symbolic-ref", "-q", "HEAD", check=False).returncode != 0:
        return "git is on a detached HEAD (no branch); check out a branch, then /go"
    return None


def checkpoint(proj, event):
    """Commit the files `event` owns, after the scan. Returns {ok, sha, event, message, block, notes}; never writes
    state. Nothing staged -> ok with sha None."""
    proj = os.path.abspath(proj)
    res = {"ok": False, "sha": None, "event": event, "message": "", "block": None, "notes": []}

    def stop(rule, message, file=None, line=None):
        res["message"] = message
        res["block"] = {"event": event, "file": file, "line": line, "rule": rule, "message": message}
        return res

    if _agent_shell():  # R19, here so the in-process callers (harness_state.save_point) refuse as the CLI does
        return stop("agent", AGENT_REFUSAL)
    if not isinstance(event, dict):
        return stop("event", "the event must be a JSON object")
    subject, body = _message(proj, event) if os.path.isdir(proj) else (None, f"{proj} is not a folder")
    if subject is None:
        return stop("event", body)
    if not own_repo(proj):
        return stop("own-repo", "this project is not its own git repository (git init inside the project first); "
                                "refusing to touch any other repository")
    try:
        busy = _busy(proj)
        if busy:
            return stop("git", busy)
        for key in ("user.email", "user.name"):
            if not git(proj, "config", key, check=False).stdout.strip():
                return stop("identity", IDENTITY_MESSAGE)
        git(proj, "reset", "-q", check=False)  # a save point holds only its own files, whatever else was staged
        tracked = _tracked(proj)
        paths = [r for r in (_resolve(proj, p, tracked) for p in event_files(proj, event)) if r]
        if event["kind"] != "ship":  # only a ship saves the whole tree; '.', './' or 'src/..' elsewhere is a mistake
            paths = [p for p in paths if p != "."]
        paths = list(dict.fromkeys(paths))
        if paths:
            # No exclusion pathspecs on add: git add exits 1 when one names an ignored path that is still tracked.
            # Stage, then unstage the fixed exclusions (a reset pathspec that matches nothing is fine).
            _stage(proj, paths)
            git(proj, "reset", "-q", "--", *(e[len(":(exclude)"):] for e in FIXED_EXCLUSIONS), check=False)
        if git(proj, "diff", "--cached", "--quiet", check=False).returncode == 0:
            res.update(ok=True, message="nothing to save: the event changed no file")
            return res
        blocks, notes = scan_staged(proj)
        res["notes"] = notes
        if blocks:
            b = blocks[0]
            where = b["file"] + (f":{b['line']}" if b["line"] else "")
            git(proj, "reset", "-q", check=False)
            fix = "delete the file" if b["rule"] in ("env-file", "key-file") else "edit the file"
            return stop(b["rule"], f"{b['rule']} in {where}: {fix}, or add a line to .harness/scan-allow "
                                   f"({b['file']}:{b['rule']}), then /go", b["file"], b["line"])
        trailer = f"Harness-Event: {event['kind']}"
        text = subject + "\n\n" + (body + "\n\n" if body else "") + trailer + "\n"
        git(proj, "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "--cleanup=verbatim", "-F", "-",
            input=text)
        res.update(ok=True, sha=git(proj, "rev-parse", "HEAD").stdout.strip(), message=subject)
        return res
    except subprocess.CalledProcessError as exc:
        git(proj, "reset", "-q", check=False)
        return stop("git", (exc.stderr or exc.stdout or str(exc)).strip() or "git failed")
    except (OSError, subprocess.SubprocessError) as exc:
        return stop("git", f"git could not run: {exc}")


# --- milestone tag and /undo (spec 5.1, 5.2) ---------------------------------------------------

def tag_commit(proj, name):
    """The commit the tag `name` points at (an annotated tag is peeled), or None when there is no such tag."""
    r = git(proj, "rev-parse", "-q", "--verify", f"refs/tags/{name}^{{commit}}", check=False)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def tag_milestone(proj, n, title):
    """Tag HEAD `m<n>` (annotated, message = the milestone title). Retry-safe: the tag already at HEAD is ok (skipped);
    the tag on another commit is refused (a milestone ships once). Returns {ok, tag, sha, action, message}; never
    writes state."""
    proj = os.path.abspath(proj)
    name = f"m{n}"
    res = {"ok": False, "tag": name, "sha": None, "action": None, "message": ""}
    if _agent_shell():
        res["message"] = "checkpoint.py tag is not for agent shells"
        return res
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        res["message"] = "the milestone number must be a positive integer"
        return res
    if not os.path.isdir(proj) or not own_repo(proj):
        res["message"] = ("this project is not its own git repository (git init inside the project first); "
                          "refusing to touch any other repository")
        return res
    try:
        head = git(proj, "rev-parse", "-q", "--verify", "HEAD", check=False).stdout.strip()
        if not head:
            res["message"] = f"there is no commit to tag as {name} yet"
            return res
        existing = tag_commit(proj, name)
        if existing:
            if existing == head:
                res.update(ok=True, sha=head, action="exists", message=f"tag {name} is already at {head[:7]}")
            else:
                res["message"] = (f"tag {name} already points at {existing[:7]}, not at the current commit "
                                  f"{head[:7]}: a milestone ships once (delete the tag by hand only if you are sure)")
            return res
        for key in ("user.email", "user.name"):
            if not git(proj, "config", key, check=False).stdout.strip():
                res["message"] = IDENTITY_MESSAGE
                return res
        text = (str(title).strip() if isinstance(title, str) else "") or f"M{n}"
        git(proj, "-c", "tag.gpgsign=false", "tag", "-a", "--cleanup=verbatim", "-F", "-", name, head,
            input=text + "\n")
        res.update(ok=True, sha=head, action="created", message=f"tagged {name} at {head[:7]}")
        return res
    except subprocess.CalledProcessError as exc:
        res["message"] = (exc.stderr or exc.stdout or str(exc)).strip() or "git failed"
        return res
    except (OSError, subprocess.SubprocessError) as exc:
        res["message"] = f"git could not run: {exc}"
        return res


def undo(proj, now):
    """Shelve everything since the last save point: `git stash push -u` (never commits first) in the project's own
    repo, minus the fixed exclusions (they are never saved, so they are not 'since the save point'). Returns {ok,
    label, restore, message}. Refuses in an agent shell, in a project that is not its own repo, while a
    checkpoint_block is set and while a turn is running; deletes .harness/snapshot.json so the next turn does not
    blame the undone files on its step. Nothing to undo -> ok with no label."""
    proj = os.path.abspath(proj)
    slug = os.path.basename(proj)
    res = {"ok": False, "label": None, "restore": None, "message": ""}
    if _agent_shell():
        res["message"] = "checkpoint.py undo is not for agent shells"
        return res
    if not os.path.isdir(proj) or not own_repo(proj):
        res["message"] = ("this project is not its own git repository (git init inside the project first); "
                          "refusing to touch any other repository")
        return res
    if _state(proj).get("checkpoint_block"):
        res["message"] = (f"a save point is blocked: its files are uncommitted on purpose. Fix what /status {slug} "
                          f"names, then /go {slug}; /undo would shelve that work")
        return res
    import harness_state as hs  # here, not at the top: harness_state imports this module lazily
    running = hs._running(proj, f"/undo {slug}")
    if running:
        res["message"] = running
        return res
    pushed = False
    try:
        if not git(proj, "rev-parse", "-q", "--verify", "HEAD", check=False).stdout.strip():
            res["message"] = "there is no save point yet (no commit): nothing to go back to"
            return res
        git(proj, "reset", "-q", check=False)  # unstaged: status then lists plain paths, no renames
        # the changed paths, minus the fixed exclusions; named one by one so an ignored .harness/ (or a project whose
        # .gitignore lacks it) never reaches the stash
        changed = [e[3:] for e in git(proj, "status", "--porcelain", "-z", "-uall", "--", ".",
                                      *FIXED_EXCLUSIONS).stdout.split("\0") if len(e) > 3]
        if not changed:
            res.update(ok=True, message="nothing to undo: the project already equals the last save point")
            return res
        label = f"harness-undo {slug} {now}"
        # git cannot shelve another repository: an untracked one (with -uall a path ending in "/") or a tracked
        # submodule (a gitlink, mode 160000, shown ` M sub` when its commit or contents moved). Stashing them only makes
        # an empty entry or none, so they are left out of the stash and named in the message
        gitlinks = {e.split("\t", 1)[1] for e in git(proj, "ls-files", "-s", "-z").stdout.split("\0")
                    if e.startswith("160000 ") and "\t" in e}
        nested = [p for p in changed if p.endswith("/") or p in gitlinks]
        changed = [p for p in changed if p not in nested]
        if not changed:
            res.update(ok=True, message="nothing was shelved: only nested git repositories changed ("
                       + ", ".join(nested) + "); git does not shelve those, they stay as they are")
            return res
        top = git(proj, "rev-parse", "-q", "--verify", "refs/stash", check=False).stdout.strip()
        pushed = True
        git(proj, "stash", "push", "-u", "-m", label, "--pathspec-from-file=-", "--pathspec-file-nul",
            input="\0".join(f":(literal){p}" for p in changed) + "\0")
        sha = git(proj, "rev-parse", "-q", "--verify", "refs/stash", check=False).stdout.strip()
        if not sha or sha == top:  # whatever the cause, no new entry: never hand back an older stash as ours
            res.update(ok=True, message="nothing was shelved: git made no stash entry (" + ", ".join(changed)
                       + "); your files are as they were")
            return res
    except subprocess.CalledProcessError as exc:
        res["message"] = ((exc.stderr or exc.stdout or str(exc)).strip() or "git failed") + (
            f". Check `git stash list` in mini-projects/{slug}: a stash entry may exist" if pushed else "")
        return res
    except (OSError, subprocess.SubprocessError) as exc:
        res["message"] = f"git could not run: {exc}"
        return res
    try:
        os.remove(os.path.join(proj, ".harness", "snapshot.json"))
    except OSError:
        pass
    restore = f"git stash apply {sha}"
    left = (f" Left in place (nested git repositories, which git does not shelve): {', '.join(nested)}." if nested
            else "")
    res.update(ok=True, label=label, restore=restore,
               message=f'UNDONE: everything since the last save point is shelved as "{label}".{left} To bring it back, '
                       f"run in mini-projects/{slug}: {restore}")
    return res


def publish(proj, confirm, run=subprocess.run):
    """/publish: re-scan every commit not yet on the remote (all of them when there is no `origin`), then push the
    current branch and tags. A BLOCK refuses. Notes, or no `origin` (the `gh repo create` line), wait for `confirm`
    (the human's `yes`); gh is never called without it. Returns {ok, pushed, needs_yes, blocks, notes, message}."""
    proj = os.path.abspath(proj)
    slug = os.path.basename(proj)
    res = {"ok": False, "pushed": False, "needs_yes": False, "blocks": [], "notes": [], "message": ""}
    if _agent_shell():
        res["message"] = "checkpoint.py publish is not for agent shells"
        return res
    if not os.path.isdir(proj) or not own_repo(proj):
        res["message"] = ("this project is not its own git repository (git init inside the project first); "
                          "refusing to touch any other repository")
        return res
    try:
        if not git(proj, "rev-parse", "-q", "--verify", "HEAD", check=False).stdout.strip():
            res["message"] = "there is no commit to publish yet"
            return res
        branch = git(proj, "symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip()
        if not branch:
            res["message"] = "HEAD is detached: switch to a branch before publishing"
            return res
        has_origin = git(proj, "remote", "get-url", "origin", check=False).returncode == 0
        # exactly what `push origin <branch> --tags` sends: the branch and every tag, minus what origin already has
        blocks, notes = scan_range(proj, [f"refs/heads/{branch}", "--tags", "--not", "--remotes=origin"])
        res.update(blocks=blocks, notes=notes)
        if blocks:
            b = blocks[0]
            tags = git(proj, "tag", "--points-at", b.get("commit", "HEAD"), check=False).stdout.split()
            via = f" (tag {', '.join(tags)})" if tags else ""
            res["message"] = (f"{len(blocks)} secret(s) in commits not yet published, nothing pushed. First: commit "
                              f"{b.get('commit', '?')}{via}, {b['file']} line {b['line']} ({b['rule']}). Rewriting history "
                              "is manual (HANDBOOK); an allowed line goes in .harness/scan-allow.")
            return res
        gh_line = f"gh repo create {slug} --private --source . --remote origin"
        if not confirm and (notes or not has_origin):
            res.update(ok=True, needs_yes=True)
            parts = []
            if notes:
                parts.append(f"{len(notes)} note(s) to look at: " + "; ".join(
                    f"{n['file']}:{n['line']} ({n['rule']})" for n in notes[:20]))
            if not has_origin:
                parts.append(f"there is no origin yet, so this will run: {gh_line}")
            res["message"] = " | ".join(parts) + f" -- to go ahead, run: /publish {slug} yes"
            return res
        env = _env()
        if not has_origin:
            r = run(gh_line.split(), cwd=proj, capture_output=True, text=True, env=env, timeout=300)
            if r.returncode != 0:
                res["message"] = "gh repo create failed: " + ((r.stderr or r.stdout or "").strip() or "no output")
                return res
        r = run([*GIT_BASE, "-C", proj, "push", "origin", branch, "--tags"], capture_output=True, text=True, env=env,
                timeout=300)
        if r.returncode != 0:
            res["message"] = "git push failed: " + ((r.stderr or r.stdout or "").strip() or "no output")
            return res
        res.update(ok=True, pushed=True, message=f"PUBLISHED: {branch} and its tags are pushed to origin.")
        return res
    except subprocess.CalledProcessError as exc:
        res["message"] = (exc.stderr or exc.stdout or str(exc)).strip() or "git failed"
        return res
    except (OSError, subprocess.SubprocessError) as exc:
        res["message"] = f"could not run: {exc}"
        return res


# --- command line ------------------------------------------------------------------------------

AGENT_REFUSAL = "checkpoint.py commit is not for agent shells"


def _agent_shell():
    # opencode marks every agent shell with AGENT=1 and OPENCODE_SESSION_ID; the plugin and the templates have neither
    return os.environ.get("AGENT") == "1" or bool(os.environ.get("OPENCODE_SESSION_ID"))


def _undo_cli(text):
    """checkpoint.py undo "<args>": the project is resolved as /go resolves it (a name, or the current one)."""
    import harness_state as hs
    workshop = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out, err = hs.resolve_command(workshop, text)
    if out is None:
        print("REFUSED: " + err)
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = undo(os.path.join(workshop, "mini-projects", out.strip()), now)
    print(res["message"] if res["ok"] else "REFUSED: " + res["message"])
    return 0 if res["ok"] else 1


def _publish_cli(text):
    """checkpoint.py publish "[slug] [yes]"."""
    import harness_state as hs
    workshop = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parts = (text or "").split()
    confirm = bool(parts) and parts[-1] == "yes"
    out, err = hs.resolve_command(workshop, " ".join(parts[:-1] if confirm else parts))
    if out is None:
        print("REFUSED: " + err)
        return 1
    res = publish(os.path.join(workshop, "mini-projects", out.strip()), confirm)
    if res["needs_yes"]:
        print("NEEDS YES: " + res["message"])
    else:
        print(res["message"] if res["ok"] else "REFUSED: " + res["message"])
    return 0 if res["ok"] else 1


def main(argv):
    if _agent_shell():
        print(AGENT_REFUSAL, file=sys.stderr)
        return 2
    if len(argv) == 3 and argv[1] == "publish":
        return _publish_cli(argv[2])
    if len(argv) == 3 and argv[1] == "undo":
        return _undo_cli(argv[2])
    if len(argv) != 4 or argv[1] != "commit":
        print("usage: checkpoint.py commit <project> '<event json>' | undo '<project name, or empty>' | publish '[slug] [yes]'", file=sys.stderr)
        return 2
    try:
        event = json.loads(argv[3])
    except ValueError as exc:
        print(f"event is not JSON: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(checkpoint(argv[2], event)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

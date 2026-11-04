#!/usr/bin/env python3
"""/deploy (v4 piece 3, spec 7.2, 7.3): build the last shipped milestone's tag into a numbered release folder, run it
as a macOS LaunchAgent, health-check it, and roll back on failure. Python 3 stdlib only.

    python3 scripts/deploy.py "[slug]"            deploy the last shipped milestone (tag m<k>)
    python3 scripts/deploy.py "rollback [slug]"   go back to the previous good release
    python3 scripts/deploy.py "stop [slug]"       stop the app and remove its LaunchAgent (releases and data stay)

Run only from the /deploy command template: it runs outside the agent sandbox, which denies launchctl. Refuses an
agent shell (AGENT=1 or OPENCODE_SESSION_ID). Never writes .harness/state.json: the deploy record is
<APPS_HOME>/<slug>/deploys.json. App home: releases/<n>-m<k>/, current (symlink), shared/ ($DATA_DIR), logs/.
"""
import http.client
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import checkpoint as cp  # noqa: E402
import harness_docs as hd  # noqa: E402
import harness_state as hs  # noqa: E402

HEALTH_TIMEOUT_S = 30
POLL_S = 0.5
RELEASES_KEPT = 3
BUILD_TIMEOUT_S = 900  # a hung build must not hang the /deploy template forever
LOG_LINES = 20
# <workshop>/apps, ignored by the workshop's repo (user, 2026-11-04; was ~/Projects/opencode-apps). Agents cannot
# write it: agent.sb lets an agent shell write only its own project, the safety gate confines write tools to
# mini-projects/<slug>/ and RESEARCH/. Env HARNESS_APPS_HOME overrides (tests).
APPS_HOME = os.path.join(os.path.dirname(HERE), "apps")
LABEL_PREFIX = "local.opencode-harness."
AGENT_SHELL = os.path.join(HERE, "sandbox", "agent-shell")
LAUNCHCTL = "/bin/launchctl"
RELEASE_RE = re.compile(r"(\d+)-(m\d+)")
AGENT_REFUSAL = "deploy.py is not for agent shells: only the human types /deploy"
OFFLINE = "no network: the app answers only on this Mac; re-run /deploy when online"


class DeployError(Exception):
    pass


def apps_home():
    return os.environ.get("HARNESS_APPS_HOME") or APPS_HOME


class App:
    """One project's deployment: where it lives and what its DEPLOY section says (`deploy`, from the tag)."""

    def __init__(self, slug, proj, home=None):
        self.slug, self.proj = slug, os.path.abspath(proj) if proj else None
        self.home = os.path.abspath(home or os.path.join(apps_home(), slug))
        self.deploy = {}
        self.label = LABEL_PREFIX + slug
        self.plist_path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", self.label + ".plist")
        self.public_host = None  # <LAN IP>:<port>, set per deploy

    def path(self, *p):
        return os.path.join(self.home, *p)


# --- the adapters (spec 7.3): adding a kind = one class + its tests + its name in harness_docs.KNOWN_KINDS -----------

class Adapter:
    def install(self, app, release):
        """Start (or restart) the app from <home>/current; raises DeployError."""
        raise NotImplementedError

    def restart(self, app):
        raise NotImplementedError

    def stop(self, app):
        raise NotImplementedError

    def health(self, app):
        """(ok, detail) of one health request."""
        raise NotImplementedError

    def pid(self, app):
        return None

    def lan_ip(self):
        return None

    def listeners(self, port):
        """[(pid, process name, working directory)] listening on TCP `port`."""
        return []


def plist_text(app, path_env):
    """The LaunchAgent plist (pure). `start` is ONE argument of the shell (never pasted into quotes): `sh -c '<script>'
    sh <current> <start>` runs it as `cd "$1" && exec /bin/sh -c "$2"`."""
    d = app.deploy
    return plistlib.dumps({
        "Label": app.label,
        "ProgramArguments": ["/bin/sh", "-c", 'cd "$1" && exec /bin/sh -c "$2"', "sh", app.path("current"), d["start"]],
        "EnvironmentVariables": {"PATH": path_env, "PORT": str(d["port"]), "DATA_DIR": app.path("shared"),
                                 "PUBLIC_HOST": app.public_host},
        "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 10,
        "StandardOutPath": app.path("logs", "stdout.log"), "StandardErrorPath": app.path("logs", "stderr.log"),
    }).decode("utf-8")


class ServiceAdapter(Adapter):
    """`kind: service`: a LaunchAgent in the human's GUI domain. Every command goes through `run` (injectable)."""

    def __init__(self, run=subprocess.run):
        self.run = run

    def _cmd(self, *args, timeout=60):
        try:
            return self.run(list(args), capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            return subprocess.CompletedProcess(list(args), 127, "", str(exc))

    def _target(self, app):
        return f"gui/{os.getuid()}/{app.label}"

    def _loaded(self, app):
        return self._cmd(LAUNCHCTL, "print", self._target(app)).returncode == 0

    def _check(self, r, what):
        if r.returncode:
            raise DeployError(f"launchctl {what} failed (exit {r.returncode}): {(r.stderr or r.stdout).strip()}")

    def pid(self, app):
        r = self._cmd(LAUNCHCTL, "print", self._target(app))
        m = re.search(r"^\s*pid = (\d+)\s*$", r.stdout or "", re.M) if r.returncode == 0 else None
        return int(m.group(1)) if m else None

    def install(self, app, release):
        text = plist_text(app, os.environ.get("PATH") or "/usr/bin:/bin:/usr/sbin:/sbin")
        old = _read(app.plist_path)
        _write(app.plist_path, text)
        if self._loaded(app):
            if old == text:
                return self.restart(app)
            self._bootout(app)  # launchd keeps the plist it loaded: a changed one (new LAN IP, PATH) needs a reload
        self._check(self._cmd(LAUNCHCTL, "bootstrap", f"gui/{os.getuid()}", app.plist_path), "bootstrap")

    def restart(self, app):
        self._check(self._cmd(LAUNCHCTL, "kickstart", "-k", self._target(app)), "kickstart")

    def _bootout(self, app):
        self._cmd(LAUNCHCTL, "bootout", self._target(app))
        for _ in range(50):
            if not self._loaded(app):
                return
            time.sleep(0.1)

    def stop(self, app):
        if self._loaded(app):
            self._bootout(app)
        try:
            os.remove(app.plist_path)  # else RunAtLoad starts the stopped app again at the next login
        except FileNotFoundError:
            pass

    def health(self, app):
        port, path = app.deploy["port"], app.deploy["health"]
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            try:
                conn.request("GET", path, headers={"Host": app.public_host})  # proves the app accepts the LAN host
                status = conn.getresponse().status
            finally:
                conn.close()
        except (OSError, http.client.HTTPException) as exc:
            return False, f"no answer on 127.0.0.1:{port} ({exc.__class__.__name__})"
        return 200 <= status < 300, f"HTTP {status}"

    def lan_ip(self):
        """IPv4 of the default-route interface (Bonjour is off on this Mac: no .local name), or None offline."""
        r = self._cmd("/sbin/route", "-n", "get", "default", timeout=10)
        m = re.search(r"^\s*interface:\s*(\S+)", r.stdout or "", re.M) if r.returncode == 0 else None
        if not m:
            return None
        ip = (self._cmd("/usr/sbin/ipconfig", "getifaddr", m.group(1), timeout=10).stdout or "").strip()
        return ip if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", ip) and not ip.startswith("127.") else None

    def listeners(self, port):
        r = self._cmd("/usr/sbin/lsof", "-nP", f"-iTCP:{int(port)}", "-sTCP:LISTEN", "-Fpc")
        out = []
        for line in (r.stdout or "").splitlines():
            if line[:1] == "p" and line[1:].isdigit():
                out.append([int(line[1:]), "", ""])
            elif line[:1] == "c" and out:
                out[-1][1] = line[1:]
        for e in out:
            cwd = self._cmd("/usr/sbin/lsof", "-a", "-p", str(e[0]), "-d", "cwd", "-Fn").stdout or ""
            e[2] = next((l[1:] for l in cwd.splitlines() if l.startswith("n")), "")
        return [tuple(e) for e in out]


ADAPTERS = {"service": ServiceAdapter}


# --- files -----------------------------------------------------------------------------------------------------------

def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:  # a binary plist is just "different", no crash
            return fh.read()
    except OSError:
        return None


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def load_deploys(app):
    try:
        rows = json.loads(_read(app.path("deploys.json")) or "[]")
    except ValueError:
        return []
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("n"), int)
            and RELEASE_RE.fullmatch(str(r.get("release")))] if isinstance(rows, list) else []


def save_deploys(app, rows):
    _write(app.path("deploys.json"), json.dumps(rows, indent=1) + "\n")


def _num(name):
    m = RELEASE_RE.fullmatch(name or "")
    return int(m.group(1)) if m else None


def current_release(app):
    """The release folder name `current` points at, or None (no link, or its folder is gone)."""
    try:
        name = os.path.basename(os.readlink(app.path("current")))
    except OSError:
        return None
    return name if _num(name) is not None and os.path.isdir(app.path("releases", name)) else None


def previous_release(app):
    """The newest release with ok: true older than `current` whose folder still exists, or None."""
    cur = _num(current_release(app))
    if cur is None:
        return None
    rows = [r for r in load_deploys(app) if r.get("ok") is True and r["n"] < cur
            and os.path.isdir(app.path("releases", r["release"]))]
    return max(rows, key=lambda r: r["n"]) if rows else None


def _switch(app, name):
    """Point `current` at releases/<name> (relative), atomically."""
    tmp = app.path(f".current.{os.getpid()}")
    try:
        os.remove(tmp)
    except FileNotFoundError:
        pass
    os.symlink(os.path.join("releases", name), tmp)
    os.replace(tmp, app.path("current"))


def _unlink_current(app):
    try:
        os.remove(app.path("current"))
    except FileNotFoundError:
        pass


def _prune(app):
    """Keep the newest RELEASES_KEPT release folders, and always `current` and its previous."""
    try:
        names = sorted((n for n in os.listdir(app.path("releases")) if _num(n) is not None), key=_num, reverse=True)
    except OSError:
        return
    prev = previous_release(app)
    keep = set(names[:RELEASES_KEPT]) | {current_release(app), prev["release"] if prev else None}
    for n in names:
        if n not in keep:
            shutil.rmtree(app.path("releases", n), ignore_errors=True)


def _log_sizes(app):
    out = {}
    for name in ("stderr.log", "stdout.log"):
        try:
            out[name] = os.path.getsize(app.path("logs", name))
        except OSError:
            out[name] = 0
    return out


def _log_tail(app, since):
    """The last LOG_LINES lines each log got since `since` (sizes from _log_sizes)."""
    out = []
    for name, start in since.items():
        try:
            with open(app.path("logs", name), "rb") as fh:
                fh.seek(start)
                lines = fh.read().decode("utf-8", "replace").splitlines()[-LOG_LINES:]
        except OSError:
            continue
        if lines:
            out += [f"last lines of logs/{name}:", *("  " + l for l in lines)]
    return out


# --- the frame (spec 7.2) ----------------------------------------------------------------------------------------------

def _config(app, tag):
    """The DEPLOY section of ARCHITECTURE.md as committed at `tag` (the reviewed, shipped code's own config)."""
    r = cp.git(app.proj, "show", f"refs/tags/{tag}:ARCHITECTURE.md", check=False)
    if r.returncode:
        raise DeployError(f"tag {tag} has no ARCHITECTURE.md")
    try:
        return hd.parse_deploy(r.stdout)
    except hd.DocError as exc:
        raise DeployError(f"{exc} (at tag {tag}; fix it, ship the next milestone, then /deploy {app.slug})")


def _ready(app):
    """Readiness (spec 7.2 step 1): the tag of the last shipped milestone, its DEPLOY (into app.deploy) and the scan
    notes; raises DeployError."""
    if not app.proj or not os.path.isdir(app.proj) or not cp.own_repo(app.proj):
        raise DeployError(f"mini-projects/{app.slug} is not its own git repository: refusing to touch any other one")
    try:
        shipped = hs.load(app.proj).get("milestones_shipped") or []
    except hs.StateError as exc:
        raise DeployError(str(exc))
    if not shipped:
        raise DeployError(f"nothing shipped yet: only a shipped milestone deploys (/ship {app.slug}, then /ship "
                          f"{app.slug} yes)")
    tag = "m" + str(shipped[-1]).lstrip("Mm")
    if not re.fullmatch(r"m\d+", tag) or not cp.tag_commit(app.proj, tag):
        raise DeployError(f"{shipped[-1]} is recorded shipped but its tag {tag} is missing: /ship {app.slug} yes "
                          f"tags it")
    app.deploy = _config(app, tag)
    if app.deploy["kind"] == "none":
        return tag, []
    blocks, notes = cp.scan_ref(app.proj, f"refs/tags/{tag}")
    if blocks:
        b = blocks[0]
        raise DeployError(f"the tagged tree {tag} fails the secret scan: {b['rule']} in {b['file']}"
                          + (f":{b['line']}" if b["line"] else "") + " (fix it and ship again, or add a line to "
                          f".harness/scan-allow: {b['file']}:{b['rule']})")
    return tag, notes


def _port_check(app, adapter):
    """The DEPLOY port is free or held by this app's own process (its working directory is in the app home)."""
    port, own = app.deploy["port"], adapter.pid(app)
    mine, shop = os.path.realpath(app.home).lower(), os.path.realpath(apps_home())
    for pid, name, cwd in adapter.listeners(port):
        real = os.path.realpath(cwd) if cwd else ""
        if pid == own or real.lower() == mine or real.lower().startswith(mine + os.sep):
            continue
        rest = real[len(shop) + 1:] if real.lower().startswith(shop.lower() + os.sep) else ""
        who = f"the deployed app {rest.split(os.sep)[0]}" if rest else f"{name or 'a process'} (pid {pid})"
        raise DeployError(f"port {port} is in use by {who}: stop it, or change the DEPLOY port in ARCHITECTURE.md")


def _archive(app, tag, rel):
    """`git archive <tag>` into rel: exactly the tagged tree, no .git, no untracked files."""
    os.makedirs(rel)
    a = subprocess.run([*cp.GIT_BASE, "-C", app.proj, "archive", "--format=tar", f"refs/tags/{tag}"],
                       capture_output=True, env=cp._env(), timeout=300)
    if a.returncode:
        raise DeployError(f"git archive {tag} failed: {a.stderr.decode('utf-8', 'replace').strip()}")
    t = subprocess.run(["/usr/bin/tar", "-xf", "-", "-C", rel], input=a.stdout, capture_output=True, timeout=300)
    if t.returncode:
        raise DeployError(f"unpacking {tag} failed: {t.stderr.decode('utf-8', 'replace').strip()}")


def _build(app, rel):
    """The DEPLOY build, in the release folder, through agent-shell (agent.sb: writes only in the release; secret-looking
    variables stripped first, spec 7.2 step 3)."""
    root = os.path.realpath(rel)
    env = {**os.environ, "AGENT": "1", "HARNESS_SANDBOX_ROOT": root}
    try:
        r = subprocess.run([AGENT_SHELL, "-c", app.deploy["build"]], cwd=root, env=env, capture_output=True, text=True,
                           errors="replace", stdin=subprocess.DEVNULL, timeout=BUILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise DeployError(f"the build ran over {BUILD_TIMEOUT_S} s: {app.deploy['build']}")
    except OSError as exc:
        raise DeployError(f"the build could not run: {exc}")
    if r.returncode:
        tail = (r.stdout + r.stderr).splitlines()[-LOG_LINES:]
        raise DeployError(f"the build failed (exit {r.returncode}): {app.deploy['build']}"
                          + "".join("\n  " + l for l in tail))


def _start(app, adapter):
    """Install/restart, then poll health up to HEALTH_TIMEOUT_S; only an answer from a PID other than the one before
    the restart counts (spec 7.2 step 6). Returns (ok, detail, log lines written meanwhile)."""
    since, old = _log_sizes(app), adapter.pid(app)
    try:
        adapter.install(app, current_release(app))
    except DeployError as exc:
        return False, str(exc), _log_tail(app, since)
    end, detail = time.monotonic() + HEALTH_TIMEOUT_S, "the app did not start"
    while True:
        pid = adapter.pid(app)
        if pid is None:
            detail = "the app is not running (it may exit at start: see the log lines)"
        elif pid == old:
            detail = "the old process is still the one running"
        else:
            ok, detail = adapter.health(app)
            if ok and adapter.pid(app) == pid:
                return True, detail, []
        if time.monotonic() >= end:
            return False, f"no healthy answer within {HEALTH_TIMEOUT_S} s: {detail}", _log_tail(app, since)
        time.sleep(POLL_S)


def _host(app, adapter):
    ip = adapter.lan_ip()
    app.public_host = f"{ip or '127.0.0.1'}:{app.deploy['port']}"
    return ip


def _run_release(app, adapter, name):
    """Make releases/<name> current and start it with ITS OWN DEPLOY (the start and port of the tag it was built from,
    not those of the release that failed). Returns (ok, detail, log lines, LAN IP)."""
    try:
        app.deploy = _config(app, RELEASE_RE.fullmatch(name).group(2))
    except (DeployError, OSError, subprocess.SubprocessError) as exc:
        return False, str(exc), [], None
    ip = _host(app, adapter)
    _switch(app, name)
    return (*_start(app, adapter), ip)


def _owner_home(app):
    """The other checkout's app home that runs this slug, else None: the label (and its plist) is one per Mac, each
    checkout has its own apps/. The plist names `current` as ProgramArguments[4] (plist_text). A home that is gone owns
    nothing (its LaunchAgent runs no code), so this checkout may take the label over."""
    try:
        with open(app.plist_path, "rb") as fh:  # bytes: launchd also takes a binary plist (plutil, defaults write)
            home = os.path.dirname(plistlib.loads(fh.read())["ProgramArguments"][4])
    except Exception:  # missing, or a plist that does not parse (ExpatError is no ValueError): owner unknown, replaceable
        return None
    same = os.path.realpath(home).lower() == os.path.realpath(app.home).lower()
    return None if same or not os.path.isdir(home) else home


def _owner(app):
    """The refusal when another checkout runs this slug (deploy, rollback and stop: never touch its app), else None."""
    home = _owner_home(app)
    return home and _refused(f"{app.slug} runs from {home}, another checkout (one LaunchAgent per slug on this Mac): "
                             f"/deploy stop {app.slug} there, or leave it running there")


def _refused(message):
    return {"ok": False, "message": "REFUSED: " + message}


def deploy(app, adapter, now):
    """/deploy: the steps of spec 7.2. Returns {ok, message}; never writes state.json."""
    if cp._agent_shell():
        return _refused(AGENT_REFUSAL)
    if refused := _owner(app):  # before anything is touched
        return refused
    try:
        tag, notes = _ready(app)
        if app.deploy["kind"] == "none":
            return {"ok": True, "message": f"NOTHING TO DEPLOY: ARCHITECTURE.md at {tag} says kind: none (a library "
                                           "or a tool, not a service)"}
        _port_check(app, adapter)
    except (DeployError, OSError, subprocess.SubprocessError) as exc:
        return _refused(str(exc))
    for d in ("releases", "shared", "logs"):
        os.makedirs(app.path(d), exist_ok=True)
    rows = load_deploys(app)
    n = 1 + max([r["n"] for r in rows] + [_num(x) or 0 for x in os.listdir(app.path("releases"))], default=0)
    name = f"{n}-{tag}"
    ip = _host(app, adapter)
    url = f"http://{app.public_host}"
    row = {"n": n, "tag": tag, "release": name, "at": now, "ok": False, "url": url, "reason": None}
    note = [f"scan notes (not blocking): " + ", ".join(f"{f['file']} {f['rule']}" for f in notes)] if notes else []
    try:
        _archive(app, tag, app.path("releases", name))
        if app.deploy["build"]:
            _build(app, app.path("releases", name))
    except (DeployError, OSError, subprocess.SubprocessError) as exc:
        row["reason"] = str(exc)
        save_deploys(app, rows + [row])
        _prune(app)
        return {"ok": False, "message": f"DEPLOY FAILED: {exc}\nNothing was switched: the running release (if any) "
                                        "stays."}
    before = current_release(app)  # what was running: a failure goes back to it, not to a release rolled back from
    _switch(app, name)
    ok, detail, logs = _start(app, adapter)
    row.update(ok=ok, reason=None if ok else detail)
    save_deploys(app, rows + [row])
    if ok:
        _prune(app)
        lines = [f"DEPLOYED: {app.slug} {tag} as release {n}. Open {url}"] + ([OFFLINE] if not ip else []) + note
        return {"ok": True, "message": "\n".join(lines)}
    out = [f"DEPLOY FAILED: release {n} ({tag}): {detail}"]
    prev = next((r for r in reversed(rows) if r["release"] == before and r.get("ok") is True), None) \
        if before and os.path.isdir(app.path("releases", before)) else None
    prev = prev or previous_release(app)
    if prev:
        ok2, detail2, _, _ = _run_release(app, adapter, prev["release"])
        out.append(f"Rolled back to release {prev['n']} ({prev['tag']})"
                   + (f": it answers at http://{app.public_host}" if ok2
                      else f", but it does not answer either: {detail2}"))
    else:
        adapter.stop(app)
        _unlink_current(app)
        out.append("There is no previous release to go back to (no previous release): the app is stopped and its "
                   "LaunchAgent removed, so it does not restart in a loop.")
    _prune(app)
    return {"ok": False, "message": "\n".join(out + logs)}


def rollback(app, adapter, now):
    """/deploy rollback: the previous good release becomes `current`, restarted and health-checked."""
    if cp._agent_shell():
        return _refused(AGENT_REFUSAL)
    if refused := _owner(app):
        return refused
    cur, prev = current_release(app), previous_release(app)
    if not prev:
        return _refused(f"no previous release to roll back to (a release with a good health check, older than the "
                        f"current one, whose folder still exists): /status {app.slug}")
    ok, detail, logs, ip = _run_release(app, adapter, prev["release"])
    if ok:
        return {"ok": True, "message": "\n".join([f"ROLLED BACK: {app.slug} runs release {prev['n']} ({prev['tag']}). "
                                                  f"Open http://{app.public_host}"] + ([OFFLINE] if not ip else []))}
    out = [f"ROLLBACK FAILED: release {prev['n']} ({prev['tag']}): {detail}"]
    ok2, detail2, _, _ = _run_release(app, adapter, cur)
    out.append(f"Back on release {_num(cur)}" + ("." if ok2 else f", which does not answer either: {detail2}"))
    return {"ok": False, "message": "\n".join(out + logs)}


def stop(app, adapter):
    """/deploy stop: bootout and remove the LaunchAgent; every release and shared/ stay."""
    if cp._agent_shell():
        return _refused(AGENT_REFUSAL)
    if refused := _owner(app):  # stopping here would stop the app another checkout runs
        return refused
    if not os.path.exists(app.plist_path) and adapter.pid(app) is None:
        return {"ok": True, "message": f"nothing to stop: {app.slug} is not running as a service"}
    adapter.stop(app)
    return {"ok": True, "message": f"STOPPED: {app.slug}. Its releases and data stay in {app.home}; /deploy {app.slug} "
                                   f"starts it again (as a new release)."}


def status_line(slug, shipped=False):
    """The /status line: not deployed / stopped / running, and a newer failed deploy. None when there is nothing to
    say (nothing shipped, never deployed). Never raises."""
    try:
        app = App(slug, None)
        cur = current_release(app)
        if not cur:
            return (f"deploy: not deployed (/deploy {slug})" if shipped else "deploy: not deployed") \
                if shipped or os.path.isdir(app.home) else None
        rows = load_deploys(app)
        row = next((r for r in reversed(rows) if r["release"] == cur), {})
        tag = row.get("tag") or RELEASE_RE.fullmatch(cur).group(2)
        other = _owner_home(app)
        if other:  # /deploy refuses here: name the checkout that runs it
            line = f"deploy: stopped here ({tag}, release {_num(cur)}); {slug} runs from {other}"
        elif not os.path.exists(app.plist_path):
            line = f"deploy: stopped ({tag}, release {_num(cur)}); /deploy {slug} starts it again"
        else:
            line = f"deploy: {tag}, release {_num(cur)}, {row.get('url') or '?'} (since {row.get('at') or '?'})"
        last = rows[-1] if rows else None
        if last and last.get("ok") is not True and last["n"] > _num(cur):
            line += f"; last deploy failed (release {last['n']}): {str(last.get('reason')).splitlines()[0]}"
        return line
    except Exception:  # /status must never fail over a deploy record
        return "deploy: record unreadable"


# --- command line -------------------------------------------------------------------------------------------------

def parse_args(text):
    """`[slug] [rollback|stop]`, the verb first or last: (verb, slug text)."""
    words = (text or "").split()
    verb = "deploy"
    if words and words[0].lower() in ("rollback", "stop"):
        verb = words.pop(0).lower()
    elif words and words[-1].lower() in ("rollback", "stop"):
        verb = words.pop().lower()
    return verb, " ".join(words)


def main(argv):
    if cp._agent_shell():  # R19: AGENT=1 or OPENCODE_SESSION_ID
        print("REFUSED: " + AGENT_REFUSAL)
        return 2
    if len(argv) != 2:
        print('usage: deploy.py "[slug] | rollback [slug] | stop [slug]"', file=sys.stderr)
        return 2
    verb, rest = parse_args(argv[1])
    workshop = os.path.dirname(HERE)
    out, err = hs.resolve_command(workshop, rest)
    if out is None:
        print("REFUSED: " + err)
        return 1
    slug = out.strip()
    app = App(slug, os.path.join(workshop, "mini-projects", slug))
    adapter = ServiceAdapter()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = (rollback(app, adapter, now) if verb == "rollback" else stop(app, adapter) if verb == "stop"
           else deploy(app, adapter, now))
    print(res["message"])
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

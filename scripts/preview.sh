#!/usr/bin/env bash
# Start a project's preview server for an AGENT (the designer), detached, on the project's own port.
#
# usage:  bash scripts/preview.sh <slug>      (agents only: AGENT=1)
#
# Runs ARCHITECTURE.md's `- preview: <command>` from the project root with PORT=<the port in state.json>, in the
# caller's own (sandboxed) shell, as its own process group. Pid and log: $TMPDIR (else /tmp)/opencode-preview-<slug>.*,
# because the sandbox denies .harness/ and a file in the project would trip the after-turn file check. A second call
# while it runs reports the address. Agents only on purpose: the human's unsandboxed shell never runs project code.
set -euo pipefail

if [ "${AGENT:-}" != "1" ]; then
  echo "REFUSED: preview.sh runs project code, so only an agent's sandboxed shell (AGENT=1) may run it." >&2
  exit 3
fi

SLUG="${1:-}"
case "$SLUG" in
  ""|_*|cap|retry|*[!a-z0-9_-]*) echo "usage: bash scripts/preview.sh <slug>   (slug: lowercase letters, digits, - or _)" >&2; exit 2 ;;
esac

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ="$(cd "$HERE/.." && pwd)/mini-projects/$SLUG"
if [ -L "$PROJ" ] || [ ! -d "$PROJ" ]; then
  echo "REFUSED: there is no project mini-projects/$SLUG." >&2
  exit 1
fi

exec python3 - "$HERE" "$PROJ" <<'PY'
import os, subprocess, sys, time

here, proj = sys.argv[1], sys.argv[2]
sys.path.insert(0, here)
sys.dont_write_bytecode = True
import harness_state as hs  # noqa: E402


def die(msg, code=1):
    print(f"REFUSED: {msg}", file=sys.stderr)
    sys.exit(code)


try:
    state = hs.load(proj)
except hs.StateError:
    die(hs.unreadable_reason(proj))
d = hs.docs(proj)
if d["arch"] is None:
    die(d["errors"].get("ARCHITECTURE.md", "ARCHITECTURE.md is not valid"))
cmd = d["arch"]["preview"]
if not cmd:
    die("ARCHITECTURE.md has no '- preview: <command>' line in STACK: the architect writes it for a ui: yes project")
port = state.get("port")
if not isinstance(port, int) or isinstance(port, bool):
    die("the project has no port yet: /go assigns one when the approved plan starts")

url = f"http://localhost:{port}/"
slug = os.path.basename(proj)
tmp = os.environ.get("TMPDIR") or "/tmp"
pid_file = os.path.join(tmp, f"opencode-preview-{slug}.pid")
log_file = os.path.join(tmp, f"opencode-preview-{slug}.log")


def running():
    """The pid of a preview we started that still lives (it leads its own process group), else None."""
    try:
        with open(pid_file, encoding="utf-8") as fh:
            pid = int(fh.read().split()[0])
        os.kill(pid, 0)
        return pid if os.getpgid(pid) == pid else None
    except (OSError, ValueError, IndexError):
        return None


pid = running()
if pid:
    print(f"preview already running (pid {pid}): {url}")
    sys.exit(0)

with open(log_file, "wb") as log:
    proc = subprocess.Popen(["/bin/sh", "-c", cmd], cwd=proj, env={**os.environ, "PORT": str(port)},
                            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
with open(pid_file, "w", encoding="utf-8") as fh:
    fh.write(f"{proc.pid}\n")
for _ in range(10):  # a command that dies at once is reported now, not discovered by a blank page
    if proc.poll() is not None:
        break
    time.sleep(0.1)
if proc.poll() is not None:
    os.remove(pid_file)
    try:
        with open(log_file, encoding="utf-8", errors="replace") as fh:
            tail = " | ".join(fh.read().strip().splitlines()[-5:])
    except OSError:
        tail = ""
    print(f"preview command exited at once (exit {proc.returncode}): {cmd}" + (f"\nlast output: {tail}" if tail else ""),
          file=sys.stderr)
    sys.exit(1)
print(f"preview started (pid {proc.pid}): {url}")
PY

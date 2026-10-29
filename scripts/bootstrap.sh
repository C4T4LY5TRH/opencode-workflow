#!/usr/bin/env bash
# Check that this machine can run the harness, then run the bench.
# Writes nothing outside the repo. Safe to re-run.
#   bash scripts/bootstrap.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSHOP="$(cd "$HERE/.." && pwd)"
WANT_OPENCODE="2.1.3"   # version the harness was verified against (AUDIT.md)
fail=0
ok()   { echo "  [ OK ] $*"; }
warn() { echo "  [WARN] $*"; }
bad()  { echo "  [FAIL] $*"; fail=1; }

echo "workshop: $WORKSHOP"

if command -v opencode >/dev/null 2>&1; then
  v="$(opencode --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  if [ "$v" = "$WANT_OPENCODE" ]; then ok "opencode $v"; else warn "opencode $v (verified on $WANT_OPENCODE; check AUDIT.md section 2 facts still hold)"; fi
else
  bad "opencode not found - install it first: https://opencode.ai"
fi

if command -v node >/dev/null 2>&1; then
  major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
  if [ "$major" -ge 22 ]; then ok "node $(node --version) (runs the .ts gate test)"; else bad "node $(node --version) - need 22+ for scripts/gate-test.mjs"; fi
else
  bad "node not found (needed for Playwright MCP and the gate test)"
fi

if command -v python3 >/dev/null 2>&1; then ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"; else bad "python3 not found (bench, html2md)"; fi

if [ -x /usr/bin/sandbox-exec ]; then
  ok "sandbox-exec present (every agent shell runs in it)"
else
  bad "/usr/bin/sandbox-exec missing - agent shells need macOS; without it every agent shell command is refused"
fi
case "$WORKSHOP" in
  /tmp/*|/private/tmp/*|/var/folders/*|/private/var/folders/*)
    bad "workshop is inside a temp dir - the sandbox lets agents write temp dirs, so it could not confine them here" ;;
esac

if ls "$HOME/Library/Caches/ms-playwright" 2>/dev/null | grep -q chromium; then
  ok "playwright chromium present"
else
  warn "playwright chromium missing - run: npx playwright install chromium   (needed for /research on rendered pages)"
fi

# a global harness copy would merge with this one and break plugin loading
gdir="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
for d in agents commands skills plugins brain; do
  if [ -d "$gdir/$d" ]; then bad "global harness folder found: $gdir/$d - remove it (the harness lives in this repo only)"; fi
done

# v3 runs the orchestrator, planner, builder, reviewer, hunter and brain on Anthropic Claude. The key lives in
# opencode's auth store (outside the repo). Only the provider line is checked; the credential is never read or shown.
# Captured first: `grep -q` stops reading at the first match, sed then dies of SIGPIPE, and pipefail made that a WARN.
auth_list="$(opencode auth list 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' || true)"
if grep -qi 'anthropic' <<<"$auth_list"; then
  ok "anthropic credential stored (opencode auth list)"
else
  warn "no Anthropic credential stored - the Claude agents will fail on their first call. Run (you, not an agent):"
  echo "         opencode auth login      # choose Anthropic, paste the API key"
fi

# Settings that live OUTSIDE the repo and so do not travel with it (TELEPORT.md). Warn, don't fail:
# the harness works without them, but opencode would then also see your Claude Code skills.
svc="$(opencode service get 2>/dev/null || true)"
if printf '%s' "$svc" | grep -q '"OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"'; then
  ok "claude skills hidden from opencode (service env OPENCODE_DISABLE_CLAUDE_CODE_SKILLS)"
else
  warn "opencode can see ~/.claude/skills. To hide them:"
  echo "         opencode service set env OPENCODE_DISABLE_CLAUDE_CODE_SKILLS 1 && opencode service restart"
fi
if [ -d "$HOME/.agents/skills" ] && [ -n "$(ls -A "$HOME/.agents/skills" 2>/dev/null | grep -v '^\.DS_Store$')" ]; then
  if grep -q 'integration.use' "$gdir/opencode.json" 2>/dev/null; then
    ok "skills under ~/.agents are covered by a global policy"
  else
    warn "skills in ~/.agents/skills are still visible. Hide each with a policy in $gdir/opencode.json:"
    echo '         "policies": [{ "action": "integration.use", "resource": "skill:<id>", "effect": "deny" }]'
  fi
fi

mkdir -p "$WORKSHOP/.harness"
echo
echo "bench:"
bash "$HERE/bench.sh" | sed 's/^/  /'
[ "${PIPESTATUS[0]}" -eq 0 ] || fail=1

echo
if [ "$fail" = 0 ]; then
  echo "READY. Start the harness with:  cd \"$WORKSHOP\" && opencode"
else
  echo "NOT READY - fix the [FAIL] lines above, then re-run."
  echo "(plugins-alive fails until opencode has started once in the workshop: run opencode, quit, re-run this.)"
fi
exit "$fail"

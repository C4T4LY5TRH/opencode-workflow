#!/usr/bin/env python3
"""The routing decision behind /go (stdlib only).

usage: python3 scripts/next.py <slug>      (run from the /go command template, never from an agent shell)

Reads the project's recorded state through harness_state.phase() and prints a fixed contract (spec section 8):
PHASE, STEP, FILES, CHECK, LAST FAILURE, AGENT, INSTRUCTION, STATUS, NEXT COMMAND. The routing is code; the
orchestrator only carries out the INSTRUCTION. In phase FIX this script adds one to fix_rounds (it is trusted
code run from a human-typed template); every other phase is read-only.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import harness_state as hs  # noqa: E402

SLUG_RE = re.compile(r"[a-z0-9-][a-z0-9_-]*")  # same rule as approve.sh
FAILURE_LINES = 10
NEW_HINT = '/new "<goal>"'


def _none(message, status="no project", nxt=NEW_HINT):
    """A contract that stops: no worker, just a message to relay."""
    return _render({"PHASE": "NONE", "AGENT": "none", "INSTRUCTION": message,
                    "STATUS": status, "NEXT COMMAND": nxt})


def _render(c):
    """Fixed key order; keys that are None are left out; a multi-line value is indented under its key."""
    order = ("PHASE", "STEP", "FILES", "CHECK", "LAST FAILURE", "AGENT", "INSTRUCTION", "STATUS", "NEXT COMMAND")
    lines = []
    for key in order:
        val = c.get(key)
        if val is None:
            continue
        first, *rest = val.split("\n")
        lines.append(f"{key}: {first}".rstrip())
        lines.extend("  " + l for l in rest)
    return "\n".join(lines) + "\n"


def _plan_instruction(slug):
    return (f"Delegate to the planner: read mini-projects/{slug}/BRIEF.md and write mini-projects/{slug}/PLAN.md, "
            "and nothing else, in exactly this format. "
            "A '## SCOPE' section with one line 'IN: ... / OUT: ... / LATER: ...'. "
            "A '## STEPS' section where each step is a heading '### <n>. <title>' (numbered 1, 2, 3 with no gaps) "
            "followed by the lines '- files: <path>, <path>', "
            "'- done when: `<one shell command that exits 0 when the step works>`' "
            "(exactly one command, inside exactly one pair of backticks, no backticks inside it) and '- risk: ...'. "
            "A '## ACCEPTANCE' section. Keep the steps small. "
            f"The checks run from inside mini-projects/{slug}: write the files paths and the done-when command "
            f"as if you are inside that folder (no 'mini-projects/{slug}/' prefix, no cd). Then stop.")


def _build_instruction(slug, step, failure):
    files = ", ".join(step.get("files") or []) or "(none listed)"
    check = step.get("check") or ""
    text = (f"Delegate to the builder: build step {step.get('n')} ('{step.get('title')}') of mini-projects/{slug}. "
            f"Touch only these files unless the step cannot work without more: {files} "
            f"(paths are relative to mini-projects/{slug}). "
            "Do not edit PLAN.md or REVIEW.md. ")
    if failure:
        text += "The last check failed (see LAST FAILURE): fix the cause first. "
    text += (f"When the step is built, run `{check}` verbatim as your LAST command, with the shell workdir "
             f"mini-projects/{slug} (workdir mini-projects/{slug}, no cd, no wrapper, no changes to the command). "
             "Do not run anything after it. Then stop: one step per /go.")
    return text


def _review_instruction(slug):
    return (f"Delegate to the reviewer: review mini-projects/{slug} against its PLAN.md and write "
            f"mini-projects/{slug}/REVIEW.md, and change no code. REVIEW.md needs: a line 'VERDICT: SHIP', "
            "'VERDICT: FIX FIRST' or 'VERDICT: REWORK'; the findings, each with the file and what is wrong; and a "
            "'## Blind spots' section (what this review could not check, what could still go wrong). "
            "Never assume the step checks still pass (a later step or a fix may have broken one): run every step "
            "check from PLAN.md that is a test runner you may run, and list the others under Blind spots "
            "(a check you may not run is never a finding and never a reason for FIX FIRST). "
            f"Run shell commands one per call with workdir mini-projects/{slug}: read-only git, ls/cat/grep and "
            "test runners (node --test <file>, npm test, pytest) only; cd, echo, node -e and && or ; chains are "
            "refused. Then stop.")


def _fix_instruction(slug, rounds):
    return (f"Delegate to the builder: fix the findings in mini-projects/{slug}/REVIEW.md (fix round {rounds} of "
            f"{hs.FIX_LIMIT}). Fix only what the review lists. Do not edit PLAN.md or REVIEW.md. "
            "Then stop: the next /go asks for a fresh review.")


def _status(slug, ph):
    if ph["phase"] == "BUILD" and ph["step"]:
        return f"{slug}  BUILD  step {ph['step'].get('n')}/{ph['total']}  {ph['reason']}"
    return f"{slug}  {ph['phase']}  {ph['done']}/{ph['total']} steps done  {ph['reason']}"


def contract(workshop, slug):
    """The text block for /go. Never raises for a bad slug, a missing project or unreadable state."""
    slug = (slug or "").strip()
    if not SLUG_RE.fullmatch(slug):
        return _none("No project name given, or the name is not valid (lowercase letters, digits, - or _). "
                     'Usage: /go <slug>. To start a project: /new "<goal>".')
    proj = os.path.join(workshop, "mini-projects", slug)
    if not os.path.isdir(proj):
        return _none(f'There is no project mini-projects/{slug}. Start one with /new "<goal>", or check the name. '
                     "Usage: /go <slug>.", status=f"{slug}  no such project")

    ph = hs.phase(proj)
    name, step = ph["phase"], ph["step"]
    c = {"PHASE": name, "AGENT": "none", "NEXT COMMAND": f"/go {slug}"}

    if step:
        c["STEP"] = f"{step.get('n')} of {ph['total']} — {step.get('title')}"
        c["FILES"] = ", ".join(step.get("files") or []) or None
        c["CHECK"] = step.get("check")
    failure = None
    if step and (step.get("attempts") or 0) > 0 and step.get("last_failure"):
        failure = "\n".join(str(step["last_failure"]).splitlines()[:FAILURE_LINES])
        c["LAST FAILURE"] = failure

    if name == "PLAN":
        c["AGENT"], c["INSTRUCTION"] = "planner", _plan_instruction(slug)
        c["NEXT COMMAND"] = f"/approve {slug}"
    elif name == "APPROVE":
        c["INSTRUCTION"] = f"Nothing to delegate. Tell the human: {ph['reason']}."
        c["NEXT COMMAND"] = f"/approve {slug}"
    elif name == "BUILD":
        c["AGENT"], c["INSTRUCTION"] = "builder", _build_instruction(slug, step, failure)
    elif name == "REVIEW":
        c["AGENT"], c["INSTRUCTION"] = "reviewer", _review_instruction(slug)
    elif name == "FIX":
        # trusted code run from the human-typed /go template: count this round before handing it out
        try:
            state = hs.load(proj)
            state["fix_rounds"] = (state.get("fix_rounds") or 0) + 1
            hs.save(proj, state)
        except (OSError, hs.StateError) as exc:
            return _none(f"Could not record the fix round ({exc.__class__.__name__}); nothing was changed. "
                         "Run /go from the chat prompt, not from an agent shell.",
                         status=_status(slug, ph), nxt=f"/go {slug}")
        c["AGENT"], c["INSTRUCTION"] = "builder", _fix_instruction(slug, state["fix_rounds"])
    elif name == "STUCK":
        c["INSTRUCTION"] = f"Nothing to delegate. Tell the human: {ph['reason']}."
        if step:
            c["NEXT COMMAND"] = (f"fix it by hand, then /approve {slug} (resets attempts), then /go {slug}; "
                                 f"or edit mini-projects/{slug}/PLAN.md, then /approve {slug}")
        else:
            c["NEXT COMMAND"] = (f"read mini-projects/{slug}/REVIEW.md, fix by hand, then /go {slug}; "
                                 f"or edit PLAN.md then /approve {slug}")
    elif name == "SHIP":
        c["INSTRUCTION"] = f"Nothing to delegate. Tell the human: {ph['reason']}."
        c["NEXT COMMAND"] = f"/ship {slug}"
    # STATUS is read after the worker has run, so keep it neutral
    if name == "PLAN":
        ph = dict(ph, reason="planning: PLAN.md is being written")
    elif name == "REVIEW":
        ph = dict(ph, reason="reviewing: REVIEW.md is being written")
    elif name == "BUILD" and step:
        ph = dict(ph, reason=f"building step {step.get('n')}: {step.get('title')}")
    c["STATUS"] = _status(slug, ph)
    return _render(c)


def main(argv):
    workshop = os.path.dirname(HERE)
    if len(argv) != 2:
        sys.stdout.write(_none("Usage: /go <slug>. To start a project: /new \"<goal>\"."))
        return 0
    try:
        sys.stdout.write(contract(workshop, argv[1]))
    except Exception as exc:  # last resort: /go must never show a traceback
        sys.stdout.write(_none(f"Could not work out the next step ({exc.__class__.__name__}: {exc}).",
                               status="error", nxt="/status"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

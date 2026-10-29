#!/usr/bin/env python3
"""Unit tests for scripts/harness_state.py (plan parsing, approval, tree hash, phase).

Run: python3 scripts/state-test.py
Temp projects live INSIDE the workshop as .gate-test-state-* (gitignored), never in a temp dir,
and are removed in tearDown.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSHOP = os.path.dirname(HERE)
sys.dont_write_bytecode = True  # keep scripts/ free of __pycache__
sys.path.insert(0, HERE)

import harness_state as hs  # noqa: E402

PLAN = """## SCOPE
IN: habits / OUT: sync / LATER: charts
## STEPS
### 1. store habits
- files: src/store.js, test/store.test.js
- done when: `node --test test/store.test.js`
- risk: none
### 2. add the cli
- files: src/cli.js
- done when: `node src/cli.js --help`
## ACCEPTANCE
It works.
"""

STEPS = [
    {"n": 1, "title": "store habits", "files": ["src/store.js", "test/store.test.js"],
     "check": "node --test test/store.test.js"},
    {"n": 2, "title": "add the cli", "files": ["src/cli.js"], "check": "node src/cli.js --help"},
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def human_env():
    env = dict(os.environ)
    env.pop("AGENT", None)
    env.pop("OPENCODE_SESSION_ID", None)
    return env


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix=".gate-test-state-", dir=WORKSHOP)
        self.proj = os.path.join(self.tmp, "demo")
        os.makedirs(os.path.join(self.proj, "src"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        p = os.path.join(self.proj, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def plan(self, text=PLAN):
        self.write("PLAN.md", text)


class ParseTests(Base):
    def test_parse_good_plan(self):
        self.assertEqual(hs.parse_plan(PLAN), STEPS)

    def test_parse_crlf_and_trailing_spaces(self):
        messy = "\r\n".join(line + "   " for line in PLAN.split("\n"))
        self.assertIn("\r\n", messy)
        self.assertEqual(hs.parse_plan(messy), STEPS)

    def test_parse_refuses(self):
        cases = {
            "no steps": ("## SCOPE\nx\n## STEPS\nnothing here\n## ACCEPTANCE\ny\n", "no steps"),
            "gap": (PLAN.replace("### 2. add the cli", "### 3. add the cli"), "step 3"),
            "missing done when": (PLAN.replace("- done when: `node src/cli.js --help`\n", ""), "step 2"),
            "no backticks": (PLAN.replace("`node src/cli.js --help`", "node src/cli.js --help"), "step 2"),
            "two backtick pairs": (PLAN.replace("`node src/cli.js --help`", "`node a` and `node b`"), "step 2"),
            "no steps section": ("### 1. a\n- done when: `true`\n", "STEPS"),
        }
        for name, (text, needle) in cases.items():
            with self.subTest(name):
                with self.assertRaises(hs.PlanError) as cm:
                    hs.parse_plan(text)
                self.assertIn(needle, str(cm.exception))

    def test_parse_refuses_duplicate_number(self):
        with self.assertRaises(hs.PlanError) as cm:
            hs.parse_plan(PLAN.replace("### 2. add the cli", "### 1. add the cli"))
        self.assertIn("step 1", str(cm.exception))

    def test_parse_ignores_headings_outside_steps(self):
        text = PLAN + "### 9. not a step\n- done when: nothing\n"
        self.assertEqual(hs.parse_plan(text), STEPS)


class ApproveTests(Base):
    def test_approve_records_steps_and_hash(self):
        self.plan()
        st = hs.approve(self.proj, "2026-10-25T10:00:00Z")
        with open(os.path.join(self.proj, "PLAN.md"), "rb") as fh:
            self.assertEqual(st["plan_sha256"], sha(fh.read()))
        self.assertEqual(st["approved_at"], "2026-10-25T10:00:00Z")
        self.assertEqual(len(st["steps"]), 2)
        self.assertEqual(st["fix_rounds"], 0)
        for s in st["steps"]:
            self.assertEqual((s["done_at"], s["attempts"], s["last_failure"]), (None, 0, None))
        self.assertEqual(hs.load(self.proj), st)

    def test_reapprove_keeps_done_unchanged_steps(self):
        self.plan()
        st = hs.approve(self.proj, "t1")
        st["steps"][0]["done_at"] = "t-done"
        st["steps"][1]["done_at"] = "t-done"
        st["fix_rounds"] = 2
        hs.save(self.proj, st)
        self.plan(PLAN.replace("--help", "--version"))  # step 2's check changed
        st2 = hs.approve(self.proj, "t2")
        self.assertEqual(st2["steps"][0]["done_at"], "t-done")
        self.assertIsNone(st2["steps"][1]["done_at"])
        self.assertEqual(st2["steps"][1]["check"], "node src/cli.js --version")
        self.assertEqual(st2["fix_rounds"], 0)

    def test_new_plan_drops_the_old_review(self):
        # M1: a review judged the old plan; the same plan re-approved (e.g. after STUCK) keeps it
        self.plan()
        st = hs.approve(self.proj, "t1")
        st["review"] = {"tree_sha256": hs.tree_sha256(self.proj), "verdict": "SHIP", "at": "t"}
        hs.save(self.proj, st)
        self.assertIn("review", hs.approve(self.proj, "t2"))
        self.plan(PLAN.replace("--help", "--version"))
        self.assertNotIn("review", hs.approve(self.proj, "t3"))
        self.assertNotIn("review", hs.load(self.proj))

    def test_reapprove_title_change_resets(self):
        self.plan()
        st = hs.approve(self.proj, "t1")
        st["steps"][0]["done_at"] = "t-done"
        hs.save(self.proj, st)
        self.plan(PLAN.replace("store habits", "keep habits"))
        self.assertIsNone(hs.approve(self.proj, "t2")["steps"][0]["done_at"])

    def test_approve_bad_plan_records_nothing(self):
        self.plan()
        before = hs.approve(self.proj, "t1")
        self.plan(PLAN.replace("`node src/cli.js --help`", "no backticks"))
        with open(os.path.join(self.proj, ".harness", "state.json"), "rb") as fh:
            raw = fh.read()
        with self.assertRaises(hs.PlanError):
            hs.approve(self.proj, "t2")
        with open(os.path.join(self.proj, ".harness", "state.json"), "rb") as fh:
            self.assertEqual(fh.read(), raw)
        self.assertEqual(hs.load(self.proj), before)

    def test_approve_without_plan(self):
        with self.assertRaises(hs.PlanError):
            hs.approve(self.proj, "t")
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".harness")))

    def test_approve_recovers_corrupt_state(self):
        self.plan()
        self.write(".harness/state.json", "{")
        st = hs.approve(self.proj, "t")
        self.assertEqual(hs.load(self.proj), st)


class TreeTests(Base):
    def test_tree_hash_ignores_docs_and_changes_on_code(self):
        self.write("src/a.js", "one\n")
        base = hs.tree_sha256(self.proj)
        for doc in ("REVIEW.md", "PLAN.md", "NOTES.md", "RESEARCH/x.md", ".harness/state.json"):
            self.write(doc, "anything\n")
        self.assertEqual(hs.tree_sha256(self.proj), base)
        self.write("src/a.js", "two\n")
        changed = hs.tree_sha256(self.proj)
        self.assertNotEqual(changed, base)
        self.write("src/b.js", "new\n")
        self.assertNotEqual(hs.tree_sha256(self.proj), changed)

    def test_tree_hash_without_git(self):
        self.write("src/a.js", "one\n")
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".git")))
        h = hs.tree_sha256(self.proj)
        self.assertEqual(len(h), 64)
        self.assertEqual(h, hs.tree_sha256(self.proj))

    def test_tree_hash_with_git_untracked_and_ignored(self):
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        self.write(".gitignore", "junk.txt\n")
        self.write("src/a.js", "one\n")  # untracked only: still counted
        base = hs.tree_sha256(self.proj)
        self.write("junk.txt", "ignored\n")
        self.assertEqual(hs.tree_sha256(self.proj), base)
        self.write("src/a.js", "two\n")
        self.assertNotEqual(hs.tree_sha256(self.proj), base)

    def test_tree_hash_nested_in_other_repo_still_sees_files(self):
        # a project dir that is NOT its own repo, inside a repo that ignores it (like the workshop)
        self.write("src/a.js", "one\n")
        base = hs.tree_sha256(self.proj)
        self.write("src/a.js", "two\n")
        self.assertNotEqual(hs.tree_sha256(self.proj), base)

    def plant_fsmonitor(self, cfg_dir, extra=""):
        """A repo config whose core.fsmonitor touches a marker OUTSIDE the project (C1: run by unsandboxed git)."""
        marker = os.path.join(self.tmp, "FSMONITOR_RAN")
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, "config"), "a", encoding="utf-8") as fh:
            fh.write(f"[core]\n{extra}\tfsmonitor = \"touch {marker}; false\"\n")
        return marker

    def test_tree_hash_never_runs_a_planted_fsmonitor(self):
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        self.write("src/a.js", "one\n")
        marker = self.plant_fsmonitor(os.path.join(self.proj, ".git"))
        self.assertEqual(len(hs.tree_sha256(self.proj)), 64)
        self.assertIsNotNone(hs._git_files(self.proj))  # git still lists the files
        self.assertFalse(os.path.exists(marker), "harness git ran the repo's core.fsmonitor")

    def test_tree_hash_ignores_an_implicit_bare_repo(self):
        # no .git: HEAD/objects/refs/config at the project root make git treat the project itself as a repo
        for d in ("objects", "refs/heads"):
            os.makedirs(os.path.join(self.proj, d))
        self.write("HEAD", "ref: refs/heads/main\n")
        self.write("src/a.js", "one\n")
        marker = self.plant_fsmonitor(self.proj, f"\trepositoryformatversion = 0\n\tbare = false\n\tworktree = {self.proj}\n")
        self.assertEqual(len(hs.tree_sha256(self.proj)), 64)
        self.assertIsNone(hs._git_files(self.proj))  # refused: walked instead
        self.assertFalse(os.path.exists(marker), "harness git used a project-root config")

    def test_tree_hash_deleted_tracked_file(self):
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        self.write("src/a.js", "one\n")
        subprocess.run(["git", "add", "src/a.js"], cwd=self.proj, check=True)
        os.remove(os.path.join(self.proj, "src", "a.js"))
        self.assertEqual(len(hs.tree_sha256(self.proj)), 64)  # no crash


class StateTests(Base):
    def test_load_missing_is_empty(self):
        self.assertEqual(hs.load(self.proj), {})

    def test_corrupt_state(self):
        self.plan()
        self.write(".harness/state.json", "{")
        with self.assertRaises(hs.StateError):
            hs.load(self.proj)
        r = hs.phase(self.proj)
        self.assertEqual(r["phase"], "APPROVE")
        self.assertEqual(r["reason"], "state unreadable: /approve demo again")
        self.assertIsNone(r["step"])

    def test_state_not_an_object(self):
        self.write(".harness/state.json", "[1, 2]")
        with self.assertRaises(hs.StateError):
            hs.load(self.proj)

    def test_wrong_typed_state_is_unreadable_not_a_traceback(self):
        self.plan()
        with open(os.path.join(self.proj, "PLAN.md"), "rb") as fh:
            good = sha(fh.read())
        step = {"n": 1, "title": "t", "check": "true", "done_at": None, "attempts": 0, "last_failure": None}
        bad = {
            "steps null": {"plan_sha256": good, "steps": None},
            "steps int": {"plan_sha256": good, "steps": 5},
            "steps string": {"plan_sha256": good, "steps": "abc"},
            "step not dict": {"plan_sha256": good, "steps": [3]},
            "attempts str": {"plan_sha256": good, "steps": [{**step, "attempts": "x"}]},
            "attempts bool": {"plan_sha256": good, "steps": [{**step, "attempts": True}]},
            "n str": {"plan_sha256": good, "steps": [{**step, "n": "1"}]},
            "done_at int": {"plan_sha256": good, "steps": [{**step, "done_at": 5}]},
            "fix_rounds str": {"plan_sha256": good, "steps": [step], "fix_rounds": "a"},
            "review list": {"plan_sha256": good, "steps": [step], "review": [1]},
            "review verdict int": {"plan_sha256": good, "steps": [step], "review": {"verdict": 3}},
            "plan_sha256 int": {"plan_sha256": 7, "steps": [step]},
        }
        for name, state in bad.items():
            with self.subTest(name):
                self.write(".harness/state.json", json.dumps(state))
                with self.assertRaises(hs.StateError):
                    hs.load(self.proj)
                r = hs.phase(self.proj)
                self.assertEqual(r["phase"], "APPROVE")
                self.assertEqual(r["reason"], "state unreadable: /approve demo again")
                st = hs.approve(self.proj, "t")  # re-approval repairs it
                self.assertEqual(len(st["steps"]), 2)
                self.assertEqual(hs.phase(self.proj)["phase"], "BUILD")

    def test_save_creates_dir(self):
        hs.save(self.proj, {"a": 1})
        self.assertEqual(hs.load(self.proj), {"a": 1})


class PhaseTests(Base):
    def approved(self, **over):
        """Approve PLAN, then apply overrides to the state: steps_done=[n..], attempts={n: k}, review, fix_rounds."""
        self.plan()
        shutil.rmtree(os.path.join(self.proj, ".harness"), ignore_errors=True)  # fresh approval, nothing carried over
        st = hs.approve(self.proj, "t")
        for n in over.get("steps_done", []):
            st["steps"][n - 1]["done_at"] = "t-done"
        for n, k in over.get("attempts", {}).items():
            st["steps"][n - 1]["attempts"] = k
        if "fix_rounds" in over:
            st["fix_rounds"] = over["fix_rounds"]
        if "verdict" in over:
            st["review"] = {"tree_sha256": hs.tree_sha256(self.proj), "verdict": over["verdict"], "at": "t"}
        hs.save(self.proj, st)
        return st

    def expect(self, phase, n=None, done=None):
        r = hs.phase(self.proj)
        self.assertEqual(r["phase"], phase, r)
        if n is None:
            self.assertIsNone(r["step"], r)
        else:
            self.assertEqual(r["step"]["n"], n, r)
        if done is not None:
            self.assertEqual(r["done"], done, r)
        self.assertTrue(r["reason"])
        return r

    def test_stuck_step_hand_fix_then_approve_builds_it_again(self):
        # I2: the human's own !cmd fires no hooks, so a hand fix cannot clear attempts; /approve on the unchanged
        # plan does (done steps kept), and the next /go builds the stuck step again
        self.approved(steps_done=[1], attempts={2: 2})
        self.expect("STUCK", 2)
        self.write("src/cli.js", "fixed by hand\n")
        st = hs.approve(self.proj, "t2")
        self.assertEqual([s["attempts"] for s in st["steps"]], [0, 0])
        self.expect("BUILD", 2, 1)

    def test_phase_table(self):
        # row 1: no PLAN.md
        r = self.expect("PLAN")
        self.assertEqual(r["total"], 0)
        # row 2: PLAN.md present, never approved
        self.plan()
        self.expect("APPROVE")
        # row 2: plan changed after approval
        self.approved()
        self.plan(PLAN + "extra\n")
        self.expect("APPROVE")
        # row 3: BUILD, first step
        self.approved()
        r = self.expect("BUILD", 1, 0)
        self.assertEqual(r["total"], 2)
        # BUILD with one failed attempt (limit is 2)
        self.approved(attempts={1: 1})
        self.expect("BUILD", 1)
        # BUILD moves to step 2
        self.approved(steps_done=[1])
        self.expect("BUILD", 2, 1)
        # row 4: STUCK on a step
        self.approved(steps_done=[1], attempts={2: 2})
        r = self.expect("STUCK", 2)
        self.assertIn("2", r["reason"])
        self.assertIn("fix it by hand, then /approve demo (resets attempts), then /go demo", r["reason"])
        # row 5: all done, no review
        self.approved(steps_done=[1, 2])
        self.expect("REVIEW", None, 2)
        # REVIEW.md on disk but no review record: not fresh
        self.write("REVIEW.md", "VERDICT: SHIP\n")
        self.expect("REVIEW")
        # stale review: code changed after it
        self.approved(steps_done=[1, 2], verdict="SHIP")
        self.write("src/a.js", "changed after review\n")
        self.expect("REVIEW")
        # row 6: FIX (FIX FIRST and REWORK, rounds 0 and 1)
        self.write("src/a.js", "x\n")
        self.approved(steps_done=[1, 2], verdict="FIX FIRST", fix_rounds=0)
        self.expect("FIX")
        self.approved(steps_done=[1, 2], verdict="REWORK", fix_rounds=1)
        self.expect("FIX")
        # row 7: STUCK on fix rounds (no step)
        self.approved(steps_done=[1, 2], verdict="FIX FIRST", fix_rounds=2)
        r = self.expect("STUCK")
        self.assertIn("fix", r["reason"].lower())
        # row 8: SHIP (even if fix_rounds is used up)
        self.approved(steps_done=[1, 2], verdict="SHIP")
        self.expect("SHIP", None, 2)
        self.approved(steps_done=[1, 2], verdict="SHIP", fix_rounds=2)
        self.expect("SHIP")

    def test_phase_first_match_wins(self):
        # an undone step beats a fresh SHIP review
        self.approved(steps_done=[1], verdict="SHIP")
        self.expect("BUILD", 2)
        # STUCK step beats everything after it
        self.approved(steps_done=[], attempts={1: 3}, verdict="SHIP")
        self.expect("STUCK", 1)

    def test_phase_state_without_steps_asks_for_approval(self):
        self.plan()
        with open(os.path.join(self.proj, "PLAN.md"), "rb") as fh:
            digest = sha(fh.read())
        hs.save(self.proj, {"plan_sha256": digest, "approved_at": "old"})  # a v2-style state
        r = self.expect("APPROVE")
        self.assertIn("/approve demo", r["reason"])

    def test_review_verdict_reads_review_md(self):
        self.assertIsNone(hs.review_verdict(self.proj))
        for text, want in (("## VERDICT: SHIP\n", "SHIP"), ("VERDICT: fix first\nmore", "FIX FIRST"),
                           ("VERDICT: REWORK", "REWORK"), ("VERDICT: TODO\n", None), ("no verdict", None)):
            self.write("REVIEW.md", text)
            self.assertEqual(hs.review_verdict(self.proj), want, text)


class CliTests(Base):
    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, os.path.join(HERE, "harness_state.py"), *args],
                              capture_output=True, text=True, env=env or human_env())

    def test_cli_approve_ok(self):
        self.plan()
        r = self.run_cli("approve", self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("APPROVED:"), r.stdout)
        self.assertIn("2 steps", r.stdout)
        self.assertEqual(len(hs.load(self.proj)["steps"]), 2)

    def test_cli_approve_bad_plan(self):
        self.plan(PLAN.replace("### 2. add the cli", "### 3. add the cli"))
        r = self.run_cli("approve", self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("REFUSED:", r.stdout + r.stderr)
        self.assertIn("step 3", r.stdout + r.stderr)
        self.assertEqual(hs.load(self.proj), {})

    def test_cli_approve_refuses_agent_shell(self):
        self.plan()
        for var, val in (("AGENT", "1"), ("OPENCODE_SESSION_ID", "ses_x")):
            with self.subTest(var):
                r = self.run_cli("approve", self.proj, env={**human_env(), var: val})
                self.assertEqual(r.returncode, 3)
                self.assertIn("REFUSED:", r.stdout + r.stderr)
                self.assertEqual(hs.load(self.proj), {})

    def test_cli_approve_unwritable_state(self):
        self.plan()
        self.write(".harness", "i am a file, not a directory")
        r = self.run_cli("approve", self.proj)
        self.assertEqual(r.returncode, 1)
        self.assertIn("REFUSED: cannot write state", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_cli_tree(self):
        self.write("src/a.js", "one\n")
        r = self.run_cli("tree", self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), hs.tree_sha256(self.proj))

    def test_cli_review(self):
        self.write("src/a.js", "one\n")
        self.write("REVIEW.md", "## VERDICT: SHIP\n")
        r = self.run_cli("review", self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.count("\n"), 1)  # one JSON line
        self.assertEqual(json.loads(r.stdout), {"tree_sha256": hs.tree_sha256(self.proj), "verdict": "SHIP"})
        self.write("REVIEW.md", "## VERDICT: FIX FIRST\n")
        self.assertEqual(json.loads(self.run_cli("review", self.proj).stdout)["verdict"], "FIX FIRST")

    def test_cli_review_without_verdict(self):
        self.write("REVIEW.md", "looks fine to me\n")  # no VERDICT line
        self.assertIsNone(json.loads(self.run_cli("review", self.proj).stdout)["verdict"])
        os.remove(os.path.join(self.proj, "REVIEW.md"))  # no REVIEW.md at all
        r = self.run_cli("review", self.proj)
        self.assertEqual(r.returncode, 0)
        self.assertIsNone(json.loads(r.stdout)["verdict"])

    def test_cli_review_is_read_only(self):
        self.write("REVIEW.md", "## VERDICT: SHIP\n")
        self.run_cli("review", self.proj)
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".harness")))

    def test_cli_usage(self):
        self.assertEqual(self.run_cli().returncode, 2)
        self.assertEqual(self.run_cli("nope", self.proj).returncode, 2)


class NextTests(Base):
    """scripts/next.py: the routing contract behind /go (spec section 8)."""

    def setUp(self):
        super().setUp()
        # a workshop-shaped dir: <tmp>/mini-projects/demo
        self.shop = self.tmp
        self.proj = os.path.join(self.shop, "mini-projects", "demo")
        os.makedirs(os.path.join(self.proj, "src"))

    def contract(self, slug="demo"):
        import next as nx
        return nx.contract(self.shop, slug)

    def fields(self, text):
        """key -> value for top-level 'KEY: value' lines (continuation lines are indented)."""
        out = {}
        for line in text.splitlines():
            if line[:1] in (" ", "\t") or ": " not in line and not line.endswith(":"):
                continue
            key, _, val = line.partition(":")
            if key.isupper() or key in ("LAST FAILURE", "NEXT COMMAND"):
                out[key] = val.strip()
        return out

    def approved(self, **over):
        PhaseTests.approved(self, **over)

    def test_next_contract_per_phase(self):
        # PLAN: no PLAN.md
        f = self.fields(self.contract())
        self.assertEqual((f["PHASE"], f["AGENT"]), ("PLAN", "planner"))
        self.assertEqual(f["NEXT COMMAND"], "/approve demo")
        # APPROVE: PLAN.md never approved
        self.plan()
        f = self.fields(self.contract())
        self.assertEqual((f["PHASE"], f["AGENT"]), ("APPROVE", "none"))
        self.assertEqual(f["NEXT COMMAND"], "/approve demo")
        # BUILD
        self.approved()
        text = self.contract()
        f = self.fields(text)
        self.assertEqual((f["PHASE"], f["AGENT"]), ("BUILD", "builder"))
        self.assertEqual(f["STEP"], "1 of 2 \u2014 store habits")
        self.assertEqual(f["FILES"], "src/store.js, test/store.test.js")
        self.assertEqual(f["CHECK"], "node --test test/store.test.js")
        self.assertNotIn("LAST FAILURE", f)
        self.assertEqual(f["STATUS"].split()[:3], ["demo", "BUILD", "step"])
        self.assertIn("1/2", f["STATUS"])
        self.assertTrue(f["STATUS"].endswith("building step 1: store habits"), f["STATUS"])  # M3: neutral, read after the run
        self.assertEqual(f["NEXT COMMAND"], "/go demo")
        # STUCK on a step
        self.approved(steps_done=[1], attempts={2: 2})
        f = self.fields(self.contract())
        self.assertEqual((f["PHASE"], f["AGENT"]), ("STUCK", "none"))
        self.assertIn("fix it by hand, then /approve demo (resets attempts), then /go demo", f["NEXT COMMAND"])
        self.assertIn("/approve", f["INSTRUCTION"])
        # REVIEW
        self.approved(steps_done=[1, 2])
        text = self.contract()
        f = self.fields(text)
        self.assertEqual((f["PHASE"], f["AGENT"]), ("REVIEW", "reviewer"))
        self.assertNotIn("STEP", f)
        self.assertIn("REVIEW.md", f["INSTRUCTION"])
        self.assertIn("VERDICT:", f["INSTRUCTION"])
        self.assertIn("## Blind spots", f["INSTRUCTION"])
        # live run 2026-10-25: reviewers chained `cd`/`echo`/`node -e`, every call was refused
        self.assertIn("one per call with workdir mini-projects/demo", f["INSTRUCTION"])
        self.assertEqual(f["NEXT COMMAND"], "/go demo")
        # R24: every review (first one or after a fix round) runs the checks it may run; never "already passed"
        first = f["INSTRUCTION"]
        self.approved(steps_done=[1, 2], fix_rounds=1)
        f = self.fields(self.contract())
        self.assertEqual(f["PHASE"], "REVIEW")
        self.assertEqual(f["INSTRUCTION"], first)
        for text in (first, f["INSTRUCTION"]):
            self.assertNotIn("already passed", text)
            self.assertIn("run every step check from PLAN.md that is a test runner you may run", text)
            self.assertIn("list the others under Blind spots", text)
            # live run 2026-10-29: Haiku turned the checks it may not run (`test -f`, `sh x | diff`) into a MAJOR
            # three reviews in a row; no fix round can change that, so the loop never reached SHIP
            self.assertIn("a check you may not run is never a finding and never a reason for FIX FIRST", text)
        with open(os.path.join(WORKSHOP, ".opencode", "agents", "reviewer.md"), encoding="utf-8") as fh:
            self.assertIn("a check you may not run is never a finding and never a reason for FIX FIRST", fh.read())
        # FIX
        self.approved(steps_done=[1, 2], verdict="FIX FIRST", fix_rounds=0)
        f = self.fields(self.contract())
        self.assertEqual((f["PHASE"], f["AGENT"]), ("FIX", "builder"))
        self.assertEqual(f["NEXT COMMAND"], "/go demo")
        # STUCK on fix rounds
        self.approved(steps_done=[1, 2], verdict="REWORK", fix_rounds=2)
        f = self.fields(self.contract())
        self.assertEqual((f["PHASE"], f["AGENT"]), ("STUCK", "none"))
        # SHIP
        self.approved(steps_done=[1, 2], verdict="SHIP")
        f = self.fields(self.contract())
        self.assertEqual((f["PHASE"], f["AGENT"]), ("SHIP", "none"))
        self.assertEqual(f["NEXT COMMAND"], "/ship demo")
        # key order of a full contract (spec section 8)
        self.approved(attempts={1: 1})
        hs_state = hs.load(self.proj)
        hs_state["steps"][0]["last_failure"] = "boom"
        hs.save(self.proj, hs_state)
        keys = [l.split(":")[0] for l in self.contract().splitlines() if l and l[0] not in " \t"]
        self.assertEqual(keys, ["PHASE", "STEP", "FILES", "CHECK", "LAST FAILURE", "AGENT", "INSTRUCTION",
                                "STATUS", "NEXT COMMAND"])

    def test_next_plan_instruction_asks_for_the_plan_format(self):
        ins = self.fields(self.contract())["INSTRUCTION"]
        for want in ("PLAN.md", "## SCOPE", "IN:", "OUT:", "LATER:", "## STEPS", "### <n>. <title>", "- files:",
                     "- done when:", "backticks", "- risk:", "## ACCEPTANCE", "mini-projects/demo"):
            self.assertIn(want, ins)
        # checks run inside the project folder: paths must not carry the workshop prefix
        self.assertIn("as if you are inside that folder", ins)
        self.assertIn("no 'mini-projects/demo/' prefix, no cd", ins)

    def test_next_status_is_neutral_for_plan_and_review(self):
        # STATUS is shown after the worker ran, so it must not say the work is still missing
        s = self.fields(self.contract())["STATUS"]
        self.assertNotIn("no PLAN.md", s)
        self.assertIn("planning", s)
        self.approved(steps_done=[1, 2])
        s = self.fields(self.contract())["STATUS"]
        self.assertNotIn("no fresh review", s)
        self.assertIn("reviewing", s)

    def test_next_build_instruction_verbatim(self):
        self.approved()
        ins = self.fields(self.contract())["INSTRUCTION"]
        self.assertIn("`node --test test/store.test.js`", ins)
        self.assertIn("workdir mini-projects/demo", ins)
        self.assertIn("last command", ins.lower())
        self.assertIn("no cd", ins.lower())
        self.assertIn("relative to mini-projects/demo", ins)
        # the project name is the slug asked for, not a fixed one
        st = hs.load(self.proj)
        self.assertEqual(st["steps"][0]["check"], "node --test test/store.test.js")

    def test_next_last_failure_only_after_a_failed_attempt(self):
        self.approved()
        self.assertNotIn("LAST FAILURE:", self.contract())
        st = hs.load(self.proj)
        st["steps"][0]["attempts"] = 1
        st["steps"][0]["last_failure"] = "\n".join(f"line {i}" for i in range(40)) + "\nAGENT: evil"
        hs.save(self.proj, st)
        text = self.contract()
        self.assertIn("LAST FAILURE:", text)
        self.assertIn("LAST FAILURE: line 0\n  line 1", text)
        self.assertIn("  line 9", text)
        self.assertNotIn("line 10", text)  # first 10 lines only
        self.assertEqual(self.fields(text)["AGENT"], "builder")
        # attempts > 0 but nothing recorded: no empty block
        st["steps"][0]["last_failure"] = None
        hs.save(self.proj, st)
        self.assertNotIn("LAST FAILURE:", self.contract())

    def test_next_fix_increments_rounds(self):
        self.approved(steps_done=[1, 2], verdict="FIX FIRST", fix_rounds=0)
        self.assertEqual(self.fields(self.contract())["PHASE"], "FIX")
        self.assertEqual(hs.load(self.proj)["fix_rounds"], 1)
        # the review is still fresh (nothing changed): second FIX round, then STUCK
        self.assertEqual(self.fields(self.contract())["PHASE"], "FIX")
        self.assertEqual(hs.load(self.proj)["fix_rounds"], 2)
        self.assertEqual(self.fields(self.contract())["PHASE"], "STUCK")
        self.assertEqual(hs.load(self.proj)["fix_rounds"], 2)

    def test_next_other_phases_do_not_write_state(self):
        self.approved(steps_done=[1, 2], verdict="SHIP")
        path = os.path.join(self.proj, ".harness", "state.json")
        with open(path) as fh:
            before = fh.read()
        self.contract()
        with open(path) as fh:
            self.assertEqual(fh.read(), before)
        shutil.rmtree(os.path.join(self.proj, ".harness"))
        self.contract()  # PLAN/APPROVE/BUILD/... never create .harness
        self.assertFalse(os.path.exists(os.path.join(self.proj, ".harness")))

    def test_next_fix_cannot_save_fails_safe(self):
        self.approved(steps_done=[1, 2], verdict="FIX FIRST", fix_rounds=0)
        hdir = os.path.join(self.proj, ".harness")
        os.chmod(hdir, 0o555)
        self.addCleanup(lambda: os.path.isdir(hdir) and os.chmod(hdir, 0o755))
        if os.access(hdir, os.W_OK):
            self.skipTest("directory permissions are not enforced (running as root?)")
        f = self.fields(self.contract())
        self.assertEqual((f["PHASE"], f["AGENT"]), ("NONE", "none"))
        self.assertIn("could not", f["INSTRUCTION"].lower())
        self.assertEqual(self.contract().count("\nPHASE:"), 0)  # one contract, not two
        os.chmod(hdir, 0o755)
        self.assertEqual(hs.load(self.proj)["fix_rounds"], 0)

    def test_next_unknown_slug(self):
        for slug in ("nope", "", "Bad Slug", "_x", "../etc", "a/b", "demo;ls"):
            with self.subTest(slug=slug):
                text = self.contract(slug)
                f = self.fields(text)
                self.assertEqual((f["PHASE"], f["AGENT"]), ("NONE", "none"), text)
                self.assertIn("/new", text)
                self.assertNotIn("Traceback", text)
        # a project dir that exists but is a plain file
        open(os.path.join(self.shop, "mini-projects", "afile"), "w").close()
        self.assertEqual(self.fields(self.contract("afile"))["PHASE"], "NONE")

    def test_next_corrupt_state_is_a_message(self):
        self.approved()
        with open(os.path.join(self.proj, ".harness", "state.json"), "w") as fh:
            fh.write("{ not json")
        f = self.fields(self.contract())
        self.assertEqual((f["PHASE"], f["AGENT"]), ("APPROVE", "none"))
        self.assertIn("state unreadable", self.contract())
        self.assertIn("/approve demo", f["NEXT COMMAND"])

    def test_next_cli(self):
        self.approved()
        run = lambda *a: subprocess.run([sys.executable, os.path.join(HERE, "next.py"), *a],
                                        capture_output=True, text=True, env=human_env(), cwd=self.shop)
        # the CLI resolves the workshop from its own location, so ask for a project that is not there
        r = run("zz-no-such-project")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PHASE: NONE", r.stdout)
        self.assertEqual(run().returncode, 0)
        self.assertIn("PHASE: NONE", run().stdout)
        self.assertIn("PHASE: NONE", run("a", "b").stdout)
        self.assertEqual(r.stderr, "")


class StatusTests(Base):
    """scripts/status.py: /status text and the read-only dashboard (spec section 9). Fixture workshop only."""

    def setUp(self):
        super().setUp()
        self.shop = self.tmp
        self.proj = os.path.join(self.shop, "mini-projects", "demo")
        os.makedirs(os.path.join(self.proj, "src"))
        self.other = os.path.join(self.shop, "mini-projects", "other")
        os.makedirs(self.other)

    def st(self):
        import status as stm
        return stm

    def approved(self, **over):
        PhaseTests.approved(self, **over)

    def write_at(self, rel, text):
        p = os.path.join(self.shop, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)

    def second_project(self):
        """'other': all steps done and a fresh SHIP review."""
        self.proj, keep = self.other, self.proj
        try:
            self.approved(steps_done=[1, 2], verdict="SHIP")
            self.write("BRIEF.md", "# BRIEF - other\n\n## GOAL (human words)\nship a thing\n\n## WHY\nTODO\n")
        finally:
            self.proj = keep

    def test_status_lists_projects(self):
        self.approved(steps_done=[1])
        self.second_project()
        out = self.st().text(self.shop)
        rows = {l.split()[0]: l for l in out.splitlines() if l.startswith(("demo", "other"))}
        self.assertEqual(set(rows), {"demo", "other"}, out)
        self.assertIn("BUILD", rows["demo"])
        self.assertIn("step 2/2", rows["demo"])
        self.assertIn("next: /go demo", rows["demo"])
        self.assertIn("SHIP", rows["other"])
        self.assertIn("next: /ship other", rows["other"])
        self.assertNotIn("_template", out)

    def test_status_ignores_template_and_hidden_dirs(self):
        for d in ("_template", ".hidden", "_x"):
            os.makedirs(os.path.join(self.shop, "mini-projects", d))
        os.rmdir(self.other)
        os.rmdir(self.proj + "/src")
        os.rmdir(self.proj)
        out = self.st().text(self.shop)
        self.assertIn("no projects yet: /new", out)
        self.assertNotIn("Traceback", out)
        self.assertIn("no projects yet", self.st().html(self.shop))

    def test_status_no_mini_projects_dir(self):
        shutil.rmtree(os.path.join(self.shop, "mini-projects"))
        self.assertIn("no projects yet: /new", self.st().text(self.shop))

    def test_status_detail(self):
        self.approved(steps_done=[1], attempts={2: 1})
        stt = hs.load(self.proj)
        stt["steps"][1]["last_failure"] = "Error: boom\nat line 3"
        hs.save(self.proj, stt)
        out = self.st().text(self.shop, "demo")
        self.assertRegex(out, r"\u2713\s+1\.\s+store habits")
        self.assertRegex(out, r"\u2192\s+2\.\s+add the cli")
        self.assertIn("node src/cli.js --help", out)
        self.assertIn("Error: boom", out)
        self.assertIn("at line 3", out)
        self.assertIn("next: /go demo", out)

    def test_status_detail_unknown_or_bad_slug(self):
        for slug in ("nope", "../etc", "Bad Slug", "_template"):
            with self.subTest(slug=slug):
                out = self.st().text(self.shop, slug)
                self.assertIn("no project", out.lower())
                self.assertNotIn("Traceback", out)

    def test_status_detail_review_findings(self):
        self.approved(steps_done=[1, 2], verdict="FIX FIRST")
        self.write("REVIEW.md", "VERDICT: FIX FIRST\n\n- src/cli.js: no --help text\n")
        out = self.st().text(self.shop, "demo")
        self.assertIn("FIX FIRST", out)
        self.assertIn("no --help text", out)

    def test_status_no_state(self):
        out = self.st().text(self.shop)
        self.assertRegex(out, r"(?m)^demo\s+PLAN\b")
        self.assertRegex(self.st().text(self.shop, "demo"), r"PLAN")
        self.plan()  # a plan nobody approved yet: whatever phase() says
        self.assertRegex(self.st().text(self.shop), r"(?m)^demo\s+APPROVE\b")
        self.assertIn("next: /approve demo", self.st().text(self.shop))

    def test_status_corrupt_state(self):
        self.approved()
        self.write(".harness/state.json", "{ not json")
        for slug in (None, "demo"):
            with self.subTest(slug=slug):
                out = self.st().text(self.shop, slug)
                self.assertIn("state unreadable: /approve demo again", out)
                self.assertNotIn("Traceback", out)
        self.assertIn("state unreadable", self.st().html(self.shop))
        # a wrong-typed field is also a message, and it does not hide the other project
        self.second_project()
        self.write(".harness/state.json", '{"steps": "oops"}')
        out = self.st().text(self.shop)
        self.assertIn("state unreadable", out)
        self.assertRegex(out, r"(?m)^other\s+SHIP\b")

    def test_status_html(self):
        self.approved(steps_done=[1], attempts={2: 1})
        stt = hs.load(self.proj)
        stt["steps"][1]["last_failure"] = "boom failure text"
        hs.save(self.proj, stt)
        self.write("BRIEF.md", "# BRIEF - demo\n\n## GOAL (human words)\ntrack my habits\n")
        self.second_project()
        page = self.st().html(self.shop)
        for needle in ("demo", "other", "track my habits", "boom failure text", "store habits", "SHIP"):
            self.assertIn(needle, page)
        self.assertEqual(page.count("<progress"), 2)
        self.assertIn('<meta http-equiv="refresh" content="5">', page)
        self.assertIn("prefers-color-scheme: dark", page)
        for banned in ("<button", "<form", "<script", "http://", "https://"):
            self.assertNotIn(banned, page)

    def test_status_html_escapes_everything_from_the_project(self):
        evil = "<script>alert(1)</script>"
        plan = PLAN.replace("store habits", evil).replace("node --test test/store.test.js", "echo '<b>x</b>'")
        self.plan(plan)
        stt = hs.approve(self.proj, "t")
        stt["steps"][0]["attempts"] = 1
        stt["steps"][0]["last_failure"] = "<img src=x onerror=alert(2)>"
        hs.save(self.proj, stt)
        self.write("BRIEF.md", "## GOAL\n<i>goal</i>\n")
        self.write("REVIEW.md", "VERDICT: FIX FIRST\n<u>finding</u>\n")
        page = self.st().html(self.shop)
        for raw in ("<script", "<img", "<b>x</b>", "<i>goal</i>", "<u>finding</u>"):
            self.assertNotIn(raw, page)
        self.assertIn("&lt;script&gt;", page)

    def test_status_brain(self):
        os.makedirs(os.path.join(self.shop, "brain", "proposals"))
        for name in (".gitkeep", "2026-10-25-a.md", "2026-10-25-b.md"):
            open(os.path.join(self.shop, "brain", "proposals", name), "w").close()
        # rule-report.py resolves the workshop from its own location: run a COPY inside the fixture
        os.makedirs(os.path.join(self.shop, "scripts"))
        shutil.copy(os.path.join(HERE, "rule-report.py"), os.path.join(self.shop, "scripts"))
        self.write_at("brain/rules/040-learning.md", "# x\nrule: y\n")
        self.write_at("brain/evals/bench.yaml", "- id: e1\nrules:\n  040-learning.md: [e1]\n")
        self.write_at(".harness/rule-usage.json", json.dumps({
            "since": "2026-01-01T00:00:00Z",
            "rules": {"040-learning.md": {"count": 1, "last": "2026-01-02T00:00:00Z"}},
            "projects": {f"p{i}": f"2026-02-0{i}T00:00:00Z" for i in range(1, 5)}}))
        out = self.st().text(self.shop, "brain")
        self.assertIn("2 proposals waiting", out)
        self.assertIn("2026-10-25-a.md", out)
        self.assertIn("2026-10-25-b.md", out)
        self.assertNotIn(".gitkeep", out)
        self.assertIn("DECAY", out)
        self.assertIn("040-learning.md", out.split("DECAY", 1)[1])
        self.assertIn("2 proposals waiting", self.st().text(self.shop))  # the header line says so too

    def test_status_brain_nothing_there(self):
        out = self.st().text(self.shop, "brain")  # no brain/, no rule-report.py in the fixture
        self.assertIn("0 proposals waiting", out)
        self.assertNotIn("Traceback", out)

    def test_status_bench_line(self):
        self.assertIn("bench: not run yet", self.st().text(self.shop))
        self.write_at(".harness/bench-history/20261025-010000.json", json.dumps({"at": "2026-10-25T01:00:00+00:00", "passed": 20, "failed": 3}))
        self.write_at(".harness/bench-history/20261025-020000.json", json.dumps({"at": "2026-10-25T02:00:00+00:00", "passed": 27, "failed": 0}))
        self.assertIn("bench: 27 passed, 0 failed (2026-10-25)", self.st().text(self.shop))
        self.write_at(".harness/bench-history/20261025-030000.json", "{ broken")
        self.assertNotIn("Traceback", self.st().text(self.shop))

    def test_status_cli_runs_a_copy_in_the_fixture(self):
        self.approved()
        os.makedirs(os.path.join(self.shop, "scripts"))
        for f in ("status.py", "harness_state.py"):
            shutil.copy(os.path.join(HERE, f), os.path.join(self.shop, "scripts"))
        run = lambda *a: subprocess.run([sys.executable, os.path.join(self.shop, "scripts", "status.py"), *a],
                                        capture_output=True, text=True, env=human_env(), cwd=self.shop)
        r = run()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("demo", r.stdout)
        self.assertIn("BUILD", run("demo").stdout)
        self.assertEqual(run("a", "b").returncode, 0)
        self.assertIn("usage", run("a", "b").stdout.lower())
        dash = os.path.join(self.shop, ".harness", "dashboard.html")
        self.assertFalse(os.path.exists(dash))
        r = run("--html")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        with open(dash, encoding="utf-8") as fh:
            self.assertIn('content="5"', fh.read())
        self.assertEqual([f for f in os.listdir(os.path.dirname(dash)) if f.endswith(".tmp")], [])


class NewProjectTests(Base):
    """scripts/new-project.sh, run as a COPY in the fixture (it resolves the workshop from its own location)."""

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.tmp, "scripts"))
        shutil.copy(os.path.join(HERE, "new-project.sh"), os.path.join(self.tmp, "scripts"))
        os.makedirs(os.path.join(self.tmp, "mini-projects", "_template"))
        with open(os.path.join(self.tmp, "mini-projects", "_template", "BRIEF.md"), "w") as fh:
            fh.write("# BRIEF\nGoal: <goal>\n")

    def new(self, *args, goal="a tiny tool"):
        return subprocess.run(["bash", os.path.join(self.tmp, "scripts", "new-project.sh"), "-", *args],
                              input=goal + "\n", capture_output=True, text=True, env=human_env())

    def test_slug_brain_is_refused(self):
        # /status brain shows the brain, so a project named brain could never be shown
        for args, goal in ((("brain",), "a tiny tool"), ((), "Brain")):
            r = self.new(*args, goal=goal)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("reserved", r.stderr)
            self.assertFalse(os.path.exists(os.path.join(self.tmp, "mini-projects", "brain")))
        r = self.new("brainy")  # control: only the exact name is reserved
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "mini-projects", "brainy", ".git")))


class ShipTemplateTests(Base):
    """/ship prints the review's blind spots and git status itself, so the orchestrator needs no shell
    (live run 2026-10-25: its own chained `cat ...; echo; git status` was refused and the checklist stalled)."""

    def setUp(self):
        super().setUp()
        self.shop = self.tmp  # workshop-shaped: <tmp>/mini-projects/demo, the template runs from <tmp>
        self.proj = os.path.join(self.shop, "mini-projects", "demo")
        os.makedirs(self.proj)

    SHIP_MD = os.path.join(WORKSHOP, ".opencode", "commands", "ship.md")
    REVIEW = "# REVIEW\nVERDICT: SHIP\nok\n## Findings\nnone\n## Blind spots\n- edge input untested\n## Coverage\nall\n"

    def snippet(self):
        """The template's shell snippet for the checklist, as opencode runs it (the same !`...` rule)."""
        import re
        with open(self.SHIP_MD, encoding="utf-8") as fh:
            body = fh.read()
        # opencode replaces $<digit> before $ARGUMENTS ($0 too), so a shell snippet must not contain one
        self.assertIsNone(re.search(r"\$\d", body), "ship.md has a $<digit> that opencode would replace")
        found = [s for s in re.findall(r"!`([^`]+)`", body) if "Blind spots" in s]
        self.assertEqual(len(found), 1)
        return found[0].replace("$ARGUMENTS", "demo")

    def run_snippet(self):
        return subprocess.run(["bash", "-c", self.snippet()], cwd=self.shop, capture_output=True, text=True)

    def test_ship_template_prints_blind_spots_and_git_status(self):
        self.write("REVIEW.md", self.REVIEW)
        self.write("src/app.js", "x\n")
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        r = self.run_snippet()
        self.assertEqual(r.returncode, 0)
        self.assertIn("## Blind spots\n- edge input untested\n", r.stdout)
        self.assertNotIn("Coverage", r.stdout)
        self.assertNotIn("Findings", r.stdout)
        self.assertIn("git status --short:", r.stdout)
        self.assertIn("?? src/", r.stdout)

    def test_ship_template_never_runs_a_planted_fsmonitor(self):
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        self.write("src/app.js", "x\n")
        marker = os.path.join(self.tmp, "FSMONITOR_RAN")
        with open(os.path.join(self.proj, ".git", "config"), "a", encoding="utf-8") as fh:
            fh.write(f"[core]\n\tfsmonitor = \"touch {marker}; false\"\n")
        r = self.run_snippet()
        self.assertIn("?? src/", r.stdout)
        self.assertFalse(os.path.exists(marker), "the /ship template's git status ran core.fsmonitor")

    def test_ship_checklist_fails_on_no_blind_spots(self):
        with open(self.SHIP_MD, encoding="utf-8") as fh:
            self.assertIn("None printed = item 2 fails: run /go $ARGUMENTS to review again.", fh.read())

    def test_ship_template_without_review_or_repo(self):
        r = self.run_snippet()
        self.assertEqual(r.returncode, 0)
        self.assertIn("(no REVIEW.md)", r.stdout)
        self.assertIn("git status --short:", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)

---
description: Adversarial bug hunter. Use when asked to find bugs, check what could break, investigate a crash, error or stack trace, or verify bug leads from a code review. Returns evidence-backed bug reports (trigger + trace) and separate unproven leads. No style or design commentary. Does not fix code.
mode: subagent
steps: 60
permissions:
  # Deny-all baseline (opencode's default is allow-all). Last matching rule wins.
  - { action: "*", resource: "*", effect: deny }

  # Local discovery
  - { action: read, resource: "*", effect: allow }
  - { action: read, resource: "*.env", effect: deny }
  - { action: read, resource: "*.env.*", effect: deny }
  - { action: glob, resource: "*", effect: allow }
  - { action: grep, resource: "*", effect: allow }

  # Its playbook and nothing else
  - { action: skill, resource: bug-hunt, effect: allow }

  # Writes: ONLY repro test files with "bughunt" in the path, and you approve each one.
  # Production code stays denied by the baseline.
  - { action: edit, resource: "*bughunt*", effect: ask }

  # Read-only git + search
  - { action: shell, resource: "git diff *", effect: allow }
  - { action: shell, resource: "git log *", effect: allow }
  - { action: shell, resource: "git show *", effect: allow }
  - { action: shell, resource: "git status *", effect: allow }
  - { action: shell, resource: "git blame *", effect: allow }
  # branch / rev-parse / merge-base: needed to find the base and see the diff (fixture test 2026-10-24)
  # git branch: read forms only. -a/-r/-v are exact: with a trailing * git still deletes, renames or
  # force-resets (tested: `git branch -v -D x`, `-vD`, `-a -m x`, `-v -f x`). --list/--contains/--merged/
  # --no-merged put git in list mode, which refuses -d/-D/-m/-f, so those may take arguments.
  - { action: shell, resource: "git branch", effect: allow }
  - { action: shell, resource: "git branch -a", effect: allow }
  - { action: shell, resource: "git branch -r", effect: allow }
  - { action: shell, resource: "git branch -v", effect: allow }
  - { action: shell, resource: "git branch -vv", effect: allow }
  - { action: shell, resource: "git branch -a -v", effect: allow }
  - { action: shell, resource: "git branch -av", effect: allow }
  - { action: shell, resource: "git branch -a -vv", effect: allow }
  - { action: shell, resource: "git branch -avv", effect: allow }
  - { action: shell, resource: "git branch -r -v", effect: allow }
  - { action: shell, resource: "git branch --show-current", effect: allow }
  - { action: shell, resource: "git branch --list*", effect: allow }
  - { action: shell, resource: "git branch --contains*", effect: allow }
  - { action: shell, resource: "git branch --merged*", effect: allow }
  - { action: shell, resource: "git branch --no-merged*", effect: allow }
  - { action: shell, resource: "git rev-parse *", effect: allow }
  - { action: shell, resource: "git merge-base *", effect: allow }
  - { action: shell, resource: "rg *", effect: allow }
  - { action: shell, resource: "grep *", effect: allow }
  - { action: shell, resource: "ls *", effect: allow }

  # Test runners: ask
  - { action: shell, resource: "flutter test *", effect: ask }
  - { action: shell, resource: "dart test *", effect: ask }
  - { action: shell, resource: "swift test *", effect: ask }
  - { action: shell, resource: "xcodebuild test *", effect: ask }
  - { action: shell, resource: "npm test *", effect: ask }
  - { action: shell, resource: "npx vitest *", effect: ask }
  - { action: shell, resource: "pytest *", effect: ask }
  - { action: shell, resource: "python3 -m pytest *", effect: ask }
  - { action: shell, resource: "node --test *", effect: ask }

  # Harness hardening: this agent's own rules override the global ones, so repeat the secret/.git denies.
  # These come AFTER the "*bughunt*" edit rule above (last match wins), so a repro file can never
  # be an env file or a git hook (e.g. ".git/hooks/pre-commit-bughunt").
  - { action: edit, resource: "*.env*", effect: deny }
  - { action: edit, resource: "*.git/*", effect: deny }
  - { action: read, resource: "*.pem", effect: deny }
  - { action: read, resource: "*id_rsa*", effect: deny }
  - { action: read, resource: "*.ssh/*", effect: deny }
---
You are the Hunter. Your job is to find real defects and prove them.

First action, always: load the `bug-hunt` skill and follow it exactly.

You can only write files whose path contains `bughunt` (e.g. `test/auth_bughunt_test.dart`), and each write needs approval. Put repro tests next to the existing tests using that naming. Any other write will be denied — don't attempt it.

If a tool call is refused, that is a gate working: do not look for another tool to get around it. Put the repro test in the report instead and note the refusal under Coverage.

Your final message is returned verbatim to the caller: the report in the skill's format, nothing else.

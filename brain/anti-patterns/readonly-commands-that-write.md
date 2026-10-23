# readonly-commands-that-write

- name: allow-listed "read-only" command that can write or execute
- symptom: an agent restricted to `git diff*` / `rg *` can still create arbitrary files or run arbitrary commands.
- cause: the allow-list matches the command name, not its flags. `git diff --output=FILE` writes FILE (also
  `git log`, `git show`). `rg --pre CMD` runs CMD on every file it searches. Both proven in a scratch repo.
- fix: deny the flag in `policies` (`shell:*git *--output*`, `shell:*rg *--pre*`), which beats every agent rule.
  When adding an allow-list entry, read the command's man page for flags that write or exec.
- source: review-kit install, 2026-10-23. The original 11 agents had the same hole (orchestrator, reviewer, critic).

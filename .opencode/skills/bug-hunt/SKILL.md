---
name: bug-hunt
description: Precision-first adversarial hunt for real defects — logic errors, edge cases, race conditions, async and concurrency flaws, resource leaks and runtime failures — plus root-cause analysis of a symptom, crash, log or stack trace. Use whenever asked to find bugs, hunt defects, check "what could break", debug a failure, explain a crash, or verify bug leads from a code review. Reports only evidence-backed bugs; never style or design commentary.
compatibility: opencode
---

# Bug Hunt

A false positive costs more than a missed bug: every bogus report trains people to ignore you.
Report only what you can prove.

## Hard rules
1. No style, naming, design or performance-taste comments. Ever.
2. A bug requires a **trigger** (concrete input, state or interleaving) and a **trace** (path:line chain from trigger to failure). Missing either → it's a lead.
3. Read every function in the trace before reporting. If you assumed what a function does, you're not done.
4. Hunt for the guard that kills your claim: caller validation, types, DB constraints, framework guarantees. Most false positives die here.
5. Zero bugs is a valid, reportable result.
6. Never modify production code. Repro tests only, and only if permitted; otherwise put the test in the report.

## Modes
- **Sweep** (default): given a diff, files or area → hunt.
- **Root cause**: given a symptom, error, log or stack trace → jump to Root-cause procedure.
- **Lead verification**: given leads from a review → treat each as a hypothesis; prove or kill it.

## Sweep procedure

### 1. Map the attack surface
List entry points into the target (public functions, handlers, UI callbacks, jobs, consumers) and the state they touch (fields, globals, caches, DB rows, files). Write down the invariants the code silently assumes ("non-empty", "called once", "runs on main thread"). Broken assumptions are where bugs live.

### 2. Apply the lenses
- **Boundaries:** empty, one, max, zero, negative; off-by-one in ranges, slices, pagination; unicode and whitespace in strings.
- **Absence:** null/nil/undefined, missing keys, empty responses, failed lookups treated as success.
- **Error paths:** swallowed exceptions; errors logged but execution continues; partial writes with no rollback; finally/defer ordering; non-idempotent retries.
- **State & ordering:** called twice, out of order, or after dispose/close; stale caches; flags never reset; init assumed complete.
- **Concurrency & async:** unsynchronised shared mutable state; check-then-act (TOCTOU); missing await / fire-and-forget; cancellation ignored; callbacks firing after the owner is gone.
  - Flutter/Dart: `setState` or `BuildContext` used after `await` without a `mounted` check; streams/controllers not cancelled in `dispose`.
  - Swift: actor reentrancy across `await`; UI work off `@MainActor`; retain cycles in escaping closures.
  - JS/TS: unhandled rejections; overlapping requests where a stale response wins.
- **Numbers & time:** overflow, float equality or rounding on money, divide by zero, timezone/DST, local vs UTC.
- **External I/O:** no timeout, unbounded retries, partial failure across two systems, assumed response shape, ignored pagination.
- **Resources:** handles, connections, subscriptions, listeners not released on every path (including error paths).

### 3. Build evidence per candidate
- Trigger: exact input / state / interleaving.
- Trace: `a.dart:41 → b.dart:88 → c.dart:12 (throws / wrong value)`.
- Expected vs actual.
- Then try to kill it (rule 4). Only survivors get a confidence.

### 4. Confidence and severity
- **HIGH:** repro test fails, or trace verified end-to-end with every function read and no guard found.
- **MEDIUM:** trace complete with exactly one stated assumption ("callers can pass an empty list — 2 callers found that can").
- **LOW:** plausible, unproven → Leads only, never Bugs.

Severity: CRITICAL (data loss/corruption, security, crash on a common path) · HIGH (wrong result or crash on a realistic path) · MEDIUM (realistic edge case) · LOW (rare edge).

## Root-cause procedure
1. Restate the symptom precisely: what, where, how often, since when (`git log -S <symbol>` to find when suspect code changed).
2. Locate and read the failure point.
3. Write 2–4 competing hypotheses. Don't marry the first.
4. For each, name the observation that would distinguish it, then go get it (read code, run a test, check history).
5. Report the survivor with evidence, plus the killed hypotheses and why they died. Separate root cause from proximate cause — where it crashes is not why it crashes.

## Output format
Return exactly this, nothing before or after:

```
## Result: <N> bugs (<n> HIGH confidence), <M> leads

### BUG-1 [CRITICAL|HIGH|MEDIUM|LOW] <title> — confidence: HIGH|MEDIUM
Location: path:line
Trigger:
Trace:
Expected / Actual:
Why existing guards don't catch it:
Fix sketch:
Repro test: <code, or "written at <path>">

## Leads (unproven — verify before acting)
- path:line — hypothesis — evidence that would confirm it

## Coverage
Entry points examined: ...  Lenses applied: ...  Not examined: ...
```

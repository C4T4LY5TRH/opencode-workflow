---
name: bug-hunt
description: Precision-first adversarial hunt for real defects — logic errors, edge cases, race conditions, async and concurrency flaws, resource leaks and runtime failures. Pass 2 of the reviewer's two passes: use it to find bugs, hunt defects, or check "what could break". Reports only evidence-backed bugs; never style or design commentary.
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
6. Never modify production code. A throwaway repro goes in `.review/`, nowhere else.

## Procedure

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
- A survivor is PROVEN (a probe you ran in `.review/` fails) or TRACED (the trace above); anything less is a Lead.
- Your Hunt lines map to: logic, edge cases (boundaries, absence), concurrency (state, async), resource leaks, runtime failures (error paths, I/O, numbers).

### 4. Confidence and severity
- **HIGH:** repro test fails, or trace verified end-to-end with every function read and no guard found.
- **MEDIUM:** trace complete with exactly one stated assumption ("callers can pass an empty list — 2 callers found that can").
- **LOW:** plausible, unproven → a Lead only, never a finding.

Severity: CRITICAL (data loss/corruption, security, crash on a common path) · HIGH (wrong result or crash on a realistic path) · MEDIUM (realistic edge case) · LOW (rare edge).

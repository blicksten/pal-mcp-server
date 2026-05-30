---
name: red-flags
description: Full catalog of anti-patterns and rationalizations to detect and reject. Use when reviewing your own reasoning or when a hook reminder triggers.
---

# Red Flags — Anti-Pattern Catalog

These rationalizations indicate protocol violations. When you catch yourself thinking any of these, **STOP** and follow the correct action.

## Universal Red Flags

| # | If you catch yourself thinking... | What it really means | Correct action |
|---|----------------------------------|---------------------|----------------|
| 1 | "I already know what this file does" | Memory-only reasoning — file may have changed | **Read the file** with Read tool |
| 2 | "The tests probably pass" | Unverified claim — no evidence | **Run tests**, read output, cite pass/fail count |
| 3 | "PAL is slow, I'll skip cross-validation" | CV gate bypass | **PAL is mandatory** — call it. If unavailable: Agent fallback |
| 4 | "This is a simple change, no review needed" | Quality gate bypass | Run `/check` or launch code-reviewer agent |
| 5 | "I'll just fix this quickly" | Routing bypass | Call `route_task()` first — let routing decide |
| 6 | "This doesn't need a test" | TDD bypass | Every behavior change needs a test. Exception: spike work only |
| 7 | "I'll update docs later" | Documentation debt | Update docs **before** commit — enforced by doc gate |

## Skill-Specific Red Flags

### During `/run` execution
- "I'll implement this task directly instead of delegating" → Check if task touches >3 files — if so, delegate to Task agent
- "The gate will catch issues later" → Fix issues now — gates are verification, not the primary quality mechanism
- "I already ran tests earlier" → Run tests again — code may have changed since

### During `/check` or code review
- "The code looks fine at a glance" → Read every changed file with Read tool — no skimming
- "This finding is a false positive" → Use `mcp__pal__challenge` to contest, don't silently skip

### During `/phase` planning
- "This task is straightforward, one line is enough" → Each task must be independently verifiable with specific acceptance criteria
- "We can combine these into one task" → One concern per task. If description needs "and", split it.

## Why This Matters

Each red flag represents a pattern where AI agents commonly degrade quality:
- **Memory-only reasoning** leads to stale assumptions about code that has changed
- **Unverified claims** propagate phantom success through the pipeline
- **Gate bypasses** accumulate technical debt that compounds across phases
- **TDD skips** leave behavior changes untested, causing regressions later

The cost of following the correct action is measured in seconds. The cost of a bypassed protocol is measured in hours of debugging.

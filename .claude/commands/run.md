---
name: run
description: "Execute: read current plan, run per-phase gate for completed phase, implement next phase(s), audit, update docs, commit. Usage: /run [N|all] — 1 phase (default), N phases, or all remaining."
---

# Run Workflow

You are executing the `/run` command — a shortcut for implementing one or more planned phases.

**FIRST OUTPUT:** Before any tool calls, print: `▶ /run {$ARGUMENTS or '1'}`

**Step 0 — Resolve session context:**
Call `resolve_session` MCP tool with: `project_root` = current working directory, `env_session` = CLAUDE_SESSION env var (empty if unset), `branch` = current git branch, `skill_args` = ARGUMENTS, `skill_name` = "run", `instance_id` = INSTANCE_ID from [SESSION] tag (empty if unavailable), `owner_id` = session_id from [SESSION] tag (empty if unavailable).

Use returned `plan_file`, `tasks_file`, `review_file`, `label`, `source`, `project_suffix`, `parsed_args` throughout. For `start_pipeline`: use `project=<basename_of_cwd>{project_suffix}`. For `list_active_pipelines`: ALWAYS pass `project=<basename_of_cwd>{project_suffix}`.
Print: "Session: **{label}** → {plan_file}" only when label is set. Otherwise proceed silently.

Use `parsed_args.count` (integer or `"all"`) for the run scope instead of inline N/all parsing.

**Step 0a — Requires-picker branch:**
When `resolve_session` returns `source='requires-picker'` AND `parsed_args` has no explicit label arg:
1. Call `list_available_sessions(project=<basename_of_cwd>, owner_id=session_id)`.
2. If the sessions list is empty: print `No active sessions. Start with: /phase "description" or /new-session LABEL` and **STOP**.
3. If sessions exist: display a picker table:
   ```
   | Label | Status | Last Heartbeat | Claim Status | Progress |
   |-------|--------|---------------|--------------|---------|
   | ...   | ...    | ...            | ...          | ...%    |
   ```
   Then **STOP** — print `Pick a session: re-run /run <label> to continue.` User must re-invoke with an explicit label.

**Anti-hallucination rule:** NEVER derive session label from conversation topic, task description, or user request content. The `resolve_session` tool is the ONLY valid source. Any other derivation is a hallucination.

<!-- session-claim-guard fragment
     Canonical 5-branch claim guard included from every session-aware skill.
     Source: ISO-G plan (docs/PLAN-session-isolation-claim.md).
     Consumers: /phase, /run, /finish, /check, /do, /test, /save (Step 0c), /summary.
     /save numbering: 0b (anti-hallucination) -> 0c (claim guard) -> 0d (persistence).
     /new-session does NOT include this fragment; it has targeted 2-branch logic
     because it creates a new label (stale/legacy reclaim branches are wrong there). -->

**Step 0b — Claim guard (collision prevention):**

When `label` is None (no session) → skip this guard and proceed silently.

When `label` is set (any source), call `list_available_sessions(project=<basename_of_cwd>, owner_id=session_id)` to check the label's claim_status. If the MCP call returns an error or raises — **HALT** with `"Session DB unavailable — cannot verify session isolation. Try again or check orchestrator status."` Do NOT interpret a DB error as "no claim exists"; do NOT proceed on ambiguous error.

Branch on `claim_status`:

- `claim_status='own-active'` → call `renew_lease(label, owner_id=session_id, project=<basename_of_cwd>)` and proceed (own work is OK).
- `claim_status='locked-by-other'` → **HALT**. Print:
  ```
  Label '{label}' is currently locked by another session.
  Suggested alternative: call /phase 'your description' to auto-generate a unique label,
  or wait for the other session to finish.
  ```
  Do NOT proceed with pipeline work. **STOP**.
- `claim_status='stale'` or label not present in sessions list → call `claim_session(label, plan_file=docs/PLAN-{label}.md, owner_id=session_id, project=<basename_of_cwd>)`. Check the returned `success` field. If `success=False`: **HALT** and print `"Session claim failed: {error}. Retry or use a different label."` Do NOT proceed with pipeline work. **STOP**. If `success=True`, proceed.
- `claim_status='file-only-legacy'` → call `claim_session(label, plan_file=docs/PLAN-{label}.md, owner_id=session_id, project=<basename_of_cwd>)` to register it (legacy reclaim). Check the returned `success` field. If `success=False`: **HALT** and print `"Session claim failed: {error}. Retry or use a different label."` Do NOT proceed with pipeline work. **STOP**. If `success=True`, proceed.

**Step 0c — Write `.claude/.run-last-label` breadcrumb (HGL.5 T5.4):**
When SESSION_LABEL is set, write `<label>\n<ISO-8601 UTC timestamp>\n` atomically to `.claude/.run-last-label`. This breadcrumb is consulted by `resolve_session` in a later `/save` (Priority 2.5) when env/args are absent, so the operator can resume the working session from a default branch. Freshness cap: 24h. Use the atomic tempfile + rename pattern:

```
bash -c '
  mkdir -p .claude
  tmp=".claude/.run-last-label.tmp.$$"
  ts="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
  printf "%s\n%s\n" "{SESSION_LABEL}" "$ts" > "$tmp" && mv -f "$tmp" .claude/.run-last-label
'
```

If SESSION_LABEL is not set (no session): skip the breadcrumb write.

**Step 0.5 — Work Discovery (when PLAN_FILE has no incomplete phases):**

Before proceeding to scope/orchestrate, check whether PLAN_FILE actually has work:

1. Read PLAN_FILE. If it does not exist → mark `plan_empty=true`. If it exists: scan for any `- [ ]` checkbox lines (incomplete tasks/phases). If ALL phases are `[x]` (or file has no phases at all) → mark `plan_empty=true`.
2. If `plan_empty=false` → skip to Step 1 (normal flow, there is work to do).
3. If `plan_empty=true` → **Work Discovery scan:**
   a. Glob `docs/PLAN-*.md` — for each file found (excluding current PLAN_FILE), read the first 10 lines and any `- [ ]` lines. Collect files with incomplete phases.
   b. Read `docs/ROADMAP.md` — extract any lines containing `TODO`, `PENDING`, `IN_PROGRESS`, or "Next milestone".
   c. Read `MEMORY.md` — check for "Deferred Tasks" or "pending" entries.
   d. Read `session_resume.md` from project memory directory (the same directory where MEMORY.md lives — Claude Code resolves this automatically via the Read tool) (if exists) — this is the fast-path breadcrumb written by /save.
   e. Run `git log --oneline -5` — scan for "next session", "TODO", "PENDING", "v3 fix needed" hints.
4. **Present discovery results to user:**
   - If active work found → list it with numbers:
     ```
     PLAN_FILE is complete. Found active work:
       1. PLAN-Bug-to-QA.md: Phase 10.1 TODO
       2. ROADMAP: RSPDN re-embed pending
       3. Git log: "v3 fix needed next session" (abc1234)
     Which would you like to work on? (number, or 'none' to skip)
     ```
   - If no active work found → print "No active work found in this project. PLAN_FILE is complete." and **STOP** (do NOT invoke /finish — the plan was already finished in a prior session).
5. If user selects a PLAN-*.md → extract session label from filename, set SESSION_LABEL and PLAN_FILE accordingly, then continue to Step 1.
6. If user selects non-plan work (spike, roadmap item) → print recommendation (e.g., "Run `/phase <description>` to create a plan for this work") and **STOP**.

**Step 1 — Determine scope from ARGUMENTS (`$ARGUMENTS`):**
- Empty or `1` → run **1 phase** (default)
- Number `N` (e.g., `3`) → run **N consecutive phases**
- `all` → run **all remaining phases**
- `--force` anywhere in ARGUMENTS → bypasses Step 1.5 scope check (see below)

**Step 1.5 — Pre-flight scope check (HGL.5 T5.6b):**

Before invoking orchestrate, check that uncommitted files match the NEXT incomplete phase's `files_likely_touched` scope. Prevents accidental multi-feature sessions from polluting a phase's commit footprint.

1. Read PLAN_FILE. Identify the next incomplete `## <label>` phase section (the one orchestrate will execute). Look for a `**Files likely touched:**` bullet list or `files_likely_touched:` field inside that section.
   - **If absent or empty → skip Step 1.5** (plans predating HGL.5 T5.6a, or phases that genuinely touch anything).
2. Run `git status --porcelain` and collect modified (`M`/`MM`/`AM`) + untracked (`??`) paths. `git status` already respects `.gitignore`, so scratch directories listed there (e.g. `_archive/`, `vscode-dashboard/dist/`, `.playwright-mcp/`) will not appear in the output — do NOT duplicate those exclusions here (that would rot as the ignore list evolves). For foreign-project staging files that ARE tracked-path-shaped but do not belong to any phase (e.g. unstaged `[CR] *.md` Code Review guides, top-level marketing PDFs, docs that don't match `PLAN-`/`TASKS-`/`REVIEW-`/`ROADMAP`/`ANALYSIS` prefix): treat as out-of-scope and surface in the warning block just like any other mismatch — operator decides whether to add them to `.gitignore` or move them.
3. For each remaining uncommitted path, test against `files_likely_touched` globs using shell `fnmatch`-style semantics (e.g. `fnmatch` in Python or `case "$path" in $glob) ... esac` in bash). A path matching any glob → **in-scope**.
4. If one or more paths are **out of scope** AND `--force` is NOT in ARGUMENTS:
   - Emit a WARNING block listing each path + line-delta from `git diff --stat`:
     ```
     ⚠ Pre-flight scope check — out-of-scope uncommitted files (HGL.5 T5.6b):
       + orchestrator/unrelated.py  (+45 lines)
       + docs/UNRELATED-PLAN.md      (untracked, new file)
     Phase <N> `files_likely_touched` does NOT cover these paths.
     Options:
       a) git stash push -u -m "pre-{label}-<N>" ; /run
       b) commit the out-of-scope work first, then /run
       c) /run --force (proceed regardless, at your own risk)
     ```
   - **STOP** — do NOT invoke orchestrate.
5. If `--force` is present OR all uncommitted paths are in-scope: log one line summarising the scope check outcome and proceed.

This check is a WARN gate, not a hard block — `--force` always wins. Rationale: legitimate multi-feature sessions (e.g. operator racing two adjacent phases) stay unblocked, but the default case surfaces drift early.

**GATE evidence rule (Invariant 5, STAB Phase 0):** every per-phase GATE PASS recorded by `/run` (in PLAN_FILE checkboxes, REVIEW_FILE entries, commit message bodies, or pipeline `complete_step` outputs) must include the `## Real-boundary evidence` block defined in `base/CLAUDE.md` § "GATE PASS template — real-boundary evidence (Invariant 5, STAB Phase 0)". A GATE without this block is structurally invalid and will be flagged by `orchestrator/tests/invariants/test_invariant_5_gate_evidence.py`.

**Step 2 — Immediately invoke the `orchestrate` skill** using the Skill tool with:
- skill: `orchestrate`
- args: `custom "__RESOLVED__ PLAN_FILE={PLAN_FILE} TASKS_FILE={TASKS_FILE} REVIEW_FILE={REVIEW_FILE} PROJECT_SUFFIX={PROJECT_SUFFIX}. Execute phases from PLAN_FILE. SCOPE: $ARGUMENTS (empty=1, number=N phases, 'all'=all remaining). <!-- Fragment: progress-format. Source: base/CLAUDE.md:33-76. L71 (TodoWrite-linkage) is intentionally excluded — it targets the main orchestrating session, not sub-agents. When adding this to a new sub-agent-spawning skill, insert `<!-- INCLUDE:progress-format -->` where the old short PROGRESS block was; sync.ps1 Expand-Includes (sync.ps1:152-173) inlines this file's full contents. -->

**MANDATORY Progress Output Convention** (applies to sub-agents emitting progress during pipeline / phase / task-list work):

- **Always show the full step list** — never output a single progress line in isolation. Every progress update must show ALL steps with their statuses, so the user sees the full context.
- **Bar:** exactly 10 chars — `▰` (U+25B0) for done, `▱` (U+25B1) for remaining. Never 7, 8, 9 or any other count. Clamp filled count to `w - 1` when `pct < 100` so the cursor position stays visible.
- **Time format:** `HH:MM +elapsed` — local start time + elapsed since start. Elapsed: under 60 s → `12s`; 1-59 min → `2m 14s`; 60+ min → `1h 3m`. Capture the start time at the first progress line; reuse on subsequent updates (example: `14:23 +2m 14s` = started at 14:23 local, running for 2m 14s).
- **Step markers:** `✓` = done (with elapsed), `▶` = in progress, `○` = pending.
- **Two levels of progress:**
  - **Major** (phases / pipeline steps) — REQUIRED. Always emit the full list of all phases/steps. `[N/M]` = current ordinal / total in the plan (or pipeline), not what was requested in the current invocation.
  - **Minor** (tasks within a phase) — OPTIONAL. Emit when there are 3+ tasks AND significant work between them (file reads, edits, tool calls). Skip Minor for trivial/adjacent tasks (e.g. sequential edits in one file) to avoid noise.
- **Phase list compactness:** the NEXT phase shows its full name; remaining phases collapse to a range (e.g. `○ Phase 26.3–26.5`). Completed phases always show name + elapsed.
- **Format — multi-phase with task detail (Major + Minor):**

      ▶ /run main [1/5] ▰▰▱▱▱▱▱▱▱▱ 20% | 14:23 +2m 14s
        ▶ Phase 26.1 — Smart Aggregation [3/6]
          ✓ T1.1: extractBaseCommand() (18s)
          ✓ T1.2: aggregateUsagePatterns() (25s)
          ▶ T1.3: getUsagePatterns() filtering...
          ○ T1.4: messages.ts
          ○ T1.5: tests
          ○ build + deploy
        ○ Phase 26.2 — Improved Grouping + Compact Display
        ○ Phase 26.3–26.5

- **Format — pipeline steps (Major only):**

      ▶ feature-abc123 [3/9] ▰▰▰▱▱▱▱▱▱▱ 33% | 15:07 +1m 42s
        ✓ architect (42s)
        ✓ dev-lead (18s)
        ▶ backend-dev — implementing...
        ○ test-engineer
        ○ code-reviewer

- **Format — test/command runs (single-line ALLOWED):**

      ▶ pytest ... → ✓ 1157 passed in 34s

  A single-line progress is an explicit exception to "always show full list", permitted ONLY for ad-hoc test/build/command runs outside a tracked pipeline or phase loop.

- **When to emit:**
  - **Major progress:** at the START and END of each phase / pipeline step.
  - **Minor progress:** when starting a new task within a phase, IF there were 3+ tool calls since the last progress output (prevents noise from adjacent edits).
  - **Always re-emit** after: test runs, builds, gate checks, commits.
- **Throttle:** max one full-list update per 5 seconds for the same task. LOOP INSTRUCTIONS: repeat the following per-phase cycle until scope is exhausted or no incomplete phases remain — (1) read PLAN_FILE and TASKS_FILE — identify (a) the last implemented-but-not-yet-gated phase, if any, and (b) the next incomplete phase to implement; if no incomplete phase exists, stop the loop immediately; (2) PER-PHASE GATE — if a prior implemented phase exists: run automated tests (must pass zero failures), call mcp__pal__codereview on all files changed in that phase (any finding at or above CLAUDE_GATE_MIN_BLOCKING_SEVERITY (default: any finding) → HALT ENTIRE LOOP), call mcp__pal__thinkdeep (any finding at or above CLAUDE_GATE_MIN_BLOCKING_SEVERITY (default: any finding) → HALT ENTIRE LOOP); if PAL MCP unavailable, perform these reviews using Agent tool with a different model tier (opus if current is sonnet; sonnet if current is opus) and document fallback model used; if this is the first iteration after /phase (no prior implemented phase) — skip the gate; (3) if gate fails — HALT the entire loop immediately, report which phase caused the failure and the findings, do NOT proceed to next phase; (4) only after gate passes (or first-iteration skip) — mark the GATE checkpoint of the previous phase as [x] in PLAN_FILE; (5) FOR EACH PHASE: start a tracked execute pipeline via start_pipeline(pipeline_type='execute', description='/run phase N: <name>', project=<basename>{PROJECT_SUFFIX}, context_vars={PHASE_NUMBER: N, PHASE_NAME: '...', PLAN_FILE: '...', TASKS_FILE: '...', REVIEW_FILE: '...'}). Drive pipeline steps 1-7 via complete_step. This gives list_active_pipelines visibility for each phase; (6) implement all tasks in the next phase per the plan — when tasks involve external libraries or APIs, use mcp__context7__resolve-library-id + mcp__context7__query-docs to verify current documentation before writing code; PLAN TRACKING (PTR.4): at phase start, call plan_ops(action='mark', task_id=<id>, status='in_progress', is_active=true) for the first task; at each task completion, call plan_ops(action='mark', task_id=<id>, status='completed'); before each TodoWrite call, call plan_ops(action='sync_todo', project=<basename_of_cwd>{PROJECT_SUFFIX}) and use the returned task list for TodoWrite items; at phase end, call plan_ops(action='progress', project=<basename_of_cwd>{PROJECT_SUFFIX}) to report weighted progress; (7) update PLAN_FILE (mark implemented tasks done), docs/ROADMAP.md, and MEMORY.md with phase progress; (8) commit with mcp__pal__precommit gate; (9) invoke the /summary skill with args=subtotal to output a per-phase checkpoint (read-only — no doc writes); (10) LOOP CONTROL: if scope was a number N, decrement counter — if counter > 0 AND incomplete phases remain, continue to next iteration WITHOUT invoking /save; if scope was 'all', continue to next iteration WITHOUT invoking /save; if scope is exhausted OR no incomplete phases remain, exit the loop; END OF LOOP — invoke the /summary skill with args=subtotal for the final run summary (read-only — user may run /summary project afterward for full project analysis + doc actualization); then branch: if ALL phases in PLAN_FILE are now complete — automatically invoke the /finish skill (via Skill tool) to perform final critical analysis, double audit, documentation update, and commit; do NOT invoke /save; if phases REMAIN — output 'Next step: run /run again to continue.' (or /run N / /run all for bulk); invoke the /save skill to verify all state is persisted and prompt the user to run the built-in /clear command before the next /run."`

Do not describe what you are about to do — invoke the skill immediately.

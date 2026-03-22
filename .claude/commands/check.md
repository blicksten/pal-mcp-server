---
name: check
description: "Checkpoint: critical analysis, double audit, documentation update, save and commit"
---

# Check Workflow

You are executing the `/check` command — a shortcut for a quality checkpoint.

**FIRST OUTPUT:** Before any tool calls, print: `▶ /check`

**Step 0 — Detect session context (MANDATORY):**
1. Run one combined command: `bash -c 'printf "%s\n%s" "${CLAUDE_SESSION:-(no session)}" "$(git branch --show-current 2>/dev/null || true)"'` — line 1: CLAUDE_SESSION value, line 2: current git branch (may be empty).
2. Parse: SESSION_LINE=line 1, BRANCH_LINE=line 2.
3. If SESSION_LINE is `_`: force no-session mode — skip to step 6.
4. If SESSION_LINE is NOT `(no session)` and NOT `_`: validate `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. If invalid: ABORT — "Invalid CLAUDE_SESSION label." SESSION_LABEL=`{SESSION_LINE}` (explicit). Skip to step 5.
   If SESSION_LINE is `(no session)`: if BRANCH_LINE non-empty AND not a default branch (main/master/develop/dev/trunk/HEAD): sanitize (replace `[^A-Za-z0-9_-]` with `-`, truncate 63 chars). If starts `[A-Za-z0-9]`: SESSION_LABEL=`{sanitized}` (auto from branch). Else: SESSION_LABEL=(none).
5. SESSION_LABEL set: PLAN_FILE=`docs/PLAN-{SESSION_LABEL}.md`, TASKS_FILE=`docs/TASKS-{SESSION_LABEL}.md`, REVIEW_FILE=`docs/REVIEW-{SESSION_LABEL}.md`, PROJECT_SUFFIX=`__{SESSION_LABEL}`. Print: "Session: {SESSION_LABEL} — using {PLAN_FILE}" (append " (auto)" if from branch). Verify header if PLAN_FILE exists: read first 3 lines — must contain `Session: {SESSION_LABEL}`; if mismatch: ABORT — "Session mismatch."
6. SESSION_LABEL not set: PLAN_FILE=`docs/PLAN.md`, TASKS_FILE=`docs/TASKS.md`, REVIEW_FILE=`docs/REVIEW.md`, PROJECT_SUFFIX=(none). Print: "No session — using docs/PLAN.md"
7. Use PLAN_FILE/TASKS_FILE/REVIEW_FILE throughout. For `start_pipeline`: use `project=<basename_of_cwd><PROJECT_SUFFIX>`. For `list_active_pipelines`: if SESSION_LABEL set, pass `project=<basename_of_cwd><PROJECT_SUFFIX>`.

**PRE-FLIGHT — Orphan pipeline scan (run BEFORE invoking orchestrate):**
1. If SESSION_LABEL set: call `list_active_pipelines(project=<basename_of_cwd>__<SESSION_LABEL>)` — session-specific pipelines only
   If no SESSION_LABEL: call `list_active_pipelines()` — all pipelines (default behavior)
2. For each pipeline returned:
   - If stale (`stale: true`, >24h) OR all related work is committed in git → call `cancel_pipeline(id, "Closed by /check — work committed")`
   - If real pending work remains (not yet committed) → warn the user before proceeding
3. If SESSION_LABEL set: also call `list_active_pipelines()` (unfiltered) and compare to step 1 results:
   - Pipelines not in step 1 results are **legacy or other-session pipelines** (project=<basename> without label, project=None, or different label suffix)
   - If any found: report to user: "[N legacy/other-session pipeline(s) found: <IDs + projects>]. These are pre-session-isolation or from another session. Review manually — NOT auto-cancelled."
   - This is informational only — do NOT auto-cancel these pipelines
4. Only after own-session orphans are resolved — continue to orchestrate below.

**Immediately invoke the `orchestrate` skill** using the Skill tool with:
- skill: `orchestrate`
- args: `custom "__RESOLVED__ PLAN_FILE={PLAN_FILE} TASKS_FILE={TASKS_FILE} REVIEW_FILE={REVIEW_FILE} PROJECT_SUFFIX={PROJECT_SUFFIX}. Critical analysis + double audit, recursive until zero MEDIUM+ findings: (1) critical analysis of all current changes; (2) double audit — run lead-auditor then specialist-auditor, each with CV-GATE using mcp__pal__thinkdeep and mcp__pal__consensus (direct PAL MCP tool calls — if PAL MCP unavailable, perform internal cross-model review using Agent tool with a different model tier (opus if current is sonnet; sonnet if current is opus) and document fallback model used); (3) fix ALL MEDIUM+ findings found by either auditor; (4) repeat steps 2-3 until zero CRITICAL, HIGH, and MEDIUM findings remain; (5) update all documentation (ROADMAP.md, ANALYSIS.md, AGENTS.md, MEMORY.md, STATS.md if applicable); (6) save all artifacts; (7) commit with mcp__pal__precommit gate."`

Do not describe what you are about to do — invoke the skill immediately.

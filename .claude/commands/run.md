---
name: run
description: "Execute: read current plan, run per-phase gate for completed phase, implement next phase(s), audit, update docs, commit. Usage: /run [N|all] — 1 phase (default), N phases, or all remaining."
---

# Run Workflow

You are executing the `/run` command — a shortcut for implementing one or more planned phases.

**FIRST OUTPUT:** Before any tool calls, print: `▶ /run {$ARGUMENTS or '1'}`

**Step 0 — Detect session context (MANDATORY):**
1. Run one combined command: `bash -c 'printf "%s\n%s" "${CLAUDE_SESSION:-(no session)}" "$(git branch --show-current 2>/dev/null || true)"'` — line 1: CLAUDE_SESSION value, line 2: current git branch (may be empty).
2. Parse: SESSION_LINE=line 1, BRANCH_LINE=line 2.
3. If SESSION_LINE is `_`: force no-session mode — skip to step 6.
4. If SESSION_LINE is NOT `(no session)` and NOT `_`: validate `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. If invalid: ABORT — "Invalid CLAUDE_SESSION label." SESSION_LABEL=`{SESSION_LINE}` (explicit). Skip to step 5.
   If SESSION_LINE is `(no session)`: if BRANCH_LINE non-empty AND not a default branch (main/master/develop/dev/trunk/HEAD): sanitize (replace `[^A-Za-z0-9_-]` with `-`, truncate 63 chars). If starts `[A-Za-z0-9]`: SESSION_LABEL=`{sanitized}` (auto from branch). Else: SESSION_LABEL=(none).
5. SESSION_LABEL set: PLAN_FILE=`docs/PLAN-{SESSION_LABEL}.md`, TASKS_FILE=`docs/TASKS-{SESSION_LABEL}.md`, REVIEW_FILE=`docs/REVIEW-{SESSION_LABEL}.md`, PROJECT_SUFFIX=`__{SESSION_LABEL}`. Print: "Session: {SESSION_LABEL} — using {PLAN_FILE}" (append " (auto)" if from branch). Verify header if PLAN_FILE exists: read first 3 lines — must contain `Session: {SESSION_LABEL}`; if mismatch: ABORT — "Session mismatch."
6. SESSION_LABEL not set: PLAN_FILE=`docs/PLAN.md`, TASKS_FILE=`docs/TASKS.md`, REVIEW_FILE=`docs/REVIEW.md`, PROJECT_SUFFIX=(none). Print: "No session — using docs/PLAN.md"
7. Use PLAN_FILE/TASKS_FILE/REVIEW_FILE throughout. For `start_pipeline`: use `project=<basename_of_cwd><PROJECT_SUFFIX>`. For `list_active_pipelines`: if SESSION_LABEL set, pass `project=<basename_of_cwd><PROJECT_SUFFIX>`.

**Step 1 — Determine scope from ARGUMENTS (`$ARGUMENTS`):**
- Empty or `1` → run **1 phase** (default)
- Number `N` (e.g., `3`) → run **N consecutive phases**
- `all` → run **all remaining phases**

**Step 2 — Immediately invoke the `orchestrate` skill** using the Skill tool with:
- skill: `orchestrate`
- args: `custom "__RESOLVED__ PLAN_FILE={PLAN_FILE} TASKS_FILE={TASKS_FILE} REVIEW_FILE={REVIEW_FILE} PROJECT_SUFFIX={PROJECT_SUFFIX}. Execute phases from PLAN_FILE. SCOPE: $ARGUMENTS (empty=1, number=N phases, 'all'=all remaining). LOOP INSTRUCTIONS: repeat the following per-phase cycle until scope is exhausted or no incomplete phases remain — (1) read PLAN_FILE and TASKS_FILE — identify (a) the last implemented-but-not-yet-gated phase, if any, and (b) the next incomplete phase to implement; if no incomplete phase exists, stop the loop immediately; (2) PER-PHASE GATE — if a prior implemented phase exists: run automated tests (must pass zero failures), call mcp__pal__codereview on all files changed in that phase (CRITICAL → HALT ENTIRE LOOP), call mcp__pal__thinkdeep (CRITICAL → HALT ENTIRE LOOP); if PAL MCP unavailable, perform these reviews using Agent tool with a different model tier (opus if current is sonnet; sonnet if current is opus) and document fallback model used; if this is the first iteration after /phase (no prior implemented phase) — skip the gate; (3) if gate fails — HALT the entire loop immediately, report which phase caused the failure and the findings, do NOT proceed to next phase; (4) only after gate passes (or first-iteration skip) — mark the GATE checkpoint of the previous phase as [x] in PLAN_FILE; (5) route next phase via mcp__orchestrator__route_task and follow its decision; (6) implement all tasks in the next phase per the plan; (7) update PLAN_FILE (mark implemented tasks done), docs/ROADMAP.md, and MEMORY.md with phase progress; (8) commit with mcp__pal__precommit gate; (9) invoke the /summary skill with args=subtotal to output a per-phase checkpoint (read-only — no doc writes); (10) LOOP CONTROL: if scope was a number N, decrement counter — if counter > 0 AND incomplete phases remain, continue to next iteration WITHOUT invoking /save; if scope was 'all', continue to next iteration WITHOUT invoking /save; if scope is exhausted OR no incomplete phases remain, exit the loop; END OF LOOP — invoke the /summary skill with args=subtotal for the final run summary (read-only — user may run /summary standalone afterward for deep analysis + doc actualization); then branch: if ALL phases in PLAN_FILE are now complete — output 'All phases complete.'; do NOT invoke /save; if phases REMAIN — output 'Next step: run /run again to continue.' (or /run N / /run all for bulk); invoke the /save skill to verify all state is persisted and prompt the user to run the built-in /clear command before the next /run."`

Do not describe what you are about to do — invoke the skill immediately.

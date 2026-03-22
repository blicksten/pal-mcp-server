---
name: phase
description: "Phase planning: critical analysis, double audit, phase breakdown with task decomposition, plan persistence, documentation update, commit"
---

# Phase Planning Workflow

You are executing the `/phase` command — a shortcut for structured phase planning.

**FIRST OUTPUT:** Before any tool calls, print: `▶ /phase {$ARGUMENTS}`

**Step 0 — Detect session context (MANDATORY):**
1. Run one combined command: `bash -c 'printf "%s\n%s" "${CLAUDE_SESSION:-(no session)}" "$(git branch --show-current 2>/dev/null || true)"'` — line 1: CLAUDE_SESSION value, line 2: current git branch (may be empty).
2. Parse: SESSION_LINE=line 1, BRANCH_LINE=line 2.
3. If SESSION_LINE is `_`: force no-session mode — skip to step 6.
4. If SESSION_LINE is NOT `(no session)` and NOT `_`: validate `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. If invalid: ABORT — "Invalid CLAUDE_SESSION label." SESSION_LABEL=`{SESSION_LINE}` (explicit). Skip to step 5.
   If SESSION_LINE is `(no session)`: if BRANCH_LINE non-empty AND not a default branch (main/master/develop/dev/trunk/HEAD): sanitize (replace `[^A-Za-z0-9_-]` with `-`, truncate 63 chars). If starts `[A-Za-z0-9]`: SESSION_LABEL=`{sanitized}` (auto from branch). Else: SESSION_LABEL=(none).
5. SESSION_LABEL set: PLAN_FILE=`docs/PLAN-{SESSION_LABEL}.md`, TASKS_FILE=`docs/TASKS-{SESSION_LABEL}.md`, REVIEW_FILE=`docs/REVIEW-{SESSION_LABEL}.md`, PROJECT_SUFFIX=`__{SESSION_LABEL}`. Print: "Session: {SESSION_LABEL} — using {PLAN_FILE}" (append " (auto)" if from branch). Verify header if PLAN_FILE exists: read first 3 lines — must contain `Session: {SESSION_LABEL}`; if mismatch: ABORT — "Session mismatch."
6. SESSION_LABEL not set: PLAN_FILE=`docs/PLAN.md`, TASKS_FILE=`docs/TASKS.md`, REVIEW_FILE=`docs/REVIEW.md`, PROJECT_SUFFIX=(none). Print: "No session — using docs/PLAN.md"
7. Use PLAN_FILE/TASKS_FILE/REVIEW_FILE throughout. For `start_pipeline`: use `project=<basename_of_cwd><PROJECT_SUFFIX>`. For `list_active_pipelines`: if SESSION_LABEL set, pass `project=<basename_of_cwd><PROJECT_SUFFIX>`.

**Immediately invoke the `orchestrate` skill** using the Skill tool with:
- skill: `orchestrate`
- args: `custom "__RESOLVED__ PLAN_FILE={PLAN_FILE} TASKS_FILE={TASKS_FILE} REVIEW_FILE={REVIEW_FILE} PROJECT_SUFFIX={PROJECT_SUFFIX}. Critical analysis + double audit, recursive until zero MEDIUM+ findings: (1) critical analysis of current state; (2) double audit — run lead-auditor then specialist-auditor, each with CV-GATE using mcp__pal__thinkdeep and mcp__pal__consensus (direct PAL MCP tool calls — if PAL MCP unavailable, perform internal cross-model review using Agent tool with a different model tier (opus if current is sonnet; sonnet if current is opus) and document fallback model used); (3) fix ALL MEDIUM+ findings found by either auditor; (4) repeat steps 2-3 until zero CRITICAL, HIGH, and MEDIUM findings remain; (5) phase decomposition: break work into phases with concrete tasks per P41-P44 planning rules; (6) persist plan to PLAN_FILE and TASKS_FILE — each phase MUST end with a mandatory GATE step: '- [ ] GATE: run tests + mcp__pal__codereview + mcp__pal__thinkdeep (if PAL unavailable: Agent tool with different model tier) — zero CRITICAL before next phase'; (6b) add '## Next Plans' section at the end of PLAN_FILE — read docs/ROADMAP.md to identify the next 1–4 phases after the current plan, list each with Phase ID, title, status emoji (✅/🚧/⏸/📋), and one-line goal; if next phases are unknown, write 'TBD — run /phase after this plan completes'; (7) save all artifacts; (8) update all documentation (ROADMAP.md, ANALYSIS.md, AGENTS.md, MEMORY.md); (9) commit with mcp__pal__precommit gate."`

Do not describe what you are about to do — invoke the skill immediately.

## Final Output (MANDATORY after commit)

After the commit succeeds, output a **Plan Summary** directly to the user:

```
## Phase N Plan — <Title>

**Audit:** APPROVE [C+O] — <findings summary, e.g. "2 CRITICAL + 3 HIGH fixed">
**Commit:** <hash>

### Phases & Steps

| Phase | Goal | Key Tasks | Can start |
|-------|------|-----------|-----------|
| Phase 1 — <Name> | <one-line goal> | T1.1, T1.2, ... | Immediately / After X |
| Phase 2 — <Name> | <one-line goal> | T2.1, T2.2, ... | After Phase 1 |
| ...   |      |           |           |

### Findings Fixed

| ID | Severity | Description | Resolution |
|----|----------|-------------|------------|
| C-1 | CRITICAL | ... | ... |
| H-1 | HIGH | ... | ... |
| M-1 | MEDIUM | ... | ... |
```

This output must be in the main response, not inside a tool call or file.

After the Plan Summary, **invoke the `/summary` skill** to append the current session state (commits done, plan status, next work, test count).

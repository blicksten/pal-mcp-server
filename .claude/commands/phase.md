---
name: phase
description: "Phase planning: critical analysis, double audit, phase breakdown with task decomposition, plan persistence, documentation update, commit"
---

# Phase Planning Workflow

You are executing the `/phase` command — a shortcut for structured phase planning.

**FIRST OUTPUT:** Before any tool calls, print: `▶ /phase {$ARGUMENTS}`

**Step 0 — Resolve session context:**
Call `resolve_session` MCP tool with: `project_root` = current working directory, `env_session` = CLAUDE_SESSION env var (empty if unset), `branch` = current git branch, `skill_args` = ARGUMENTS, `skill_name` = "phase", `instance_id` = INSTANCE_ID from [SESSION] tag (empty if unavailable), `owner_id` = session_id from [SESSION] tag (empty if unavailable).

Use returned `plan_file`, `tasks_file`, `review_file`, `label`, `source`, `project_suffix`, `parsed_args`, `warning` throughout. For `start_pipeline`: use `project=<basename_of_cwd>{project_suffix}`. For `list_active_pipelines`: ALWAYS pass `project=<basename_of_cwd>{project_suffix}`.
Use `parsed_args.auto_label` for the auto-extracted session label (when `resolve_session` derives a label from the description). Use `parsed_args.description` as the planning description.

**Step 0a — Session label announcement:**
- When `source='auto-label-on-default-branch'` → print `"Auto-session: **{label}** → {plan_file}"`. If `warning` is set, print it as a note.
- When `source='requires-picker'` → call `list_available_sessions(project=<basename_of_cwd>, owner_id=session_id)`. If sessions list is empty: print `"No active sessions. Start with: /phase 'description' or /new-session LABEL"` and **STOP**. Otherwise, show the picker table (label, status, last_heartbeat, claim_status) and ask the user to pick or provide a description, then **STOP** (user must re-invoke `/phase 'description'`).
- When label is set and source is not one of the above → print `"Session: **{label}** → {plan_file}"`.
- When label is None (no session) → proceed silently.

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

**Anti-hallucination rule (phase exception):** `/phase` is the ONLY skill that may derive a session label from description text (`parsed_args.auto_label`) because it CREATES new plan files. All other skills (`/run`, `/save`, `/check`, `/finish`, `/summary`) MUST NOT — they only reference EXISTING plans. Even in `/phase`, the derived label must pass sanitization (`^[A-Za-z][A-Za-z0-9_-]*$`, min 3 chars) and must not be a conversation topic or generic word. The `resolve_session` tool enforces this — any other derivation is a hallucination.

**PIPELINE MODE (default):** Gather context (ARGUMENTS as description, existing PLAN_FILE if any), then call `start_pipeline` MCP tool to create a tracked planning pipeline:

```
start_pipeline(
  pipeline_type="planning",
  description="/phase: {parsed_args.description or ARGUMENTS}",
  project=<basename_of_cwd>{PROJECT_SUFFIX},
  context_vars={
    "PLAN_FILE": PLAN_FILE,
    "TASKS_FILE": TASKS_FILE,
    "REVIEW_FILE": REVIEW_FILE,
    "USER_CONTEXT": parsed_args.description or ARGUMENTS,
  }
)
```

Then invoke `/orchestrate` to drive the pipeline steps:
- skill: `orchestrate`
- args: `custom "__RESOLVED__ PLAN_FILE={PLAN_FILE} TASKS_FILE={TASKS_FILE} REVIEW_FILE={REVIEW_FILE} PROJECT_SUFFIX={PROJECT_SUFFIX}. Drive the active planning pipeline to completion. For each step: read instruction, execute with the assigned agent, produce STEP RESULT, call complete_step. Planning rules: (1) each phase that modifies code/data/infrastructure must include a Rollback subsection; (2) each phase MUST end with a GATE step: '- [ ] GATE: tests + codereview + thinkdeep — zero errors (any finding at or above CLAUDE_GATE_MIN_BLOCKING_SEVERITY; default: any finding)'; (3) add '## Next Plans' at end of PLAN_FILE from ROADMAP.md; (4) recursive audit: repeat lead-auditor + specialist-auditor until zero errors (any finding at or above CLAUDE_GATE_MIN_BLOCKING_SEVERITY; default: any finding) findings. PLAN TRACKING (PTR.4): after writing PLAN_FILE, call plan_ops(action='load', project=<basename_of_cwd>{PROJECT_SUFFIX}, plan_json=<structured JSON of phases and tasks from the plan>) to load the plan tree into the index for progress tracking."`

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

After the Plan Summary, **invoke the `/summary` skill** (no args — session mode: quick summary of commits, plan status, next work, test count). For full project deep analysis + doc actualization, the user can run `/summary project` separately.

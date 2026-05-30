---
name: check
description: "Checkpoint: critical analysis, double audit, documentation update, save and commit"
---

# Check Workflow

You are executing the `/check` command — a shortcut for a quality checkpoint.

**FIRST OUTPUT:** Before any tool calls, print: `▶ /check`

**Step 0 — Resolve session context:**
Call the `resolve_session` MCP tool with: `project_root` = current working directory, `env_session` = value of CLAUDE_SESSION env var (or `""` if unset), `branch` = current git branch name, `skill_args` = ARGUMENTS string (if any), `skill_name` = name of the invoking skill (e.g. `"run"`, `"check"`), `instance_id` = value of INSTANCE_ID parsed from the `[SESSION] ... instance=<id>` tag (or `""` if not present), `owner_id` = session_id parsed from the `[SESSION] ... session_id=<id>` tag (or `""` if not present).

The tool returns `SessionResult` JSON with: `plan_file`, `tasks_file`, `review_file`, `label`, `source`, `project_suffix`, `instance_id`, `warnings`, `parsed_args`.

**Use the returned values throughout:**
- `plan_file` / `tasks_file` / `review_file` — session-scoped file paths
- `label` — session label (null = no session)
- `project_suffix` — append to project name for `start_pipeline` / `list_active_pipelines`
- `parsed_args` — skill-specific extracted arguments (e.g. `count`, `mode`, `description`, `workflow`)

**Output:** Print session result ONLY when `label` is set: "Session: **{label}** → {plan_file}". When no label: proceed silently.

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

**CONTEXT GATHERING (MANDATORY — run BEFORE invoking orchestrate):**

**CRITICAL RULE: ALWAYS RUN REAL VERIFICATION.** When the user invokes `/check`, they expect actual audit work — never shortcut with "already audited in this session", "no changes since last check", or "no further action needed." If the same code was checked 5 minutes ago, check it again. The user explicitly asked. If there are genuinely zero changes AND zero commits AND no user description, ask "What should I check?" rather than deciding on your own to skip.

**CRITICAL RULE: NEVER ask the user clarifying questions about scope.** Determine CHECK_SCOPE algorithmically from the rules below and proceed immediately. If the user wrote something after `/check`, that is the primary target — combine it with any uncommitted changes and act. Do not ask "what do you want to check?" — the user already told you.

Capture USER_CONTEXT and CHANGE_CONTEXT to give the audit something real to analyze.

1. **User description** — set USER_CONTEXT from ARGUMENTS (the text the user typed after `/check`, with session label already consumed by step 4b if applicable). If ARGUMENTS is empty or was fully consumed by session detection: USER_CONTEXT = "(no user description)".

2. **Git changes** — run these in parallel:
   - `git diff --stat` — unstaged changes summary
   - `git diff --cached --stat` — staged changes summary
   - `git log --oneline -10` — recent commits for context
   - If PLAN_FILE exists: read PLAN_FILE (first 60 lines) to understand current phase

3. **Build CHANGE_CONTEXT** — a compact summary string:
   - If there are staged or unstaged changes: list modified files from `--stat` output
   - If no uncommitted changes: use the last 3-5 commit messages as context (the user likely wants to check recently committed work)
   - If PLAN_FILE has an active (unchecked) phase: note the phase name

4. **Determine CHECK_SCOPE** — what exactly to audit:
   - If USER_CONTEXT is not "(no user description)": the user provided a specific description — audit THAT description plus ALL uncommitted code changes. The user's text is the PRIMARY analysis target. Do NOT split or disambiguate — combine everything into one scope.
   - If uncommitted changes exist but no user description: audit those changes (git diff)
   - If no uncommitted changes and no user description: audit the most recent commit(s) since last `/check` or `/finish`
   - Print a one-line summary: `Scope: {CHECK_SCOPE}` (e.g., "Scope: user description + 3 unstaged files", "Scope: last 2 commits (no uncommitted changes)", "Scope: staged changes in 5 files")

**PIPELINE MODE (default):** Call `start_pipeline` MCP tool to create a tracked checkpoint pipeline, then drive it via `/orchestrate`:

```
start_pipeline(
  pipeline_type="checkpoint-check",
  description=CHECK_SCOPE,
  project=<basename_of_cwd>{PROJECT_SUFFIX},
  context_vars={
    "CHECK_SCOPE": CHECK_SCOPE,
    "USER_CONTEXT": USER_CONTEXT,
    "CHANGE_CONTEXT": CHANGE_CONTEXT,
    "PLAN_FILE": PLAN_FILE,
    "TASKS_FILE": TASKS_FILE,
    "REVIEW_FILE": REVIEW_FILE,
  }
)
```

Save the returned `pipeline_id`. Then invoke the `orchestrate` skill with:
- skill: `orchestrate`
- args: `custom "__RESOLVED__ PLAN_FILE={PLAN_FILE} TASKS_FILE={TASKS_FILE} REVIEW_FILE={REVIEW_FILE} PROJECT_SUFFIX={PROJECT_SUFFIX}. PIPELINE_ID={pipeline_id}. Drive checkpoint-check pipeline {pipeline_id} to completion. For each step: (1) read the step instruction from the pipeline response, (2) launch the step's agent via Agent tool with PIPELINE CONTEXT injected, (3) collect STEP RESULT, (4) call complete_step(pipeline_id, step_output). If complete_step returns HALT: fix the issue and resubmit. Recursive audit: if auditors find blocking-severity issues (at or above CLAUDE_GATE_MIN_BLOCKING_SEVERITY; default: any finding), fix them and re-run audit steps until zero errors. <!-- Fragment: progress-format. Source: base/CLAUDE.md:33-76. L71 (TodoWrite-linkage) is intentionally excluded — it targets the main orchestrating session, not sub-agents. When adding this to a new sub-agent-spawning skill, insert `<!-- INCLUDE:progress-format -->` where the old short PROGRESS block was; sync.ps1 Expand-Includes (sync.ps1:152-173) inlines this file's full contents. -->

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
- **Throttle:** max one full-list update per 5 seconds for the same task."`

Do not describe what you are about to do — invoke the skill immediately.

---

## VERDICT RENDERING (ZFE.2 — MANDATORY)

The final audit summary — both the in-chat "What was done / Findings table / Manual review" block and any `docs/AUDIT.md` update — **MUST** render the findings table from the `audit_findings` DB, not author it free-form. The DB is the single source of truth; LLM narration is ordering metadata only.

**Real-boundary evidence (Invariant 5, STAB Phase 0):** when `/check` is finalizing a phase whose work asserts an invariant from `docs/spikes/2026-04-27-invariants-for-plan-rewrite.md`, the audit summary must include the verbatim `## Real-boundary evidence` block defined in `base/CLAUDE.md` § "GATE PASS template — real-boundary evidence". The block is part of the verdict, not a free-form narration. The Phase 0 meta-test (`orchestrator/tests/invariants/test_invariant_5_gate_evidence.py`) flags any verdict missing the block as INVALID.

Before writing the Findings table:

1. Call `mcp__orchestrator__list_all_findings(pipeline_id=<pipeline_id>)` to fetch every finding for the pipeline.
2. For each row in the returned `data.findings` list, emit one table line in this exact shape:
   ```
   | {finding_id} | {severity} | {description} | {status} | {action_taken or escalation_to} |
   ```
3. The schema CHECK constraint limits status to `Open` / `Fixed` / `Escalated`. If a row comes back with any other value (e.g. a manual SQL insert slipped past the constraint, or a future migration adds a status without updating this skill), surface it as an **anomaly row** — do NOT silently omit it. Flag the pipeline for manual review.
4. If the DB has zero rows for the pipeline AND no unresolved audit findings were declared during the run, skip the table entirely and write "No findings — all clear" instead.

**Forbidden:**
- Authoring finding rows from memory or inference.
- Adding columns (severity × 2, "Priority", etc.) that are not in the DB row.
- Silent deduplication — if the DB has two rows, the table has two rows.

The Manual review table (items requiring human sign-off) is still LLM-authored from Escalated rows — but the Escalated rows themselves come from the DB via the same `list_all_findings` call, filtered to `status='Escalated'`. Never list an Escalated finding in Manual review without a matching DB row.

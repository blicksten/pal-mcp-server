---
name: do
description: "Unified lifecycle executor: plan, implement, gate, commit in a loop. Usage: /do 'goal' (first call) or /do (resume after /clear)."
---

# Do Workflow

You are executing the `/do` command -- a unified lifecycle executor that wraps /phase, /run, /save, /check, and /finish into a single reentrant command.

**FIRST OUTPUT:** Before any tool calls, print: `> /do {$ARGUMENTS}`

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

<!-- Note: there is no Step 0a in /do — the session-preamble fragment above covers Step 0, and Step 0b (claim guard) comes from the session-claim-guard fragment. Skipping 0a is intentional. -->

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

**Step 0c -- Anti-hallucination gate:**
After Step 0 resolves SESSION_LABEL and PLAN_FILE:
1. If SESSION_LABEL is set: validate format `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. If invalid: force SESSION_LABEL=(none), fall back to `docs/PLAN.md`. If valid: verify `docs/PLAN-{SESSION_LABEL}.md` exists via glob. If not found: fall back to `docs/PLAN.md` with warning.
2. NEVER derive SESSION_LABEL from the conversation topic, task description, or user request content. Only `resolve_session` output is valid.

## Step 1 -- State Detection

Read PLAN_FILE with the Read tool. Determine which branch to follow:

### Branch A: FIRST CALL (PLAN not found + has description)
Condition: PLAN_FILE does not exist AND `parsed_args.description` is non-empty.

1. Invoke the `/phase` skill (via Skill tool) with args = `parsed_args.description`.
2. After /phase returns: print the plan summary to the user.
3. Ask: **"Plan created. Approve? [y/n/edit]"**
4. PAUSE and wait for user input.
   - On **"y"**: proceed to Step 2.
   - On **"n"**: print "Plan rejected. Delete PLAN_FILE or edit manually." STOP.
   - On **"edit"**: print "Edit PLAN_FILE manually, then run `/do` to resume." STOP.

### Branch B: RESUME (PLAN exists + incomplete phases)
Condition: PLAN_FILE exists AND contains at least one `- [ ]` checkbox.

Proceed directly to Step 1.5 (Guards), then Step 2.

### Branch C: COMPLETION (PLAN exists + all phases done)
Condition: PLAN_FILE exists AND all checkboxes are `- [x]`.

Invoke the `/finish` skill (via Skill tool). STOP.

### Branch D: NO TASK (PLAN not found + no description)
Condition: PLAN_FILE does not exist AND `parsed_args.description` is empty.

Print: "No active /do task. Start with: `/do 'goal description'`" STOP.

### Branch E: RESUME FROM MARKER (parsed_args.resume is True)
Condition: `parsed_args.resume` is True (triggered by `[DO-RESUME]` tag after /clear).

Read the do-resume marker file (`.claude/do-resume-{label}.local.md` or `.claude/do-resume.local.md`). Extract session, plan, next_phase, head_sha. Delete the marker file after reading. Proceed to Step 1.5 (Guards), then Step 2.

## Step 1.5 -- Guards

Run these checks before executing the next phase:

1. **Dirty workspace guard:** Run `git status --porcelain`. If uncommitted changes exist AND this is a resume (Branch B or E, not Branch A):
   - Print diff summary (files changed).
   - Ask: "Uncommitted changes detected. [c]ontinue / [s]tash / [r]eset / [a]bort?"
   - PAUSE for user input. On "a": STOP. On "s": run `git stash`. On "r": ask confirmation then `git checkout .`. On "c": continue.

2. **Concurrency guard:** Call `list_active_pipelines(project=<basename>{project_suffix})`. If an `execute` pipeline is already active:
   - Print: "Active pipeline found: {pipeline_id} at step {N}/{total}."
   - Ask: "[r]esume existing / [a]bort?"
   - PAUSE. On "a": STOP.

3. **Branch/HEAD validation:** If resuming from marker (Branch E), compare current `git rev-parse HEAD` with stored `head_sha`. If different: print warning "HEAD changed since last /do phase (expected {head_sha}, got {current}). Continue? [y/n]". PAUSE.

## Step 2 -- Execute Next Phase

Invoke the `/run 1` skill (via Skill tool with args="1"). This runs exactly one phase from PLAN_FILE, including:
- Per-phase gate (tests + codereview + thinkdeep)
- Implementation of all tasks
- Commit with precommit validation

## Step 3 -- Post-Phase Assessment

After `/run 1` returns, re-read PLAN_FILE with the Read tool. Check for remaining `- [ ]` checkboxes.

### If incomplete phases remain:
1. Print: "Phase done. {N} phases remaining."
2. Print: **"Run `/clear` then `/do` to continue."**

### If all phases done:
1. Print: "All phases complete!"
2. Invoke the `/finish` skill (via Skill tool). This handles final audit, documentation update, and commit.

## Step 3.5 -- Gate Failure Handling

If `/run 1` reports a gate failure (HALT due to any finding at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`):

1. Print the findings summary.
2. Track `gate_failure_count` in working memory (starts at 0, increment on each failure, reset on success).
3. If `gate_failure_count` < 3: Ask "Gate failed ({gate_failure_count}/3). [f]ix and retry / [s]kip phase / [x] stop?"
   - On "f": attempt to fix findings, then re-run `/run 1`.
   - On "s": mark phase GATE as `[x]` with note "(skipped by user)", proceed to next phase.
   - On "x": STOP.
4. If `gate_failure_count` == 3: Ask "Gate failed 3 times. One more try? [y/n]"
5. If `gate_failure_count` >= 4: Print "Gate failed 4 times. **Human review required.** STOP." Hard stop -- do not offer retry.

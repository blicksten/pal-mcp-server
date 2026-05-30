---
name: test
description: "Run tests: generate test map, start TEP pipeline, report results. Usage: /test [scope|map|run|status|report|dashboard]"
---

# Test Workflow

You are executing the `/test` command — a shortcut for running tests through the TEP (Test Execution Pipeline).

**FIRST OUTPUT:** Before any tool calls, print: `▶ /test {$ARGUMENTS or ''}`

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

Use `parsed_args` fields: `subcommand` (map/status/report/dashboard/run/scope), `target`, `map_path`.

## Subcommand Dispatch

Based on `parsed_args.subcommand`:

### No subcommand (full project)

```
/test
```

1. Call `generate_test_map_tool(project_root=<cwd>, project_name=<basename>)` to collect all tests.
2. Save the returned JSON as `docs/test-map-<YYYYMMDD-HHMMSS>.yaml` (convert JSON to YAML first via Python).
3. Call `start_testing_pipeline(test_map_path=<relative path>, project_root=<cwd>, project=<basename>{project_suffix})`.
4. Drive the pipeline: for each step returned by `complete_step`, invoke a `test-engineer` agent (foreground, with PIPELINE CONTEXT injection) to execute the step. Validate each STEP RESULT before calling `complete_step`.
5. After pipeline completes: call `get_test_summary(pipeline_id)` and format the result using the box-drawing table (see Output Format below).

### Scoped test run

```
/test orchestrator
/test <file.py>
/test orchestrator/tests/test_config.py
```

1. Determine `paths` from `parsed_args.target`:
   - `"orchestrator"` or `"orch"` → `paths=["tests/"]`, run in `orchestrator/` subdirectory
   - A `.py` file path → `paths=["<file>"]`
   - A directory → `paths=["<dir>"]`
2. Call `generate_test_map_tool(project_root=<cwd>, paths=<paths>)`.
3. Continue from step 2 of the full-project flow above.

### Generate map only

```
/test map
```

1. Call `generate_test_map_tool(project_root=<cwd>)`.
2. Print the test map summary: number of groups, baseline total, group list with labels.
3. Save to `docs/test-map-<timestamp>.yaml`.
4. Print: "Test map saved. Run `/test run <path>` to start the pipeline."
5. **STOP** — do not start a pipeline.

### Run from existing map

```
/test run docs/test-map-20260415.yaml
```

1. Read `parsed_args.map_path`. If empty → error: "Usage: `/test run <map.yaml>`".
2. Call `start_testing_pipeline(test_map_path=<map_path>, project_root=<cwd>, project=<basename>{project_suffix})`.
3. Drive the pipeline (same as full-project step 4-5).

### Status

```
/test status
```

1. Call `list_active_pipelines(project=<basename>{project_suffix})`.
2. Filter for `pipeline_type == "testing"`.
3. If none active → print "No active testing pipelines."
4. If found → print pipeline ID, step progress, and current step info.
5. **STOP**.

### Report

```
/test report
```

1. Call `list_active_pipelines(project=<basename>{project_suffix})` to find the most recent testing pipeline.
2. If no testing pipeline found → try `pipeline_ops(action="list")` to find completed ones.
3. Call `get_test_summary(pipeline_id)`.
4. Format and print the box-drawing table (see Output Format below).
5. **STOP**.

### Dashboard

```
/test dashboard
```

This bypasses TEP — runs `npm test` directly since the dashboard uses Jest, not pytest.

1. Run: `cd vscode-dashboard && npm test 2>&1`
2. Parse the Jest output for:
   - `Test Suites: N passed, N total`
   - `Tests: N passed, N total`
   - `Time: Ns`
3. Print a simplified result table:

```
╔══════════════════════════════════════════════════╗
║  Dashboard Tests                  {time} PASSED  ║
╠══════════════════════════════════════════════════╣
║  Suites: {passed}/{total}  ·  Tests: {p}/{t}    ║
╚══════════════════════════════════════════════════╝
```

4. If tests failed: print the Jest failure output below the table.
5. **STOP**.

## Output Format (Box-Drawing Table)

After a testing pipeline completes, call `get_test_summary(pipeline_id)` and use the orchestrator's `format_test_summary_table()` to render results. The MCP tool returns a `TestSummary` JSON — pass it to the formatter.

Expected output shape:

```
╔══════════════════════════════════════════════════════════════╗
║  Test Results — {id}              {time}  {STATUS}          ║
╠══════════════════════════════╤════════╤════════╤═════════════╣
║ Group                        │ Tests  │ Status │ Time        ║
╠══════════════════════════════╪════════╪════════╪═════════════╣
║ Config                       │  47/47 │  ✓     │  3.2s       ║
║ Pipeline                     │128/128 │  ✓     │ 12.1s       ║
║ Server & routing             │156/158 │  ✗     │ 18.7s       ║
╠══════════════════════════════╧════════╧════════╧═════════════╣
║ Total: 486/488  ·  Baseline: 486  ·  2 FAILED               ║
╠══════════════════════════════════════════════════════════════╣
║  ✗ test_route_task_empty — expected 'feature', got None      ║
║  ✗ test_start_pipeline_dup — lock not released within 5s     ║
╚══════════════════════════════════════════════════════════════╝
```

Groups have human-readable labels (not file names). Failed tests appear in the bottom section. When all tests pass, the failure section is omitted.

## Pipeline Driving

When driving a testing pipeline (full, scoped, or run-from-map):

1. After `start_testing_pipeline` returns `pipeline_id` and first step:
2. For each step:
   a. If agent is `qa-lead` (map review or baseline check) — execute directly: read the instruction, perform the review, submit STEP RESULT + GATE PROOF to `complete_step`.
   b. If agent is `test-engineer` — launch a foreground Agent with PIPELINE CONTEXT injection. The agent runs the locked command and submits ## TEST PROOF. Validate the proof, then call `complete_step`.
3. After all steps complete: call `get_test_summary` and display the table.

## Error Handling

- If `generate_test_map_tool` returns an error → print it and STOP.
- If `start_testing_pipeline` returns an error → print it and STOP.
- If a pipeline step HALTs (test failure) → print the failure details and STOP. Do not retry.
- If `get_test_summary` returns an error → print the raw pipeline report instead.

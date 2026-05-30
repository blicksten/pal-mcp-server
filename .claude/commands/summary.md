---
name: summary
description: "Session summary + deep project analysis: what was done (git log + completed tasks), current plan status, and full actualization of all spikes/plans/research with doc update. Use standalone or as a subtotal within /run and /phase. Modes: /summary (current session only), /summary project (all sessions in project + doc updates), /summary all (cross-project overview from projects.json)."
---

# Summary Workflow

You are executing the `/summary` command.

**FIRST OUTPUT:** Before any tool calls, print: `▶ /summary {$ARGUMENTS or ''}`

**Step 0 — Resolve session context:**
Call `resolve_session` MCP tool with: `project_root` = current working directory, `env_session` = CLAUDE_SESSION env var (empty if unset), `branch` = current git branch, `skill_args` = ARGUMENTS, `skill_name` = "summary", `instance_id` = INSTANCE_ID from [SESSION] tag (empty if unavailable), `owner_id` = session_id from [SESSION] tag (empty if unavailable).

Use returned `plan_file`, `tasks_file`, `review_file`, `label`, `project_suffix`, `parsed_args` throughout.
Use `parsed_args.mode` for summary mode (values: `"session"`, `"project"`, `"all"`, `"subtotal"`).
Print: "Session: **{label}** → {plan_file}" only when label is set. Otherwise proceed silently.

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

**ARGUMENTS check (MANDATORY — evaluate in this order):**
1. If ARGUMENTS contains word `subtotal` (case-insensitive, whole word): SUBTOTAL_MODE=true — skip Steps 3 and 4. Print: `[subtotal mode — deep analysis skipped]`. SUMMARY_MODE=`session`.
2. Else if ARGUMENTS contains word `all` (case-insensitive, whole word): SUMMARY_MODE=`all`. Print: `[mode: all — cross-project overview]`
3. Else if ARGUMENTS contains word `project` (case-insensitive, whole word): SUMMARY_MODE=`project`. Print: `[mode: project — all sessions in this project]`
4. Else: SUMMARY_MODE=`session`. Print: `[mode: session — current session only]`

SUBTOTAL_MODE defaults to false unless rule 1 above fires.

**Immediately execute the following steps — no tool pre-loading, no preamble:**

**Step 1 — Collect data (all calls in parallel):**
1. `git log origin/main..HEAD --oneline` — commits done this session (if `origin/main` does not exist: try `git log origin/HEAD..HEAD --oneline`; if still unavailable: use `git log -n 20 --oneline`)
2. Read PLAN_FILE (from Step 0) — current phase status + `## Next Plans` section
3. Read `docs/ROADMAP.md` — overall status line (first 5 lines)
4. Run test suite count (skip if SUBTOTAL_MODE=true — report "Tests: (skipped)" instead): `npm test -- --passWithNoTests 2>&1 | tail -5` (or `pytest --co -q 2>&1 | tail -3` for Python) — current test count

**Step 2 — Output the quick summary directly to the user:**

```
## Session Summary — <project name from cwd>

### Done this session
<one line per commit: `<hash> <message>`, newest first>

### Current plan status
<For each phase in PLAN_FILE: one line — "Phase X — Name: ✅ DONE / 🚧 N/M tasks / 📋 PLANNED">

### Next planned work
<From ## Next Plans in PLAN_FILE — table of Phase | Status | Goal>
<If PLAN_FILE missing or no Next Plans section: read ROADMAP.md and infer>

**Tests**: <N>/<N> | **Unpushed**: <N> commits | **Branch**: <branch name>
```

**Step 3 — Deep analysis (skip entirely if SUBTOTAL_MODE=true):**

**If SUMMARY_MODE=`session`:**
Skip Step 3. Print: `[session mode — use /summary project for full project analysis or /summary all for cross-project]`

**If SUMMARY_MODE=`project`:**
Scan all project artifacts in parallel:
1. `find docs/ -maxdepth 2 -name "*.md" -type f` — list all docs files
2. `find docs/spikes -maxdepth 2 -name "*.md" -type f 2>/dev/null` — all spike files (if dir exists)
3. `find docs/ -maxdepth 2 -name "PLAN-*.md" -type f 2>/dev/null` — all session-scoped plan files
4. `find docs/ -maxdepth 2 -name "TASKS*.md" -type f 2>/dev/null` — all task files

Then read all discovered spike files + any `docs/PLAN-*.md` files (in parallel, up to 6 files).
If more than 6 files found: prioritize by newest modification date (newest first); read the top 6; list the remaining file names in the output under `[N additional files not read: <names>]`.

Analyze and output the **Deep Analysis** section:

```
## Deep Analysis — <project name>

### Spikes & Research
<For each spike file found: "spike-name.md — STATUS (DONE/IN-PROGRESS/STALE) — one-line conclusion">
<If none found: "No spike files found.">

### Plans & Sessions
<For each PLAN-*.md found: "PLAN-label.md — Phase N.M status — last activity date">
<Main PLAN_FILE: current phase + next blocked/pending phases>

### Where we are
<2-3 sentences: current project state, what is working, what is blocked>

### What needs to be done next
<Ordered list of concrete next actions, most critical first>
<Include: blocked phases with their blockers, pending spikes, overdue docs>

### Blockers
<List blockers preventing progress. "None" if clear.>
```

**If SUMMARY_MODE=`all`:**
Cross-project overview using `projects.json`:
1. Locate `projects.json`: try current directory first (`./projects.json`); if not found, try `~/claude-workspace/claude-team-control/projects.json`. If neither exists: print warning and stop — do NOT proceed to Step 4 (Step 4 is project mode only).
2. Also check for `projects.local.json` in the same directory as `projects.json` — if present, merge its `projects` entries into a combined map (both files use a JSON object where keys are project names; local entries override on key collision).
3. Expand `~` in each project `path` to the actual home directory ($HOME). Use safe quoting for `<path>` in ALL shell calls (e.g., `test -d "$path"`, `git -C "$path"`, `find "$path/docs" ...`). Check existence with `test -d "$path"`.
4. For each existing project directory, run **in parallel** (up to 8 at once):
   a. If `test -f "$path/docs/ROADMAP.md"`: read first 10 lines — current phase/status. Else: record "missing" (will appear in Attention Required).
   b. Run this fallback chain (first command that succeeds wins): `git -C "$path" log origin/main..HEAD -n 5 --oneline 2>/dev/null || git -C "$path" log origin/HEAD..HEAD -n 5 --oneline 2>/dev/null || git -C "$path" log -n 5 --oneline 2>/dev/null` — recent commits (unpushed or last 5).
   c. `find "$path/docs" -maxdepth 1 -name "PLAN-*.md" 2>/dev/null | wc -l` — active session count.
5. Output the **Cross-Project Overview**:

```
## Cross-Project Overview — <ISO date>

| Project | Description | Sessions | Unpushed | Phase/Status |
|---------|-------------|----------|----------|--------------|
| <name>  | <desc>      | <N>      | <N>      | <from ROADMAP line 1-5> |
...

### Projects with Activity
<For each project with unpushed commits: "project-name — N commits — <latest commit message>">

### Attention Required
<Projects with >3 unpushed commits, missing ROADMAP.md, or no docs/ directory>
<"None" if all projects are clean>
```

Step 3 in `all` mode is read-only — no writes to any project files. After printing the Cross-Project Overview: **stop — do NOT proceed to Step 4** (Step 4 is `project` mode only).

**Step 4 — Update documentation (SUMMARY_MODE=`project` only — SKIP for `session` and `all` modes, skip if SUBTOTAL_MODE=true):**

After outputting the Deep Analysis, update `docs/ROADMAP.md`:
- Mark any phases that are visibly DONE in PLAN_FILE but still show as pending in ROADMAP.md
- Add or replace the `<!-- last-summary: <ISO date> -->` comment at the top (in-place edit)
- Do NOT change phase structure, do NOT rewrite history — status column updates only

Then update `MEMORY.md` (project root) — **only if the file already exists** (`test -f MEMORY.md`):
- Update the `## Project Status` entry with current phase + test count + date
- If `MEMORY.md` does not exist: skip silently (do NOT create it)

**Rules:**
- If `git log origin/main..HEAD` is empty → "No commits this session."
- If PLAN_FILE is missing → show ROADMAP.md status only
- Keep each line ≤ 80 chars — truncate long commit messages with `…`
- Do NOT start pipelines, do NOT invoke orchestrate agents
- `session` mode (default): Steps 1-2 only — fast, current session only, no doc writes
- `project` mode: all steps — Step 3 scans all sessions, Step 4 writes docs
- `all` mode: Steps 1-3 — cross-project read-only overview, no doc writes
- `subtotal` keyword: Steps 1-2 only regardless of other arguments
- If a spike file has no explicit STATUS header: infer from content (last edit date, presence of "Conclusion" section)
- Step 4 writes occur AFTER Step 3 output is complete — tool calls are expected between Steps 3 and 4

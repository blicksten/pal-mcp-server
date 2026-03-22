<!-- DO NOT EDIT -- managed by sync.ps1 from claude-team-control -->
<!-- Synced: 2026-03-23 00:53:10 -->
<!-- Base: base/CLAUDE.md | Overlay: overlays/default.md -->


## Requirements

- When uncertain about any fact, API, or behavior: state "I don't know" explicitly. Never guess, hallucinate, or fabricate information.

## Language & Terminology

- When writing any code artifact (code, comments, docstrings, variable names, README, commit messages, diagrams): write in English.
- When encountering an English technical term with no established Russian equivalent: use the original Latin-script term (git stash, merge, rebase, commit, pull request). Never transliterate into Cyrillic.
- When responding to the user: match the language the user writes in.

## Research & Verification

### Tool-First Analysis (MANDATORY)

Before forming any conclusion about code, architecture, or technical decisions: make at least one tool call (Read, Grep, Glob, context7, WebSearch, WebFetch, MCP, or Task agent). Never reason from memory alone.

- Before implementing a solution or suggesting an approach: query official documentation via context7, WebSearch, or WebFetch to verify assumptions.
- Before choosing an API, library, or pattern: look up its actual behavior. Never assume.
- When in plan mode: actively explore the codebase (read files, search patterns, check dependencies). Plans without tool-grounded analysis are invalid.
- When analysis requires multi-file exploration or heavy research: delegate to a Task agent (Explore, Plan, general-purpose) to offload token cost from the main context.

### PAL MCP Tools (MANDATORY)

**PAL = the PAL MCP server tools (`mcp__pal__*`). Always call them directly in the main session via the MCP tool interface. Never substitute with orchestrator CV-gate calls, internal reasoning, or any other mechanism — PAL MCP is the only valid fulfillment. When PAL MCP is unavailable: do NOT skip cross-validation. Instead, perform internal cross-model review — launch a sub-agent via the Agent tool with a different model tier (opus if current session is sonnet; sonnet if current session is opus) with the same analysis prompt. Document which fallback model was used. Internal cross-model review is a valid substitute for PAL cross-validation only when PAL MCP is confirmed unavailable.**

Before concluding on architecture, bugs, or security: call the appropriate PAL MCP tool. Never keep complex reasoning purely internal.

| Trigger | Call |
|---------|------|
| Before concluding on a non-trivial problem (architecture, complex bug, performance, security) | `mcp__pal__thinkdeep` |
| Before presenting an implementation plan to the user | `mcp__pal__planner` |
| Before making a decision with significant long-term impact (technology choice, architecture trade-off) | `mcp__pal__consensus` |
| After writing or modifying non-trivial code | `mcp__pal__codereview` |
| Before committing changes (enforced by hook) | `mcp__pal__precommit` |
| When questioning a previous conclusion or disagreeing with a finding | `mcp__pal__challenge` |
| When brainstorming or seeking a second opinion | `mcp__pal__chat` |
| When debugging a complex bug or investigating a multi-component issue | `mcp__pal__debug` |

## Project Structure

File placement rules and directory conventions: see `docs/PROJECT-STRUCTURE.md` in the claude-team-control repo.

**Quick reference — prohibited (never do these):**
- Do NOT create files in `base/` other than `CLAUDE.md`
- Do NOT put agent/skill files outside their designated directories (`agents/`, `skills/`)
- Do NOT add Python packages to orchestrator without updating `pyproject.toml`
- Do NOT edit `projects.local.json` in commits -- it is user-specific and gitignored
- Do NOT store secrets, credentials, or API keys anywhere in this repo
- Do NOT edit `.claude/CLAUDE.md` directly -- overwritten by sync

**Naming conventions:** directories + non-Python files: `kebab-case`; Python modules: `snake_case`; exceptions: `CLAUDE.md`, `README.md`, `ROADMAP.md`, `ANALYSIS.md`.

## Agent & Tool Usage

- When a task requires information from an MCP server: call it. Never skip available MCP tools when they are relevant.
- When a task is complex (multi-file, multi-domain, deep analysis): delegate to a specialized agent via Task tool (Explore, Plan, Bash, general-purpose).
- When a repetitive task pattern emerges: create a new agent definition, document it in `docs/AGENTS.md`, and update these instructions.
- When multiple independent tool calls are needed: batch them in a single message. Never make sequential calls where parallel is possible.

## Linter & Pre-commit Discipline (MANDATORY)

- **When lint fails: fix the code, not the config.** Never add rules to `ignore = []`, `extend-ignore`, or `per-file-ignores` to make a failing check pass. Fix the underlying code issue instead.
- **Per-line `# noqa: RULE — reason`** is allowed ONLY for confirmed false positives that cannot be fixed by changing code (e.g. a parameterized SQL query flagged as S608, or an intentional `sys.stderr = open(...)` redirect). Always include a reason after the dash.
- **`per-file-ignores` in lint config** may only be used for file-type-specific patterns that are genuinely intentional across ALL files of that type (e.g. `S101` assert in all tests). Never use it to suppress individual findings.
- **Never use `--no-verify`** or any mechanism to bypass pre-commit hooks.
- **Never weaken the lint ruleset** (`select`, `ignore`, `extend-ignore`) without explicit user approval per rule added.

## Tool Discipline (MANDATORY)

Use the right tool for each operation. Never use shell commands or Python scripts as substitutes for dedicated tools.

**Dedicated tools — always prefer over Bash:**

| Operation | Use this tool | Never use via Bash |
|-----------|--------------|-------------------|
| Write a new file | `Write` | `cat > file`, `tee`, `echo >`, Python script, heredoc |
| Modify an existing file | `Edit` | `sed`, `awk`, Python script, heredoc |
| Edit a Jupyter notebook | `NotebookEdit` | `Edit` (raw JSON), Python script |
| Read a file | `Read` | `cat`, `head`, `tail` |
| Search file content | `Grep` | `grep`, `rg` |
| Find files by pattern | `Glob` | `ls`; `find -maxdepth 2` only when Glob cannot express the depth constraint |

**Bash — use directly for operations no dedicated tool covers:**
git, npm, pytest, docker, curl, chmod, mkdir, mv, cp, rm, process management, running formatters/linters, and any side-effect-producing tool (builds, generators, package managers). When a tool creates files as part of its job (e.g. `npm install`, `pytest --junitxml`), that is Bash's job — the prohibition is on using shell/Python as a *manual file-content transport*.

**Never use shell/Python as a manual file-content transport:**
- `cat > /tmp/script.py << "PYSCRIPT" && python3 /tmp/script.py` — write a file instead
- `tee file.md << "EOF"` — write a file instead
- any heredoc that writes textual project-file content

**Escape clause:** If a dedicated tool genuinely cannot handle the operation (e.g. binary file, byte-precise output, network call), Bash is permitted. This clause applies only to *tool capability* gaps — not to tools being blocked or failing. Add a one-line comment explaining why the dedicated tool is insufficient.

**When a dedicated tool is blocked or fails:** stop immediately, investigate why (hook? permission? path issue?), then ask the user. Never chain Bash workarounds as a substitute for a blocked tool. The escape clause does NOT apply here.

## Automatic Task Routing (MANDATORY)

Before starting ANY implementation: assess the task scope and route it. Never ask the user "should I use an agent?" -- decide and proceed.

| Signal | Threshold | Route to |
|--------|-----------|----------|
| Files affected | >3 files | Pipeline or agents |
| Architecture change | Any (new component, API, data model) | `architect` agent, then pipeline |
| Security surface | Auth, input validation, crypto, secrets | `security-lead` agent |
| Bug complexity | Multi-component, race condition, data corruption | `/orchestrate bugfix` pipeline |
| New feature | Any user-facing feature | `/orchestrate feature` pipeline |
| Code review request | Any PR or diff review | `code-reviewer` agent (triggers L1 CV) |
| Audit request | Plan review, risk assessment | `lead-auditor` agent (triggers L1 CV) |
| Deployment | Any release, deploy, migration | `/orchestrate deploy` pipeline |

**Routing decision:**
- Question / reading only → answer directly
- Single file, cosmetic fix → implement directly
- Single file, logic/security change → use relevant agent (code-reviewer, security-lead, architect)
- Multiple files, one concern → use relevant agent(s)
- Multiple files, multiple concerns → `/orchestrate` pipeline

**Rules:** When in doubt: use agents. Announce route in one line before starting. Before any non-trivial implementation: call `mcp__orchestrator__route_task(description)` and follow its decision.

Full routing details (MCP orchestrator integration, CV gates, pipeline execution): see `/routing-rules` skill.

## Permissions

- When reading log/output files (`.output`, `*.log`, `*.txt` in temp dirs, server stdout/stderr, test runner output): read without asking for confirmation.
- When reading project source files (any file within the project directory or related project directories): read without asking for confirmation.
- When reading configuration files (`.env`, `*.json`, `*.toml`, `*.yaml`, `*.cfg` in project directories): read without asking for confirmation.

## Git & GitLab

- After creating a git commit: remind the user to push to GitLab (or offer to push). Never let commits accumulate locally.
- At the start of a session: run `git status` and `git log origin/main..HEAD`. When unpushed commits exist: notify the user immediately.
- When pushing: use `git push origin main` (or the current branch name). Never force-push without explicit user approval.

## Delivery Policy (claude-team-control only)

Rules for safely delivering rule/script changes to team machines via `scripts/update.ps1`.

**Pre-commit validation (enforced by hook):**
- All `.ps1` files must pass `[System.Management.Automation.Language.Parser]::ParseFile` with zero parse errors before commit.
- The `powershell-syntax` pre-commit hook runs automatically on every staged `.ps1` file.

**Breaking change criteria** — requires explicit team announcement before merging:
- Any change to `sync.ps1` function signatures or overlay format
- Any change to `projects.json` schema
- Any change to hook file names or exit codes in `hooks/`
- Removal of any existing skill or agent file (renaming requires both old and new to exist for one release cycle)

**`update.ps1` auto-rollback behavior:**
After a successful `git pull`, `update.ps1` runs `[System.Management.Automation.Language.Parser]::ParseFile` on every newly pulled `.ps1` file in `claude-team-control`. If any file fails validation, `update.ps1` automatically runs `git reset --hard <pre-pull-HEAD>` on that machine and marks the update as failed. The developer will see `PREFLIGHT FAIL: <file>: <error>`. This is expected behavior — fix the upstream commit and the next pull will succeed.

**Rollback procedure:**
1. `git revert <commit>` (never force-push)
2. `git push origin main` — `update.ps1` auto-rollback on each machine clears the bad state on next pull
3. Notify team of the revert via the usual channel

## Database Protection (CRITICAL -- NEVER VIOLATE)

Enforced automatically by `protect-db.sh` hook -- blocks destructive commands on DB paths.

- When encountering any database file or directory (`*.db`, `*.sqlite`, `*.sqlite3`, `*chroma*`, `chroma_db/`, `pgdata`, `*redis*data`, `*mongo*data`, `*elastic*data`, `*mysql*data`, `*_db/`): NEVER delete it. Zero exceptions.
- Before any destructive operation on a DB path: create a backup first:
  1. `cp -r <db_dir> _archive/<db>_backup_$(date +%Y-%m-%d)/`
  2. Verify: `ls -la _archive/<db>_backup_*/`
  3. Only then proceed.
- Allowed operations: backup, copy, archive, read. Forbidden: `rm -rf`, `rmdir`, `shutil.rmtree()`, `DROP TABLE/DATABASE`, `docker volume rm`.
- When adding a new database to a project: add its path pattern to `hooks/protect-db.sh` `DB_PATTERN` and run `/sync`.

## Session Start Protocol

At the start of each session, execute these steps in order:
0. **Detect session scope:**
   a. Run `Bash: echo "${CLAUDE_SESSION:-(no session)}"` — always produces visible output.
   b. If output is `_` (escape hatch): force no-session mode — skip to step f.
   c. If output is NOT `(no session)` and NOT `_`: validate against `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. If invalid: ABORT. If valid: SESSION_LABEL=`{value}` (explicit). Skip to step e.
   d. If output is `(no session)`: run `Bash: git branch --show-current 2>/dev/null || true`. If result is non-empty AND not a default branch (`main`, `master`, `develop`, `dev`, `trunk`, `HEAD`): sanitize (replace `[^A-Za-z0-9_-]` with `-`, truncate to 63 chars). If sanitized starts with `[A-Za-z0-9]`: SESSION_LABEL=`{sanitized}` (auto from branch). Otherwise: no SESSION_LABEL.
   e. If SESSION_LABEL set: PLAN_FILE=`docs/PLAN-{SESSION_LABEL}.md`, TASKS_FILE=`docs/TASKS-{SESSION_LABEL}.md`, REVIEW_FILE=`docs/REVIEW-{SESSION_LABEL}.md`. Confirm: "Session: {SESSION_LABEL} — using {PLAN_FILE}." (append " (auto)" if derived from branch).
   f. If SESSION_LABEL not set: PLAN_FILE=`docs/PLAN.md`, TASKS_FILE=`docs/TASKS.md`, REVIEW_FILE=`docs/REVIEW.md`. Confirm: "No session — using docs/PLAN.md."
1. Read PLAN_FILE -- check for in-progress plans.
2. Read `docs/ROADMAP.md` -- check current phase status.
3. Call `list_active_pipelines()` -- check for interrupted pipelines. If SESSION set, pass `project=<basename_of_cwd>__{SESSION}` to filter.
4. Check the `[SYNC CHECK]` line from the SessionStart hook output:
   - Out of sync: report the stale files to the user and ask if they want to run `/sync`.
   - In sync: confirm to the user ("rules are up to date").
   - No `[SYNC CHECK]` line (unmanaged project): skip silently.
5. When active pipelines exist: report them to the user with resume instructions before accepting new tasks.
5b. For each active pipeline reported: check git log -- if all pipeline work is committed, call `cancel_pipeline(id, reason)` to close it. Do not leave orphans.
6. When other pending work exists: report it before accepting new tasks.

## Per-Phase Gate (MANDATORY)

Before starting any new implementation phase from PLAN_FILE (see Session Start Protocol step 0):
1. Run automated tests (`npm test`, `pytest`, etc.) — must pass with zero failures.
2. Call `mcp__pal__codereview` on all files changed in the previous phase. Any CRITICAL → HALT, fix, re-review.
3. Call `mcp__pal__thinkdeep` on the previous phase's changes. Any CRITICAL → HALT.
4. If PAL MCP is unavailable: perform steps 2-3 using internal cross-model review (Agent tool, different model tier). Document which fallback model was used.
5. Only after all three pass: mark the previous phase complete in PLAN_FILE (`[x]`) and proceed to the next.

Never skip this gate. Never proceed to the next phase while the previous phase has unresolved CRITICAL findings.
Note: gate checks CRITICAL-only (lightweight checkpoint). Full zero-MEDIUM+ standard is enforced by the end-of-plan double audit.

## Parallel Session Protocol

When working on two or more unrelated features simultaneously in the same project directory:

### Setup (once per terminal)
```bash
export CLAUDE_SESSION=<label>   # e.g., 15-E, WI-12345, feat-auth
```

### Label naming rules
**Must derive label from a unique identifier:**

| Source | Examples | Safe? |
|--------|----------|-------|
| Phase / roadmap number | `15-E`, `5P`, `SES` | Yes — unique by definition |
| TFS work item / ticket | `WI-12345`, `BUG-789` | Yes — unique by definition |
| Git branch name | `feat-auth`, `bugfix-login` | Yes — unique per branch |
| Date + topic | `0320-transport` | Yes — unique per day+topic |

**Forbidden:** generic categories — `bugfix`, `feature`, `docs`, `fix` — two sessions can pick the same label.

**Tip:** `git branch --show-current` gives you a ready-made unique label.

### What gets scoped vs. global
| Artifact | Scoped? | How |
|----------|---------|-----|
| `docs/PLAN-{label}.md` | YES | Session plan file |
| `docs/TASKS-{label}.md` | YES | Session task breakdown |
| `docs/REVIEW-{label}.md` | YES | Session code review |
| `docs/AUDIT.md` | NO | Global — project audit history |
| `docs/ROADMAP.md` | NO | Global — pull before write |
| `MEMORY.md` | NO | Global — sessions append entries |

### ROADMAP.md concurrent write safety
Before writing to `docs/ROADMAP.md`: run `git pull --rebase` if another session is active.
Write only append-only entries (new phase rows). On merge conflict: keep both entries, sort by phase number.

### Alternative: git worktrees (best for long-running parallel tracks)
```bash
git worktree add ../project-feature -b feature/15E
# Each worktree has own docs/PLAN.md and naturally scoped pipelines
```

## Context & Token Optimization (MANDATORY)

- Before moving to a different feature, phase, or task domain: commit all current work and update `docs/`. Never carry stale context.
- When research or exploration exceeds 3 file reads: delegate to a Task agent. Never run heavy scanning in the main context.
- Before reading a file: check if it was already read in this conversation and not modified since. Never re-read unchanged files.
- When multiple independent tool calls are needed: batch them in one message.
- When responding: use minimum words needed. No filler phrases, no restating the question.
- When tracking multi-step progress: use TodoWrite. Never write status paragraphs in chat.
- When a subagent returns results: extract only relevant findings. Never paste full tool outputs verbatim.
- Before context compresses or session ends: persist all state to files (PLAN_FILE, `docs/ROADMAP.md`, pipeline state via `complete_step`, MEMORY.md).

**Glob safety:** NEVER use `**/*.md` or any `**/*` pattern on project roots. Use `*.md` (root only), `docs/*.md` (specific subdir), `find -maxdepth 2`, or delegate to a Task agent.

## Plan & Documentation Gate (MANDATORY before commit)

Before committing: update all documentation:
- `docs/ROADMAP.md` -- mark completed phases, record commit context, update status tables.
- `docs/ANALYSIS.md` -- reflect architectural changes, new patterns, updated regex catalogs.
- `docs/AGENTS.md` -- if agents were created or modified.
- `MEMORY.md` -- update project state (current phase, test counts, key lessons).

Plan persistence rules (artifact index, ADR format, spike format, clean context gate): see `/planning-rules` skill.

Documentation quality standards (Mermaid, tables, collapsibles, emoji markers, code block tags): see `/docs-rules` skill.

Cost-aware development (scripts-over-agents table, CV gate applicability, agent memory protocol, collaboration handoff): see `/agent-memory-rules` skill.

## Plan & Phase Numbering Convention

Consistent numbering prevents confusion between roadmap phases and sub-phases within implementation plans.

**Roadmap phases** (`docs/ROADMAP.md`): `Phase N` (N = integer, e.g. 1–9).
These are the canonical top-level identifiers. Never reuse them as sub-phase names inside plan files.

> **Legacy exception — claude-team-control Phases 5A–5P:** These phases predate the `Phase N` integer rule (introduced 2026-03) and use a letter-suffix system (5A, 5B, 5B.2, 5C.1…5P). They are **frozen and immutable**. The next roadmap phase in that project is **Phase 6** (integer only, no letters). Never introduce new letter-suffix phases.

**Sub-phases within a plan file**: `Phase N.M`
- N = parent roadmap phase number (matches ROADMAP.md)
- M = sequential sub-phase index within that plan (1, 2, 3…)
- Example: Phase 9.1, Phase 9.2, Phase 9.3 are the first three sub-phases of the Phase 9 plan

**Off-roadmap plans** (tooling, infra, optimization — no roadmap phase number):
- Format: `LABEL.M` where LABEL is a 2–5 char uppercase acronym from the plan name
- Example: `GPU.0`, `GPU.1`, `GPU.2` for a GPU optimization plan

**Tasks within a sub-phase**: `T[M].[K]`
- M = local sub-phase number (same digit as Phase N.M suffix)
- K = task sequence within that sub-phase (1, 2, 3…)
- Example: T1.1, T1.2 within Phase 9.1; T2.1, T2.2 within Phase 9.2
- Within the plan file, short form T[M].[K] is unambiguous (phase heading provides N)
- Cross-file references must use full form: `Phase 9.2 T2.3`

**Tasks within off-roadmap phases** (LABEL.M): use the same `T[M].[K]` format where M is the
numeric index of that phase. Example: T0.1, T1.2 for tasks within GPU.0 and GPU.1.

**GATE steps**: not numbered — always the last item in a phase, written as `- [ ] GATE: ...`

**IDs are immutable**: never renumber existing phase or task assignments once created.
To insert a new phase between existing ones: add it at the end and document the logical ordering,
or leave a gap. Do NOT shift existing numbers.

**Completed / archived plans**: do NOT renumber historical plan files. Leave as written.

**Why this matters**: using Phase 1–6 inside a Phase 9 sub-plan collides with roadmap Phase 1–6,
causing ambiguity in cross-references, audit trails, and ROADMAP.md log entries.

## Independent Audit (MANDATORY)

After creating any implementation plan OR implementing changes touching >3 files: conduct a structured audit before proceeding.

Full audit workflow, verification evidence format, depth checklist, Rules Architect agent: see `/planning-rules` skill.

**Minimum requirement when `/planning-rules` is not loaded:**
- After plan design: launch `lead-auditor` agent before implementation begins.
- Every APPROVE verdict must include Verification Evidence (files read, PAL tools called, edge cases analyzed).
- Zero MEDIUM+ findings before proceeding (MEDIUM+ means CRITICAL, HIGH, or MEDIUM severity). Any CRITICAL, HIGH, or MEDIUM finding = HALT + fix + re-audit.
- Audit is recursive: re-run after every fix cycle until the audit returns zero CRITICAL, HIGH, and MEDIUM findings. Do not proceed while any MEDIUM+ finding is open.
- After the audit completes (APPROVE or final ESCALATE): output a **Session Summary** to the user with three parts:
  1. **What was done** — one-paragraph summary of changes made and findings resolved.
  2. **Findings table** — all findings across all audit cycles, with columns: `ID | Severity | Description | Status | Action taken`. Status values: `Fixed`, `Deferred`, `Open`.
  3. **Manual review table** — separate table listing items the user must verify manually: `Item | Why manual | Risk if skipped`. Include: all Deferred and Open findings, external integrations not covered by automated tests, security controls requiring human sign-off. Exclude: Fixed findings.


<!-- === Project-specific overlay: default.md === -->

## Project Notes

This project is managed by claude-team-control sync.

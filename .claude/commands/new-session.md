---
name: new-session
description: "Initialize a new session context: create docs/PLAN-{label}.md with Session header, remind to set CLAUDE_SESSION env var. Usage: /new-session LABEL"
---

# New Session Workflow

You are executing the `/new-session` command — a helper to set up an isolated session context for parallel work.

**Step 1 — Extract and validate the label from `$ARGUMENTS`:**
1. If `$ARGUMENTS` is empty: ABORT — "Usage: /new-session LABEL (e.g., /new-session 15-E or /new-session WI-12345)"
2. Extract LABEL = first word of `$ARGUMENTS`.
3. Validate: LABEL must match `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. If invalid: ABORT — "Invalid label '{LABEL}'. Use only letters, digits, hyphens, underscores (max 64 chars). Start with letter or digit."
4. Check label is unique — NOT a generic category: if LABEL is one of [bugfix, feature, fix, docs, chore, hotfix, refactor, test, update]: ABORT — "Label '{LABEL}' is too generic — two sessions can pick the same label. Use a unique identifier: phase number, TFS ticket, or branch name (e.g., WI-12345, 15-E, feat-auth)."

**Step 1a — Collision pre-check (ISO-G.2):**

`/new-session` creates a NEW label, so the full 5-branch claim guard fragment is semantically wrong here (its `stale → reclaim` and `file-only-legacy → reclaim` branches are valid for skills that act on an existing label, but contradict "create a new session" semantics). Instead, a targeted 2-branch check:

1. Call `resolve_session` with `project_root=<cwd>`, `env_session=<CLAUDE_SESSION or "">`, `branch=<current git branch>`, `skill_args=""` (do NOT pass LABEL as args — the returned `session_id` must identify THIS window, not the new label being created), `skill_name="new-session"`, `instance_id=<INSTANCE_ID from [SESSION] tag>`. Save returned `session_id` as SESSION_ID.
2. Call `list_available_sessions(project=<basename_of_cwd>, owner_id=SESSION_ID)` and find the row where `label == LABEL`.
3. **If the row is missing, or `claim_status` is `absent`, `stale`, or `file-only-legacy`** → proceed to Step 2 (treat as a fresh label).
4. **If `claim_status == 'locked-by-other'`** (row present, active, different `owner_id`) → **HALT**. Print: `"Label '{LABEL}' is already active by another session. Pick a unique label (append -v2, -b, etc.) or wait for the other session to finish."` Do NOT call `claim_session`. Do NOT create the plan file. **STOP**.
5. **If `claim_status == 'own-active'`** (row present, same `owner_id`) → do NOT auto-proceed. Retain the existing Step 2 file-exists prompt semantics (see below) to protect against typos like `/new-session WI-999` when the user meant `WI-998`. The DB claim is informational for classification; it does NOT bypass Step 2.

After this check passes (no HALT): proceed to Step 2. `claim_session` is NOT called here — it is deferred to Step 3a (after Step 3 creates the plan file, so the claim points at a real file). Do NOT call `claim_session` inline at the end of Step 1a — that would register a claim for a non-existent plan file.

**Step 2 — Check if plan file already exists:**
1. Check if `docs/PLAN-{LABEL}.md` exists.
2. If it exists: warn the user — "docs/PLAN-{LABEL}.md already exists. Overwrite? (yes/no)"
3. Wait for confirmation. If "no": ABORT.

**Step 3 — Create the plan file:**
Create `docs/PLAN-{LABEL}.md` with this exact template (replace {LABEL} and {TODAY}):

```markdown
# Plan: [describe your feature here]

Session: {LABEL}
**Created:** {TODAY}
**Status:** Draft

## Problem Statement

[Describe what problem this session is solving]

## Next Steps

Run `/phase <description>` to create a structured plan with audit.
```

**Step 3a — Register DB claim (ISO-G.2):**
Call `claim_session(label=LABEL, plan_file="docs/PLAN-{LABEL}.md", owner_id=SESSION_ID, project=<basename_of_cwd>)` using the SESSION_ID captured in Step 1a. If `success=False`: print `"Session claim failed: {error}. Retry or use a different label."` and **STOP** — do NOT proceed to Step 3b (no `.claude/.session` write for an unclaimed label).

**Step 3b — Persist session label:**
Write `.claude/.session` to persist the session across `/clear` (atomic write): run `bash -c 'tmp=".claude/.session.tmp.$$"; printf "%s" "{LABEL}" > "$tmp" && mv -f "$tmp" .claude/.session 2>/dev/null || rm -f "$tmp" 2>/dev/null'`.

**Step 4 — Output setup instructions:**

Print exactly:

```
Session '{LABEL}' initialized.

Plan file: docs/PLAN-{LABEL}.md

Set your session env var (run in your terminal):

    export CLAUDE_SESSION={LABEL}

Then start planning:

    /phase <description of what you're working on>

When done and merged:

    unset CLAUDE_SESSION
    rm docs/PLAN-{LABEL}.md docs/TASKS-{LABEL}.md docs/REVIEW-{LABEL}.md 2>/dev/null || true
```

**Note on auto-detection:** If your terminal is on a non-default git branch (not main/master/develop/dev/trunk), Claude will auto-detect the branch name as your session label — no `export` needed. `/new-session` is still useful when you want to pre-create the plan file template before switching branches, or when the auto-detected label doesn't match what you want. To suppress auto-detection: `export CLAUDE_SESSION=_`.

Do not describe what you are about to do — execute immediately.

---

## Reference: Parallel Session Protocol

When working on two or more unrelated features simultaneously in the same project directory:

### Session detection order

**Hook detection** (`sync-check.py` — runs at session start, emits `[SESSION]` tag):

1. `CLAUDE_SESSION` env var — set once per terminal (works in terminal Claude Code only, NOT in VSCode extension)
2. Git branch — auto-detected when on a non-default branch (works everywhere)
3. `.claude/.session` file — persisted by skills, validated against `docs/PLAN-{label}.md` existence (survives `/clear`)
4. Single auto-detect — when exactly 1 `docs/PLAN-*.md` exists, it is used automatically
5. Default — `docs/PLAN.md`

**Skill detection** (each skill's Step 0 — calls `resolve_session` MCP tool):

Skills call `resolve_session(project_root, env_session, branch, skill_args, skill_name)` which resolves in this order:
1. Reuse — already resolved in this conversation
2. `[SESSION]` hook tag — from sync-check.py output (covers hook priorities 1–4 above)
3. **Args-based** — first word of command arguments matches an existing `docs/PLAN-{word}.md` (e.g. `/check INC` → session `INC`)
4. Bash fallback — reads `CLAUDE_SESSION` env var + branch directly (only when hook didn't fire)
5. `session_resume.md` probe — breadcrumb from `/save` (only in `/run`, `/check`, `/finish`, `/summary`, `/orchestrate`)
6. Default — `docs/PLAN.md`

The `resolve_session` tool returns `SessionResult` with `plan_file`, `tasks_file`, `review_file`, `label`, `project_suffix`, `parsed_args`.

> **Note:** Skills never read `.session` directly — they write it. The hook reads and validates it at the next session start.

**`/phase` auto-labels from description:** `/phase routing rules for the dashboard` → auto-session `routing` → plan saved to `docs/PLAN-routing.md`. No setup required.

### Setup options

**VSCode (recommended) — use args or let Claude ask:**
```
/check INC           # args-based: picks PLAN-INC.md automatically
/check               # if 2+ plans exist: shows selection menu
/phase routing rules # auto-labels as "routing" → creates PLAN-routing.md
```

**Terminal — env var (explicit, works across all commands):**
```bash
export CLAUDE_SESSION=<label>   # e.g., INC, feat-auth, WI-12345
```

**Git branch (automatic, works everywhere):**
```bash
git checkout -b feat-auth   # → session label "feat-auth" auto-detected
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

### What gets scoped vs. global
| Artifact | Scoped? | How |
|----------|---------|-----|
| `docs/PLAN-{label}.md` | YES | Session plan file |
| `docs/TASKS-{label}.md` | YES | Session task breakdown |
| `docs/REVIEW-{label}.md` | YES | Session code review |
| `.claude/.session` | YES | Persists active session label across `/clear`; written by skills, validated by hook |
| `docs/AUDIT.md` | NO | Global — project audit history |
| `docs/ROADMAP.md` | NO | Global — pull before write |
| `MEMORY.md` | NO | Global — sessions append entries |

### ROADMAP.md concurrent write safety
Before writing to `docs/ROADMAP.md`: run `git pull --rebase` if another session is active.
Write only append-only entries (new phase rows). On merge conflict: keep both entries, sort by phase number.

### Best choice for long-running parallel tracks: git worktrees
```bash
git worktree add ../project-feature -b feature/15E
# Each worktree has own docs/PLAN.md and naturally scoped pipelines
```

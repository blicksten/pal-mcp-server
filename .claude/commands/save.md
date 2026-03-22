---
name: save
description: "Context cleanup: verify all state is persisted to files, then prompt user to run the built-in /clear command"
---

# Save Workflow

You are executing the `/save` skill — a context cleanup checkpoint between phases.

**Note on terminology:**
- `/save` — this skill (defined here, invokable via slash command)
- `/clear` — a **built-in Claude Code command** (Clear conversation) that actually clears the context. It cannot be called programmatically; the user must run it manually.

**FIRST OUTPUT:** Before any tool calls, print: `▶ /save`

**Step 0 — Detect session context (MANDATORY):**
1. Run one combined command: `bash -c 'printf "%s\n%s" "${CLAUDE_SESSION:-(no session)}" "$(git branch --show-current 2>/dev/null || true)"'` — line 1: CLAUDE_SESSION value, line 2: git branch (may be empty).
2. Parse SESSION_LINE and BRANCH_LINE. If SESSION_LINE is `_` or (`(no session)` with empty/default BRANCH_LINE): SESSION_LABEL=(none). If `(no session)` and BRANCH_LINE non-empty and not default branch (main/master/develop/dev/trunk/HEAD): sanitize BRANCH_LINE (replace `[^A-Za-z0-9_-]` with `-`, truncate 63 chars) → SESSION_LABEL=`{sanitized}` (auto). If SESSION_LINE is explicit (not `(no session)`, not `_`): SESSION_LABEL=`{SESSION_LINE}`.
3. If SESSION_LABEL set: PLAN_FILE=`docs/PLAN-{SESSION_LABEL}.md`, TASKS_FILE=`docs/TASKS-{SESSION_LABEL}.md`. Print: "Session: {SESSION_LABEL}" (append " (auto)" if from branch).
4. If no SESSION_LABEL: PLAN_FILE=`docs/PLAN.md`, TASKS_FILE=`docs/TASKS.md`. Print: "No session — using docs/PLAN.md"

## Steps

1. Verify that all state is persisted to files:
   - PLAN_FILE (from Step 0) — previous phase GATE checkpoint marked `[x]`, current phase tasks marked as implemented
   - TASKS_FILE (from Step 0) — task breakdown current
   - `docs/ROADMAP.md` — phase progress updated
   - `MEMORY.md` — project state current
   - All changes committed (`git status` must be clean)

2. If anything is not persisted: save it now before clearing context.

3. Output this message to the user (same meaning; match the user's language; keep command tokens `/clear` verbatim):

---

**Context ready for cleanup.**

All state is persisted to PLAN_FILE, TASKS_FILE, `docs/ROADMAP.md`, and `MEMORY.md`. The next `/run` will read the plan from files and continue from where this phase left off.

> Run the built-in **`/clear`** command (Context → Clear conversation) to start the next phase in a clean context.

---

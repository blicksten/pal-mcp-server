---
name: planning-rules
description: Full planning, audit, and plan-persistence rules. Load this skill when designing implementation plans, entering plan mode, running audits, or before committing phased work.
---

# Planning, Audit & Plan Persistence Rules

This skill is automatically injected by `start-pipeline-gate.sh` and by `/plan-feature`. Load it manually with `/planning-rules` when doing any phased implementation.

---

## Audit Findings Enforcement (ZFE) — MANDATORY

Every finding raised inside a pipeline MUST live in the `audit_findings` DB table with `status IN ('Open', 'Fixed', 'Escalated')`. The CHECK constraint at the schema level makes `'Deferred'` / `'Informational'` / `'Out of scope'` / `'Manual review'` physically impossible values — ZFE.1+2 enforce this mechanically.

- **Record findings via MCP only:** use `mcp__orchestrator__record_finding` (CRITICAL/HIGH/MEDIUM/LOW + description + action_taken with a causality marker when status != 'Open'). Never hand-edit the DB or skip the call.
- **Transition findings via MCP only:** `resolve_finding` (Open → Fixed) and `escalate_finding` (Open → Escalated, escalation_to required) are the only legal transitions. Both require an `action_taken` string ≥ 20 chars containing at least one causality marker (`->`, `#`, `commit `, `ticket `, `issue `).
- **Audit-role declaration:** before closing a step whose agent is in `PipelineExecutor._AUDIT_ROLE_AGENTS` (`lead-auditor`, `specialist-auditor`, `code-reviewer`, `security-auditor`, `architect`), call `mcp__orchestrator__mark_audit_complete(pipeline_id, step_number, agent, evidence_summary)`. `evidence_summary` must be non-empty (≥ 20 chars non-whitespace). The precondition gate in `_complete_step_locked` HALTs the step otherwise.
- **Self-policing per phase GATE:** the plan's DB check `SELECT COUNT(*) FROM audit_findings WHERE pipeline_id=? AND status NOT IN ('Open','Fixed','Escalated')` must always return 0 (CHECK constraint guarantees this once ZFE.1 has landed). Defensive scan of the phase's REVIEW prose via `scripts/scan_finding_prose.py` (stdlib string ops, not shell grep) as belt-and-braces.
- **Verdict rendering from DB:** `/check` and `/finish` verdict templates call `mcp__orchestrator__list_all_findings(pipeline_id)` and emit one markdown row per DB row. Do NOT free-form author the findings table.
- **Strict-mode HALT (ZFE.6 default ON):** audit-role steps whose CV-gate flagged `step_audit_summaries.cv_disputed=1` HALT at close until the auditor reconciles via `record_finding` / `escalate_finding` / `mcp__pal__challenge`. Set `CLAUDE_ZFE_CV_VALIDATED_STRICT=0` only as a documented opt-out, logged in `docs/compliance/hgl1-canary-YYYY-MM-DD.md`.

Violation of any rule above is itself a finding.

---

## Independent Audit (MANDATORY)

After creating any implementation plan: conduct a structured audit before approving for execution. No implementation begins without audit approval.

### When to Run the Audit

- After plan design (before user approval / ExitPlanMode).
- After implementing changes touching >3 files (before commit).
- After major refactoring.

### Audit Workflow

Every APPROVE verdict (specialist or Chief Architect) must include Verification Evidence (see format below). An APPROVE without evidence is invalid.

1. **Launch Lead Auditor** -- start a `lead-auditor` agent (fallback: `general-purpose` only if `lead-auditor` is unavailable).
   - The Lead Auditor reads the plan and identifies required domain expertise.
   - The Lead Auditor delegates review to one or more Specialist Auditor agents, each with clear domain scope.

2. **Specialist Auditors execute** -- launched by Lead Auditor or in parallel by orchestrator.
   - Each Specialist receives a focused scope (e.g., "audit database query patterns", "audit backward compatibility").
   - Before issuing any verdict: complete all applicable items in the Audit Depth Checklist (below).
   - When auditing code or architecture changes: call `mcp__pal__thinkdeep`. Surface-level reasoning is insufficient.
   - When auditing docs-only, config-only, or single-file trivial changes: PAL usage is recommended but not mandatory.
   - Produce one verdict: **APPROVE** / **REJECT with findings** (CRITICAL/HIGH/MEDIUM/LOW + fix recommendations) / **ESCALATE to user**.

3. **Chief Architect Review** -- after all Specialist Auditors finish, the Lead Auditor performs a holistic review:
   - Focus on cross-domain gaps no single specialist could see. Validate that specialist findings do not contradict each other.
   - Before issuing verdict: call `mcp__pal__consensus` for cross-domain validation and read source code at integration points.
   - Produce verdict: APPROVE / REJECT with findings / ESCALATE.

4. **No inventing, no guessing** -- auditors must not fabricate concerns. Only concrete, verifiable findings from actual code analysis and documentation. When unsure: ESCALATE, never assume.

5. **On REJECT** -- fix all findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY` (default: `low`, meaning every finding including LOW), re-submit to the same auditor. **Audit is recursive**: repeat the fix + re-audit cycle until APPROVE (zero errors) or ESCALATE. Do not proceed while any finding at or above threshold is open. After specialist fixes: Chief Architect re-reviews the whole plan.
   - When re-audit finds any blocking-severity issues in a previously APPROVED plan: trigger the Audit Failure Protocol (see "Zero errors on Re-audit").

6. **Final outcome:**
   - All auditors + Chief Architect APPROVE: implementation begins.
   - Any level ESCALATE: notify user with the unresolved question.
   - Record the audit summary in the plan file.

7. **Session Summary (MANDATORY output after audit APPROVE or final ESCALATE):**
   After the audit completes (one final summary — not after each recursive pass), output to the user:

   **a) What was done** — one-paragraph summary: what changed, how many audit cycles ran, what findings were resolved.

   **b) Findings table** — every finding across all cycles:
   ```
   | ID | Severity | Description | Status | Action taken |
   |----|----------|-------------|--------|--------------|
   | M-01 | MEDIUM | ... | Fixed | Updated lead-auditor.md:288 |
   | L-02 | LOW | ... | Fixed | Updated file:line |
   ```
   Status values: `Fixed` / `Open (escalated)`. **No "Deferred" status** — all findings of any severity must be fixed in the current audit cycle. If a finding genuinely cannot be fixed (requires hardware, external service, etc.), escalate to user — never silently defer.

   **c) Manual review table** — items user must verify by hand (separate from findings table):
   ```
   | Item | Why manual verification needed | Risk if skipped |
   |------|-------------------------------|-----------------|
   | Escalated L-06: UNC NTLM leak | Requires opt-in setting design | Security |
   ```
   Include: all Open (escalated) findings (any severity), external system integrations not covered by automated tests, security controls requiring human sign-off. Exclude: Fixed findings (already auto-verified).

### Execution Plan Requirement

After audit approval (all levels APPROVE): structure the plan as a detailed execution roadmap before implementing.

- Format as **Phase -> Steps**: each phase contains numbered, atomic steps.
- Each step has a **checkpoint**: what was done, what file changed, what to verify.
- The plan must be **resumable**: readable by any developer or agent to continue from last completed step.
- Mark completed steps with `[x]`; pending steps remain `[ ]`.
- Record commit hashes, test counts, and deviations inline after each phase.
- Save to `docs/ROADMAP.md` or a plan file -- never only in conversation memory.
- Each phase that modifies code, data, or infrastructure must include a **Rollback** subsection: ordered steps to undo the phase changes if they cause breakage. For genuinely irreversible phases: write `Rollback: N/A — [mitigation plan: backup / forward-fix / feature-flag]` instead.

### Per-Phase PAL Verification Gate (MANDATORY)

Before starting the next phase of any phased implementation plan: complete the verification gate for the current phase.

1. Run automated checks (`npm test`, `pytest`, etc.) -- must pass with zero failures. For new code paths introduced in this phase: verify by reviewing the diff and new test files that corresponding tests exist -- not just that existing tests pass.
2. Call `mcp__pal__codereview` on all files changed in this phase. On any finding at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY` (default: any finding): HALT, fix, re-review.
3. Call `mcp__pal__thinkdeep` for deep analysis of the phase's changes. On any finding at or above threshold: HALT.
4. If PAL MCP is unavailable: perform steps 2-3 using internal cross-model review (Agent tool, different model tier — opus if current is sonnet; sonnet if current is opus). Document which fallback was used.
5. Only after all automated checks pass AND both PAL tools (or fallback) return zero errors (no findings above threshold): mark phase complete and proceed.
   If a finding is believed to be a false positive: use `mcp__pal__challenge` to contest it, or escalate to the user. Never silently skip or downgrade findings.

**Real-boundary evidence requirement (Invariant 5, STAB Phase 0):** when recording a GATE PASS for any phase whose GATE asserts an invariant from `docs/spikes/2026-04-27-invariants-for-plan-rewrite.md`, include the verbatim `## Real-boundary evidence` block defined in `base/CLAUDE.md` § "GATE PASS template — real-boundary evidence (Invariant 5, STAB Phase 0)". A GATE PASS without this block is structurally invalid — the Phase 0 meta-test (`orchestrator/tests/invariants/test_invariant_5_gate_evidence.py`) will flag it. Per-invariant boundary requirements + the closed `EXPECTED_FINDINGS` set live in the same template.

**Timeout-resistant pattern (use for deep audits that may exceed 300s):**
Claude Code's MCP client aborts any tool call at ~300s. Reasoning models like `gpt-5.2-pro` with `review_validation_type=external` routinely exceed this. Direct `mcp__pal__codereview` / `mcp__pal__thinkdeep` calls in this regime hang and then fail with `AbortError`, losing the result. When that risk exists, wrap the call:

```
task_id = mcp__orchestrator__queue_review(gate_type="codereview", prompt=..., model="gpt-5.2-pro")
# AI polls every 15-30s
record = mcp__orchestrator__get_review(task_id)  # status: queued → running → done|failed|timeout
```

On primary-model timeout the worker retries once with `gpt-5.1-codex` automatically; `fallback_used=true` in the result record signals the fallback path. For gates expected to finish under ~90s, direct `mcp__pal__*` calls are still fine.

### End-of-Plan Double Audit (MANDATORY)

After all phases are complete and before committing:

1. Call `mcp__pal__precommit` -- full diff review, security scan, change impact assessment.
2. Call `mcp__pal__consensus` (multi-model, >=2 models) -- holistic architecture review.
3. When any finding at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY` (default: any finding) appears: create a fix task, re-run the relevant phase gate, then re-run the double audit. Repeat until zero errors remain.

> **Note:** Invoking the `/finish` skill satisfies all requirements of this section. When `/finish` is run (manually or automatically via Per-Phase Gate step 6 / `/run` LOOP CONTROL), the End-of-Plan Double Audit is fulfilled — do not run it again separately.

### Audit Scope Checklist

When auditing, check each of these:
- Logic gaps, race conditions, missing error handling
- Security holes (injection, XSS, auth bypass)
- Coupling issues, backward compatibility breaks — before modifying any exported function or shared module: Grep for all call sites first
- Untested paths, wrong assumptions about APIs/libraries — use mcp__context7__resolve-library-id + mcp__context7__query-docs (or WebSearch when context7 lacks the library) to verify actual API behavior before flagging as a finding
- Performance regressions, deployment blind spots
- Blast radius -- which other components are affected

### Zero errors on Re-audit (ABSOLUTE RULE)

When a re-audit or implementation review discovers any finding at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY` (default: any finding) in a previously APPROVED plan: this is an Audit Failure. The initial audit was deficient.

**On Audit Failure:**
1. HALT -- stop all implementation immediately.
2. Root cause analysis -- document WHY the initial audit missed it in `docs/AUDIT.md` under "Audit Failures".
3. Full re-audit -- re-audit the entire plan from scratch, not just the failed area.
4. Process update -- add the gap to the Audit Depth Checklist to prevent recurrence.
5. Run `/orchestrate deep-validate` to achieve zero-finding state.

### Audit Verification Evidence (MANDATORY)

Every APPROVE verdict must include this section:

```
## Verification Evidence
- **Files read**: [files with line ranges actually examined]
- **Documentation verified**: [context7 queries or WebSearch URLs consulted]
- **PAL tools used**: [tool name -> key conclusion]
- **Code patterns checked**: [Grep/Glob queries run, what was verified]
- **Edge cases analyzed**: [boundary conditions, error paths, concurrency scenarios]
- **Cross-domain risks**: [integration points checked]
```

- When a section is not applicable: explain why. Never leave sections empty.
- Evidence must be specific: "read `router.py:45-120`, verified route registration pattern" -- not "read the code".
- Record evidence in `docs/AUDIT.md` alongside the verdict.

### Audit Depth Checklist

Before issuing APPROVE, confirm each applicable item:

- [ ] **Source code read** -- all affected files read with `Read` tool (not just referenced)
- [ ] **Technical assumptions verified** -- every claim confirmed via context7 or WebSearch
- [ ] **PAL analysis performed** -- `thinkdeep` (specialist) or `consensus` (Chief Architect) called
- [ ] **Edge cases considered** -- boundary values, empty inputs, concurrent access analyzed
- [ ] **Security surface noted** -- security implications flagged for security specialist if beyond scope
- [ ] **Backward compatibility verified** -- existing consumers and dependents checked for breakage
- [ ] **Test coverage assessed** -- existing tests reviewed; gaps flagged
- [ ] **Cross-domain integration verified** -- interaction points with other modules checked

Report which items were completed and which were not applicable (with justification).

### Rules Architect Agent

When creating or modifying CLAUDE.md instructions: delegate to the Rules Architect agent. Never write rules ad-hoc from an implementation agent.

**Agent profile:**
- Type: `general-purpose` agent with role **Rules Architect**
- Expertise: technical writing, process design, CLAUDE.md conventions

**Before writing any rule, the Rules Architect must:**
- Consult Claude Code documentation via context7 or WebSearch for best practices.
- Study existing CLAUDE.md patterns in the project.

**Rule quality requirements (every rule must satisfy all five):**
- **Atomic** -- one rule = one concern.
- **Actionable** -- describes a concrete action, not an abstract goal.
- **Verifiable** -- possible to check whether followed.
- **Non-contradictory** -- no conflicts with existing rules; replacement rules state what they replace.
- **Scoped** -- clear when it applies and when it does not.

**Workflow:** Rules Architect produces a draft. Chief Architect reviews before applying to any CLAUDE.md.

---

## Plan Continuity & Documentation (MANDATORY)

- After completing planning or any implementation phase: save the full plan to `docs/ROADMAP.md` with enough detail to resume from any point.
- After analyzing the codebase: save findings to `docs/ANALYSIS.md` (architecture, components, patterns, regex catalogs, configuration, known issues).
- When a phase produces critical changes: immediately update `docs/ROADMAP.md` to reflect impact on future phases.
- After completing a phase: update `docs/ROADMAP.md` with completion status, actual test counts, and commit hashes.
- When discovering a gotcha: add it to the roadmap's "Known Gotchas" section.
- Before committing (gate -- do not commit without this): update all documentation:
  - `docs/ROADMAP.md` -- mark completed phases, record commit context, update status tables.
  - `docs/ANALYSIS.md` -- reflect architectural changes, new patterns, updated regex catalogs.
  - `docs/AGENTS.md` -- if agents were created or modified.
  - `MEMORY.md` -- update project state (current phase, test counts, key lessons).
  - Code comments -- ensure new/changed functions have accurate docstrings.

---

## Task Granularity (Advisory)

Each task in a plan should be: **(a)** scoped to one logical concern, **(b)** independently verifiable with a specific test or command, **(c)** worthy of its own commit. Red flags for oversized tasks: description longer than 2 lines, task touching more than 5 files without justification, description containing "and" joining unrelated changes. When in doubt, split.

---

## Plan Persistence After Thinking (MANDATORY)

Before starting implementation: verify that the plan is persisted to a file. Plans existing only in conversation context are invalid.

### Persistence Rules

| Trigger | Save to | Format |
|---------|---------|--------|
| After producing a plan in plan mode | PLAN_FILE (`docs/PLAN.md` by default, or `docs/PLAN-{label}.md` if CLAUDE_SESSION is set) | Problem statement, options, decision + rationale, numbered steps; **must include `## Next Plans` section** listing the next 1–4 phases from `docs/ROADMAP.md` with status and one-line goals |
| After PAL tools produce strategic findings | PLAN_FILE, REVIEW_FILE, or `docs/AUDIT.md` | Key conclusions summary |
| After making an architecture decision (e.g., introduces a new library/framework, changes a public API contract, or removes a previously available option) | `docs/adr/NNNN-<title>.md` | Context, Decision, Consequences, Status |
| After completing a spike/research | `docs/spikes/YYYY-MM-DD-<topic>.md` | Question, options, recommendation, evidence |
| After a postmortem | `docs/postmortems/YYYY-MM-DD-<title>.md` | Timeline, root cause, impact, action items |

### Clean Context Gate

Before starting implementation, verify all six:
- [ ] Plan saved to `docs/` with clear execution steps.
- [ ] Each step has a checkpoint (what to verify).
- [ ] Steps are numbered and atomic (resumable from any point).
- [ ] No plan details exist ONLY in conversation -- all persisted to files.
- [ ] `## Next Plans` section present in PLAN_FILE — lists next 1–4 phases with status and goals.
- [ ] Every phase in this plan includes a **Rollback** subsection.

### Artifact Index

After creating any decision artifact (ADR, spike, postmortem, plan): update `docs/INDEX.md` with a link to the new artifact.

---

## Plan & Phase Numbering Convention

Consistent numbering prevents confusion between roadmap phases and sub-phases within implementation plans.

**Human-readable summary:**

| Context | Accepted form | Example |
|---------|---------------|---------|
| Roadmap phases (`docs/ROADMAP.md`) | `Phase N` (N ≥ 1) | `Phase 6` |
| Sub-phases within a plan file | `Phase N.M` | `Phase 9.2` |
| Off-roadmap plans | `LABEL.M` (LABEL = 2–5 UPPERCASE letters) | `NAM.1`, `HGL.3` |
| Tasks within any phase | `T[M].[K]` (M, K non-negative integers) | `T1.1`, `T6.11` |

> **Legacy exception -- claude-team-control Phases 5A-5P:** These phases predate the `Phase N` integer rule (introduced 2026-03) and use a letter-suffix system (5A, 5B, 5B.2, 5C.1...5P). They are **frozen and immutable**. The next roadmap phase in that project is **Phase 6** (integer only, no letters). Never introduce new letter-suffix phases.

**Authoritative enforcement layers (NAM — shipped 2026-04):**

1. **Python validator** — `orchestrator/naming.py` (`validate_phase_label`, `validate_task_label`). Single source of truth for the grammar.
2. **DB-level registry** — `phase_labels(project_id, label, canonical_label, is_legacy, ...)` table in the orchestrator index DB. A composite FK on `phases.(project_id, phase_label)` rejects unregistered labels; a trigger enforces the same grammar at the SQL layer for parity.
3. **Pre-commit hook** — `hooks/phase-label-lint.sh` (registered in `.pre-commit-config.yaml`). Lints `## Phase` / `### Phase` headings in staged `docs/PLAN-*.md` files and the filename stem of newly added PLAN files.

> See `orchestrator/naming.py` for the authoritative grammar. Human-written plans and ROADMAP.md are subject to all three layers on commit.

**Legacy exception workflow:** When a pre-existing non-conforming label needs to survive (e.g. `PDB-EXT.5a`), register it via `scripts/inventory_labels.py` + `scripts/load_inventory.py` with a human-signed `docs/legacy-label-inventory.csv` entry (`is_legacy=1`). AI-signed rows are rejected.

**Tasks within a sub-phase** `T[M].[K]`:
- M = local sub-phase number (same digit as Phase N.M suffix)
- K = task sequence within that sub-phase (1, 2, 3...)
- Example: T1.1, T1.2 within Phase 9.1; T2.1, T2.2 within Phase 9.2
- Within the plan file, short form T[M].[K] is unambiguous (phase heading provides N)
- Cross-file references must use full form: `Phase 9.2 T2.3`

**GATE steps**: not numbered -- always the last item in a phase, written as `- [ ] GATE: ...`

**IDs are immutable**: never renumber existing phase or task assignments once created.
To insert a new phase between existing ones: add it at the end and document the logical ordering,
or leave a gap. Do NOT shift existing numbers.

**Completed / archived plans**: do NOT renumber historical plan files. Leave as written.

**Why this matters**: using Phase 1-6 inside a Phase 9 sub-plan collides with roadmap Phase 1-6,
causing ambiguity in cross-references, audit trails, and ROADMAP.md log entries.

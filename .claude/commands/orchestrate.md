---
name: orchestrate
description: "Orchestrate multi-agent workflows: feature, bugfix, deploy, audit, qa, review, refactor, incident, migration, spike, perf, onboard, docs, techdebt, deep-validate, research, compare, analysis"
---

# Orchestrate Workflow

**SESSION SCOPING (MANDATORY at entry):** Independently resolve session context — skill invocations do NOT share variable scope with the caller.

**SHORTCUT — when called from another skill (run/finish/check/phase):** if ARGUMENTS begins with `__RESOLVED__`, parse PLAN_FILE, TASKS_FILE, REVIEW_FILE, PROJECT_SUFFIX from the marker (format: `__RESOLVED__ PLAN_FILE=<path> TASKS_FILE=<path> REVIEW_FILE=<path> PROJECT_SUFFIX=<value>`). Derive SESSION_LABEL: if PLAN_FILE matches `docs/PLAN-{label}.md`, SESSION_LABEL=`{label}`; else SESSION_LABEL=(none). Print: `[pre-resolved: {PLAN_FILE}]`. **Skip steps 1-4 below.**

**STANDALONE — when invoked directly** (ARGUMENTS does NOT begin with `__RESOLVED__`):
1. Print: `▶ /orchestrate {first word of ARGUMENTS}` — then proceed.
2. Call `resolve_session` MCP tool with: `project_root` = current working directory, `env_session` = CLAUDE_SESSION env var (empty if unset), `branch` = current git branch, `skill_args` = ARGUMENTS, `skill_name` = "orchestrate", `instance_id` = INSTANCE_ID from [SESSION] tag (empty if unavailable), `owner_id` = session_id from [SESSION] tag (empty if unavailable).

Use returned `plan_file`, `tasks_file`, `review_file`, `label`, `project_suffix`, `parsed_args` throughout. For `start_pipeline`: `project=<basename_of_cwd>{project_suffix}`. For `list_active_pipelines`: ALWAYS pass `project=<basename_of_cwd>{project_suffix}`.
Print: "Session: **{label}** → {plan_file}" only when label is set. Otherwise proceed silently.

**Anti-hallucination rule:** NEVER derive session label from conversation topic, task description, or user request content. The `resolve_session` tool is the ONLY valid source. `__RESOLVED__` shortcut from a caller skill is also valid. Any other derivation is a hallucination.

**INVARIANT (ISO-G.2):** standalone `/orchestrate` MUST NOT call `claim_session`, `renew_lease`, or write plan/tasks/review files. It MAY call `start_pipeline` — pipeline ownership is enforced at `pipeline_ops(cancel)` per SES.2, not at creation time, so no claim is needed on create. If a future change gives `/orchestrate` any of those forbidden responsibilities, add a `session-claim-guard` include directive here (same syntax used by `/run`, `/finish`, etc.) and reconsider the `__RESOLVED__` pass-through contract — caller skills already hold the claim, so expanding the guard into `/orchestrate` would either double-check or race with them.

You are the Workflow Orchestrator. You coordinate multi-agent workflows by invoking the right agents in the right order, passing context between them, and ensuring quality gates are met.

## Usage

```
/orchestrate <workflow> "<description>"
```

Supported workflows:
- `feature` — Full feature implementation pipeline
- `bugfix` — Bug investigation and fix pipeline
- `deploy` — Deployment preparation pipeline
- `audit` — Plan audit pipeline
- `qa` — Full QA verification pipeline
- `review` — Code review pipeline
- `refactor` — Code refactoring without behavior change
- `incident` — Production incident response and hotfix
- `migration` — Library upgrade, API change, DB migration
- `spike` — Research spike, feasibility study
- `perf` — Performance optimization
- `onboard` — Project onboarding and context documentation
- `deep-validate` — Exhaustive validation of changes/plans to zero-finding state
- `custom` — **DEPRECATED** escape hatch. Use named pipelines (checkpoint-check, checkpoint-finish, planning, execute) instead. Logs warning on use.

## Workflow Definitions

### Feature Pipeline (`/orchestrate feature "..."`)

```
1. architect [plan mode] — Design review, interface design
   → GATE: Design approved by human
   → [CV-GATE:consensus] Validate architecture decisions with OpenAI
2. dev-lead — Break into tasks, assign implementation order
3. IMPLEMENTATION (sequential or parallel based on scope):
   → backend-dev — Service logic, API endpoints
      → Read: TASKS file first
      → Bash: run tests after implementation
      → proof_required: must include ## TEST PROOF
   → frontend-dev — Templates, CSS, client-side (optional)
   → abap-specialist — ABAP objects, CDS views, function modules, transports (SAP projects)
   → test-engineer — Write tests in parallel with implementation
4. code-reviewer — Review all changes (Claude + OpenAI via PAL)
   → [CV-GATE:codereview] OpenAI independent code review
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)
5. qa-lead — Run full test suite, validate coverage
   → Bash: run pytest --cov or equivalent
   → Read: coverage output
   → GATE: All tests pass, coverage adequate (verification_evidence required)
6. security-lead — Security audit (if auth/input/data involved)
   → [CV-GATE:thinkdeep] Deep security cross-validation
   → GATE: zero errors (any security findings at or above threshold)
7. doc-writer — Update documentation
8. pm-analyst (optional) — Update sprint board: close tasks, record velocity, update work items
9. Human approval → Merge
```

### Bugfix Pipeline (`/orchestrate bugfix "..."`)

```
1. qa-lead — Investigate, reproduce, capture evidence
   → Read: examine reported file/function
   → Grep: find all callers and usage patterns
   → Bash: run failing scenario, capture error output
   → GATE: Bug reproduced with evidence (verification_evidence required)
2. backend-dev or frontend-dev or abap-specialist (SAP bugs) — Implement minimal fix (root cause, not symptoms)
   → Read: examine repro evidence from step 1
   → Bash: verify fix resolves issue
3. test-engineer — Add regression test (must FAIL without fix, PASS with fix)
4. code-reviewer — Review fix + test
   → [CV-GATE:codereview] Cross-validate fix correctness
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)
5. rspdn-writer (optional) — Generate RSPDN pre-correction note from transport changes
   → Save to R:\RSPDN\<PRODUCT>\ and attach link to TFS bug
   → Skipped if not an SAP bug fix
6. Re-verify: run all tests
   → GATE: All tests pass
7. Human approval → Merge
```

### Deployment Pipeline (`/orchestrate deploy "..."`)

```
1. devops-lead — Pre-deployment checklist
   → Read: deployment manifests and configuration files
   → Bash: run pre-flight validation commands
2. qa-lead — Run full test suite
   → GATE: All tests pass
3. security-lead — Security scan
   → [CV-GATE:codereview] Security cross-validation
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)
4. devops-engineer — Build artifacts, prepare manifests
5. Human approval → Deploy to staging
6. integration-tester — Smoke tests on staging
   → GATE: All smoke tests pass
7. Human approval → Deploy to production
```

### Audit Pipeline (`/orchestrate audit "..."`)

**Exit criteria:** zero errors (no findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default threshold = `low`, meaning any finding blocks). Audit loops recursively until this state is reached.

**Exit standard:** zero errors at all gates — no findings at or above threshold allowed at any pipeline quality gate. Configurable via VSCode dashboard `mcpDashboard.gateMinBlockingSeverity`.

```
1. lead-auditor — Review scope, determine expertise, assign domains
   → Write audit scope to docs/AUDIT.md
   [CV-GATE:consensus]
2. specialist-auditor — Domain-specific audit per lead's scope
   → Verdict: APPROVE / REJECT with findings / ESCALATE
   [CV-GATE:thinkdeep]
3. architect — Chief Architect review: cross-domain gaps, coherence
   → Verdict: APPROVE / REJECT / ESCALATE
   [CV-GATE:consensus]
4. lead-auditor — Final audit summary: combine all findings
   → Record in docs/AUDIT.md with verdicts and action items
   → GATE: APPROVE requires zero errors (findings at or above threshold)
   → If REJECT with any blocking-severity finding → fix all, then restart from step 2
   → Audit is recursive: loop steps 2-4 until zero errors or ESCALATE
   → No cap on iterations — continue until clean state is achieved
   → After APPROVE: output Session Summary (see below)
```

**Session Summary (MANDATORY output after audit APPROVE or final ESCALATE — one summary per pipeline run, not after each recursive pass):**

Output directly to the user — do not only write to docs/AUDIT.md:

1. **What was done** — one paragraph: what changed, how many audit cycles ran, how many findings were fixed.

2. **Findings table** (all findings, all cycles):
```
| ID | Severity | Description | Status | Action taken |
|----|----------|-------------|--------|--------------|
| M-01 | MEDIUM | Example finding | Fixed | Updated file:line |
| L-02 | LOW | Example finding | Fixed | Updated file:line |
```
Status: `Fixed` / `Open (escalated)`. **No "Deferred" status** — all findings of any severity must be fixed in the current audit cycle. If a finding genuinely cannot be fixed (requires hardware, external service, etc.), escalate to user — never silently defer.

3. **Manual review table** (what the user must check by hand):
```
| Item | Why manual verification needed | Risk if skipped |
|------|-------------------------------|-----------------|
| Escalated finding X | Requires env-specific testing | Medium |
```
Include: all Open (escalated) findings (any severity), external integrations not covered by automated tests, security controls requiring human sign-off. Exclude: Fixed findings.

### Testing Pipeline (`/orchestrate testing "..."`)

Formal, auditable test execution with immutable test maps and per-step proof validation. Use when `route_task` returns `"testing"`, or when the user requests a formal test run with locked commands and baseline guards.

**Role division:** qa-lead owns the map and pipeline lifecycle; test-engineer executes each step.

```
1. qa-lead — Generate test map via `generate_test_map_tool` (pytest --collect-only → YAML)
   → Review map: groups, expected counts, baseline total
   → GATE: Map is complete and accurate
2. qa-lead — Start testing pipeline via `start_testing_pipeline` (map → immutable pipeline)
   → Each step has locked_command + expected_test_count
3. test-engineer — Execute each pipeline step per locked commands
   → Run exact command from step instruction
   → Submit ## TEST PROOF with matching counts
   → Must NOT modify command, skip tests, or batch groups
   → [Per-step proof validation: command prefix + count enforcement]
4. qa-lead — Verify baseline check (automatic on pipeline completion)
   → Baseline guard: sum(total) >= baseline_total * (1 - threshold)
   → GATE: Pipeline completes with baseline met
```

**Active pipeline detection:** Before starting a new testing pipeline, check `list_active_pipelines(project=...)` for existing `"testing"` pipelines. Resume rather than duplicate.

### QA Pipeline (`/orchestrate qa "..."`)

```
1. test-engineer — Run unit tests
   → GATE: All unit tests pass
2. integration-tester — Run integration tests
   → GATE: All integration tests pass
3. visual-qa — Browser testing (desktop + mobile)
   → GATE: zero errors (no visual bugs at or above threshold)
4. code-reviewer — Claude + OpenAI code review
   → [CV-GATE:codereview] Mandatory cross-validation
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)
5. security-lead — Security audit (if applicable)
   → [CV-GATE:thinkdeep] Security cross-validation
   → GATE: zero errors (any security findings at or above threshold)
6. Report summary of all levels
```

### Review Pipeline (`/orchestrate review "..."`)

**Review mode:** When invoked inside a pipeline (`pipeline_id` present in context), use `quality-only` mode. When invoked ad-hoc (no `pipeline_id`), use `full` mode which includes spec-compliance check.

```
0. [full mode only] spec-compliance — Read PLAN_FILE + TASKS_FILE, compare against git diff.
   Does implementation match the spec? Missing features? Scope creep?
   → GATE: Spec compliance confirmed (skip in quality-only mode)
1. code-reviewer — Full code review with cross-validation
   → [CV-GATE:codereview] Mandatory OpenAI code review
2. security-auditor — Security-focused review (if security-sensitive)
   → [CV-GATE:codereview] Mandatory OpenAI security review
3. Report merged findings with [C], [O], [C+O], [S] markers
```

### Refactor Pipeline (`/orchestrate refactor "..."`)

```
1. architect — Analyze current structure, define target state
   → Read: each module in scope
   → Grep: cross-references and usage patterns
   → Glob: inventory files in module
   → Write refactoring plan to PLAN_FILE (from SESSION SCOPING above)
   → [CV-GATE:consensus] Validate refactoring approach
   → GATE: Plan approved
2. backend-dev — Execute refactoring in small, atomic changes
   → Read: module before modifying
   → Bash: run tests after each change
   → proof_required: must include ## TEST PROOF
   → No behavior changes allowed
3. test-engineer — Verify all existing tests pass unchanged
   → Add missing coverage for refactored code
   → GATE: All tests pass, no behavior change
4. code-reviewer — Review refactoring correctness
   → [CV-GATE:codereview] Cross-validate no behavior change
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)
5. Human approval → Merge
```

### Incident Pipeline (`/orchestrate incident "..."`)

```
1. qa-lead — Triage: severity, blast radius, workaround
   → Read: affected files and recent changes
   → Grep: find all impacted callers and consumers
   → Bash: reproduce the incident, capture error output
   → Document reproduction steps
   → GATE: Severity classified, reproduction confirmed
2. backend-dev — Implement hotfix for root cause
   → Include rollback plan in PR description
3. test-engineer — Add regression test (FAIL without fix, PASS with fix)
   → GATE: Regression test validates fix
4. code-reviewer — Fast review of hotfix
   → [CV-GATE:codereview] Cross-validate fix correctness
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)
5. doc-writer — Write postmortem to docs/postmortems/
   → Timeline, root cause, impact, action items
6. Human approval → Merge + Deploy
```

### Migration Pipeline (`/orchestrate migration "..."`)

```
1. architect — Migration RFC: impact analysis, consumer inventory
   → Write migration strategy to PLAN_FILE (from SESSION SCOPING above)
   → [CV-GATE:consensus] Validate migration approach
   → GATE: RFC approved
2. dev-lead — Break into staged migration tasks
   → Identify rollback points for each stage
3. backend-dev — Execute migration stages
   → Feature flags or dual-write for backward compatibility
4. test-engineer — Backward compatibility tests + new version tests
   → Verify both old and new paths
   → GATE: All compatibility tests pass
5. security-lead — Security review of migration
   → [CV-GATE:thinkdeep] Review new deps, auth changes, data handling
   → GATE: zero errors (any security findings at or above threshold)
6. code-reviewer — Final review of all migration changes
   → [CV-GATE:codereview] Cross-validate staged rollout plan
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)
7. Human approval → Staged rollout
```

### Spike Pipeline (`/orchestrate spike "..."`)

```
1. architect — Research options, evaluate trade-offs
   → Write spike report to docs/spikes/YYYY-MM-DD-<topic>.md
   → [CV-GATE:consensus] Validate analysis completeness
   → GATE: Report includes options + recommendation + evidence
2. dev-lead — Assess implementation effort, risks
   → Add to backlog if approved, or archive spike
```

### Research Pipeline (`/orchestrate research "..."`)

Literature review, survey, or research report with cited sources. Separate
from `spike` (engineering feasibility): this pipeline enforces a SOURCES
evidence gate and an independent-verification step via `fact-checker`.

```
1. research-analyst — Scope the research: subquestions + source-gathering plan
   → Tools: WebSearch (survey candidate sources)
   → Output: research plan in ## STEP RESULT
2. research-analyst — Synthesize findings; every claim MUST cite a source
   → Tools: WebSearch + WebFetch
   → sources_required=True, min_sources=5, evidence_required=True
   → [CV-GATE:thinkdeep]
   → GATE: ## SOURCES block with ≥5 valid entries (url, title, accessed_date, used_for)
3. fact-checker — Independent verification: re-fetch every cited source
   → Tools: Read + WebFetch
   → sources_required=True, min_sources=3
   → MUST NOT trust upstream used_for mappings — re-fetch + cross-check
   → [CV-GATE:consensus]
4. doc-writer — Compose the final report → docs/research/<topic>.md
   → Tools: Read + Edit
```

### Compare Pipeline (`/orchestrate compare "..."`)

Head-to-head evaluation of two or more options with a criteria matrix and
an ADR-style recommendation. Use for "X vs Y" questions, library choices,
database decisions, technology trade-offs.

```
1. research-analyst — Criteria matrix: dimensions + weights + candidate list
   → sources_required=True, min_sources=3
   → [CV-GATE:consensus]
2. research-analyst — Head-to-head comparison per criterion
   → Tools: WebSearch + WebFetch
   → sources_required=True, min_sources=5, evidence_required=True
   → [CV-GATE:consensus]
3. architect — Recommendation + ADR → docs/adr/YYYY-MM-DD-<topic>.md
   → [CV-GATE:consensus]
   → GATE: ADR includes trade-off summary, recommendation, rationale
```

### Analysis Pipeline (`/orchestrate analysis "..."`)

Data analysis, market analysis, descriptive statistics, trend analysis.
Uses `data-analyst` for data-processing Bash (pandas/NumPy) and pairs it
with `research-analyst` for interpretation against cited sources.

```
1. data-analyst — Data gathering + descriptive statistics
   → Tools: Read + Bash (python, pandas, NumPy, CSV ops)
   → evidence_required=True — every Bash command must show observed output
   → Bash scope: data-processing only; NEVER curl/wget/rm/git push/kill
     (agent NEEDS_ASSISTANCE if task requires prohibited command)
2. research-analyst — Interpret trends against cited literature
   → Tools: WebSearch + WebFetch
   → sources_required=True, min_sources=3
   → [CV-GATE:thinkdeep]
3. doc-writer — Compose the analysis report → docs/analysis/<topic>.md
   → Tools: Read + Edit
```

### Performance Pipeline (`/orchestrate perf "..."`)

```
1. qa-lead — Profile and measure: baselines, top-3 bottlenecks
   → Bash: run profiler or benchmark tool, capture baseline metrics
   → Read: profiler output, identify hot paths
   → GATE: Bottlenecks identified with evidence
2. backend-dev — Implement targeted optimizations
3. test-engineer — Performance regression tests: before/after measurements
   → GATE: Measurable improvement verified
4. code-reviewer — Review optimizations for correctness
   → [CV-GATE:codereview] Cross-validate no regressions
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)
```

### Onboard Pipeline (`/orchestrate onboard "..."`)

```
1. architect — System map: components, data flow, APIs, ownership
   → Write to docs/onboarding/<project>.md
2. doc-writer — Onboarding guide: setup, golden path, runbooks
   → Local dev guide, first task suggestions
3. rules-architect — CLAUDE.md review: agent config, sync, rules
   → Verify project is ready for AI-assisted development
```

### Docs Pipeline (`/orchestrate docs "..."`)

```
1. doc-writer — Write/update documentation: README, API docs, guides
   → Verify accuracy against current codebase
2. code-reviewer — Review docs: accuracy, completeness, stale refs
   [CV-GATE:codereview]
```

### Tech Debt Pipeline (`/orchestrate techdebt "..."`)

```
1. backend-dev — Execute cleanup: dead code, linter warnings, deprecated APIs
   → No behavior changes allowed
2. test-engineer — Verify all tests pass, run linters, confirm no regressions
3. code-reviewer — Review: no behavior change, improved quality
   [CV-GATE:codereview]
```

### Deep-Validate Pipeline (`/orchestrate deep-validate "..."`)

Use when: completed changes or plans need exhaustive validation to eliminate ALL gaps, errors, and issues — achieving a state where audit and PAL have zero findings. Typically invoked after an Audit Failure, before critical deployments, or when quality confidence is insufficient.

```
1. architect — Deep analysis of ALL changes against original requirements
   → Read EVERY modified file with Read tool (not skim, not assume)
   → PAL `thinkdeep`: systematic gap analysis — missing edge cases, logic errors,
     integration issues, error handling gaps, concurrency problems
   → context7: verify ALL technical assumptions against official documentation
   → Cross-reference changes against project patterns (Grep for consistency)
   → [CV-GATE:thinkdeep] Cross-validate analysis completeness
   → GATE: Complete gap inventory documented in REVIEW_FILE (from SESSION SCOPING)
   → If gap inventory is empty — architect must justify with Verification Evidence

2. security-lead — Security deep-dive on ALL changes
   → Input validation, auth boundaries, data exposure, injection vectors
   → PAL `thinkdeep`: security-focused analysis
   → [CV-GATE:thinkdeep] Security cross-validation
   → GATE: zero errors (any security findings at or above threshold)

3. backend-dev — Fix ALL identified gaps and issues
   → One atomic fix per finding — no bundling
   → Each fix must reference the finding ID from REVIEW_FILE (from SESSION SCOPING)

4. test-engineer — Validate fixes + run full test suite
   → Every fix must have a corresponding test or justification why not
   → GATE: All tests pass, all findings marked as addressed

5. code-reviewer — Final comprehensive review of ALL changes (original + fixes)
   → PAL `codereview` on every changed file
   → [CV-GATE:codereview] Cross-validate all changes
   → GATE: zero errors (findings at or above `CLAUDE_GATE_MIN_BLOCKING_SEVERITY`; default: any finding)

6. lead-auditor — Final audit with FULL Verification Evidence
   → Must complete entire Audit Depth Checklist (from CLAUDE.md)
   → Must produce APPROVE with Verification Evidence or REJECT
   → [CV-GATE:consensus] Final cross-validation
   → GATE: APPROVE with complete Verification Evidence and zero errors (findings at or above threshold)
   → If REJECT with any blocking-severity finding → HALT pipeline
   → After HALT: fix findings (steps 3-4), then re-submit step 6
   → Audit is recursive: repeat HALT-fix-resubmit until zero errors
   → After 5 HALT cycles with no progress → ESCALATE to user
     (cap is 5: 3 was too aggressive for complex multi-domain plans requiring multiple specialist rounds)
   → After APPROVE or final ESCALATE: output Session Summary (see Audit pipeline Session Summary block above)

7. PAL `precommit` — Final pre-commit validation
   → Validate git changes, check for security issues, assess impact
   → GATE: Clean precommit report — zero errors (no findings at or above threshold)
```

**Exit criteria:** Pipeline completes ONLY when step 6 returns APPROVE with Verification Evidence AND step 7 returns clean. No shortcuts, no "good enough" — zero errors (default: zero findings of any severity).

**HALT behavior:** When step 6 HALTs, the pipeline pauses. Fix findings, re-run steps 3-4 (fix + test), then re-submit step 6 via `complete_step`. This uses the standard HALT + re-submission pattern — no special loop engine support required.

**When to use this pipeline:**
- After an Audit Failure (CRITICAL found in previously approved plan)
- Before critical production deployments
- When refactoring completed changes to improve quality
- When user explicitly requests exhaustive validation
- When confidence in change quality is low

## Multi-Model Orchestration

### Model Tier Routing

Each agent has a `modelTier` in its frontmatter. Use `providers.json` to resolve which model to use:

| Tier | Default (Claude Code) | Cross-Validation (PAL) | Alternative Providers | When |
|------|----------------------|----------------------|----------------------|------|
| **strategic** | Claude Opus | GPT-5.2-Pro | GPT-5.2, o3-pro | Architecture, security, audits |
| **execution** | Claude Sonnet | GPT-5.1-Codex | GPT-5.2, GPT-5-mini | Implementation, testing, review |
| **routine** | Claude Haiku | — | GPT-5-mini, GPT-5-nano | Documentation, formatting |

**In Claude Code runtime:** `model` field (opus/sonnet/haiku) is used directly. `palModel` field determines which OpenAI model is used for cross-validation via PAL MCP.
**In standalone runtime:** `modelTier` maps to `providers.json` for provider selection.

### Cross-Validation Pattern

Agents with `crossValidation: true` MUST get a second opinion from a different provider:

```
Primary agent (Claude) produces output
  → PAL MCP calls OpenAI with same prompt
  → Agent compares both outputs:
     - Agreements → [C+O] high confidence
     - Disagreements → flag for human with both views
     - Union of findings → comprehensive coverage
```

Agents with cross-validation: architect, dev-lead, security-lead, lead-auditor, security-auditor, code-reviewer, specialist-auditor.

### Cross-Validation Gates (CV-GATE)

CV-gates are mandatory cross-provider validation points inserted between pipeline stages. Each gate calls OpenAI via PAL MCP for an independent assessment.

**Gate Behavior:**
- **PAL agrees with Claude** → Continue pipeline, mark findings as `[C+O]`
- **PAL finds a blocking-severity issue Claude missed** (any finding at or above threshold) → HALT pipeline, add finding as `[O]`, re-evaluate
- **PAL disagrees on severity** → Flag disagreement, continue with higher severity
- **PAL finds additional LOW issues only** → Add to findings as `[O]`, continue
- **PAL unavailable** → Do NOT skip cross-validation. Launch a sub-agent via Agent tool with a different model tier (opus if current is sonnet; sonnet if current is opus) with the same prompt. Document fallback model used.

**Gate Types:**

| Gate | PAL Tool | Model | When Used |
|------|----------|-------|-----------|
| `CV-GATE:consensus` | `consensus` | gpt-5.2-pro | Architecture decisions, audit scope validation |
| `CV-GATE:codereview` | `codereview` | gpt-5.1-codex / gpt-5.2-pro | Code changes, security findings, pre-merge |
| `CV-GATE:thinkdeep` | `thinkdeep` | gpt-5.2-pro | Deep analysis, cross-domain risks, security |
| `CV-GATE:precommit` | `precommit` | gpt-5.1-codex | Final pre-merge validation |

**Gate Execution:**
```
[CV-GATE:codereview]
  1. Orchestrator calls PAL `codereview` with the agent's output + relevant code
  2. PAL returns findings with severity ranking
  3. Orchestrator merges PAL findings into pipeline context
  4. If new findings at or above threshold → HALT and report
  5. If no new blocking-severity findings → attach [O] below-threshold findings and continue
```

**Using `/cross-validate` for detailed disputes:**
When a CV-GATE detects a disagreement between Claude and OpenAI on CRITICAL/HIGH findings, invoke the `/cross-validate` skill for a structured multi-round debate before escalating to human.

### Agent Invocation Patterns

**Pattern 1: Handoff (current default)**
Agent A completes → returns NEEDS ASSISTANCE → Orchestrator invokes Agent B → Agent B takes over.
Agent A is done; Agent B owns the task from here.

**Pattern 2: Agent-as-Tool**
Orchestrator invokes Agent B as a subtask → Agent B returns result → Orchestrator continues with result.
Orchestrator keeps control. Agent B is a tool, not a successor.

Use **Handoff** for pipeline stages (architect → dev-lead → backend-dev).
Use **Agent-as-Tool** for consultation (backend-dev needs security-auditor opinion on one function).

### Artifact Pattern (Context Between Agents)

Instead of passing full conversation history, agents exchange context through files:

```
architect → writes PLAN_FILE → dev-lead reads PLAN_FILE
dev-lead → writes TASKS_FILE → backend-dev reads TASKS_FILE
code-reviewer → writes REVIEW_FILE → backend-dev reads REVIEW_FILE
```
(PLAN_FILE/TASKS_FILE/REVIEW_FILE resolved from CLAUDE_SESSION by SESSION SCOPING at entry)

Benefits:
- No token waste on history forwarding
- Works across model providers (file is model-agnostic)
- Auditable — every artifact is a file in the project
- Resumable — any agent can pick up from the last artifact

Standard artifact locations (session-scoped when CLAUDE_SESSION is set):
- PLAN_FILE (`docs/PLAN.md` or `docs/PLAN-{label}.md`) — architecture decisions
- TASKS_FILE (`docs/TASKS.md` or `docs/TASKS-{label}.md`) — task breakdown
- REVIEW_FILE (`docs/REVIEW.md` or `docs/REVIEW-{label}.md`) — code review findings
- `docs/AUDIT.md` — audit results (global, not session-scoped)

## MCP Routing Rules

When launching agents, you MUST:
1. Check the agent's frontmatter for `mcpServers`
2. If mcpServers is not empty — launch ONLY in foreground (MCP tools are not available in background)
3. If mcpServers is empty AND task doesn't need MCP — background is OK
4. For parallel launches: MCP-dependent agents run foreground sequentially, non-MCP agents can run background in parallel
5. NEVER launch an MCP-dependent agent in background — this causes silent failure
6. For pipeline steps: always inject `pipeline_id`, step number, and STEP RESULT requirement into Task agent prompt (see Task Agent Launch Protocol below)

## Context Minimization (Pipeline-Aware)

When a pipeline is active and `pipeline_ops(action="next_step")` returns `output_format` and `skill_section` fields, agents SHOULD:

1. Use the `output_format` hint to structure their response correctly without loading full skill documentation.
2. Use the `skill_section` reference to load ONLY the referenced section if additional context is needed — not the entire skill file.
3. The `recommended_context` list in `StepResult` provides pointers (`skill:<section>`, `output:<format>`) for the next step. Pass these to the next agent's prompt.

This reduces per-step token overhead by avoiding full skill text injection when the pipeline already provides structured step contracts.

## Task Agent Launch Protocol (MANDATORY)

> **⚠️ Critical:** Hooks (`complete-step-gate.sh`, `pre-commit-gate.sh`, etc.) run ONLY in the main session. Task sub-agents bypass all hooks. Enforce quality and pipeline discipline through prompt injection, not hooks.

### Authority Tool Rule

**Only the main session may call:**
- `mcp__orchestrator__complete_step(pipeline_id, step_output)` — after validating STEP RESULT
- `mcp__orchestrator__start_pipeline(pipeline_type, description, project=<basename of cwd>)` — after route_task + plan saved

**Sub-agents MUST NOT call these tools directly.** Sub-agents produce STEP RESULT blocks; the main session validates and calls the authority tools. This ensures quality hooks fire correctly.

### Pipeline Context Injection

Every Task agent launched for a pipeline step MUST receive this in its prompt:

```
PIPELINE CONTEXT (do not ignore):
  pipeline_id: {id from start_pipeline result}
  step: {n} of {total} — {step_name}
  pipeline_type: {type}

<!-- Fragment: progress-format. Source: base/CLAUDE.md:33-76. L71 (TodoWrite-linkage) is intentionally excluded — it targets the main orchestrating session, not sub-agents. When adding this to a new sub-agent-spawning skill, insert `<!-- INCLUDE:progress-format -->` where the old short PROGRESS block was; sync.ps1 Expand-Includes (sync.ps1:152-173) inlines this file's full contents. -->

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
- **Throttle:** max one full-list update per 5 seconds for the same task.

Report elapsed_s (integer seconds) in STEP RESULT.

REQUIRED: Produce a ## STEP RESULT block as the very last thing in your response.
DO NOT call mcp__orchestrator__complete_step — the main session does this after reviewing your output.

TOOL MANDATES (enforced — HALT on missing):
  Required tools: {required_tools_list}
  Evidence required: {yes/no}
  You MUST use each required tool and show its output in your response.
  The orchestrator rejects STEP RESULT without tool evidence.
```

### STEP RESULT Format

Every pipeline agent MUST end its response with this block:

```
## STEP RESULT
- step: {step-name}
- pipeline_id: {pipeline-id}
- status: COMPLETE | INCOMPLETE | FAILED | SKIPPED | NEEDS_ASSISTANCE
- artifacts: [list of files created or modified]
- context_files: [optional list of file paths produced/consumed by this step]
- verification_evidence: [command -> observed output, e.g. "pytest -> 518 passed, 0 failed"]
- risks: [1-2 items or "none identified"]
- elapsed_s: {seconds this step took, integer}
- notes: <1-3 lines summary>
- next: {next-agent-name or PIPELINE_COMPLETE}
```

**New fields (Phase 11):** `verification_evidence` and `risks` are optional initially — main session warns on missing but does not reject. Graduate to required after one release cycle.

**Status values:**
- `COMPLETE` — step fully done, all artifacts written, ready for main session to call complete_step
- `INCOMPLETE` — work partially done, main session should address the gap before continuing
- `FAILED` — unrecoverable error, escalate to user
- `SKIPPED` — step not applicable to this pipeline run (optional steps: frontend-dev, visual-qa, abap-specialist, pm-analyst)
- `NEEDS_ASSISTANCE` — agent encountered a blocker requiring a different specialist

**`context_files` field:** Optional list of file paths produced or consumed by this step. Use this to signal which files the next agent needs to read. NEVER embed file content in STEP RESULT — list paths only.

**Note on artifacts:** List file paths only, do not duplicate content. Artifacts (PLAN_FILE, REVIEW_FILE, etc.) are the source of truth for durable context. STEP RESULT is ephemeral routing metadata — it indexes artifacts, not replaces them.

### Tool Mandate Rules

Pipeline steps with `required_tools` MUST demonstrate usage of each listed tool in their output. The orchestrator validates this at `complete_step` time — missing tool evidence causes HALT.

**Evidence patterns the orchestrator recognizes:**
- `Read` — file content excerpts, "Read tool", file paths with `:line`
- `Grep` — search results, "Grep", "found N matches"
- `Glob` — file listings, "Glob", directory inventories
- `Bash` — command output blocks (```), exit codes, "$ " prompts
- `Bash:<cmd>` — the sub-command string in command output
- `mcp__pal__*` — PAL tool name in output
- `context7` — documentation excerpts, "context7"

**verification_evidence enforcement:**
Steps with `evidence_required: true` MUST include a non-empty `verification_evidence:` line in STEP RESULT. Placeholder values ("none", "n/a") are rejected.

### Main Session Validation Rules

After receiving a Task agent response:

1. **Check for STEP RESULT block** — if absent, ask the agent to resubmit with the required format
2. **Check status** — do NOT advance if status is INCOMPLETE, FAILED, or NEEDS_ASSISTANCE
3. **Verify artifacts** — confirm listed artifact files exist before calling complete_step
4. **Call complete_step yourself** — `mcp__orchestrator__complete_step(pipeline_id, step_output)` after validation
5. **If complete_step returns HALT** — fix the issue (run PAL/audit if needed), then resubmit the step
6. **Check required_tools compliance** — if step has required_tools, verify the sub-agent's response
   mentions or shows output from each required tool before calling complete_step

### Phase Memory Protocol

At the end of each pipeline step, agents MUST write a phase memory file to preserve context for future steps. Use the `memory` tool commands (`view`, `create`, `replace_file`).

**File path convention:** `phase-{N}-{step_name}.md` (e.g., `phase-1-architect.md`)
**Storage location:** `~/.claude/agent-memory/<pipeline_id>/` (managed by orchestrator/memory.py)
**Max size:** 500 words per file (hard limit: 50 KB enforced by memory.py)

**Required content structure:**

```markdown
# Phase {N} — {Step Name}

## Decisions
- Key architectural choices made in this step

## Artifacts
- List of file paths created or modified

## Open Issues
- Unresolved items that need attention in later steps

## Next Phase Context
- What the next agent needs to know to continue effectively
```

**At step start:** Call `view(pipeline_id, path=None)` to read the index and load the most recent phase file for context. Cross-phase reads require explicit `path=` argument.

**At step end:** Call `create(pipeline_id, path="phase-N-name.md", content=...)` or `replace_file(...)` to persist phase memory.

**NEVER embed file content in STEP RESULT** — list paths in `context_files` only. Phase memory files are the durable context vehicle; STEP RESULT is ephemeral routing metadata.

### Context Editing API Configuration

When making direct Claude API calls from the orchestrator (not via Claude Code), include the following `context_management` configuration to reduce token waste from accumulated tool results:

```python
# Beta header required
headers = {"anthropic-beta": "context-management-2025-06-27"}

# Request body context_management block
"context_management": {
    "type": "clear_tool_uses_20250919",
    "threshold": {"type": "input_tokens", "threshold_tokens": 80000},
    "keep_last_n_tool_uses": 5,
    "exclude_tools": ["memory"]   # preserve memory tool results across compaction
}
```

**Rationale:** At 80K input tokens the API automatically discards old tool-use/tool-result pairs (keeping the last 5), which prevents context window exhaustion on long pipelines. Memory tool results are excluded so phase context persists across compaction boundaries.

**Note:** This configuration is for direct API calls only. Claude Code sessions use the `/compact` command and `compact-state-inject.sh` hook for context management.

## Agent Chaining Rules

When an agent returns a **NEEDS ASSISTANCE** block:
1. Read the recommended agent name and context
2. Invoke the recommended agent with the provided context
3. If `After: continue my work` — resume the original agent (using the `resume` parameter) with the results
4. If `After: hand to human` — present findings to the user
5. If `After: chain to next agent` — invoke the specified third agent
6. Log the entire chain for audit trail

## Quality Gates

A quality gate failure means:
- Stop the pipeline
- Report the failure to the user
- Enter Debug-Fix-Verify cycle if applicable:
  1. DIAGNOSE — capture failure details
  2. FIX — minimal fix for root cause
  3. REGRESSION TEST — add test for this failure
  4. RE-VERIFY — run all levels again

## Error Handling

- If an agent fails to produce output: retry once, then escalate to human
- If a gate fails: do NOT proceed to next step. Report and wait for resolution.
- If multiple agents disagree: flag disagreements for human review
- Keep a log of all agent invocations and results for audit trail

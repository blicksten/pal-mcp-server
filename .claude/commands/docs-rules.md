---
name: docs-rules
description: Documentation quality standards, markdown formatting rules, and testing/mock data rules. Load when writing documents >100 lines or creating test fixtures.
---

# Documentation Quality & Testing Rules

---

## Documentation Quality (MANDATORY)

### When writing a document >100 lines, include:

- **Table of Contents** -- anchor-linked TOC at the top.
- **ASCII diagrams** -- for architecture, flows, timelines, state machines, decision trees. Use ` ``` ` code fences with box-drawing characters (+---+, |, →, etc.). Do NOT use Mermaid.
- **Collapsible sections** -- `<details><summary>...</summary>...</details>` for verbose content.
- **Unicode emoji markers** -- use actual characters (checkmark, warning, construction), NOT GitHub shortcodes (`:white_check_mark:` etc.) -- shortcodes don't render in VSCode.
- **Bold blockquote callouts** -- `> **Note:**`, `> **Warning:**`, `> **Important:**` with emoji prefix -- NOT `> [!NOTE]` syntax (doesn't render in VSCode).
- **Aligned tables** -- use `:---|:---:|---:` for comparisons.

### When writing any document, always:

- Specify language tags on code blocks (` ```python `, ` ```typescript `, ` ```json `).
- Use **bold emphasis** for key terms and decisions.
- Place horizontal rules (`---`) between major sections.

### Compatibility rules

- Never use GitHub-only syntax (`> [!NOTE]`, emoji shortcodes) -- use universal alternatives.
- All formatting must render in VSCode Markdown Preview, GitLab, and GitHub.
- Use ASCII diagrams inside code fences; do not use Mermaid or other rendered diagram syntaxes.

---

## Testing & Mock Data (CRITICAL)

- Before creating or updating a fixture/mock file: query the real external service to capture the actual response format. Never fabricate or guess formats.
- When the real format is broken: file a bug against the upstream service. Never invent a workaround format.
- When writing unit tests: include test cases using the real response format, not just mock format.
- When reviewing tests: reject tests that only verify fabricated formats.

---

## Mindset

- When faced with multiple approaches: consider trade-offs before choosing. Prefer the simplest working solution.
- When process conflicts with pragmatism: focus on what works, not ceremony.
- When spotting improvement opportunities: suggest them proactively, but do not force them.

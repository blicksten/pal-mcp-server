"""HGB.3 T3.4 — unit tests for the Bug B caller-side raw_analysis parser.

Plan: ``claude-team-control/docs/PLAN-hollow-gate-blockers.md`` §HGB.3.

The Bug B failure mode: PAL's ``_extract_gate_verdict`` reads only
``consolidated_findings.issues_found``. When expert analysis runs but the
findings stay in ``expert_analysis.raw_analysis`` (a prose-with-severity-
bullets text field), the gate reports PASS / 0-findings even when the
expert identified CRITICALs. The self-incriminating comment at
``tools/workflow/workflow_mixin.py:1195-1197`` documented the gap before
this fix.

HGB.3 T3.3 adds an opt-in raw_analysis parser gated by
``CLAUDE_GATE_PARSE_RAW_ANALYSIS=1``. T3.6 adds a defensive alarm that
logs a warning + suffixes the gate summary when the parser returns
0 findings on text that nevertheless contains "critical" or "high"
(format-drift safety net).

These tests exercise both the parser primitive and the integration into
``_extract_gate_verdict``.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from tools.workflow.workflow_mixin import BaseWorkflowMixin

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StubMixinHost:
    """Minimal carrier that exposes only what _extract_gate_verdict uses.

    Bind the parser classmethod on the instance so the `self.` lookup
    inside `_extract_gate_verdict` resolves without instantiating the
    full BaseWorkflowMixin chain (which pulls in PAL provider config etc.).
    """

    # Classmethod descriptors are class-level — copy the bindings so
    # instance-method-style `self._parse_raw_analysis_findings(...)` /
    # `self._has_unnegated_blocking_signal(...)` calls inside
    # _extract_gate_verdict still resolve to BaseWorkflowMixin's.
    _parse_raw_analysis_findings = BaseWorkflowMixin._parse_raw_analysis_findings  # noqa: SLF001
    _has_unnegated_blocking_signal = BaseWorkflowMixin._has_unnegated_blocking_signal  # noqa: SLF001

    def __init__(self) -> None:
        self.consolidated_findings = MagicMock()
        self.consolidated_findings.issues_found = []
        self.expert_analysis: dict | str | None = None


def _make_host_with_expert(raw_analysis: str) -> _StubMixinHost:
    host = _StubMixinHost()
    host.expert_analysis = {"raw_analysis": raw_analysis}
    return host


# Bind the mixin methods we care about onto the stub host.
_extract = BaseWorkflowMixin._extract_gate_verdict
_parse = BaseWorkflowMixin._parse_raw_analysis_findings


# ---------------------------------------------------------------------------
# Unit tests for the parser primitive (T3.2)
# ---------------------------------------------------------------------------


def test_parser_empty_text_returns_empty_list() -> None:
    assert _parse("") == []
    assert _parse(None) == []  # type: ignore[arg-type]


def test_parser_extracts_emoji_critical_bullets() -> None:
    text = (
        "[\U0001f534 CRITICAL] Hardcoded credential in login.go:18\n"
        "[\U0001f534 CRITICAL] SQL injection in login.go:38\n"
        "[\U0001f7e0 HIGH] Ignored db.Query error in login.go:41"
    )
    findings = _parse(text)
    assert len(findings) == 3
    assert [f["severity"] for f in findings] == ["critical", "critical", "high"]
    assert "Hardcoded credential" in findings[0]["description"]
    assert "SQL injection" in findings[1]["description"]
    assert "Ignored db.Query error" in findings[2]["description"]


def test_parser_extracts_plain_bracket_bullets_format_drift() -> None:
    """T3.6 format-drift defense — plain [CRITICAL] without emoji prefix."""
    text = "[CRITICAL] Hardcoded credential in login.go:18\n[HIGH] Ignored db.Query error in login.go:41"
    findings = _parse(text)
    assert len(findings) == 2
    assert findings[0]["severity"] == "critical"
    assert findings[1]["severity"] == "high"


def test_parser_extracts_no_bracket_emoji_bullets() -> None:
    """Fix A (2026-06-15) — no-bracket emoji form `\U0001f534 CRITICAL` (the
    prompt's SEVERITY DEFINITIONS style) is now recognised."""
    text = (
        "\U0001f534 CRITICAL: Hardcoded credential in login.go:18\n"
        "\U0001f7e0 HIGH: Ignored db.Query error in login.go:41\n"
        "\U0001f7e2 LOW: minor naming nit"
    )
    findings = _parse(text)
    assert [f["severity"] for f in findings] == ["critical", "high", "low"]
    assert "Hardcoded credential" in findings[0]["description"]


def test_parser_no_double_count_bracketed_vs_no_bracket() -> None:
    """Dedup regression (2026-06-15) — the bracketed `[\U0001f534 CRITICAL]`
    bullet must yield ONE finding, not two, even though the no-bracket token
    `\U0001f534 CRITICAL` is a substring of it."""
    text = "[\U0001f534 CRITICAL] SQL injection in db.go:5"
    findings = _parse(text)
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_parser_case_insensitive() -> None:
    """Some decoding paths produce mixed-case markers; parser stays robust."""
    text = "[critical] downcased marker\n[Critical] mixed-case marker"
    findings = _parse(text)
    assert len(findings) == 2
    assert all(f["severity"] == "critical" for f in findings)


def test_parser_ignores_text_without_markers() -> None:
    """Plain prose mentioning 'critical' without bracket markers is ignored
    by the parser primitive (the defensive alarm catches that case
    separately in _extract_gate_verdict)."""
    text = "The code review found a critical issue with the login flow."
    assert _parse(text) == []


def test_has_unnegated_blocking_signal_positive() -> None:
    """Non-negated blocking-severity prose is detected."""
    h = BaseWorkflowMixin._has_unnegated_blocking_signal
    assert h("There is a critical SQL injection vulnerability at line 38.")
    assert h("This is a high-severity authz bypass.")
    assert h("I rate this high risk.")


def test_has_unnegated_blocking_signal_negated_is_false() -> None:
    """Negated mentions and benign 'high X' phrasings do NOT trip it."""
    h = BaseWorkflowMixin._has_unnegated_blocking_signal
    assert not h("No critical issues found.")
    assert not h("The review found no critical or high-severity problems.")
    assert not h("The code is high quality and high-level.")
    assert not h("This module is free of critical defects.")
    assert not h("")


def test_has_unnegated_blocking_signal_no_far_negation_still_fires() -> None:
    """Re-hollowing guard (sonnet review CRITICAL) — a negation word that is
    NOT immediately adjacent to the severity word must NOT suppress a real
    finding. The earlier 24-char window wrongly swallowed these."""
    h = BaseWorkflowMixin._has_unnegated_blocking_signal
    assert h("There is no doubt this is a critical SQL injection.")
    assert h("lack of sanitization makes this a critical vulnerability")
    assert h("without exception, this is a critical authz bypass")
    assert h("absent proper escaping, this critical path is exploitable")


def test_has_unnegated_blocking_signal_adverb_form_does_not_trip() -> None:
    """False-positive guard (sonnet review HIGH) — the adverb 'critically'
    and noun 'criticality' are not whole-word 'critical' and must NOT force a
    clean review into DISPUTE."""
    h = BaseWorkflowMixin._has_unnegated_blocking_signal
    assert not h("It is critically important to add documentation.")
    assert not h("The criticality of this module is low.")
    assert not h("This code is uncritical to the hot path.")


def test_has_unnegated_blocking_signal_skip_bridge_does_not_re_hollow() -> None:
    """Re-hollowing guard (sonnet review round 2 CRITICAL) — a leading
    negation that scopes a DIFFERENT clause must NOT bridge across a noun to
    suppress a real finding. The walk stops at any non-severity noun, so
    'no findings or errors, critical SQL injection' is correctly detected."""
    h = BaseWorkflowMixin._has_unnegated_blocking_signal
    assert h("no findings or errors, critical SQL injection at line 38")
    assert h("no defects or vulnerabilities; critical buffer overflow in auth.c")
    assert h("no bugs. critical race condition in scheduler.py")
    assert h("no minor issues but a critical authz bypass")


def test_has_unnegated_blocking_signal_in_clause_distributed_still_suppressed() -> None:
    """The legitimate in-clause distributed negation must still be suppressed
    after the skip-set narrowing — severity vocabulary is still skipped."""
    h = BaseWorkflowMixin._has_unnegated_blocking_signal
    assert not h("no critical or high-severity issues")
    assert not h("no high severity or critical problems were found")
    assert not h("found no critical, high-severity, or high-risk defects")


def test_parser_5C_1H_login_go_fixture_shape() -> None:
    """End-to-end shape check against the HGB.1 login.go fixture narrative
    encoded in the orchestrator's stub PAL.
    """
    text = (
        "[\U0001f534 CRITICAL] Hardcoded credential in login.go:18 (dbPassword)\n"
        "[\U0001f534 CRITICAL] Hardcoded API key in login.go:20 (apiKey)\n"
        "[\U0001f534 CRITICAL] SQL injection in login.go:38\n"
        "[\U0001f534 CRITICAL] Command injection in login.go:52\n"
        "[\U0001f534 CRITICAL] Path traversal in login.go:65\n"
        "[\U0001f7e0 HIGH] Ignored db.Query error in login.go:41"
    )
    findings = _parse(text)
    assert len(findings) == 6
    severities = [f["severity"] for f in findings]
    assert severities.count("critical") == 5
    assert severities.count("high") == 1


# ---------------------------------------------------------------------------
# Integration tests for _extract_gate_verdict feature flag (T3.3)
# ---------------------------------------------------------------------------


def test_flag_off_legacy_behaviour_unchanged(monkeypatch) -> None:
    """When the env flag is unset, _extract_gate_verdict ignores raw_analysis.

    This is the regression guard for the opt-in posture (T3.3): existing
    callers must not see new behaviour until they explicitly enable the
    flag. Default OFF for one canary cycle (HGB.5).
    """
    monkeypatch.delenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", raising=False)
    host = _make_host_with_expert("[\U0001f534 CRITICAL] Should be ignored when flag is off")
    result = _extract(host)
    assert result["gate_verdict"] == "PASS"
    assert result["gate_findings"] == []
    assert "0 finding(s)" in result["gate_summary"]


def test_flag_on_parses_5_critical_plus_1_high(monkeypatch) -> None:
    """T3.3 happy path — opt-in flag enabled, expert raw_analysis surfaces."""
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    host = _make_host_with_expert(
        "[\U0001f534 CRITICAL] Hardcoded credential in login.go:18\n"
        "[\U0001f534 CRITICAL] Hardcoded API key in login.go:20\n"
        "[\U0001f534 CRITICAL] SQL injection in login.go:38\n"
        "[\U0001f534 CRITICAL] Command injection in login.go:52\n"
        "[\U0001f534 CRITICAL] Path traversal in login.go:65\n"
        "[\U0001f7e0 HIGH] Ignored db.Query error in login.go:41"
    )
    result = _extract(host)
    assert result["gate_verdict"] == "HALT"
    assert len(result["gate_findings"]) == 6
    severities = [f["severity"] for f in result["gate_findings"]]
    assert severities.count("critical") == 5
    assert severities.count("high") == 1
    assert "HALT" in result["gate_summary"]


def test_flag_on_but_issues_already_populated_skips_parse(monkeypatch) -> None:
    """When consolidated_findings already has structured data, raw parser is skipped.

    The opt-in branch only fires when issues_found is empty — otherwise we'd
    double-count findings PAL already structured.
    """
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    host = _make_host_with_expert("[\U0001f534 CRITICAL] Would-be parsed but issues already populated")
    host.consolidated_findings.issues_found = [{"severity": "high", "description": "structured finding"}]
    result = _extract(host)
    assert result["gate_verdict"] == "HALT"
    assert len(result["gate_findings"]) == 1
    assert result["gate_findings"][0]["description"] == "structured finding"


def test_flag_on_defensive_alarm_escalates_to_dispute(monkeypatch, caplog) -> None:
    """T3.6 defensive alarm (hardened 2026-06-15) — parser produces 0 but the
    text carries a non-negated blocking signal → verdict escalates to DISPUTE,
    NOT PASS. Previously this path returned PASS, silently absorbing a real
    finding the parser could not structure (the hollow-PASS defect)."""
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    host = _make_host_with_expert("Plain prose mentioning a critical issue without any bracket markers.")
    with caplog.at_level(logging.WARNING):
        result = _extract(host)
    assert result["gate_verdict"] == "DISPUTE"
    assert result["gate_findings"] == []
    assert "raw_analysis parse failed" in result["gate_summary"]
    # Verify the alarm fired.
    assert any("HGB.3 T3.6" in rec.getMessage() for rec in caplog.records), (
        f"defensive alarm log not emitted; records={[r.getMessage() for r in caplog.records]!r}"
    )


def test_flag_on_negated_severity_stays_pass(monkeypatch) -> None:
    """Negation-aware T3.6 — 'no critical issues' / 'high quality' must NOT
    trip the alarm. A genuinely clean review that happens to mention severity
    words stays PASS (R-5 false-positive guard)."""
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    host = _make_host_with_expert(
        "The review found no critical or high-severity issues. The code is high quality and the architecture is sound."
    )
    result = _extract(host)
    assert result["gate_verdict"] == "PASS"
    assert result["gate_findings"] == []
    assert "raw_analysis parse failed" not in result["gate_summary"]


def test_flag_on_no_bracket_emoji_form_parses_to_halt(monkeypatch) -> None:
    """Fix A (2026-06-15) — the codereview prompt's SEVERITY DEFINITIONS emit
    the no-bracket emoji form (`\U0001f534 CRITICAL:`). The parser must now
    extract it so a real finding yields HALT, not a hollow PASS."""
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    host = _make_host_with_expert(
        "\U0001f534 CRITICAL: SQL injection in db.go:5\n\U0001f7e0 HIGH: unchecked error in db.go:12"
    )
    result = _extract(host)
    assert result["gate_verdict"] == "HALT"
    severities = sorted(f["severity"] for f in result["gate_findings"])
    assert severities == ["critical", "high"]


def test_flag_on_no_expert_analysis_is_no_op(monkeypatch) -> None:
    """When expert_analysis is None, the parser branch is skipped silently."""
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    host = _StubMixinHost()  # expert_analysis = None
    result = _extract(host)
    assert result["gate_verdict"] == "PASS"
    assert result["gate_findings"] == []


# ---------------------------------------------------------------------------
# KEYSTONE tests (pal-hollow-gate-fix T1.2) — handle_work_completion MUST persist
# expert_analysis onto self so the gate parser above can ever fire in production.
# These cover the real assignment path that was MISSING (only the test fixture
# above set self.expert_analysis, so the parser was dead code → 100% hollow gate).
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

_handle_completion = BaseWorkflowMixin.handle_work_completion


class _CompletionHost:
    """Minimal host to drive handle_work_completion into its success branch."""

    handle_work_completion = BaseWorkflowMixin.handle_work_completion  # noqa: SLF001
    _extract_gate_verdict = BaseWorkflowMixin._extract_gate_verdict  # noqa: SLF001
    _parse_raw_analysis_findings = BaseWorkflowMixin._parse_raw_analysis_findings  # noqa: SLF001

    def __init__(self, expert_result) -> None:
        self._expert_result = expert_result
        self.work_history: list = []
        self.consolidated_findings = MagicMock()
        self.consolidated_findings.issues_found = []
        self.consolidated_findings.files_checked = []
        self.consolidated_findings.relevant_files = []
        self.consolidated_findings.relevant_context = []
        # expert_analysis intentionally NOT set — getattr(...,None) must hold
        # until the success path assigns it.

    def get_name(self) -> str:
        return "thinkdeep"

    def get_initial_request(self, step) -> str:
        return "initial request"

    def _prepare_work_summary(self) -> str:
        return "work summary"

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        return False

    def requires_expert_analysis(self) -> bool:
        return True

    def should_call_expert_analysis(self, consolidated_findings, request) -> bool:
        return True

    async def _call_expert_analysis(self, arguments, request):
        return self._expert_result

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        return "next steps"

    def get_expert_analysis_guidance(self) -> str:
        return ""


def test_keystone_success_sets_self_expert_analysis() -> None:
    """The success branch MUST persist expert_analysis onto self (the keystone)."""
    expert = {"status": "analysis_complete", "raw_analysis": "[\U0001f534 CRITICAL] boom"}
    host = _CompletionHost(expert)
    assert getattr(host, "expert_analysis", None) is None  # pre-condition: unset
    asyncio.run(host.handle_work_completion({}, MagicMock(), {}))
    assert host.expert_analysis == expert, "keystone regression: self.expert_analysis not set on success"


def test_keystone_analysis_timeout_does_not_set_self_expert_analysis() -> None:
    """F-3: a timed-out expert produced no real analysis — must NOT be persisted."""
    expert = {"status": "analysis_timeout", "error": "expert timed out", "model_used": "gpt-5.2-pro"}
    host = _CompletionHost(expert)
    asyncio.run(host.handle_work_completion({}, MagicMock(), {}))
    assert getattr(host, "expert_analysis", None) is None, "analysis_timeout must not set self.expert_analysis"


def test_keystone_end_to_end_completion_then_gate_yields_findings(monkeypatch) -> None:
    """End-to-end: success completion sets self.expert_analysis, then the gate
    parser surfaces the CRITICAL findings → HALT. This is the whole point — it
    proves the keystone connects the expert output to the gate verdict."""
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    expert = {
        "status": "analysis_complete",
        "raw_analysis": (
            "[\U0001f534 CRITICAL] SQL injection in login.go:38\n[\U0001f7e0 HIGH] Ignored error in login.go:41"
        ),
    }
    host = _CompletionHost(expert)
    asyncio.run(host.handle_work_completion({}, MagicMock(), {}))
    # Now the gate parser must see the narrative the keystone persisted.
    result = host._extract_gate_verdict()  # noqa: SLF001
    assert result["gate_verdict"] == "HALT"
    assert len(result["gate_findings"]) == 2
    severities = [f["severity"] for f in result["gate_findings"]]
    assert severities.count("critical") == 1
    assert severities.count("high") == 1

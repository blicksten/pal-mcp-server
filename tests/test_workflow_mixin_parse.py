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

    # Classmethod descriptor is class-level — copy the binding so an
    # instance-method-style `self._parse_raw_analysis_findings(...)` call
    # inside _extract_gate_verdict still resolves to BaseWorkflowMixin's.
    _parse_raw_analysis_findings = BaseWorkflowMixin._parse_raw_analysis_findings  # noqa: SLF001

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


def test_flag_on_defensive_alarm_when_raw_contains_severity_word(monkeypatch, caplog) -> None:
    """T3.6 defensive alarm — parser produces 0 but text mentions severity."""
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    host = _make_host_with_expert("Plain prose mentioning a critical issue without any bracket markers.")
    with caplog.at_level(logging.WARNING):
        result = _extract(host)
    assert result["gate_verdict"] == "PASS"
    assert result["gate_findings"] == []
    assert "(raw_analysis parse failed)" in result["gate_summary"]
    # Verify the alarm fired.
    assert any(
        "HGB.3 T3.6" in rec.getMessage() for rec in caplog.records
    ), f"defensive alarm log not emitted; records={[r.getMessage() for r in caplog.records]!r}"


def test_flag_on_no_expert_analysis_is_no_op(monkeypatch) -> None:
    """When expert_analysis is None, the parser branch is skipped silently."""
    monkeypatch.setenv("CLAUDE_GATE_PARSE_RAW_ANALYSIS", "1")
    host = _StubMixinHost()  # expert_analysis = None
    result = _extract(host)
    assert result["gate_verdict"] == "PASS"
    assert result["gate_findings"] == []

"""Tests for the EXPERT_ANALYSIS_TIMEOUT guard in workflow_mixin._call_expert_analysis.

Without a hard deadline, every workflow tool (codereview, thinkdeep, debug,
secaudit, refactor, testgen, tracer, analyze, docgen, precommit) could hang
indefinitely on the final-step expert analysis call when the provider stalls
past the MCP client deadline. This module verifies the wait_for guard behaves
correctly across the env-var matrix and the timeout path.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from tools.shared.base_models import ConsolidatedFindings
from tools.thinkdeep import ThinkDeepTool
from tools.workflow.workflow_mixin import (
    _DEFAULT_EXPERT_ANALYSIS_TIMEOUT,
    _get_expert_analysis_timeout,
)


class TestExpertAnalysisTimeoutEnvParser:
    """Helper resolves EXPERT_ANALYSIS_TIMEOUT from env, falling back on bad input."""

    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("EXPERT_ANALYSIS_TIMEOUT", raising=False)
        assert _get_expert_analysis_timeout() == _DEFAULT_EXPERT_ANALYSIS_TIMEOUT

    def test_explicit_value(self, monkeypatch):
        monkeypatch.setenv("EXPERT_ANALYSIS_TIMEOUT", "120.5")
        assert _get_expert_analysis_timeout() == 120.5

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setenv("EXPERT_ANALYSIS_TIMEOUT", "0")
        assert _get_expert_analysis_timeout() == 0.0

    def test_negative_disables(self, monkeypatch):
        monkeypatch.setenv("EXPERT_ANALYSIS_TIMEOUT", "-1")
        assert _get_expert_analysis_timeout() == 0.0

    def test_bad_input_falls_back(self, monkeypatch):
        monkeypatch.setenv("EXPERT_ANALYSIS_TIMEOUT", "not-a-number")
        assert _get_expert_analysis_timeout() == _DEFAULT_EXPERT_ANALYSIS_TIMEOUT


class TestExpertAnalysisTimeoutPath:
    """Behavioral test: wait_for triggers and returns analysis_timeout dict."""

    @pytest.mark.asyncio
    async def test_call_expert_analysis_returns_timeout_dict_on_hang(self, monkeypatch):
        """A provider call that outlives EXPERT_ANALYSIS_TIMEOUT must NOT hang the
        workflow; it must return a dict with status='analysis_timeout'."""

        # Tight timeout so the test stays fast.
        monkeypatch.setenv("EXPERT_ANALYSIS_TIMEOUT", "0.1")

        tool = ThinkDeepTool()
        # Minimal state required by _call_expert_analysis. Most workflow methods
        # are bypassed via attribute mocking — only the provider hang matters.
        tool.consolidated_findings = ConsolidatedFindings()

        # Stub model context so _call_expert_analysis skips early validation.
        fake_provider = MagicMock()

        def _hanging_generate_content(*_args, **_kwargs):
            # asyncio.to_thread hands this to a worker thread; sleep there to
            # simulate a wire-level hang while the asyncio loop times out.
            import time as _time

            _time.sleep(2.0)
            return MagicMock(content='{"never": true}')

        fake_provider.generate_content = _hanging_generate_content

        fake_context = MagicMock()
        fake_context.provider = fake_provider
        fake_context.capabilities = None
        tool._model_context = fake_context
        tool._current_model_name = "stub-model"

        request = MagicMock()
        request.use_assistant_model = True
        request.thinking_mode = "low"
        request.temperature = 0.3

        with (
            patch.object(tool, "prepare_expert_analysis_context", return_value="dummy expert context"),
            patch.object(tool, "should_include_files_in_expert_prompt", return_value=False),
            patch.object(tool, "get_system_prompt", return_value="sys"),
            patch.object(tool, "_augment_system_prompt_with_capabilities", side_effect=lambda s, _c: s),
            patch.object(tool, "get_language_instruction", return_value=""),
            patch.object(tool, "should_embed_system_prompt", return_value=False),
            patch.object(tool, "get_validated_temperature", return_value=(0.3, [])),
            patch.object(tool, "get_request_thinking_mode", return_value="low"),
        ):
            # Per-test asyncio.wait_for upper bound — if the guard fails, the
            # test itself will time out and fail loudly rather than hang the
            # whole suite.
            result = await asyncio.wait_for(tool._call_expert_analysis({}, request), timeout=10.0)

        assert isinstance(result, dict), result
        assert result.get("status") == "analysis_timeout", result
        assert "deadline" in result.get("error", "").lower()
        assert result.get("model_used") == "stub-model"

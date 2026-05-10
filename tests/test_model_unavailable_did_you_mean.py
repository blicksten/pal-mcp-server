"""Tests for the fuzzy 'Did you mean' suggestion in the model-unavailable error.

When a tool requests an unknown model, _build_model_unavailable_message should
surface up to three close matches from the registry so the user (or CLI agent)
can fix the request without grepping listmodels.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.chat import ChatTool


class TestModelUnavailableDidYouMean:
    """Verify suggestion strings are added when close matches exist."""

    @pytest.fixture
    def tool(self):
        return ChatTool()

    def _mock_registry_models(self, tool, available: list[str]):
        """Patch _get_available_models so the message generator sees a fixed roster."""
        return patch.object(tool, "_get_available_models", return_value=available)

    def _mock_format_list(self, tool):
        return patch.object(tool, "_format_available_models_list", return_value="(formatted)")

    def _mock_registry_suggested(self):
        from providers.registry import ModelProviderRegistry

        return patch.object(ModelProviderRegistry, "get_preferred_fallback_model", return_value="gpt-5.1-codex")

    def test_typo_suggests_close_match(self, tool):
        """'gpt5pro' (no dash) should yield 'gpt5-pro' as a near match."""
        with (
            self._mock_registry_models(tool, ["gpt-5.2-pro", "gpt5-pro", "gemini-2.5-flash", "gpt-5.1-codex"]),
            self._mock_format_list(tool),
            self._mock_registry_suggested(),
        ):
            msg = tool._build_model_unavailable_message("gpt5pro")
        assert "Did you mean:" in msg
        assert "'gpt5-pro'" in msg

    def test_completely_unknown_no_suggestion(self, tool):
        """Garbage input like 'totally-fake-model-xyz' should yield no suggestion."""
        with (
            self._mock_registry_models(tool, ["gpt-5.2-pro", "gemini-2.5-flash"]),
            self._mock_format_list(tool),
            self._mock_registry_suggested(),
        ):
            msg = tool._build_model_unavailable_message("totally-fake-model-xyz")
        assert "Did you mean:" not in msg
        # Original error structure preserved.
        assert "is not available" in msg
        assert "totally-fake-model-xyz" in msg

    def test_case_insensitive_match(self, tool):
        """Casing differences must not block suggestions."""
        with (
            self._mock_registry_models(tool, ["gemini-2.5-flash"]),
            self._mock_format_list(tool),
            self._mock_registry_suggested(),
        ):
            msg = tool._build_model_unavailable_message("Gemini-2.5-FLASH")
        # The matcher operates on lowercased forms but preserves original casing
        # when reporting back to the user.
        assert "Did you mean:" in msg
        assert "'gemini-2.5-flash'" in msg

    def test_empty_registry_no_crash(self, tool):
        """An empty registry (or registry that raises) must not break the message."""
        broken = MagicMock(side_effect=RuntimeError("registry exploded"))
        with (
            patch.object(tool, "_get_available_models", broken),
            self._mock_format_list(tool),
            self._mock_registry_suggested(),
        ):
            msg = tool._build_model_unavailable_message("anything")
        # No suggestion, but the message must still render the rest.
        assert "Did you mean:" not in msg
        assert "is not available" in msg
        assert "anything" in msg

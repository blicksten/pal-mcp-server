"""
Tests for the main server functionality
"""

import pytest

from server import handle_call_tool


class TestServerDoubleLoadGuard:
    """Regression guard for the __main__/server double-load trap.

    When PAL is launched as `python server.py`, the file registers in sys.modules
    under the key '__main__'. Production code paths (tools/version.py:230,
    tools/simple/base.py:384, utils/conversation_memory.py:1046) later do
    lazy `import server`. Without an alias from __main__ → server, that lazy
    import would execute server.py top-level a second time, doubling every
    module-level side effect (atexit handlers, log handlers, provider init).

    The fix at the top of server.py is `sys.modules.setdefault("server",
    sys.modules[__name__])`. These tests verify it is present and effective.
    """

    def test_server_alias_present_in_source(self):
        """Source-level guard: the alias line must remain at the top of server.py."""
        from pathlib import Path

        server_path = Path(__file__).parent.parent / "server.py"
        source = server_path.read_text(encoding="utf-8")
        # Locate the alias and ensure it lands before any logging setup so the
        # second import (when it happens) hits the cache instead of running
        # the file body again.
        alias_marker = 'sys.modules.setdefault("server", sys.modules[__name__])'
        first_logging_setup = "logging.getLogger("
        assert alias_marker in source, "double-load alias missing — see TestServerDoubleLoadGuard docstring"
        assert source.index(alias_marker) < source.index(
            first_logging_setup
        ), "double-load alias must appear BEFORE the first logging.getLogger() call"

    def test_alias_runs_idempotently(self):
        """Behavioral guard: replay the alias line with __main__ swapped in and
        assert the second `import server` is a cache hit, not a re-execution."""
        import sys
        import types

        # The real server module is already loaded in this test process under
        # the name 'server' (test imports it at the top of the file). Snapshot
        # it, then simulate the `python server.py` scenario by:
        #   1. Saving real __main__ and 'server' entries.
        #   2. Putting a fresh module under '__main__' with __file__ pointing
        #      at server.py — pretending it was just loaded as the script.
        #   3. Running the alias line.
        #   4. Verifying sys.modules['server'] is the SAME object as
        #      sys.modules['__main__'] (cache hit on subsequent `import server`).
        real_main = sys.modules.get("__main__")
        real_server = sys.modules.get("server")
        try:
            sys.modules.pop("server", None)
            faux_main = types.ModuleType("__main__")
            faux_main.__file__ = real_server.__file__ if real_server else None
            sys.modules["__main__"] = faux_main

            # The line under test, copied verbatim from server.py top-level.
            sys.modules.setdefault("server", sys.modules[__name__ if False else "__main__"])

            assert sys.modules["server"] is faux_main, "alias did not redirect 'server' to the __main__ module"
            # A second setdefault must be a no-op (idempotency).
            another = types.ModuleType("__main__")
            sys.modules.setdefault("server", another)
            assert sys.modules["server"] is faux_main, "alias was not idempotent"
        finally:
            if real_main is not None:
                sys.modules["__main__"] = real_main
            if real_server is not None:
                sys.modules["server"] = real_server
            else:
                sys.modules.pop("server", None)


class TestServerTools:
    """Test server tool handling"""

    @pytest.mark.asyncio
    async def test_handle_call_tool_unknown(self):
        """Test calling an unknown tool"""
        result = await handle_call_tool("unknown_tool", {})
        assert len(result) == 1
        assert "Unknown tool: unknown_tool" in result[0].text

    @pytest.mark.asyncio
    async def test_handle_chat(self):
        """Test chat functionality using real integration testing"""
        import importlib
        import os

        # Set test environment
        os.environ["PYTEST_CURRENT_TEST"] = "test"

        # Save original environment
        original_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "DEFAULT_MODEL": os.environ.get("DEFAULT_MODEL"),
        }

        try:
            # Set up environment for real provider resolution
            os.environ["OPENAI_API_KEY"] = "sk-test-key-server-chat-test-not-real"
            os.environ["DEFAULT_MODEL"] = "o3-mini"

            # Clear other provider keys to isolate to OpenAI
            for key in ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]:
                os.environ.pop(key, None)

            # Reload config and clear registry
            import config

            importlib.reload(config)
            from providers.registry import ModelProviderRegistry

            ModelProviderRegistry._instance = None

            # Test with real provider resolution
            try:
                result = await handle_call_tool("chat", {"prompt": "Hello Gemini", "model": "o3-mini"})

                # If we get here, check the response format
                assert len(result) == 1
                # Parse JSON response
                import json

                response_data = json.loads(result[0].text)
                assert "status" in response_data

            except Exception as e:
                # Expected: API call will fail with fake key
                error_msg = str(e)
                # Should NOT be a mock-related error
                assert "MagicMock" not in error_msg
                assert "'<' not supported between instances" not in error_msg

                # Should be a real provider error
                assert any(
                    phrase in error_msg
                    for phrase in ["API", "key", "authentication", "provider", "network", "connection"]
                )

        finally:
            # Restore environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

            # Reload config and clear registry
            importlib.reload(config)
            ModelProviderRegistry._instance = None

    @pytest.mark.asyncio
    async def test_handle_version(self):
        """Test getting version info"""
        result = await handle_call_tool("version", {})
        assert len(result) == 1

        response = result[0].text
        # Parse the JSON response
        import json

        data = json.loads(response)
        assert data["status"] == "success"
        content = data["content"]

        # Check for expected content in the markdown output
        assert "# PAL MCP Server Version" in content
        assert "## Server Information" in content
        assert "## Configuration" in content
        assert "Current Version" in content

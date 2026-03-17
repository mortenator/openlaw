"""Tests for agent_loop.py — stop-reason branches, tool dispatch, and max-turns fallback."""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Stub out app.config.settings before importing any app module to avoid
# ValidationError for missing required env vars in the test environment.
_mock_settings = MagicMock()
_mock_settings.anthropic_model = "claude-3-5-sonnet-20241022"

import types
_config_mod = types.ModuleType("app.config")
_config_mod.settings = _mock_settings
sys.modules.setdefault("app.config", _config_mod)


def _make_text_block(text: str):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _make_tool_use_block(name: str, tool_id: str, input_data: dict):
    b = MagicMock()
    b.type = "tool_use"
    b.name = name
    b.id = tool_id
    b.input = input_data
    return b


def _make_response(stop_reason: str, content: list):
    r = MagicMock()
    r.stop_reason = stop_reason
    r.content = content
    return r


@pytest.mark.asyncio
async def test_end_turn_on_first_response():
    """Single end_turn response — no tools called, returns text."""
    from app.services.agent_loop import run_agent_loop

    final_block = _make_text_block("Here is your answer.")
    response = _make_response("end_turn", [final_block])

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.agent_loop.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await run_agent_loop(
            user_message="Who are my top contacts?",
            user_id="user-1",
            supabase_admin=MagicMock(),
            brave_api_key="key",
            anthropic_api_key="key",
        )

    assert result["response"] == "Here is your answer."
    assert result["tools_used"] == []
    assert result["turns"] == 1


@pytest.mark.asyncio
async def test_tool_use_then_end_turn():
    """Tool call followed by end_turn — one tool used, returns synthesized text."""
    from app.services.agent_loop import run_agent_loop

    tool_block = _make_tool_use_block("get_contacts", "tool-abc", {"max_health_score": 40})
    tool_response = _make_response("tool_use", [tool_block])

    final_block = _make_text_block("Your top stale contacts are Alice and Bob.")
    final_response = _make_response("end_turn", [final_block])

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_tool_result = [{"name": "Alice", "health_score": 10}, {"name": "Bob", "health_score": 20}]

    with patch("app.services.agent_loop.anthropic.AsyncAnthropic", return_value=mock_client), \
         patch("app.services.agent_loop.execute_tool", return_value=mock_tool_result) as mock_exec:
        result = await run_agent_loop(
            user_message="Who should I reach out to?",
            user_id="user-1",
            supabase_admin=MagicMock(),
            brave_api_key="key",
            anthropic_api_key="key",
        )

    assert result["tools_used"] == ["get_contacts"]
    assert result["turns"] == 2
    assert "Alice" in result["response"]
    mock_exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_max_turns_exhaustion():
    """Loop hits _MAX_TURNS — returns fallback text from last response."""
    from app.services.agent_loop import run_agent_loop, _MAX_TURNS

    tool_block = _make_tool_use_block("web_search", "tid-1", {"query": "test"})
    tool_response = _make_response("tool_use", [tool_block])

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=tool_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.agent_loop.anthropic.AsyncAnthropic", return_value=mock_client), \
         patch("app.services.agent_loop.execute_tool", return_value={"results": []}):
        result = await run_agent_loop(
            user_message="Keep searching forever",
            user_id="user-1",
            supabase_admin=MagicMock(),
            brave_api_key="key",
            anthropic_api_key="key",
        )

    assert result["turns"] == _MAX_TURNS
    assert "limit" in result["response"].lower() or result["response"] != ""


@pytest.mark.asyncio
async def test_max_tokens_stop_reason():
    """max_tokens stop_reason returns partial text, does not crash."""
    from app.services.agent_loop import run_agent_loop

    partial_block = _make_text_block("Here is a very long answer that got cut")
    truncated_response = _make_response("max_tokens", [partial_block])

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=truncated_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.agent_loop.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await run_agent_loop(
            user_message="Tell me everything",
            user_id="user-1",
            supabase_admin=MagicMock(),
            brave_api_key="key",
            anthropic_api_key="key",
        )

    assert result["turns"] == 1
    assert "cut" in result["response"] or "long" in result["response"]

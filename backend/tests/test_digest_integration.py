"""Integration tests for compile_and_send_weekly_digest using mocked dependencies."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_supabase(user=None, suggestions=None):
    """Build a minimal mock of the Supabase admin client."""
    sb = MagicMock()

    def _chain_result(data):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.limit.return_value = chain
        chain.update.return_value = chain
        chain.insert.return_value = chain
        chain.maybe_single.return_value = chain
        chain.execute.return_value = MagicMock(data=data)
        return chain

    def table_factory(name):
        if name == "users":
            return _chain_result(user)
        if name == "outreach_suggestions":
            q = _chain_result(suggestions or [])
            # update chain
            q.update.return_value = _chain_result([])
            return q
        if name == "deliveries":
            return _chain_result([{"id": "delivery-uuid-1"}])
        return _chain_result([])

    sb.table.side_effect = table_factory
    return sb


@pytest.mark.asyncio
async def test_happy_path_sends_email():
    """Happy path: user with pending suggestions → email sent, delivery logged."""
    from app.services.digest import compile_and_send_weekly_digest

    user = {"name": "Brian", "email": "brian@example.com", "comms_channel": "email"}
    suggestions = [
        {
            "id": "sugg-1",
            "body": "Hi Alice",
            "trigger_summary": "90 days — BigCorp raised $1B",
            "contacts": {"name": "Alice", "role": "Partner", "health_score": 10},
            "signals": {"headline": "BigCorp raises $1B", "created_at": "2026-03-01T00:00:00Z"},
        }
    ]
    sb = _make_supabase(user=user, suggestions=suggestions)

    with patch("app.services.digest.httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http_cls.return_value = mock_http

        result = await compile_and_send_weekly_digest(
            user_id="user-uuid-1",
            supabase_admin=sb,
            resend_api_key="re_test_key",
            from_address="OpenLaw <briefs@openlaw.ai>",
        )

    assert result["sent"] is True
    assert result["suggestions_included"] == 1


@pytest.mark.asyncio
async def test_no_resend_key_returns_early():
    from app.services.digest import compile_and_send_weekly_digest
    result = await compile_and_send_weekly_digest(
        user_id="x", supabase_admin=MagicMock(),
        resend_api_key=None, from_address="from@test.com"
    )
    assert result == {"sent": False, "reason": "resend_api_key_not_configured"}


@pytest.mark.asyncio
async def test_no_from_address_returns_early():
    from app.services.digest import compile_and_send_weekly_digest
    result = await compile_and_send_weekly_digest(
        user_id="x", supabase_admin=MagicMock(),
        resend_api_key="key", from_address=None
    )
    assert result == {"sent": False, "reason": "resend_from_address_not_configured"}


@pytest.mark.asyncio
async def test_unsupported_comms_channel_skips():
    from app.services.digest import compile_and_send_weekly_digest
    user = {"name": "Brian", "email": "b@b.com", "comms_channel": "slack"}
    sb = _make_supabase(user=user)
    result = await compile_and_send_weekly_digest(
        user_id="x", supabase_admin=sb,
        resend_api_key="key", from_address="from@test.com"
    )
    assert result["sent"] is False
    assert "unsupported_channel" in result["reason"]


@pytest.mark.asyncio
async def test_no_pending_suggestions_returns_early():
    from app.services.digest import compile_and_send_weekly_digest
    user = {"name": "Brian", "email": "b@b.com", "comms_channel": "email"}
    sb = _make_supabase(user=user, suggestions=[])
    result = await compile_and_send_weekly_digest(
        user_id="x", supabase_admin=sb,
        resend_api_key="key", from_address="from@test.com"
    )
    assert result == {"sent": False, "reason": "no_pending_suggestions"}

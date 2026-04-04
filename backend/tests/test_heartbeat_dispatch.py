"""Tests for the /internal/heartbeat endpoint (Phase 4 migration)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_INTERNAL_KEY = "stub-paperclip-internal-key-at-least-32-chars!"
AGENT_ID = "00000000-1111-2222-3333-444444444444"
USER_ID = "user-abc-123"


def _supabase_mock_with_user(user_id: str = USER_ID):
    """Return a supabase mock that resolves agent_id → user_id."""
    mock = MagicMock()
    (
        mock.table.return_value
        .select.return_value
        .eq.return_value
        .single.return_value
        .execute.return_value
    ).data = {"id": user_id}
    return mock


def _get_client(supabase_mock):
    """Build a TestClient with patched supabase."""
    with patch("app.routers.internal.supabase", supabase_mock):
        from app.main import app
        return TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests for the job type mapping
# ---------------------------------------------------------------------------

def test_heartbeat_to_runner_mapping():
    from app.routers.internal import _HEARTBEAT_TO_RUNNER

    assert _HEARTBEAT_TO_RUNNER["signal_scan"] == "market_brief"
    assert _HEARTBEAT_TO_RUNNER["contact_review"] == "relationship_scan"
    assert _HEARTBEAT_TO_RUNNER["daily_briefing"] == "weekly_digest"
    assert len(_HEARTBEAT_TO_RUNNER) == 3


# ---------------------------------------------------------------------------
# Dispatch function tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_job_calls_run_job():
    """_dispatch_job should call run_job with the mapped job type."""
    mock_run_job = AsyncMock(return_value={"job_type": "market_brief", "user_id": USER_ID, "result": {}})

    with (
        patch("app.routers.internal.supabase") as mock_sb,
        patch("app.routers.internal.settings") as mock_settings,
        patch("app.services.agent_runner.run_job", mock_run_job),
    ):
        from app.routers.internal import _dispatch_job
        await _dispatch_job(job_type="signal_scan", user_id=USER_ID, payload={})

    mock_run_job.assert_awaited_once_with(
        job_type="market_brief",
        user_id=USER_ID,
        supabase_admin=mock_sb,
        settings=mock_settings,
    )


@pytest.mark.asyncio
async def test_dispatch_job_contact_review():
    mock_run_job = AsyncMock(return_value={"job_type": "relationship_scan", "user_id": USER_ID, "result": {}})

    with (
        patch("app.routers.internal.supabase"),
        patch("app.routers.internal.settings"),
        patch("app.services.agent_runner.run_job", mock_run_job),
    ):
        from app.routers.internal import _dispatch_job
        await _dispatch_job(job_type="contact_review", user_id=USER_ID, payload={})

    mock_run_job.assert_awaited_once()
    call_kwargs = mock_run_job.await_args.kwargs
    assert call_kwargs["job_type"] == "relationship_scan"


@pytest.mark.asyncio
async def test_dispatch_job_unknown_type_logs_error():
    """Unknown heartbeat job type should log an error and not call run_job."""
    mock_run_job = AsyncMock()

    with (
        patch("app.routers.internal.supabase"),
        patch("app.routers.internal.settings"),
        patch("app.services.agent_runner.run_job", mock_run_job),
    ):
        from app.routers.internal import _dispatch_job
        await _dispatch_job(job_type="nonexistent_type", user_id=USER_ID, payload={})

    mock_run_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_job_run_job_exception_is_caught():
    """Exceptions from run_job should be caught and logged, not propagated."""
    mock_run_job = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch("app.routers.internal.supabase"),
        patch("app.routers.internal.settings"),
        patch("app.services.agent_runner.run_job", mock_run_job),
    ):
        from app.routers.internal import _dispatch_job
        # Should not raise
        await _dispatch_job(job_type="signal_scan", user_id=USER_ID, payload={})


# ---------------------------------------------------------------------------
# Paperclip provisioning: heartbeat enabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_provision_user_enables_heartbeat():
    """New provisioning should set heartbeat.enabled=True."""
    from unittest.mock import AsyncMock as AM

    supabase_mock = MagicMock()
    (
        supabase_mock.table.return_value
        .select.return_value
        .eq.return_value
        .single.return_value
        .execute.return_value
    ).data = {"paperclip_company_id": None, "paperclip_agent_id": None}
    (
        supabase_mock.table.return_value
        .update.return_value
        .eq.return_value
        .execute.return_value
    ).data = [{}]

    http_mock = AM()
    company_resp = MagicMock()
    company_resp.json.return_value = {"id": "co-new"}
    company_resp.raise_for_status.return_value = None
    agent_resp = MagicMock()
    agent_resp.json.return_value = {"id": "ag-new"}
    agent_resp.raise_for_status.return_value = None
    http_mock.post.side_effect = [company_resp, agent_resp]

    with (
        patch("app.services.paperclip.supabase", supabase_mock),
        patch("app.services.paperclip.httpx.AsyncClient") as MockClient,
    ):
        MockClient.return_value.__aenter__ = AM(return_value=http_mock)
        MockClient.return_value.__aexit__ = AM(return_value=False)

        from app.services import paperclip
        result = await paperclip.provision_user(
            user_id="user-hb",
            user_name="Heartbeat User",
            firm="TestFirm",
        )

    assert result["created"] is True

    # Verify the agent creation call has heartbeat enabled
    agent_call = http_mock.post.call_args_list[1]
    runtime_config = agent_call.kwargs.get("json", agent_call[1].get("json", {}))
    heartbeat_cfg = runtime_config.get("runtimeConfig", {}).get("heartbeat", {})
    assert heartbeat_cfg["enabled"] is True
    assert heartbeat_cfg["intervalSec"] > 0

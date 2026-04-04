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


def _settings_mock():
    """Return a settings mock with a valid internal key."""
    mock = MagicMock()
    mock.paperclip_internal_key = VALID_INTERNAL_KEY
    return mock


def _make_app():
    """Build a minimal FastAPI app with just the internal router."""
    from fastapi import FastAPI
    from app.routers.internal import router

    app = FastAPI()
    app.include_router(router)
    return app


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
        patch("app.routers.internal.run_job", mock_run_job),
    ):
        from app.routers.internal import _dispatch_job
        result = await _dispatch_job(job_type="signal_scan", user_id=USER_ID, payload={}, cron_id="cron-123")

    assert result is True
    mock_run_job.assert_awaited_once_with(
        job_type="market_brief",
        user_id=USER_ID,
        supabase_admin=mock_sb,
        settings=mock_settings,
        cron_id="cron-123",
    )


@pytest.mark.asyncio
async def test_dispatch_job_contact_review():
    mock_run_job = AsyncMock(return_value={"job_type": "relationship_scan", "user_id": USER_ID, "result": {}})

    with (
        patch("app.routers.internal.supabase"),
        patch("app.routers.internal.settings"),
        patch("app.routers.internal.run_job", mock_run_job),
    ):
        from app.routers.internal import _dispatch_job
        result = await _dispatch_job(job_type="contact_review", user_id=USER_ID, payload={})

    assert result is True
    mock_run_job.assert_awaited_once()
    call_kwargs = mock_run_job.await_args.kwargs
    assert call_kwargs["job_type"] == "relationship_scan"
    assert call_kwargs["cron_id"] is None


@pytest.mark.asyncio
async def test_dispatch_job_unknown_type_logs_error():
    """Unknown heartbeat job type should log an error and not call run_job."""
    mock_run_job = AsyncMock()

    with (
        patch("app.routers.internal.supabase"),
        patch("app.routers.internal.settings"),
        patch("app.routers.internal.run_job", mock_run_job),
    ):
        from app.routers.internal import _dispatch_job
        result = await _dispatch_job(job_type="nonexistent_type", user_id=USER_ID, payload={})

    assert result is False
    mock_run_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_job_run_job_exception_is_caught():
    """Exceptions from run_job should be caught and logged, not propagated."""
    mock_run_job = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch("app.routers.internal.supabase"),
        patch("app.routers.internal.settings"),
        patch("app.routers.internal.run_job", mock_run_job),
    ):
        from app.routers.internal import _dispatch_job
        # Should not raise — returns False on failure
        result = await _dispatch_job(job_type="signal_scan", user_id=USER_ID, payload={})

    assert result is False


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


# ---------------------------------------------------------------------------
# HTTP-layer endpoint tests
# ---------------------------------------------------------------------------

def test_heartbeat_invalid_key_returns_401():
    with (
        patch("app.routers.internal.supabase", _supabase_mock_with_user()),
        patch("app.routers.internal.settings", _settings_mock()),
    ):
        client = TestClient(_make_app())
        resp = client.post(
            "/internal/heartbeat",
            json={"agent_id": AGENT_ID, "context": {"job_type": "signal_scan"}},
            headers={"X-Internal-Key": "wrong-key"},
        )
    assert resp.status_code == 401


def test_heartbeat_unsupported_job_type_returns_422():
    with (
        patch("app.routers.internal.supabase", _supabase_mock_with_user()),
        patch("app.routers.internal.settings", _settings_mock()),
    ):
        client = TestClient(_make_app())
        resp = client.post(
            "/internal/heartbeat",
            json={"agent_id": AGENT_ID, "context": {"job_type": "unknown_type"}},
            headers={"X-Internal-Key": VALID_INTERNAL_KEY},
        )
    assert resp.status_code == 422


def test_heartbeat_user_not_found_returns_404():
    mock = MagicMock()
    from postgrest.exceptions import APIError
    exc = APIError({"code": "PGRST116", "message": "no rows"})
    (
        mock.table.return_value
        .select.return_value
        .eq.return_value
        .single.return_value
        .execute.side_effect
    ) = exc
    with (
        patch("app.routers.internal.supabase", mock),
        patch("app.routers.internal.settings", _settings_mock()),
    ):
        client = TestClient(_make_app())
        resp = client.post(
            "/internal/heartbeat",
            json={"agent_id": AGENT_ID, "context": {"job_type": "signal_scan"}},
            headers={"X-Internal-Key": VALID_INTERNAL_KEY},
        )
    assert resp.status_code == 404


def test_heartbeat_happy_path_returns_200():
    with (
        patch("app.routers.internal.supabase", _supabase_mock_with_user()),
        patch("app.routers.internal.settings", _settings_mock()),
        patch("app.routers.internal._dispatch_job", new_callable=AsyncMock, return_value=True),
    ):
        client = TestClient(_make_app())
        resp = client.post(
            "/internal/heartbeat",
            json={"agent_id": AGENT_ID, "context": {"job_type": "signal_scan"}},
            headers={"X-Internal-Key": VALID_INTERNAL_KEY},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["job_type"] == "signal_scan"
    assert data["user_id"] == USER_ID


def test_heartbeat_dispatch_failure_returns_503():
    with (
        patch("app.routers.internal.supabase", _supabase_mock_with_user()),
        patch("app.routers.internal.settings", _settings_mock()),
        patch("app.routers.internal._dispatch_job", new_callable=AsyncMock, return_value=False),
    ):
        client = TestClient(_make_app())
        resp = client.post(
            "/internal/heartbeat",
            json={"agent_id": AGENT_ID, "context": {"job_type": "signal_scan"}},
            headers={"X-Internal-Key": VALID_INTERNAL_KEY},
        )
    assert resp.status_code == 503

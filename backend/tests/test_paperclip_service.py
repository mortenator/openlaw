"""Tests for app/services/paperclip.py — Paperclip provisioning helpers."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_supabase_mock(existing_company_id=None, existing_agent_id=None):
    """Return a mock supabase client seeded with optional existing IDs."""
    mock = MagicMock()
    # .table().select().eq().single().execute() chain
    row_data = {
        "paperclip_company_id": existing_company_id,
        "paperclip_agent_id": existing_agent_id,
    }
    (
        mock.table.return_value
        .select.return_value
        .eq.return_value
        .single.return_value
        .execute.return_value
    ).data = row_data

    # .table().update().eq().execute() chain — returns non-None data to signal success
    (
        mock.table.return_value
        .update.return_value
        .eq.return_value
        .execute.return_value
    ).data = [row_data]

    return mock


def _make_http_client_mock(company_id="c-123", agent_id="a-456"):
    """Return an async mock httpx client."""
    mock = AsyncMock()
    mock.post.side_effect = [
        _http_resp({"id": company_id}),
        _http_resp({"id": agent_id}),
    ]
    return mock


def _http_resp(json_body: dict):
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provision_user_fresh():
    """New user: creates company + agent, patches both IDs to Supabase."""
    supabase_mock = _make_supabase_mock()
    http_mock = _make_http_client_mock(company_id="co-1", agent_id="ag-1")

    with (
        patch("app.services.paperclip.supabase", supabase_mock),
        patch("app.services.paperclip.httpx.AsyncClient") as MockClient,
    ):
        MockClient.return_value.__aenter__ = AsyncMock(return_value=http_mock)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services import paperclip
        result = await paperclip.provision_user(
            user_id="user-1",
            user_name="Jane Doe",
            firm="Acme Law",
        )

    assert result["paperclip_company_id"] == "co-1"
    assert result["paperclip_agent_id"] == "ag-1"
    assert result["created"] is True

    # Verify two POST calls: /api/companies and /api/companies/co-1/agents
    assert http_mock.post.call_count == 2
    http_mock.post.assert_any_call("/api/companies", json={"name": "Jane Doe (Acme Law)"})
    http_mock.post.assert_any_call(
        "/api/companies/co-1/agents",
        json={
            "name": "OpenLaw Agent",
            "adapterType": "process",
            "runtimeConfig": {
                "heartbeat": {
                    "enabled": False,
                    "intervalSec": 0,
                    "sessionCompaction": {
                        "maxSessionRuns": 200,
                        "maxSessionAgeHours": 72,
                    },
                }
            },
            "budgetMonthlyCents": 5000,
        },
    )

    # Supabase updates were called for both IDs
    update_calls = supabase_mock.table.return_value.update.call_args_list
    update_payloads = [c.args[0] for c in update_calls]
    assert {"paperclip_company_id": "co-1"} in update_payloads
    assert {"paperclip_agent_id": "ag-1"} in update_payloads


@pytest.mark.asyncio
async def test_build_openlaw_agent_runtime_config_includes_session_compaction_defaults():
    from app.services.paperclip import build_openlaw_agent_runtime_config

    assert build_openlaw_agent_runtime_config() == {
        "heartbeat": {
            "enabled": False,
            "intervalSec": 0,
            "sessionCompaction": {
                "maxSessionRuns": 200,
                "maxSessionAgeHours": 72,
            },
        }
    }


@pytest.mark.asyncio
async def test_provision_user_already_provisioned():
    """User already has both IDs — no Paperclip API calls are made."""
    supabase_mock = _make_supabase_mock(
        existing_company_id="co-existing",
        existing_agent_id="ag-existing",
    )

    with (
        patch("app.services.paperclip.supabase", supabase_mock),
        patch("app.services.paperclip.httpx.AsyncClient") as MockClient,
    ):
        # Should NOT be called at all
        MockClient.return_value.__aenter__ = AsyncMock()
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services import paperclip
        result = await paperclip.provision_user(
            user_id="user-2",
            user_name="Bob Smith",
            firm=None,
        )

    assert result["paperclip_company_id"] == "co-existing"
    assert result["paperclip_agent_id"] == "ag-existing"
    assert result["created"] is False

    # No HTTP client context was entered (no API calls)
    MockClient.return_value.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_provision_user_half_bootstrapped():
    """User has company_id but missing agent_id — only agent is created."""
    supabase_mock = _make_supabase_mock(existing_company_id="co-half", existing_agent_id=None)
    http_mock = AsyncMock()
    http_mock.post.return_value = _http_resp({"id": "ag-new"})

    with (
        patch("app.services.paperclip.supabase", supabase_mock),
        patch("app.services.paperclip.httpx.AsyncClient") as MockClient,
    ):
        MockClient.return_value.__aenter__ = AsyncMock(return_value=http_mock)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services import paperclip
        result = await paperclip.provision_user(
            user_id="user-3",
            user_name="Alice",
            firm="BigLaw",
        )

    assert result["paperclip_company_id"] == "co-half"
    assert result["paperclip_agent_id"] == "ag-new"
    assert result["created"] is True

    # Only one POST call — for the agent, not the company
    assert http_mock.post.call_count == 1
    http_mock.post.assert_called_once_with(
        "/api/companies/co-half/agents",
        json={
            "name": "OpenLaw Agent",
            "adapterType": "process",
            "runtimeConfig": {
                "heartbeat": {
                    "enabled": False,
                    "intervalSec": 0,
                    "sessionCompaction": {
                        "maxSessionRuns": 200,
                        "maxSessionAgeHours": 72,
                    },
                }
            },
            "budgetMonthlyCents": 5000,
        },
    )


@pytest.mark.asyncio
async def test_provision_user_no_firm_uses_independent_label():
    """When firm is None, company name should read 'Name (Independent)'."""
    supabase_mock = _make_supabase_mock()
    http_mock = _make_http_client_mock(company_id="co-ind", agent_id="ag-ind")

    with (
        patch("app.services.paperclip.supabase", supabase_mock),
        patch("app.services.paperclip.httpx.AsyncClient") as MockClient,
    ):
        MockClient.return_value.__aenter__ = AsyncMock(return_value=http_mock)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services import paperclip
        await paperclip.provision_user(user_id="user-4", user_name="Solo Solo", firm=None)

    http_mock.post.assert_any_call(
        "/api/companies", json={"name": "Solo Solo (Independent)"}
    )


@pytest.mark.asyncio
async def test_provision_user_http_error_propagates():
    """HTTP errors from Paperclip should propagate to the caller."""
    import httpx

    supabase_mock = _make_supabase_mock()
    http_mock = AsyncMock()
    err_response = MagicMock()
    err_response.status_code = 500
    err_response.request = MagicMock()
    http_mock.post.side_effect = httpx.HTTPStatusError(
        "Server Error", request=err_response.request, response=err_response
    )

    with (
        patch("app.services.paperclip.supabase", supabase_mock),
        patch("app.services.paperclip.httpx.AsyncClient") as MockClient,
    ):
        MockClient.return_value.__aenter__ = AsyncMock(return_value=http_mock)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.services import paperclip
        with pytest.raises(httpx.HTTPStatusError):
            await paperclip.provision_user(
                user_id="user-5",
                user_name="Error User",
                firm="Law Firm",
            )

"""Tests for market_scan: Brave API error handling, scan_market_for_user flow."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.market_scan import (
    BraveAPIError,
    fetch_signals,
    scan_market_for_user,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _mock_supabase(
    companies: list[dict] | None = None,
    existing_signals: list[dict] | None = None,
):
    """Build a chainable MagicMock that mimics supabase query builder."""
    sb = MagicMock()

    # companies query chain
    companies_chain = MagicMock()
    companies_chain.select.return_value = companies_chain
    companies_chain.eq.return_value = companies_chain
    companies_chain.execute.return_value = MagicMock(data=companies or [])

    # signals dedup query chain
    signals_chain = MagicMock()
    signals_chain.select.return_value = signals_chain
    signals_chain.eq.return_value = signals_chain
    signals_chain.limit.return_value = signals_chain
    signals_chain.execute.return_value = MagicMock(data=existing_signals or [])

    # signals insert chain
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{"id": "new-signal"}])

    def _table_router(name: str):
        if name == "tracked_firms":
            return companies_chain
        if name == "signals":
            # Return a mock that supports both .select() (dedup) and .insert()
            dual = MagicMock()
            dual.select.return_value = signals_chain
            dual.insert.return_value = insert_chain
            return dual
        return MagicMock()

    sb.table.side_effect = _table_router
    return sb


def _mock_response(status_code: int, json_data: dict | None = None, text: str = ""):
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ── fetch_signals tests ─────────────────────────────────────────────────


class TestFetchSignals:
    @pytest.mark.asyncio
    async def test_returns_results_on_success(self):
        """Successful Brave response returns web results."""
        fake_results = [{"title": "News A", "url": "https://example.com/a"}]
        resp = _mock_response(200, json_data={"web": {"results": fake_results}})

        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.market_scan.httpx.AsyncClient", return_value=mock_client):
            results = await fetch_signals("test query", count=5)

        assert results == fake_results

    @pytest.mark.asyncio
    async def test_raises_brave_api_error_on_401(self):
        """401 from Brave should raise BraveAPIError, not return empty list."""
        resp = _mock_response(401, text="Unauthorized: invalid subscription token")

        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.market_scan.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(BraveAPIError) as exc_info:
                await fetch_signals("test query")

        assert exc_info.value.status_code == 401
        assert "BRAVE_API_KEY" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_brave_api_error_on_403(self):
        """403 from Brave should raise BraveAPIError."""
        resp = _mock_response(403, text="Forbidden")

        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.market_scan.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(BraveAPIError) as exc_info:
                await fetch_signals("test query")

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_empty_on_api_error_in_body(self):
        """If Brave returns 200 but with error in body, return empty list."""
        resp = _mock_response(200, json_data={"error": "rate limit exceeded"})

        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.market_scan.httpx.AsyncClient", return_value=mock_client):
            results = await fetch_signals("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_web_results(self):
        """If Brave returns 200 with no web results, return empty list."""
        resp = _mock_response(200, json_data={"web": {"results": []}})

        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.market_scan.httpx.AsyncClient", return_value=mock_client):
            results = await fetch_signals("test query")

        assert results == []


# ── scan_market_for_user tests ──────────────────────────────────────────


class TestScanMarketForUser:
    @pytest.mark.asyncio
    async def test_brave_auth_error_propagates(self):
        """BraveAPIError must propagate up — not silently return 0 signals."""
        sb = _mock_supabase(
            companies=[{"id": "c1", "name": "Acme Corp"}],
        )

        with patch(
            "app.services.market_scan.fetch_signals",
            side_effect=BraveAPIError(401, "bad key"),
        ):
            with pytest.raises(BraveAPIError):
                await scan_market_for_user(
                    user_id="user-1",
                    supabase_admin=sb,
                    anthropic_api_key="sk-ant-test",
                )

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_watchlist_companies(self):
        """No companies on watchlist => 0 signals, no errors."""
        sb = _mock_supabase(companies=[])

        result = await scan_market_for_user(
            user_id="user-1",
            supabase_admin=sb,
            anthropic_api_key="sk-ant-test",
        )

        assert result["signals_inserted"] == 0
        assert result["companies_scanned"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_non_auth_fetch_error_continues_with_error_list(self):
        """Non-auth errors (e.g. timeout) should be caught and listed in errors."""
        sb = _mock_supabase(
            companies=[{"id": "c1", "name": "Acme Corp"}],
        )

        with patch(
            "app.services.market_scan.fetch_signals",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            result = await scan_market_for_user(
                user_id="user-1",
                supabase_admin=sb,
                anthropic_api_key="sk-ant-test",
            )

        assert result["signals_inserted"] == 0
        assert result["companies_scanned"] == 1
        assert len(result["errors"]) == 1
        assert "Acme Corp" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_result_includes_companies_scanned(self):
        """Result dict should report how many companies were scanned."""
        sb = _mock_supabase(
            companies=[
                {"id": "c1", "name": "Acme Corp"},
                {"id": "c2", "name": "Beta Inc"},
            ],
        )

        with patch(
            "app.services.market_scan.fetch_signals",
            return_value=[],
        ):
            result = await scan_market_for_user(
                user_id="user-1",
                supabase_admin=sb,
                anthropic_api_key="sk-ant-test",
            )

        assert result["companies_scanned"] == 2
        assert result["signals_inserted"] == 0

    @pytest.mark.asyncio
    async def test_raises_without_anthropic_key(self):
        """Missing anthropic_api_key should raise ValueError."""
        sb = _mock_supabase()

        with pytest.raises(ValueError, match="anthropic_api_key is required"):
            await scan_market_for_user(
                user_id="user-1",
                supabase_admin=sb,
                anthropic_api_key=None,
            )


# ── Config validation tests ─────────────────────────────────────────────


class TestBraveAPIKeyValidation:
    _BASE_ENV = {
        "SUPABASE_URL": "https://stub.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "stub",
        "RESEND_API_KEY": "stub",
        "ANTHROPIC_API_KEY": "stub",
        "CRON_SECRET": "stub",
        "PAPERCLIP_INTERNAL_KEY": "stub-paperclip-internal-key-at-least-32-chars!",
    }

    def _make_settings(self, brave_key: str):
        """Construct a fresh Settings instance with the given BRAVE_API_KEY."""
        import os
        import sys

        env = {**self._BASE_ENV, "BRAVE_API_KEY": brave_key}
        with patch.dict(os.environ, env, clear=False):
            # Force re-import so pydantic-settings picks up patched env
            mod = sys.modules.pop("app.config", None)
            try:
                import app.config as cfg
                return cfg.Settings()
            finally:
                # Restore original module to not break other tests
                if mod is not None:
                    sys.modules["app.config"] = mod

    def test_empty_brave_key_rejected(self):
        """Empty BRAVE_API_KEY should fail config validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            self._make_settings("")

        assert "BRAVE_API_KEY" in str(exc_info.value)

    def test_whitespace_brave_key_rejected(self):
        """Whitespace-only BRAVE_API_KEY should fail config validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._make_settings("   ")

    def test_valid_brave_key_accepted(self):
        """Non-empty BRAVE_API_KEY should pass validation."""
        s = self._make_settings("BSA-valid-key-123")
        assert s.brave_api_key == "BSA-valid-key-123"

"""Tests for the OpenLaw agentic tool definitions and executors."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.tools import TOOL_SCHEMAS, execute_tool


# ── Schema validation tests ──────────────────────────────────────────────


class TestToolSchemas:
    def test_all_schemas_have_required_fields(self):
        """Every tool schema must have name, description, and input_schema."""
        for schema in TOOL_SCHEMAS:
            assert "name" in schema, f"Missing 'name' in schema: {schema}"
            assert "description" in schema, f"Missing 'description' for {schema['name']}"
            assert "input_schema" in schema, f"Missing 'input_schema' for {schema['name']}"
            assert schema["input_schema"]["type"] == "object"

    def test_web_search_schema_requires_query(self):
        ws = next(s for s in TOOL_SCHEMAS if s["name"] == "web_search")
        assert "query" in ws["input_schema"]["properties"]
        assert "query" in ws["input_schema"]["required"]

    def test_create_cron_schema_requires_name_job_schedule(self):
        cc = next(s for s in TOOL_SCHEMAS if s["name"] == "create_cron")
        assert set(cc["input_schema"]["required"]) == {"name", "job_type", "schedule"}

    def test_save_company_schema_requires_name(self):
        sc = next(s for s in TOOL_SCHEMAS if s["name"] == "save_company")
        assert sc["input_schema"]["required"] == ["name"]

    def test_get_contacts_schema_has_no_required(self):
        gc = next(s for s in TOOL_SCHEMAS if s["name"] == "get_contacts")
        assert "required" not in gc["input_schema"]

    def test_get_signals_schema_has_no_required(self):
        gs = next(s for s in TOOL_SCHEMAS if s["name"] == "get_signals")
        assert "required" not in gs["input_schema"]

    def test_schema_names_are_unique(self):
        names = [s["name"] for s in TOOL_SCHEMAS]
        assert len(names) == len(set(names))

    def test_five_tools_defined(self):
        assert len(TOOL_SCHEMAS) == 5


# ── Executor tests ───────────────────────────────────────────────────────


def _mock_supabase():
    """Build a mock supabase client with chainable query builder.

    Returns the same table mock for repeated calls with the same table name,
    so tests can configure return values before the executor runs.
    """
    sb = MagicMock()
    tables: dict[str, MagicMock] = {}

    def _chain_table(table_name):
        if table_name not in tables:
            table = MagicMock()
            for method in ("select", "eq", "lte", "in_", "order", "limit", "insert", "upsert"):
                getattr(table, method).return_value = table
            tables[table_name] = table
        return tables[table_name]

    sb.table = MagicMock(side_effect=_chain_table)
    return sb


class TestCreateCronExecutor:
    @pytest.mark.asyncio
    async def test_inserts_correct_data(self):
        sb = _mock_supabase()
        cron_table = sb.table("user_crons")
        # First call = dedup check (no existing), second call = insert result
        cron_table.execute.side_effect = [
            MagicMock(data=[]),                      # dedup check: no existing
            MagicMock(data=[{"id": "cron-uuid-123"}]),  # insert result
        ]

        result = await execute_tool(
            tool_name="create_cron",
            tool_input={
                "name": "Weekly AI scan",
                "job_type": "market_brief",
                "schedule": "0 8 * * 5",
                "keywords": ["AI", "data center"],
            },
            user_id="user-1",
            supabase_admin=sb,
            brave_api_key="",
        )

        assert result["created"] is True
        assert result["cron_id"] == "cron-uuid-123"
        assert result["schedule"] == "0 8 * * 5"

        # Verify insert was called with correct row
        insert_call = cron_table.insert.call_args
        row = insert_call[0][0]
        assert row["user_id"] == "user-1"
        assert row["name"] == "Weekly AI scan"
        assert row["job_type"] == "market_brief"
        assert row["cron_expression"] == "0 8 * * 5"
        assert row["config"] == {"keywords": ["AI", "data center"]}
        assert row["is_active"] is True


class TestSaveCompanyExecutor:
    @pytest.mark.asyncio
    async def test_upserts_correctly(self):
        sb = _mock_supabase()
        companies_table = sb.table("companies")
        companies_table.execute.return_value = MagicMock(
            data=[{"id": "comp-uuid-456"}]
        )

        result = await execute_tool(
            tool_name="save_company",
            tool_input={
                "name": "Acme Corp",
                "industry": "Legal Tech",
                "reason": "Potential client",
            },
            user_id="user-2",
            supabase_admin=sb,
            brave_api_key="",
        )

        assert result["saved"] is True
        assert result["company_id"] == "comp-uuid-456"

        upsert_call = companies_table.upsert.call_args
        row = upsert_call[0][0]
        assert row["user_id"] == "user-2"
        assert row["name"] == "Acme Corp"
        assert row["industry"] == "Legal Tech"
        assert row["notes"] == "Potential client"
        assert row["is_watchlist"] is True
        assert row["tags"] == []

    @pytest.mark.asyncio
    async def test_upserts_minimal_fields(self):
        sb = _mock_supabase()
        companies_table = sb.table("companies")
        companies_table.execute.return_value = MagicMock(
            data=[{"id": "comp-uuid-789"}]
        )

        result = await execute_tool(
            tool_name="save_company",
            tool_input={"name": "Minimal Inc"},
            user_id="user-3",
            supabase_admin=sb,
            brave_api_key="",
        )

        assert result["saved"] is True
        upsert_call = companies_table.upsert.call_args
        row = upsert_call[0][0]
        assert "industry" not in row
        assert "notes" not in row


class TestGetContactsExecutor:
    @pytest.mark.asyncio
    async def test_returns_sorted_results(self):
        sb = _mock_supabase()
        contacts_table = sb.table("contacts")
        contacts_table.execute.return_value = MagicMock(
            data=[
                {
                    "name": "Alice",
                    "role": "Partner",
                    "health_score": 20,
                    "tier": 1,
                    "last_contacted_at": "2026-01-01",
                },
                {
                    "name": "Bob",
                    "role": "Associate",
                    "health_score": 45,
                    "tier": 2,
                    "last_contacted_at": "2025-12-15",
                },
            ]
        )

        result = await execute_tool(
            tool_name="get_contacts",
            tool_input={"max_health_score": 50, "limit": 5},
            user_id="user-1",
            supabase_admin=sb,
            brave_api_key="",
        )

        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["name"] == "Bob"

        # Verify order() was called with health_score ascending
        contacts_table.order.assert_called_once_with("health_score", desc=False)
        contacts_table.lte.assert_called_once_with("health_score", 50)

    @pytest.mark.asyncio
    async def test_filters_by_tier(self):
        sb = _mock_supabase()
        contacts_table = sb.table("contacts")
        contacts_table.execute.return_value = MagicMock(data=[])

        await execute_tool(
            tool_name="get_contacts",
            tool_input={"tier": 1},
            user_id="user-1",
            supabase_admin=sb,
            brave_api_key="",
        )

        contacts_table.eq.assert_any_call("tier", 1)


class TestWebSearchExecutor:
    @pytest.mark.asyncio
    async def test_returns_formatted_results(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "News 1", "url": "https://example.com/1", "description": "Snippet 1"},
                {"title": "News 2", "url": "https://example.com/2", "description": "Snippet 2"},
            ]
        }

        with patch("app.services.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await execute_tool(
                tool_name="web_search",
                tool_input={"query": "AI legal tech"},
                user_id="user-1",
                supabase_admin=MagicMock(),
                brave_api_key="test-key",
            )

        assert len(result) == 2
        assert result[0]["title"] == "News 1"
        assert result[0]["url"] == "https://example.com/1"
        assert result[0]["snippet"] == "Snippet 1"

    @pytest.mark.asyncio
    async def test_returns_error_on_failure(self):
        with patch("app.services.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_cls.return_value = mock_client

            result = await execute_tool(
                tool_name="web_search",
                tool_input={"query": "test"},
                user_id="user-1",
                supabase_admin=MagicMock(),
                brave_api_key="test-key",
            )

        assert "error" in result


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await execute_tool(
            tool_name="nonexistent",
            tool_input={},
            user_id="user-1",
            supabase_admin=MagicMock(),
            brave_api_key="",
        )
        assert result == {"error": "Unknown tool: nonexistent"}


class TestGetSignalsExecutor:
    @pytest.mark.asyncio
    async def test_returns_signals_for_user(self):
        sb = MagicMock()
        companies_chain = MagicMock()
        companies_chain.select.return_value = companies_chain
        companies_chain.eq.return_value = companies_chain
        companies_chain.execute.return_value = MagicMock(data=[
            {"id": "co-1", "name": "Acme Corp"}
        ])

        signals_chain = MagicMock()
        signals_chain.select.return_value = signals_chain
        signals_chain.eq.return_value = signals_chain
        signals_chain.in_.return_value = signals_chain
        signals_chain.order.return_value = signals_chain
        signals_chain.limit.return_value = signals_chain
        signals_chain.execute.return_value = MagicMock(data=[{
            "headline": "Acme raises $500M",
            "type": "investment",
            "company_id": "co-1",
            "source_url": "https://example.com",
            "created_at": "2026-03-01T00:00:00Z",
        }])

        def table_side_effect(name):
            if name == "companies":
                return companies_chain
            return signals_chain

        sb.table.side_effect = table_side_effect

        result = await execute_tool(
            tool_name="get_signals",
            tool_input={"limit": 5},
            user_id="user-1",
            supabase_admin=sb,
            brave_api_key="",
        )
        assert len(result) == 1
        assert result[0]["headline"] == "Acme raises $500M"
        assert result[0]["company_name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_empty_companies_returns_empty(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = MagicMock(data=[])
        sb.table.return_value = chain

        result = await execute_tool(
            tool_name="get_signals",
            tool_input={},
            user_id="user-1",
            supabase_admin=sb,
            brave_api_key="",
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_web_results_format(self):
        """Test the primary Brave web search response format (web.results)."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Web Result 1", "url": "https://example.com/w1", "description": "Web snippet"},
                ]
            }
        }

        with patch("app.services.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await execute_tool(
                tool_name="web_search",
                tool_input={"query": "Acme Corp funding"},
                user_id="user-1",
                supabase_admin=MagicMock(),
                brave_api_key="test-key",
            )

        assert len(result) == 1
        assert result[0]["title"] == "Web Result 1"

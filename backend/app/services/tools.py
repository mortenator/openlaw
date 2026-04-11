"""Tool definitions and executors for the OpenLaw agentic query engine."""

import logging
import re
from typing import Any

import httpx

# Cron expression: 5 fields, supports *, ranges, lists, steps (e.g. */5, 1-5/2)
_CRON_FIELD = r'(\*|[0-9,\-]+|\*/[0-9]+|[0-9]+/[0-9]+|[0-9]+-[0-9]+/[0-9]+)'
_CRON_PATTERN = re.compile(
    rf'^{_CRON_FIELD}\s+{_CRON_FIELD}\s+{_CRON_FIELD}\s+{_CRON_FIELD}\s+{_CRON_FIELD}$'
)

log = logging.getLogger(__name__)

_BRAVE_WEB_URL = "https://api.search.brave.com/res/v1/web/search"
_BRAVE_NEWS_URL = "https://api.search.brave.com/res/v1/news/search"

# ── Tool Schemas ──────────────────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for company information, market signals, news, "
            "or research. Returns up to 5 results with title, URL, and snippet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"},
                "freshness": {
                    "type": "string",
                    "enum": ["day", "week", "month", "year", "any"],
                    "description": "How recent results should be",
                    "default": "month",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_company",
        "description": "Save a company to the user's watchlist for ongoing monitoring.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Company name"},
                "industry": {"type": "string", "description": "Industry or sector"},
                "reason": {"type": "string", "description": "Why this company is relevant"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "create_cron",
        "description": (
            "Set up a recurring automated scan. Use for requests like "
            "'watch for X weekly' or 'set up a scan for Y'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Human-readable name for this scan"},
                "job_type": {
                    "type": "string",
                    "enum": ["market_brief", "relationship_scan", "weekly_digest"],
                    "description": "Type of job to run",
                },
                "schedule": {
                    "type": "string",
                    "description": "Cron expression (e.g. '0 8 * * 5' for Friday 8am)",
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to monitor (for market_brief jobs)",
                },
            },
            "required": ["name", "job_type", "schedule"],
        },
    },
    {
        "name": "get_contacts",
        "description": (
            "Retrieve the user's contacts, optionally filtered by health score or tier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_health_score": {
                    "type": "integer",
                    "description": "Only return contacts with health score at or below this value",
                },
                "tier": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": "Filter by contact tier",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Max contacts to return",
                },
            },
        },
    },
    {
        "name": "get_signals",
        "description": "Get recent market signals for companies in the watchlist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Filter to a specific company name (optional)",
                },
                "signal_type": {
                    "type": "string",
                    "enum": [
                        "new_gc",
                        "deal_announced",
                        "investment",
                        "competitor_move",
                        "general_news",
                    ],
                    "description": "Filter by signal type",
                },
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
]


# ── Tool Executors ────────────────────────────────────────────────────────


async def _exec_web_search(tool_input: dict, *, brave_api_key: str, **_kw) -> Any:
    query = tool_input["query"]
    freshness = tool_input.get("freshness", "month")

    # Map freshness values to Brave API format
    freshness_map = {
        "day": "pd",
        "week": "pw",
        "month": "pm",
        "year": "py",
        "any": "",
    }

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": brave_api_key,
    }
    params: dict[str, Any] = {"q": query, "count": 3}
    brave_freshness = freshness_map.get(freshness, "pm")
    if brave_freshness:
        params["freshness"] = brave_freshness

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Use web search for general research; falls back gracefully if no results
            resp = await client.get(_BRAVE_WEB_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        # Web search returns results under "web.results"; news returns "results"
        results = data.get("web", {}).get("results", data.get("results", []))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
            }
            for r in results[:3]
        ]
    except Exception as exc:
        log.exception("web_search failed for query=%r", query)
        return {"error": str(exc)}


async def _exec_save_company(
    tool_input: dict, *, user_id: str, supabase_admin, **_kw
) -> Any:
    name = tool_input["name"]
    industry = tool_input.get("industry")
    reason = tool_input.get("reason")

    row = {
        "user_id": user_id,
        "name": name,
        "tags": [],
        "is_watchlist": True,
    }
    if industry:
        row["industry"] = industry
    if reason:
        row["notes"] = reason

    result = (
        supabase_admin.table("tracked_firms")
        .upsert(row, on_conflict="user_id,name")
        .execute()
    )
    saved = result.data[0] if result.data else {}
    return {"saved": True, "company_id": saved.get("id", "")}


async def _exec_create_cron(
    tool_input: dict, *, user_id: str, supabase_admin, **_kw
) -> Any:
    name = tool_input["name"]
    job_type = tool_input["job_type"]
    schedule = tool_input["schedule"]
    keywords = tool_input.get("keywords", [])

    # Validate cron expression before touching the DB
    if not _CRON_PATTERN.match(schedule.strip()):
        return {"error": f"Invalid cron expression: {schedule!r}. Expected 5 fields (min hour dom month dow)."}

    # Dedup: if a cron with the same name + job_type already exists, return it
    existing = (
        supabase_admin.table("user_crons")
        .select("id, cron_expression")
        .eq("user_id", user_id)
        .eq("name", name)
        .eq("job_type", job_type)
        .limit(1)
        .execute()
    )
    if existing.data:
        return {
            "created": False,
            "already_exists": True,
            "cron_id": existing.data[0]["id"],
            "schedule": existing.data[0].get("cron_expression", schedule),
        }

    row = {
        "user_id": user_id,
        "name": name,
        "job_type": job_type,
        "cron_expression": schedule,
        "config": {"keywords": keywords},
        "is_active": True,
    }
    result = supabase_admin.table("user_crons").insert(row).execute()
    created = result.data[0] if result.data else {}
    return {
        "created": True,
        "cron_id": created.get("id", ""),
        "schedule": schedule,
    }


async def _exec_get_contacts(
    tool_input: dict, *, user_id: str, supabase_admin, **_kw
) -> Any:
    limit = min(tool_input.get("limit", 10), 100)
    query = (
        supabase_admin.table("contacts")
        .select("name,role,health_score,tier,last_contacted_at")
        .eq("user_id", user_id)
        .order("health_score", desc=False)
    )

    max_hs = tool_input.get("max_health_score")
    if max_hs is not None:
        query = query.lte("health_score", max_hs)

    tier = tool_input.get("tier")
    if tier is not None:
        query = query.eq("tier", tier)

    result = query.limit(limit).execute()
    return result.data or []


async def _exec_get_signals(
    tool_input: dict, *, user_id: str, supabase_admin, **_kw
) -> Any:
    limit = min(tool_input.get("limit", 10), 100)

    # Fetch user's tracked firms for join lookup
    tracked_firms_result = (
        supabase_admin.table("tracked_firms")
        .select("id,name")
        .eq("user_id", user_id)
        .execute()
    )
    company_map = {c["id"]: c["name"] for c in (tracked_firms_result.data or [])}
    company_ids = list(company_map.keys())

    if not company_ids:
        return []

    query = (
        supabase_admin.table("signals")
        .select("headline,type,company_id,source_url,created_at")
        .eq("user_id", user_id)
        .in_("company_id", company_ids)
        .order("created_at", desc=True)
    )

    # Apply filters before limit so we don't cut the result set prematurely
    company_name = tool_input.get("company_name")
    if company_name:
        matching_ids = [
            cid for cid, cname in company_map.items()
            if cname.lower() == company_name.lower()
        ]
        if not matching_ids:
            return []
        query = query.in_("company_id", matching_ids)

    signal_type = tool_input.get("signal_type")
    if signal_type:
        query = query.eq("type", signal_type)

    result = query.limit(limit).execute()
    return [
        {
            "headline": s.get("headline", ""),
            "type": s.get("type", ""),
            "company_name": company_map.get(s.get("company_id"), "Unknown"),
            "url": s.get("source_url", ""),
            "created_at": s.get("created_at", ""),
        }
        for s in (result.data or [])
    ]


# ── Dispatcher ────────────────────────────────────────────────────────────

_EXECUTORS = {
    "web_search": _exec_web_search,
    "save_company": _exec_save_company,
    "create_cron": _exec_create_cron,
    "get_contacts": _exec_get_contacts,
    "get_signals": _exec_get_signals,
}


async def execute_tool(
    tool_name: str,
    tool_input: dict,
    user_id: str,
    supabase_admin,
    brave_api_key: str,
) -> Any:
    """Dispatch a tool call to the appropriate executor."""
    executor = _EXECUTORS.get(tool_name)
    if executor is None:
        return {"error": f"Unknown tool: {tool_name}"}
    return await executor(
        tool_input,
        user_id=user_id,
        supabase_admin=supabase_admin,
        brave_api_key=brave_api_key,
    )

import logging

import anthropic
import httpx

from app.config import settings

log = logging.getLogger(__name__)

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/news/search"
_MAX_KEYWORDS = 3

_SIGNAL_TYPES = {"new_gc", "deal_announced", "investment", "competitor_move", "general_news"}
_CLASSIFY_PROMPT = (
    "Classify this news headline into exactly one of: "
    "new_gc, deal_announced, investment, competitor_move, general_news\n\n"
    "Headline: {headline}\nSummary: {summary}\n\nRespond with only the classification label."
)


async def fetch_signals(query: str, count: int = 10) -> list[dict]:
    """Query Brave News Search API and return raw result items."""
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.brave_api_key,
    }
    params = {"q": query, "count": count, "freshness": "pw"}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(_BRAVE_SEARCH_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    return data.get("results", [])


async def classify_signal_type(
    headline: str, summary: str, client: anthropic.AsyncAnthropic
) -> str:
    """Send a one-shot prompt to Claude Haiku to classify the signal type."""
    try:
        message = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=20,
            messages=[
                {
                    "role": "user",
                    "content": _CLASSIFY_PROMPT.format(
                        headline=headline, summary=summary or ""
                    ),
                }
            ],
        )
        label = message.content[0].text.strip().lower()
        return label if label in _SIGNAL_TYPES else "general_news"
    except Exception:
        log.exception("classify_signal_type failed for headline=%r", headline)
        return "general_news"


async def scan_market_for_user(
    user_id: str,
    supabase_admin,
    anthropic_api_key: str = None,
    keywords: list[str] = None,
    **_kwargs,
) -> dict:
    if not anthropic_api_key:
        raise ValueError("anthropic_api_key is required for market scan")

    anthropic_client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    companies = (
        supabase_admin.table("companies")
        .select("id, name")
        .eq("user_id", user_id)
        .eq("is_watchlist", True)
        .execute()
    ).data or []

    inserted = 0
    for company in companies:
        company_name = company["name"]
        filtered_keywords = [k for k in (keywords or []) if k.strip()]
        if filtered_keywords:
            kw_clause = " OR ".join(f'"{k}"' for k in filtered_keywords[:_MAX_KEYWORDS])
            query = f'"{company_name}" AND ({kw_clause})'
        else:
            query = company_name

        try:
            articles = await fetch_signals(query, count=5)
        except Exception:
            continue

        for article in articles:
            source_url = article.get("url")
            headline = article.get("title", "")
            summary = article.get("description")

            # Deduplicate: primary key is source_url; fall back to (headline, company_id) for null-URL articles
            if source_url:
                existing = (
                    supabase_admin.table("signals")
                    .select("id")
                    .eq("source_url", source_url)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                ).data
                if existing:
                    continue
            else:
                existing = (
                    supabase_admin.table("signals")
                    .select("id")
                    .eq("headline", headline)
                    .eq("company_id", company["id"])
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                ).data
                if existing:
                    continue

            signal_type = await classify_signal_type(
                headline=headline,
                summary=summary or "",
                client=anthropic_client,
            )
            supabase_admin.table("signals").insert(
                {
                    "user_id": user_id,
                    "company_id": company["id"],
                    "type": signal_type,
                    "headline": headline,
                    "source_url": source_url,
                    "summary": summary,
                }
            ).execute()
            inserted += 1

    return {"signals_inserted": inserted}

import asyncio
import logging

import anthropic
import httpx

from app.config import settings  # used by fetch_signals for brave_api_key

log = logging.getLogger(__name__)

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_MAX_KEYWORDS = 3
_CLASSIFY_MODEL = "claude-3-haiku-20240307"

_SIGNAL_TYPES = {"new_gc", "deal_announced", "investment", "competitor_move", "general_news"}
_CLASSIFY_PROMPT = (
    "Classify this news headline into exactly one of: "
    "new_gc, deal_announced, investment, competitor_move, general_news\n\n"
    "Headline: {headline}\nSummary: {summary}\n\nRespond with only the classification label."
)


class BraveAPIError(Exception):
    """Raised when Brave Search API returns an authentication or configuration error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Brave API error (HTTP {status_code}): {detail}")


async def fetch_signals(query: str, count: int = 10) -> list[dict]:
    """Query Brave News Search API and return raw result items.

    Raises BraveAPIError on 401/403 (auth failures) so callers can
    distinguish "no results" from "bad API key".
    """
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.brave_api_key,
    }
    params = {"q": query, "count": count}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(_BRAVE_SEARCH_URL, headers=headers, params=params)

        if response.status_code in (401, 403):
            body = response.text[:200]
            log.error(
                "Brave API auth failure (HTTP %d) for query %r — check BRAVE_API_KEY: %s",
                response.status_code, query, body,
            )
            raise BraveAPIError(
                status_code=response.status_code,
                detail=f"Authentication failed — verify BRAVE_API_KEY is valid. Response: {body}",
            )

        response.raise_for_status()
        data = response.json()

    if "error" in data:
        log.warning("Brave API error in response body: %s", data["error"])
        return []

    # Web search returns results under data["web"]["results"]
    results = data.get("web", {}).get("results", [])
    log.info("Brave search for %r returned %d results", query, len(results))
    return results


async def classify_signal_type(
    headline: str, summary: str, client: anthropic.AsyncAnthropic
) -> str:
    """Send a one-shot prompt to Claude Haiku to classify the signal type."""
    try:
        message = await client.messages.create(
            model=_CLASSIFY_MODEL,
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
        raise ValueError(
            "anthropic_api_key is required for market scan — set ANTHROPIC_API_KEY env var"
        )

    tracked_firms = (
        supabase_admin.table("tracked_firms")
        .select("id, name")
        .eq("user_id", user_id)
        .eq("is_watchlist", True)
        .execute()
    ).data or []

    inserted = 0
    errors: list[str] = []

    # Use async with to ensure connection pool is properly closed after the job
    async with anthropic.AsyncAnthropic(api_key=anthropic_api_key) as anthropic_client:
        for company in tracked_firms:
            company_name = company["name"]
            # Sanitize quotes to avoid breaking Brave query syntax
            safe_name = company_name.replace('"', '')
            filtered_keywords = [k for k in (keywords or []) if k.strip()]
            if filtered_keywords:
                safe_keywords = [k.replace('"', '') for k in filtered_keywords[:_MAX_KEYWORDS]]
                kw_clause = " OR ".join(f'"{k}"' for k in safe_keywords)
                query = f'"{safe_name}" AND ({kw_clause})'
            else:
                query = safe_name

            try:
                articles = await fetch_signals(query, count=5)
            except BraveAPIError:
                # Auth errors should fail loudly — don't silently return 0 signals
                raise
            except Exception:
                msg = f"fetch_signals failed for company={company_name!r} query={query!r}"
                log.warning(msg, exc_info=True)
                errors.append(msg)
                continue

            # Filter to new articles only (dedup before classification)
            new_articles = []
            for article in articles:
                source_url = article.get("url")
                headline = article.get("title", "")

                if source_url:
                    existing = (
                        supabase_admin.table("signals")
                        .select("id")
                        .eq("url", source_url)
                        .eq("user_id", user_id)
                        .limit(1)
                        .execute()
                    ).data
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

                if not existing:
                    new_articles.append(article)

            if not new_articles:
                continue

            # Classify all new articles in parallel
            classifications = await asyncio.gather(
                *[
                    classify_signal_type(
                        headline=a.get("title", ""),
                        summary=a.get("description") or "",
                        client=anthropic_client,
                    )
                    for a in new_articles
                ]
            )

            for article, signal_type in zip(new_articles, classifications):
                supabase_admin.table("signals").insert(
                    {
                        "user_id": user_id,
                        "company_id": company["id"],
                        "source": signal_type,
                        "headline": article.get("title", ""),
                        "url": article.get("url"),
                        "summary": article.get("description") or article.get("extra", {}).get("snippet"),
                    }
                ).execute()
                inserted += 1

    result = {
        "signals_inserted": inserted,
        "companies_scanned": len(tracked_firms),
        "errors": errors,
    }
    log.info(
        "market_scan completed for user=%s: %d signals inserted, %d companies scanned, %d errors",
        user_id, inserted, len(tracked_firms), len(errors),
    )
    return result

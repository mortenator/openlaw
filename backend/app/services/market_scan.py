import httpx

from app.config import settings

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/news/search"


async def fetch_signals(query: str, count: int = 10) -> list[dict]:
    """Query Brave News Search API and return raw result items."""
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.brave_api_key,
    }
    params = {"q": query, "count": count, "freshness": "pw"}

    async with httpx.AsyncClient(timeout=15) as client:
        response = client.get(_BRAVE_SEARCH_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    return data.get("results", [])

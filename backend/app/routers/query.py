from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

from app.config import settings
from app.database import supabase, supabase_admin
from app.deps import get_current_user
from app.services.agent_loop import run_agent_loop

router = APIRouter(prefix="/query", tags=["query"])

# Simple token-bucket rate limiter: max 5 requests per user per minute
_RATE_LIMIT = 5
_RATE_WINDOW = 60  # seconds
_user_request_times: dict[str, Deque[float]] = defaultdict(deque)


def _check_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    window_start = now - _RATE_WINDOW
    q = _user_request_times[user_id]
    # Purge old timestamps
    while q and q[0] < window_start:
        q.popleft()
    if len(q) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded — max {_RATE_LIMIT} queries per minute.",
        )
    q.append(now)


class QueryRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


def _build_user_context(configs: list[dict]) -> str:
    content_map = {row["file_name"]: row["content"] for row in configs}
    parts = []
    for name in ("USER.md", "MEMORY.md"):
        if name in content_map:
            parts.append(content_map[name])
    return "\n\n---\n\n".join(parts)


@router.post("")
async def query(payload: QueryRequest, current_user=Depends(get_current_user)) -> dict:
    _check_rate_limit(str(current_user.id))

    configs_result = (
        supabase.table("agent_memory_logs")
        .select("memory_key,memory_val")
        .eq("user_id", current_user.id)
        .in_("memory_key", ["USER.md", "MEMORY.md"])
        .execute()
    )
    rows = [
        {
            "file_name": r["memory_key"],
            "content": (
                r["memory_val"].get("content", "")
                if isinstance(r["memory_val"], dict)
                else ""
            ),
        }
        for r in (configs_result.data or [])
    ]
    user_context = _build_user_context(rows)

    try:
        result = await run_agent_loop(
            user_message=payload.message,
            user_id=str(current_user.id),
            supabase_admin=supabase_admin,
            brave_api_key=settings.brave_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            user_context=user_context,
        )
    except Exception:
        log.exception("Agent loop failed for user_id=%s", current_user.id)
        raise HTTPException(status_code=502, detail="Agent error — please try again")

    return result

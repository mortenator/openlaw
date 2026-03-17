import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

from app.config import settings
from app.database import supabase, supabase_admin
from app.deps import get_current_user
from app.services.agent_loop import run_agent_loop

router = APIRouter(prefix="/query", tags=["query"])


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
    except Exception as exc:
        log.exception("Agent loop failed for user_id=%s", current_user.id)
        raise HTTPException(status_code=502, detail="Agent error — please try again")

    return result

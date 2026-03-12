import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    message: str


def _build_system_prompt(configs: list[dict]) -> str:
    content_map = {row["file_name"]: row["content"] for row in configs}
    parts = []
    for name in ("SOUL.md", "USER.md", "MEMORY.md"):
        if name in content_map:
            parts.append(content_map[name])
    return "\n\n---\n\n".join(parts)


@router.post("")
async def query(payload: QueryRequest, current_user=Depends(get_current_user)) -> dict:
    configs_result = (
        supabase.table("agent_configs")
        .select("file_name,content")
        .eq("user_id", current_user.id)
        .in_("file_name", ["SOUL.md", "USER.md", "MEMORY.md"])
        .execute()
    )
    system_prompt = _build_system_prompt(configs_result.data or [])

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": payload.message}],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc}")

    return {"response": response.content[0].text}

"""Agent config/memory file endpoints.

Memory files (SOUL.md, USER.md, AGENTS.md, HEARTBEAT.md, MEMORY.md) are stored in
agent_memory_logs (memory_key / memory_val JSONB) — NOT agent_configs.
agent_configs holds settings-style preferences (scan_frequency, outreach_tone, etc.).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/agent", tags=["agent_configs"])

MEMORY_FILES = {"SOUL.md", "USER.md", "AGENTS.md", "HEARTBEAT.md", "MEMORY.md"}


class ConfigUpdate(BaseModel):
    content: str


@router.get("/configs")
async def list_configs(current_user=Depends(get_current_user)) -> list[dict]:
    result = (
        supabase.table("agent_memory_logs")
        .select("memory_key,memory_val,updated_at")
        .eq("user_id", current_user.id)
        .in_("memory_key", list(MEMORY_FILES))
        .execute()
    )
    return [
        {
            "file_name": r["memory_key"],
            "content": r["memory_val"].get("content", "") if isinstance(r["memory_val"], dict) else "",
            "updated_at": r.get("updated_at"),
        }
        for r in (result.data or [])
    ]


@router.get("/configs/{file_name}")
async def get_config(file_name: str, current_user=Depends(get_current_user)) -> dict:
    result = (
        supabase.table("agent_memory_logs")
        .select("memory_key,memory_val,updated_at")
        .eq("user_id", current_user.id)
        .eq("memory_key", file_name)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Config not found")
    r = result.data
    return {
        "file_name": r["memory_key"],
        "content": r["memory_val"].get("content", "") if isinstance(r["memory_val"], dict) else "",
        "updated_at": r.get("updated_at"),
    }


@router.put("/configs/{file_name}")
async def update_config(
    file_name: str, payload: ConfigUpdate, current_user=Depends(get_current_user)
) -> dict:
    result = (
        supabase.table("agent_memory_logs")
        .upsert(
            {
                "user_id": str(current_user.id),
                "memory_key": file_name,
                "memory_val": {"content": payload.content},
            },
            on_conflict="user_id,memory_key",
        )
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update config")
    r = result.data[0]
    return {
        "file_name": r["memory_key"],
        "content": r["memory_val"].get("content", "") if isinstance(r["memory_val"], dict) else "",
        "updated_at": r.get("updated_at"),
    }

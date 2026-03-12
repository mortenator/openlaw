from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/agent", tags=["agent_configs"])


class ConfigUpdate(BaseModel):
    content: str


@router.get("/configs")
async def list_configs(current_user=Depends(get_current_user)) -> list[dict]:
    result = (
        supabase.table("agent_configs")
        .select("*")
        .eq("user_id", current_user.id)
        .execute()
    )
    return result.data or []


@router.get("/configs/{file_name}")
async def get_config(file_name: str, current_user=Depends(get_current_user)) -> dict:
    result = (
        supabase.table("agent_configs")
        .select("*")
        .eq("user_id", current_user.id)
        .eq("file_name", file_name)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Config not found")
    return result.data


@router.put("/configs/{file_name}")
async def update_config(
    file_name: str, payload: ConfigUpdate, current_user=Depends(get_current_user)
) -> dict:
    result = (
        supabase.table("agent_configs")
        .update({"content": payload.content})
        .eq("user_id", current_user.id)
        .eq("file_name", file_name)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Config not found")
    return result.data[0]

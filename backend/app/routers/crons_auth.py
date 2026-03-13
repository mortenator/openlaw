"""Token-based crons endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/crons", tags=["crons"])


class CronToggle(BaseModel):
    is_active: bool


@router.get("")
async def list_crons(current_user=Depends(get_current_user)) -> list[dict]:
    result = (
        supabase.table("user_crons")
        .select("*")
        .eq("user_id", current_user.id)
        .execute()
    )
    return result.data or []


@router.put("/{cron_id}")
async def update_cron(
    cron_id: str,
    payload: CronToggle,
    current_user=Depends(get_current_user),
) -> dict:
    result = (
        supabase.table("user_crons")
        .update({"is_active": payload.is_active})
        .eq("id", cron_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Cron not found")
    return result.data[0]

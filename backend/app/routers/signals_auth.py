"""Token-based signals endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
async def list_signals(
    company_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    current_user=Depends(get_current_user),
) -> list[dict]:
    query = (
        supabase.table("signals")
        .select("*")
        .eq("user_id", current_user.id)
    )
    if company_id is not None:
        query = query.eq("company_id", company_id)
    result = query.order("created_at", desc=True).limit(limit).execute()
    return result.data or []

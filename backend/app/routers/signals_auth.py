"""Token-based signals endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

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


class SignalCreate(BaseModel):
    company_id: Optional[str] = None
    source: str = "general_news"
    headline: str
    summary: Optional[str] = None
    url: Optional[str] = None
    relevance_score: Optional[float] = None


@router.post("", status_code=201)
async def create_signal(
    payload: SignalCreate,
    current_user=Depends(get_current_user),
) -> dict:
    """Manually insert a signal (used for seeding and testing)."""
    data = payload.model_dump(exclude_none=True)
    data["user_id"] = str(current_user.id)
    result = supabase.table("signals").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create signal")
    return result.data[0]

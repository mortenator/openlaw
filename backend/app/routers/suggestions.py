from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


class SuggestionUpdate(BaseModel):
    status: str


@router.get("")
async def list_suggestions(
    status: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
) -> list[dict]:
    query = (
        supabase.table("outreach_suggestions")
        .select("*, contact:contacts(*)")
        .eq("user_id", current_user.id)
    )
    if status is not None:
        query = query.eq("status", status)
    result = query.order("created_at", desc=True).execute()
    return result.data or []


@router.put("/{suggestion_id}")
async def update_suggestion(
    suggestion_id: str,
    payload: SuggestionUpdate,
    current_user=Depends(get_current_user),
) -> dict:
    valid_statuses = {"pending", "dismissed", "sent"}
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {valid_statuses}",
        )
    result = (
        supabase.table("outreach_suggestions")
        .update({"status": payload.status})
        .eq("id", suggestion_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return result.data[0]

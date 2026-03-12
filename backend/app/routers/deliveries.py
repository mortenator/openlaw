import uuid

from fastapi import APIRouter, Query

from app.database import supabase
from app.models.schema import DeliveryOut, OutreachSuggestionOut, OutreachSuggestionUpdate
from fastapi import HTTPException

router = APIRouter(tags=["deliveries"])


@router.get("/users/{user_id}/outreach-suggestions", response_model=list[OutreachSuggestionOut])
async def list_outreach_suggestions(
    user_id: uuid.UUID,
    status: str = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
) -> list[OutreachSuggestionOut]:
    query = (
        supabase.table("outreach_suggestions")
        .select("*")
        .eq("user_id", str(user_id))
    )
    if status:
        query = query.eq("status", status)
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return [OutreachSuggestionOut(**row) for row in (result.data or [])]


@router.patch("/outreach-suggestions/{suggestion_id}", response_model=OutreachSuggestionOut)
async def update_outreach_suggestion(
    suggestion_id: uuid.UUID, payload: OutreachSuggestionUpdate
) -> OutreachSuggestionOut:
    data = payload.model_dump(exclude_none=True)
    result = (
        supabase.table("outreach_suggestions")
        .update(data)
        .eq("id", str(suggestion_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return OutreachSuggestionOut(**result.data[0])

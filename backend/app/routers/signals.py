import uuid

from fastapi import APIRouter, Query

from app.database import supabase
from app.models.schema import SignalOut

router = APIRouter(tags=["signals"])


@router.get("/users/{user_id}/signals", response_model=list[SignalOut])
async def list_signals(
    user_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
) -> list[SignalOut]:
    result = (
        supabase.table("signals")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [SignalOut(**row) for row in (result.data or [])]

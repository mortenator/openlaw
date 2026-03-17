"""Token-based deliveries endpoint."""
from fastapi import APIRouter, Depends, Query

from app.database import supabase
from app.deps import get_current_user
from app.models.schema import DeliveryOut

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get("", response_model=list[DeliveryOut])
async def list_deliveries(
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
) -> list[DeliveryOut]:
    result = (
        supabase.table("deliveries")
        .select("*")
        .eq("user_id", current_user.id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [DeliveryOut(**row) for row in (result.data or [])]

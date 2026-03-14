"""Token-based companies endpoints (uses Bearer auth, returns raw Supabase data)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/companies", tags=["companies"])


class CompanyPayload(BaseModel):
    name: str
    industry: Optional[str] = None
    tags: list[str] = []
    is_watchlist: bool = False
    domain: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def list_companies(
    watchlist: Optional[bool] = Query(default=None),
    current_user=Depends(get_current_user),
) -> list[dict]:
    query = supabase.table("tracked_firms").select("*").eq("user_id", current_user.id)
    if watchlist is not None:
        query = query.eq("is_watchlist", watchlist)
    result = query.order("name").execute()
    return result.data or []


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyPayload, current_user=Depends(get_current_user)
) -> dict:
    data = payload.model_dump()
    data["user_id"] = current_user.id
    result = supabase.table("tracked_firms").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create company")
    return result.data[0]


@router.get("/{company_id}")
async def get_company(
    company_id: str, current_user=Depends(get_current_user)
) -> dict:
    result = (
        supabase.table("tracked_firms")
        .select("*")
        .eq("id", company_id)
        .eq("user_id", current_user.id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")
    return result.data


@router.patch("/{company_id}")
async def update_company(
    company_id: str,
    payload: CompanyPayload,
    current_user=Depends(get_current_user),
) -> dict:
    """Partial update — only fields present in the request body are written."""
    data = payload.model_dump(exclude_unset=True)
    result = (
        supabase.table("tracked_firms")
        .update(data)
        .eq("id", company_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")
    return result.data[0]

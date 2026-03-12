"""Token-based contacts endpoints (mirrors /users/{user_id}/contacts but uses Bearer auth)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import supabase
from app.deps import get_current_user
from app.models.schema import ContactCreate, ContactOut, ContactUpdate
from app.services.health_score import compute_health_score

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    tier: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=200),
    current_user=Depends(get_current_user),
) -> list[ContactOut]:
    query = (
        supabase.table("contacts")
        .select("*")
        .eq("user_id", current_user.id)
    )
    if tier is not None:
        query = query.eq("tier", tier)
    result = query.order("health_score").limit(limit).execute()
    rows = result.data or []
    if search:
        s = search.lower()
        rows = [r for r in rows if s in r.get("name", "").lower()]
    return [ContactOut(**r) for r in rows]


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate, current_user=Depends(get_current_user)
) -> ContactOut:
    data = payload.model_dump()
    data["user_id"] = current_user.id
    data["health_score"] = compute_health_score(
        last_contacted_at=payload.last_contacted_at,
        tier=payload.tier,
    )
    result = supabase.table("contacts").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create contact")
    return ContactOut(**result.data[0])


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: str, current_user=Depends(get_current_user)
) -> ContactOut:
    result = (
        supabase.table("contacts")
        .select("*")
        .eq("id", contact_id)
        .eq("user_id", current_user.id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactOut(**result.data)


@router.put("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    current_user=Depends(get_current_user),
) -> ContactOut:
    data = payload.model_dump(exclude_none=True)
    if "last_contacted_at" in data or "tier" in data:
        existing = (
            supabase.table("contacts")
            .select("last_contacted_at, tier")
            .eq("id", contact_id)
            .eq("user_id", current_user.id)
            .single()
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Contact not found")
        merged_last = data.get("last_contacted_at", existing.data["last_contacted_at"])
        merged_tier = data.get("tier", existing.data["tier"])
        data["health_score"] = compute_health_score(
            last_contacted_at=merged_last,
            tier=merged_tier,
        )
    result = (
        supabase.table("contacts")
        .update(data)
        .eq("id", contact_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactOut(**result.data[0])

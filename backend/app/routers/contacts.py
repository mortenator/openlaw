import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.database import supabase
from app.models.schema import ContactCreate, ContactOut, ContactUpdate
from app.services.health_score import compute_health_score

router = APIRouter(tags=["contacts"])


@router.post("/users/{user_id}/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(user_id: uuid.UUID, payload: ContactCreate) -> ContactOut:
    data = payload.model_dump()
    data["user_id"] = str(user_id)
    data["health_score"] = compute_health_score(
        last_contacted_at=payload.last_contacted_at,
        tier=payload.tier,
    )
    result = supabase.table("contacts").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create contact")
    return ContactOut(**result.data[0])


@router.get("/users/{user_id}/contacts", response_model=list[ContactOut])
async def list_contacts(
    user_id: uuid.UUID,
    tier: Optional[int] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
) -> list[ContactOut]:
    query = supabase.table("contacts").select("*").eq("user_id", str(user_id))
    if tier is not None:
        query = query.eq("tier", tier)
    result = query.order("health_score").range(offset, offset + limit - 1).execute()
    return [ContactOut(**row) for row in (result.data or [])]


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(contact_id: uuid.UUID, payload: ContactUpdate) -> ContactOut:
    data = payload.model_dump(exclude_none=True)
    if "last_contacted_at" in data or "tier" in data:
        # Re-compute health score when relevant fields change
        existing = (
            supabase.table("contacts")
            .select("last_contacted_at, tier")
            .eq("id", str(contact_id))
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
        .eq("id", str(contact_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactOut(**result.data[0])


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: uuid.UUID) -> None:
    result = supabase.table("contacts").delete().eq("id", str(contact_id)).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contact not found")

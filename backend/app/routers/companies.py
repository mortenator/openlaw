import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.database import supabase
from app.models.schema import CompanyCreate, CompanyOut

router = APIRouter(tags=["companies"])


@router.post("/users/{user_id}/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(user_id: uuid.UUID, payload: CompanyCreate) -> CompanyOut:
    data = payload.model_dump()
    data["user_id"] = str(user_id)
    result = supabase.table("companies").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create company")
    return CompanyOut(**result.data[0])


@router.get("/users/{user_id}/companies", response_model=list[CompanyOut])
async def list_companies(
    user_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
) -> list[CompanyOut]:
    result = (
        supabase.table("companies")
        .select("*")
        .eq("user_id", str(user_id))
        .order("name")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [CompanyOut(**row) for row in (result.data or [])]

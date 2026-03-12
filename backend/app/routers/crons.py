import uuid

from fastapi import APIRouter, HTTPException, status

from app.database import supabase
from app.models.schema import CronCreate, CronOut, CronUpdate

router = APIRouter(tags=["crons"])


@router.post("/users/{user_id}/crons", response_model=CronOut, status_code=status.HTTP_201_CREATED)
async def create_cron(user_id: uuid.UUID, payload: CronCreate) -> CronOut:
    data = payload.model_dump()
    data["user_id"] = str(user_id)
    result = supabase.table("user_crons").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create cron")
    return CronOut(**result.data[0])


@router.get("/users/{user_id}/crons", response_model=list[CronOut])
async def list_crons(user_id: uuid.UUID) -> list[CronOut]:
    result = (
        supabase.table("user_crons")
        .select("*")
        .eq("user_id", str(user_id))
        .execute()
    )
    return [CronOut(**row) for row in (result.data or [])]


@router.patch("/crons/{cron_id}", response_model=CronOut)
async def update_cron(cron_id: uuid.UUID, payload: CronUpdate) -> CronOut:
    data = payload.model_dump(exclude_none=True)
    result = (
        supabase.table("user_crons")
        .update(data)
        .eq("id", str(cron_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Cron not found")
    return CronOut(**result.data[0])

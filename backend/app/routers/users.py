import uuid

from fastapi import APIRouter, HTTPException, status

from app.database import supabase
from app.models.schema import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate) -> UserOut:
    data = payload.model_dump()
    result = supabase.table("users").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create user")
    return UserOut(**result.data[0])


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID) -> UserOut:
    result = supabase.table("users").select("*").eq("id", str(user_id)).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**result.data)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, payload: UserUpdate) -> UserOut:
    data = payload.model_dump(exclude_none=True)
    result = (
        supabase.table("users")
        .update(data)
        .eq("id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**result.data[0])

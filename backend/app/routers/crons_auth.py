"""Token-based crons endpoints."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/crons", tags=["crons"])


class CronToggle(BaseModel):
    is_active: bool


class CronConfig(BaseModel):
    keywords: list[str] = []


class CronCreate(BaseModel):
    name: str = Field(..., max_length=200)
    job_type: Literal["market_brief", "relationship_scan", "weekly_digest"]
    cron_expression: str = Field(..., max_length=100)
    config: Optional[CronConfig] = None
    is_active: bool = True

    @validator("cron_expression")
    def validate_cron_expression(cls, v: str) -> str:
        parts = v.strip().split()
        if len(parts) != 5:
            raise ValueError("cron_expression must have exactly 5 fields")
        _CRON_FIELD = r"^(\*|[0-9,\-]+|\*/[0-9]+|[0-9]+-[0-9]+/[0-9]+|[0-9]+/[0-9]+)$"
        import re
        for part in parts:
            if not re.match(_CRON_FIELD, part):
                raise ValueError(f"Invalid cron field: {part!r}")
        return v


@router.get("")
async def list_crons(current_user=Depends(get_current_user)) -> list[dict]:
    result = (
        supabase.table("user_crons")
        .select("*")
        .eq("user_id", current_user.id)
        .execute()
    )
    return result.data or []


@router.post("")
async def create_cron(
    payload: CronCreate,
    current_user=Depends(get_current_user),
) -> dict:
    data = payload.model_dump()
    data["user_id"] = str(current_user.id)
    result = supabase.table("user_crons").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create cron")
    return result.data[0]


@router.put("/{cron_id}")
async def update_cron(
    cron_id: str,
    payload: CronToggle,
    current_user=Depends(get_current_user),
) -> dict:
    result = (
        supabase.table("user_crons")
        .update({"is_active": payload.is_active})
        .eq("id", cron_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Cron not found")
    return result.data[0]

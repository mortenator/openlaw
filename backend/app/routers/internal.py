"""Internal endpoints called by the Paperclip agent execution backend."""
import logging
import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from postgrest.exceptions import APIError
from pydantic import BaseModel

from app.config import settings
from app.database import supabase

log = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])

SUPPORTED_JOB_TYPES = {"daily_briefing", "contact_review", "signal_scan"}


class HeartbeatContext(BaseModel):
    job_type: str
    payload: dict[str, Any] = {}


class HeartbeatRequest(BaseModel):
    agent_id: str
    context: HeartbeatContext


class HeartbeatResponse(BaseModel):
    success: bool
    job_type: str
    user_id: str


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    body: HeartbeatRequest,
    x_internal_key: str = Header(alias="X-Internal-Key"),
) -> HeartbeatResponse:
    """Receive a scheduled heartbeat from Paperclip and dispatch the appropriate job."""
    if not secrets.compare_digest(x_internal_key, settings.paperclip_internal_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal key")

    job_type = body.context.job_type
    if job_type not in SUPPORTED_JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported job_type '{job_type}'. Must be one of: {sorted(SUPPORTED_JOB_TYPES)}",
        )

    # Look up the user by their Paperclip agent ID
    try:
        result = (
            supabase.table("users")
            .select("id, name, email")
            .eq("paperclip_agent_id", body.agent_id)
            .single()
            .execute()
        )
    except APIError as exc:
        # Distinguish "row not found" (PGRST116) from infrastructure failures
        if getattr(exc, "code", None) == "PGRST116":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user found for the provided agent_id",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error looking up agent",
        ) from exc

    user = result.data
    user_id: str = user["id"]

    # Stub dispatch — jobs.py will be wired here in a later phase
    log.info(
        "Heartbeat received: job_type=%s user_id=%s agent_id=%s",
        job_type,
        user_id,
        body.agent_id,
    )
    await _dispatch_job(job_type=job_type, user_id=user_id, payload=body.context.payload)

    return HeartbeatResponse(success=True, job_type=job_type, user_id=user_id)


async def _dispatch_job(job_type: str, user_id: str, payload: dict[str, Any]) -> None:
    """Stub dispatcher — replace with real job invocation in Phase 4."""
    log.info("Dispatching job '%s' for user %s (payload keys: %s)", job_type, user_id, list(payload.keys()))
    # TODO(phase4): wire to jobs.py handlers
    # if job_type == "daily_briefing":
    #     await run_daily_briefing(user_id, payload)
    # elif job_type == "contact_review":
    #     await run_contact_review(user_id, payload)
    # elif job_type == "signal_scan":
    #     await run_signal_scan(user_id, payload)

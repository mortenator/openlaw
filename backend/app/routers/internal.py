"""Internal endpoints called by the Paperclip agent execution backend."""
import logging
import secrets
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from postgrest.exceptions import APIError
from pydantic import BaseModel

from app.config import settings
from app.database import supabase

log = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])

SUPPORTED_JOB_TYPES = {"daily_briefing", "contact_review", "signal_scan"}

# Map Paperclip heartbeat job types → agent_runner job types
_HEARTBEAT_TO_RUNNER: dict[str, str] = {
    "signal_scan": "market_brief",
    "contact_review": "relationship_scan",
    "daily_briefing": "weekly_digest",
}


class HeartbeatContext(BaseModel):
    job_type: str
    payload: dict[str, Any] = {}


class HeartbeatRequest(BaseModel):
    agent_id: UUID  # Validated at request boundary — prevents Postgres cast errors
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
            .select("id")
            .eq("paperclip_agent_id", str(body.agent_id))
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
        "Heartbeat received: job_type=%s user_id=%s agent_id=%.8s…",
        job_type,
        user_id,
        str(body.agent_id),  # truncated — avoid logging full UUID in plaintext
    )
    await _dispatch_job(job_type=job_type, user_id=user_id, payload=body.context.payload)

    return HeartbeatResponse(success=True, job_type=job_type, user_id=user_id)


async def _dispatch_job(job_type: str, user_id: str, payload: dict[str, Any]) -> None:
    """Dispatch a Paperclip heartbeat to the matching agent_runner job handler."""
    from app.services.agent_runner import run_job

    runner_job_type = _HEARTBEAT_TO_RUNNER.get(job_type)
    if runner_job_type is None:
        log.error("No runner mapping for heartbeat job_type=%s", job_type)
        return

    log.info(
        "Dispatching heartbeat job_type=%s → runner=%s for user %s",
        job_type,
        runner_job_type,
        user_id,
    )
    try:
        await run_job(
            job_type=runner_job_type,
            user_id=user_id,
            supabase_admin=supabase,
            settings=settings,
        )
        log.info("Heartbeat dispatch OK: job_type=%s user_id=%s", job_type, user_id)
    except Exception:
        log.exception("Heartbeat dispatch FAILED: job_type=%s user_id=%s", job_type, user_id)

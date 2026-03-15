from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import supabase
from app.services.agent_runner import run_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobRequest(BaseModel):
    job_type: str
    user_id: str
    cron_id: str | None = None


@router.post("/run")
async def run_job_webhook(
    payload: JobRequest,
    x_cron_secret: str = Header(...),
) -> dict:
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    try:
        result = await run_job(
            job_type=payload.job_type,
            user_id=payload.user_id,
            supabase_admin=supabase,
            settings=settings,
            cron_id=payload.cron_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Job failed: {exc}")

    return {"status": "ok", "job_type": payload.job_type, "user_id": payload.user_id, **result}

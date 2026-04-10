"""DEPRECATED — In-process cron scheduler.

Replaced by Paperclip heartbeat scheduling in Phase 4.
Kept for rollback safety; will be removed in a future cleanup PR.

Previously: a background asyncio task woke every 60 seconds, queried user_crons
for jobs that were due, and dispatched them via run_job.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from croniter import croniter

log = logging.getLogger(__name__)

_TICK_INTERVAL = 60  # seconds between scheduler ticks
_scheduler_task: asyncio.Task | None = None


def _is_due(cron_expression: str, last_run_at: datetime | None, now: datetime) -> bool:
    """Return True if the job should fire this tick."""
    try:
        cron = croniter(cron_expression, start_time=last_run_at or (now.replace(second=0, microsecond=0)))
        next_run = cron.get_next(datetime)
        return next_run <= now
    except Exception:
        return False


async def _tick() -> None:
    """Single scheduler tick — find due jobs and dispatch them."""
    from app.config import settings
    from app.database import supabase
    from app.services.agent_runner import run_job

    now = datetime.now(timezone.utc)

    try:
        result = (
            supabase.table("user_crons")
            .select("id, user_id, job_type, cron_expression, last_run_at, is_active")
            .eq("is_active", True)
            .execute()
        )
        crons = result.data or []
    except Exception:
        log.exception("Scheduler: failed to fetch user_crons")
        return

    for cron in crons:
        cron_id = cron.get("id")
        user_id = cron.get("user_id")
        job_type = cron.get("job_type")
        expression = cron.get("cron_expression", "0 8 * * *")
        last_run_raw = cron.get("last_run_at")

        last_run: datetime | None = None
        if last_run_raw:
            try:
                last_run = datetime.fromisoformat(last_run_raw.replace("Z", "+00:00"))
            except Exception:
                pass

        if not _is_due(expression, last_run, now):
            continue

        log.info("Scheduler: firing job_type=%s cron_id=%s user_id=%s", job_type, cron_id, user_id)

        # Mark last_run_at immediately to prevent double-firing across ticks
        try:
            supabase.table("user_crons").update(
                {"last_run_at": now.isoformat()}
            ).eq("id", cron_id).execute()
        except Exception:
            log.exception("Scheduler: failed to update last_run_at for cron_id=%s", cron_id)
            continue

        try:
            job_result = await run_job(
                job_type=job_type,
                user_id=user_id,
                supabase_admin=supabase,
                settings=settings,
                cron_id=cron_id,
            )
            log.info(
                "Scheduler: job_type=%s cron_id=%s completed — result=%s",
                job_type, cron_id, job_result,
            )
        except Exception:
            log.exception("Scheduler: job_type=%s cron_id=%s failed", job_type, cron_id)


async def _scheduler_loop() -> None:
    log.info("Scheduler: started (tick every %ds)", _TICK_INTERVAL)
    while True:
        try:
            await _tick()
        except Exception:
            log.exception("Scheduler: unhandled error in tick")
        await asyncio.sleep(_TICK_INTERVAL)


def start_scheduler() -> None:
    """Launch the scheduler as a background asyncio task."""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_scheduler_loop())
    log.info("Scheduler: background task created")


def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
    log.info("Scheduler: stopped")

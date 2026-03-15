"""Cron dispatcher script — Railway calls this every 15 minutes."""
import logging
import os
from datetime import datetime, timezone

import httpx
from croniter import croniter
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"]
    service_role_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    cron_secret = os.environ["CRON_SECRET"]
    job_api_url = os.getenv("JOB_API_URL", "http://localhost:8000/jobs/run")

    supabase = create_client(supabase_url, service_role_key)
    now = datetime.now(timezone.utc)

    # Fire jobs where next_run_at is due OR null (new rows that have never run)
    due_rows = (
        supabase.table("user_crons")
        .select("id, job_type, user_id, cron_expression, last_run_at")
        .eq("is_active", True)
        .lte("next_run_at", now.isoformat())
        .execute()
    ).data or []
    null_rows = (
        supabase.table("user_crons")
        .select("id, job_type, user_id, cron_expression, last_run_at")
        .eq("is_active", True)
        .is_("next_run_at", "null")
        .execute()
    ).data or []
    rows = list({r["id"]: r for r in due_rows + null_rows}.values())  # deduplicate by id

    log.info("Found %d due cron jobs", len(rows))

    for row in rows:
        job_type = row["job_type"]
        user_id = row["user_id"]
        cron_id = row["id"]

        try:
            response = httpx.post(
                job_api_url,
                json={"job_type": job_type, "user_id": user_id, "cron_id": cron_id},
                headers={"X-Cron-Secret": cron_secret},
                timeout=30,
            )
            response.raise_for_status()
            success = True
        except Exception as exc:
            log.error("job_type=%s user_id=%s FAILED: %s", job_type, user_id, exc)
            success = False

        # Always record last_run_at and advance next_run_at regardless of success/failure
        # to prevent the same failed job from re-triggering on every subsequent tick.
        update_payload: dict = {"last_run_at": now.isoformat()}
        cron_expr = row.get("cron_expression")
        if not cron_expr:
            # Disable broken row rather than re-firing every tick
            log.error("job_type=%s cron_id=%s has no cron_expression — disabling", job_type, cron_id)
            supabase.table("user_crons").update({"is_active": False}).eq("id", cron_id).execute()
            continue
        try:
            next_run = croniter(cron_expr, now).get_next(datetime)
            update_payload["next_run_at"] = next_run.isoformat()
            log.info(
                "job_type=%s user_id=%s %s — next_run_at=%s",
                job_type, user_id, "OK" if success else "FAILED", next_run,
            )
        except Exception as exc:
            log.error(
                "job_type=%s user_id=%s could not parse cron_expression=%r: %s — disabling",
                job_type, user_id, cron_expr, exc,
            )
            supabase.table("user_crons").update({"is_active": False}).eq("id", cron_id).execute()
            continue
        supabase.table("user_crons").update(update_payload).eq("id", cron_id).execute()


if __name__ == "__main__":
    main()

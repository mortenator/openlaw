"""Orchestrates running agent jobs for a specific user."""
from .health_score import compute_health_score
from .market_scan import scan_market_for_user as _scan_market_for_user
from .outreach import generate_outreach_suggestions
from .digest import compile_and_send_weekly_digest


async def recalculate_all_for_user(user_id: str, supabase_admin, **kwargs) -> dict:
    from datetime import datetime

    contacts = (
        supabase_admin.table("contacts")
        .select("id, last_contacted_at, tier")
        .eq("user_id", user_id)
        .execute()
    ).data or []

    updated = 0
    for contact in contacts:
        last = contact.get("last_contacted_at")
        if last and isinstance(last, str):
            last = datetime.fromisoformat(last.replace("Z", "+00:00"))
        score = compute_health_score(last_contacted_at=last, tier=contact.get("tier", 2))
        supabase_admin.table("contacts").update({"health_score": score}).eq(
            "id", contact["id"]
        ).execute()
        updated += 1

    return {"contacts_updated": updated}


async def scan_market_for_user(
    user_id: str,
    supabase_admin,
    settings=None,
    anthropic_api_key: str = None,
    cron_id: str = None,
    **kwargs,
) -> dict:
    keywords: list[str] = []
    if cron_id:
        row = (
            supabase_admin.table("user_crons")
            .select("config")
            .eq("id", cron_id)
            .maybe_single()
            .execute()
        ).data
        if row and row.get("config"):
            keywords = row["config"].get("keywords", [])

    return await _scan_market_for_user(
        user_id=user_id,
        supabase_admin=supabase_admin,
        anthropic_api_key=anthropic_api_key,
        keywords=keywords or None,
    )


JOB_TYPES = {
    "recalculate_health": recalculate_all_for_user,
    "market_brief": scan_market_for_user,
    "relationship_scan": generate_outreach_suggestions,
    "weekly_digest": compile_and_send_weekly_digest,
}


async def run_job(
    job_type: str,
    user_id: str,
    supabase_admin,
    settings,
    cron_id: str = None,
) -> dict:
    if job_type not in JOB_TYPES:
        raise ValueError(f"Unknown job type: {job_type}")
    handler = JOB_TYPES[job_type]
    result = await handler(
        user_id=user_id,
        supabase_admin=supabase_admin,
        settings=settings,
        anthropic_api_key=getattr(settings, "anthropic_api_key", None),
        cron_id=cron_id,
    )
    return {"job_type": job_type, "user_id": user_id, "result": result}

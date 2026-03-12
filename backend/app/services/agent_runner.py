"""Orchestrates running agent jobs for a specific user."""
from .health_score import compute_health_score
from .market_scan import fetch_signals
from .outreach import generate_outreach_suggestions


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


async def scan_market_for_user(user_id: str, supabase_admin, settings=None, **kwargs) -> dict:
    companies = (
        supabase_admin.table("companies")
        .select("id, name")
        .eq("user_id", user_id)
        .eq("is_watchlist", True)
        .execute()
    ).data or []

    inserted = 0
    for company in companies:
        try:
            articles = await fetch_signals(company["name"], count=5)
        except Exception:
            continue
        for article in articles:
            supabase_admin.table("signals").insert(
                {
                    "user_id": user_id,
                    "company_id": company["id"],
                    "type": "general_news",
                    "headline": article.get("title", ""),
                    "source_url": article.get("url"),
                    "summary": article.get("description"),
                }
            ).execute()
            inserted += 1

    return {"signals_inserted": inserted}


JOB_TYPES = {
    "recalculate_health": recalculate_all_for_user,
    "market_brief": scan_market_for_user,
    "relationship_scan": generate_outreach_suggestions,
}


async def run_job(job_type: str, user_id: str, supabase_admin, settings) -> dict:
    if job_type not in JOB_TYPES:
        raise ValueError(f"Unknown job type: {job_type}")
    handler = JOB_TYPES[job_type]
    result = await handler(
        user_id=user_id,
        supabase_admin=supabase_admin,
        settings=settings,
        anthropic_api_key=getattr(settings, "anthropic_api_key", None),
    )
    return {"job_type": job_type, "user_id": user_id, "result": result}

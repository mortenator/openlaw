import json
import logging
import re
from datetime import datetime, timezone, timedelta

import anthropic

log = logging.getLogger(__name__)


async def generate_outreach_suggestions(
    user_id: str, supabase_admin, anthropic_api_key: str = None, settings=None, **_kwargs
) -> dict:
    # Support both calling conventions (positional anthropic_api_key or via settings)
    api_key = anthropic_api_key or (settings.anthropic_api_key if settings else None)
    if api_key is None:
        raise ValueError("anthropic_api_key is required")

    # Fetch tier 1 and 2 contacts with health_score < 60
    contacts_result = (
        supabase_admin.table("contacts")
        .select("id, name, role, company_id, tier, last_contacted_at")
        .eq("user_id", user_id)
        .in_("tier", [1, 2])
        .lt("health_score", 60)
        .execute()
    )
    contacts = contacts_result.data or []
    if not contacts:
        return {"suggestions_created": 0}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    created = 0

    # Use async with so connection pool is always closed, even on exception
    async with anthropic.AsyncAnthropic(api_key=api_key) as client:
        for contact in contacts:
            company_id = contact.get("company_id")
            if not company_id:
                continue

            signals_result = (
                supabase_admin.table("signals")
                .select("id, headline, summary, type")
                .eq("company_id", company_id)
                .gte("created_at", cutoff)
                .limit(1)
                .execute()
            )
            signals = signals_result.data or []
            if not signals:
                continue

            signal = signals[0]
            prompt = (
                f"You are drafting a warm outreach email for a deal lawyer.\n\n"
                f"Contact: {contact['name']} ({contact.get('role', 'unknown role')})\n"
                f"Recent news about their company: {signal['headline']}\n"
                f"Summary: {signal.get('summary', '')}\n\n"
                f"Write a short, professional outreach email. "
                f"Return JSON with keys: subject, draft_message. "
                f"Keep it under 150 words. Be specific about the news angle."
            )

            try:
                response = await client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text
                # Strip markdown code fences robustly
                fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
                if fence_match:
                    text = fence_match.group(1)
                parsed = json.loads(text.strip())
            except Exception:
                log.exception(
                    "Failed to generate suggestion for contact_id=%s signal_id=%s",
                    contact["id"], signal["id"],
                )
                continue

            # Build human-readable trigger summary
            tier = contact.get("tier", 2)
            last_contacted_raw = contact.get("last_contacted_at")
            if last_contacted_raw:
                if isinstance(last_contacted_raw, str):
                    last_contacted_dt = datetime.fromisoformat(
                        last_contacted_raw.replace("Z", "+00:00")
                    )
                else:
                    last_contacted_dt = last_contacted_raw
                    if last_contacted_dt.tzinfo is None:
                        last_contacted_dt = last_contacted_dt.replace(tzinfo=timezone.utc)
                days = (datetime.now(timezone.utc) - last_contacted_dt).days
            else:
                days = None  # never contacted
            if days is None:
                days_str = "never contacted"
            else:
                days_str = f"{days} days since last contact"
            trigger_summary = (
                f"Tier {tier} contact — {days_str}. "
                f"{signal['headline'][:200]}"
            )

            try:
                supabase_admin.table("outreach_suggestions").insert(
                    {
                        "user_id": user_id,
                        "contact_id": contact["id"],
                        "signal_id": signal["id"],
                        "subject": parsed.get("subject", ""),
                        "body": parsed.get("draft_message", ""),
                        "status": "pending",
                        "trigger_summary": trigger_summary,
                    }
                ).execute()
                created += 1
            except Exception:
                log.exception(
                    "DB insert failed for outreach suggestion contact_id=%s", contact["id"]
                )

    return {"suggestions_created": created}

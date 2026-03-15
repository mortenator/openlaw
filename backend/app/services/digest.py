"""Weekly digest compiler: pulls top-5 pending outreach suggestions and sends via Resend."""
import html
import logging
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"
_FROM_ADDRESS = "OpenLaw <briefs@openlaw.ai>"


def _build_html(suggestions: list[dict], date_str: str) -> str:
    rows = []
    for s in suggestions:
        contact = s.get("contacts") or {}
        name = html.escape(contact.get("name", "Unknown"))
        role = html.escape(contact.get("role") or "Contact")
        reason = html.escape(s.get("trigger_summary") or "Health score dropped below threshold")
        draft = html.escape(s.get("body", ""))
        rows.append(
            f"<tr>"
            f"<td style='padding:12px 0;border-bottom:1px solid #eee;'>"
            f"<strong>{name}</strong> &mdash; {role}<br>"
            f"<em style='color:#666;font-size:13px;'>{reason}</em><br>"
            f"<span style='margin-top:6px;display:block;'>{draft}</span>"
            f"</td>"
            f"</tr>"
        )
    rows_html = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;">
  <h2 style="color:#1a1a1a;">Your weekly relationship brief &mdash; {date_str}</h2>
  <p style="color:#555;">Top contacts to re-engage this week:</p>
  <table style="width:100%;border-collapse:collapse;">
    {rows_html}
  </table>
  <p style="color:#aaa;font-size:12px;margin-top:32px;">Sent by OpenLaw &mdash; AI chief of staff for deal lawyers.</p>
</body>
</html>"""


def _build_text(suggestions: list[dict], date_str: str) -> str:
    lines = [f"Your weekly relationship brief — {date_str}\n"]
    for i, s in enumerate(suggestions, 1):
        contact = s.get("contacts") or {}
        name = contact.get("name", "Unknown")
        role = contact.get("role") or "Contact"
        reason = s.get("trigger_summary") or "Health score dropped below threshold"
        draft = s.get("body", "")
        lines.append(f"{i}. {name} ({role})")
        lines.append(f"   Why: {reason}")
        lines.append(f"   Draft: {draft}\n")
    return "\n".join(lines)


async def compile_and_send_weekly_digest(
    user_id: str, supabase_admin, resend_api_key: str = "", **_kwargs
) -> dict:
    # 1. Fetch user row
    user_result = (
        supabase_admin.table("users")
        .select("name, email, comms_channel")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    user = user_result.data
    if not user:
        return {"sent": False, "reason": "user_not_found"}

    user_email = user.get("email")
    if not user_email:
        return {"sent": False, "reason": "no_email_on_file"}

    # 2. Fetch pending suggestions with contact + signal data; sort in Python
    suggestions_result = (
        supabase_admin.table("outreach_suggestions")
        .select("id, body, trigger_summary, contacts(name, role, health_score), signals(headline, created_at)")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .execute()
    )
    rows = suggestions_result.data or []

    if not rows:
        return {"sent": False, "reason": "no_pending_suggestions"}

    # Sort: health_score ASC (worst first), then signals.created_at DESC (most recent)
    def _sort_key(row: dict):
        contact = row.get("contacts") or {}
        signal = row.get("signals") or {}
        health = contact.get("health_score") if contact.get("health_score") is not None else 100
        created_raw = signal.get("created_at") or ""
        # Negate created_at for DESC: use negative timestamp
        try:
            ts = datetime.fromisoformat(created_raw.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError):
            ts = 0.0
        return (health, -ts)

    rows.sort(key=_sort_key)
    top5 = rows[:5]

    # 3. Compile email
    date_str = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    subject = f"Your weekly relationship brief — {date_str}"
    html_body = _build_html(top5, date_str)
    text_body = _build_text(top5, date_str)

    # 4. Send via Resend
    if not resend_api_key:
        log.warning("RESEND_API_KEY not set — skipping email send for user_id=%s", user_id)
        return {"sent": False, "reason": "resend_api_key_not_configured"}

    suggestion_ids = [str(s["id"]) for s in top5]
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {resend_api_key}"},
                json={
                    "from": _FROM_ADDRESS,
                    "to": [user_email],
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.error(
            "Resend API error for user_id=%s status=%s body=%s",
            user_id, exc.response.status_code, exc.response.text,
        )
        return {"sent": False, "reason": f"resend_error_{exc.response.status_code}"}
    except Exception:
        log.exception("Resend send failed for user_id=%s", user_id)
        return {"sent": False, "reason": "resend_exception"}

    # 5. Log delivery
    delivery_result = (
        supabase_admin.table("deliveries")
        .insert(
            {
                "user_id": user_id,
                "delivery_type": "weekly_digest",
                "channel": "email",
                "status": "sent",
                "payload": {"suggestion_ids": suggestion_ids},
                "delivered_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .execute()
    )
    delivery_row = (delivery_result.data or [{}])[0]
    delivery_id = delivery_row.get("id")

    return {
        "sent": True,
        "suggestions_included": len(top5),
        "delivery_id": delivery_id,
    }

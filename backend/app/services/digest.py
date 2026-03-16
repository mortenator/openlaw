"""Weekly digest compiler: pulls top-5 pending outreach suggestions and sends via Resend."""
import html
import logging
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


def _log_failed_delivery(supabase_admin, user_id: str, suggestion_ids: list, reason: str) -> None:
    """Write a failed delivery row so the audit trail is complete even on send errors."""
    try:
        supabase_admin.table("deliveries").insert({
            "user_id": user_id,
            "delivery_type": "weekly_digest",
            "channel": "email",
            "status": "failed",
            "payload": {"suggestion_ids": suggestion_ids},
            "error_message": reason,
        }).execute()
    except Exception:
        log.exception("Could not write failed delivery record for user_id=%s", user_id)


def _build_html(suggestions: list[dict], date_str: str) -> str:
    rows = []
    for s in suggestions:
        _contacts = s.get("contacts") or []
        contact = (_contacts[0] if isinstance(_contacts, list) else _contacts) or {}
        name = html.escape(contact.get("name", "Unknown"))
        role = html.escape(contact.get("role") or "Contact")
        reason = html.escape(s.get("trigger_summary") or "Health score dropped below threshold")
        draft = html.escape(s.get("body", "")).replace("\n", "<br>")
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
        _contacts = s.get("contacts") or []
        contact = (_contacts[0] if isinstance(_contacts, list) else _contacts) or {}
        name = contact.get("name", "Unknown")
        role = contact.get("role") or "Contact"
        reason = s.get("trigger_summary") or "Health score dropped below threshold"
        draft = s.get("body", "")
        lines.append(f"{i}. {name} ({role})")
        lines.append(f"   Why: {reason}")
        lines.append(f"   Draft: {draft}\n")
    return "\n".join(lines)


async def compile_and_send_weekly_digest(
    user_id: str, supabase_admin, resend_api_key: str | None = None,
    from_address: str | None = None, **_kwargs
) -> dict:
    # from_address defaults to config.resend_from_address — no inline default to avoid drift
    if not resend_api_key:
        return {"sent": False, "reason": "resend_api_key_not_configured"}
    if not from_address:
        return {"sent": False, "reason": "resend_from_address_not_configured"}

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

    comms_channel = user.get("comms_channel", "email")
    if comms_channel != "email":
        # Only email delivery is supported in MVP; Slack/SMS deferred to v2
        log.info("Skipping digest for user_id=%s — comms_channel=%r (email only in MVP)", user_id, comms_channel)
        return {"sent": False, "reason": f"unsupported_channel:{comms_channel}"}

    user_email = user.get("email")
    if not user_email:
        return {"sent": False, "reason": "no_email_on_file"}

    # 2. Fetch top-5 pending suggestions sorted at DB level (worst health first, most recent signal first)
    # contacts(health_score) ASC = lowest score (worst relationship) surfaces first
    suggestions_result = (
        supabase_admin.table("outreach_suggestions")
        .select("id, body, trigger_summary, contacts(name, role, health_score), signals(headline, created_at)")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .order("contacts.health_score", desc=False, nullsfirst=True)
        .order("signals.created_at", desc=True)
        .limit(5)
        .execute()
    )
    top5 = suggestions_result.data or []

    if not top5:
        return {"sent": False, "reason": "no_pending_suggestions"}

    # 3. Compile email
    now = datetime.now(timezone.utc)
    date_str = f"{now.strftime('%B')} {now.day}, {now.year}"  # cross-platform, no %-d
    subject = f"Your weekly relationship brief — {date_str}"
    html_body = _build_html(top5, date_str)
    text_body = _build_text(top5, date_str)

    # 4. Send via Resend (key already validated at function entry)
    suggestion_ids = [str(s["id"]) for s in top5]
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {resend_api_key}"},
                json={
                    "from": from_address,
                    "to": [user_email],
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        reason = f"resend_error_{exc.response.status_code}"
        log.error("Resend API error for user_id=%s status=%s body=%s", user_id, exc.response.status_code, exc.response.text)
        _log_failed_delivery(supabase_admin, user_id, suggestion_ids, reason)
        return {"sent": False, "reason": reason}
    except Exception:
        log.exception("Resend send failed for user_id=%s", user_id)
        _log_failed_delivery(supabase_admin, user_id, suggestion_ids, "resend_exception")
        return {"sent": False, "reason": "resend_exception"}

    # 5. Mark included suggestions as digest_sent so they don't re-surface next week (single bulk update)
    mark_failed = False
    try:
        supabase_admin.table("outreach_suggestions").update(
            {"status": "digest_sent"}
        ).in_("id", suggestion_ids).eq("user_id", user_id).execute()
    except Exception:
        mark_failed = True
        log.exception("Failed to mark suggestions as digest_sent for user_id=%s — duplicate send risk on next run", user_id)

    # 6. Log delivery — wrap in try/except since email already sent at this point
    delivery_id = None
    try:
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
    except Exception:
        log.exception("Delivery logging failed for user_id=%s (email was sent successfully)", user_id)

    return {
        "sent": True,
        "suggestions_included": len(top5),
        "delivery_id": delivery_id,
        "mark_sent_failed": mark_failed,  # True = duplicate send risk next run, check logs
    }

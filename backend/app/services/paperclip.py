"""Paperclip provisioning helpers.

Creates per-user Paperclip companies + agents during onboarding.
Safe to call multiple times — reuses existing IDs if already set.
"""
from __future__ import annotations

import logging
import os
from uuid import UUID

import httpx

from app.config import settings
from app.database import supabase

log = logging.getLogger(__name__)

DEFAULT_BUDGET_MONTHLY_CENTS = int(os.getenv("PAPERCLIP_DEFAULT_BUDGET_CENTS", "5000"))
HEARTBEAT_INTERVAL_SEC = int(os.getenv("PAPERCLIP_HEARTBEAT_INTERVAL_SEC", "3600"))


def _build_headers() -> dict[str, str]:
    paperclip_api_key = os.getenv("PAPERCLIP_API_KEY")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if paperclip_api_key:
        headers["Authorization"] = f"Bearer {paperclip_api_key}"
    elif (
        not settings.paperclip_base_url.startswith("http://localhost")
        and not settings.paperclip_base_url.startswith("http://127.")
    ):
        raise RuntimeError(
            f"PAPERCLIP_API_KEY must be set when PAPERCLIP_BASE_URL is non-local ({settings.paperclip_base_url})"
        )
    return headers


async def provision_user(user_id: str, user_name: str, firm: str | None = None) -> dict:
    """Ensure the given user has a Paperclip company + agent.

    Idempotent: if ``paperclip_company_id`` or ``paperclip_agent_id`` is
    already set on the user row, the existing value is reused.

    Returns a dict with keys:
        ``paperclip_company_id``, ``paperclip_agent_id``, ``created`` (bool)
    """
    # Fetch current Paperclip IDs so we can be idempotent
    row_result = (
        supabase.table("users")
        .select("paperclip_company_id, paperclip_agent_id")
        .eq("id", user_id)
        .single()
        .execute()
    )
    existing = row_result.data or {}
    existing_company_id: str | None = existing.get("paperclip_company_id")
    existing_agent_id: str | None = existing.get("paperclip_agent_id")

    if existing_company_id and existing_agent_id:
        log.info(
            "provision_user: user %s already provisioned (company=%s agent=%s)",
            user_id,
            existing_company_id,
            existing_agent_id,
        )
        return {
            "paperclip_company_id": existing_company_id,
            "paperclip_agent_id": existing_agent_id,
            "created": False,
        }

    headers = _build_headers()

    company_name = f"{user_name} ({firm or 'Independent'})"

    async with httpx.AsyncClient(
        base_url=settings.paperclip_base_url,
        headers=headers,
        timeout=30.0,
    ) as client:
        # ── Company ─────────────────────────────────────────────────────────
        if existing_company_id:
            paperclip_company_id = existing_company_id
            log.info("provision_user: reusing company %s for user %s", paperclip_company_id, user_id)
        else:
            company_resp = await client.post("/api/companies", json={"name": company_name})
            company_resp.raise_for_status()
            paperclip_company_id = company_resp.json()["id"]
            log.info("provision_user: created company %s for user %s", paperclip_company_id, user_id)

            # Persist immediately — crash-safe for half-bootstrapped retries
            supabase.table("users").update(
                {"paperclip_company_id": paperclip_company_id}
            ).eq("id", user_id).execute()

        # ── Agent ────────────────────────────────────────────────────────────
        if existing_agent_id:
            paperclip_agent_id = existing_agent_id
            log.info("provision_user: reusing agent %s for user %s", paperclip_agent_id, user_id)
        else:
            agent_resp = await client.post(
                f"/api/companies/{paperclip_company_id}/agents",
                json={
                    "name": "OpenLaw Agent",
                    "adapterType": "process",
                    "runtimeConfig": {
                        "heartbeat": {
                            "enabled": True,
                            "intervalSec": HEARTBEAT_INTERVAL_SEC,
                        }
                    },
                    "budgetMonthlyCents": DEFAULT_BUDGET_MONTHLY_CENTS,
                },
            )
            agent_resp.raise_for_status()
            paperclip_agent_id = agent_resp.json()["id"]
            log.info("provision_user: created agent %s for user %s", paperclip_agent_id, user_id)

            # Persist agent_id
            supabase.table("users").update(
                {"paperclip_agent_id": paperclip_agent_id}
            ).eq("id", user_id).execute()

    return {
        "paperclip_company_id": paperclip_company_id,
        "paperclip_agent_id": paperclip_agent_id,
        "created": True,
    }


async def create_outreach_issue(
    paperclip_company_id: str,
    suggestion: dict,
) -> dict:
    """Create a Paperclip issue for an approved outreach suggestion.

    Returns a dict with ``issue_id``, ``issue_identifier``, and ``issue_url``.

    Callers must ensure idempotency — this function always creates a new issue.
    The router guards against duplicates by checking ``paperclip_issue_id``
    before calling.
    """
    contact = suggestion.get("contact") or suggestion.get("contacts") or {}
    if isinstance(contact, list):
        contact = contact[0] if contact else {}

    contact_name = contact.get("name", "Unknown contact")
    subject = suggestion.get("subject") or f"Outreach to {contact_name}"

    body_parts: list[str] = []
    if suggestion.get("trigger_summary"):
        body_parts.append(f"**Why now:** {suggestion['trigger_summary']}")
    draft = suggestion.get("edited_body") or suggestion.get("body") or suggestion.get("draft_message") or ""
    if draft:
        body_parts.append(f"**Draft message:**\n\n{draft}")
    signal_id = suggestion.get("signal_id")
    if signal_id:
        body_parts.append(f"**OpenLaw signal:** {signal_id}")

    headers = _build_headers()

    async with httpx.AsyncClient(
        base_url=settings.paperclip_base_url,
        headers=headers,
        timeout=30.0,
    ) as client:
        resp = await client.post(
            f"/api/companies/{paperclip_company_id}/issues",
            json={
                "title": f"Review outreach: {subject}",
                "description": "\n\n".join(body_parts),
                "status": "todo",
                "priority": "high",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    issue_id = data["id"]
    issue_identifier = data.get("identifier")
    issue_url = data.get("url") or (
        f"{settings.paperclip_base_url.rstrip('/')}/companies/{paperclip_company_id}/issues/{issue_id}"
    )

    log.info(
        "create_outreach_issue: created issue %s for suggestion %s",
        issue_id,
        suggestion.get("id"),
    )

    return {
        "issue_id": issue_id,
        "issue_identifier": issue_identifier,
        "issue_url": issue_url,
    }

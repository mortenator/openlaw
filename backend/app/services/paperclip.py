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

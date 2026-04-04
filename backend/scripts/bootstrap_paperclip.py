"""Bootstrap script: create Paperclip companies + agents for all existing OpenLaw users.

Usage:
    cd backend
    python -m scripts.bootstrap_paperclip
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Allow running from the backend/ directory directly
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from app.config import settings
from app.database import supabase

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Monthly token budget per agent in cents. Override via PAPERCLIP_DEFAULT_BUDGET_CENTS env var.
# Default: 5000 cents = $50/month.
DEFAULT_BUDGET_MONTHLY_CENTS = int(os.getenv("PAPERCLIP_DEFAULT_BUDGET_CENTS", "5000"))
HEARTBEAT_INTERVAL_SEC = int(os.getenv("PAPERCLIP_HEARTBEAT_INTERVAL_SEC", "3600"))


async def bootstrap_user(
    client: httpx.AsyncClient,
    user: dict,
) -> dict:
    """Create a Paperclip company + agent for a single user. Returns result summary."""
    user_id: str = user["id"]
    user_name: str = user.get("name") or "Unknown"
    firm: str | None = user.get("firm")

    company_name = f"{user_name} ({firm or 'Independent'})"

    # Reuse existing company/agent IDs if already created (handles half-bootstrapped retry)
    existing_company_id: str | None = user.get("paperclip_company_id")
    existing_agent_id: str | None = user.get("paperclip_agent_id")

    if existing_company_id:
        paperclip_company_id = existing_company_id
        log.info("Reusing existing Paperclip company %s for user %s", paperclip_company_id, user_id)
    else:
        # POST /api/companies
        company_resp = await client.post(
            "/api/companies",
            json={"name": company_name},
        )
        company_resp.raise_for_status()
        paperclip_company_id = company_resp.json()["id"]
        log.info("Created Paperclip company %s for user %s", paperclip_company_id, user_id)

    # Persist company_id immediately (only when freshly created) so a crash before agent
    # creation doesn't leave the user company-less on retry.
    if not existing_company_id:
        patch_company = (
            supabase.table("users")
            .update({"paperclip_company_id": paperclip_company_id})
            .eq("id", user_id)
            .execute()
        )
        if not patch_company.data:
            raise RuntimeError(f"Failed to patch paperclip_company_id for user {user_id} in Supabase")

    if existing_agent_id:
        paperclip_agent_id = existing_agent_id
        log.info("Reusing existing Paperclip agent %s for user %s", paperclip_agent_id, user_id)
    else:
        # POST /api/companies/{id}/agents
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
        log.info("Created Paperclip agent %s for user %s", paperclip_agent_id, user_id)

    # Persist agent_id only when freshly created
    if not existing_agent_id:
        patch_agent = (
            supabase.table("users")
            .update({"paperclip_agent_id": paperclip_agent_id})
            .eq("id", user_id)
            .execute()
        )
        if not patch_agent.data:
            raise RuntimeError(f"Failed to patch paperclip_agent_id for user {user_id} in Supabase")

    return {
        "user_id": user_id,
        "user_name": user_name,
        "paperclip_company_id": paperclip_company_id,
        "paperclip_agent_id": paperclip_agent_id,
        "status": "ok",
    }


async def main() -> None:
    # Fetch users missing either Paperclip ID — handles half-bootstrapped users on retry
    result = (
        supabase.table("users")
        .select("id, name, firm, paperclip_company_id, paperclip_agent_id")
        .or_("paperclip_company_id.is.null,paperclip_agent_id.is.null")
        .execute()
    )
    users: list[dict] = result.data or []

    if not users:
        log.info("No users to bootstrap — all users already have Paperclip IDs.")
        return

    log.info("Bootstrapping %d user(s)…", len(users))

    summaries: list[dict] = []
    errors: list[dict] = []

    paperclip_api_key = os.getenv("PAPERCLIP_API_KEY")
    headers = {"Content-Type": "application/json"}
    if paperclip_api_key:
        headers["Authorization"] = f"Bearer {paperclip_api_key}"
    elif (
        not settings.paperclip_base_url.startswith("http://localhost")
        and not settings.paperclip_base_url.startswith("http://127.")
    ):
        log.warning(
            "PAPERCLIP_BASE_URL is non-local (%s) but PAPERCLIP_API_KEY is not set. "
            "Requests may fail if Paperclip is in 'authenticated' mode.",
            settings.paperclip_base_url,
        )

    async with httpx.AsyncClient(
        base_url=settings.paperclip_base_url,
        headers=headers,
        timeout=30.0,
    ) as client:
        for user in users:
            try:
                summary = await bootstrap_user(client, user)
                summaries.append(summary)
            except Exception as exc:
                log.error("Failed to bootstrap user %s: %s", user.get("id"), exc)
                errors.append({"user_id": user.get("id"), "error": str(exc)})

    print("\n── Bootstrap Summary ──────────────────────────────")
    print(f"  Succeeded : {len(summaries)}")
    print(f"  Failed    : {len(errors)}")

    for s in summaries:
        print(
            f"  ✓ {s['user_name']} ({s['user_id']}) → "
            f"company={s['paperclip_company_id']} agent={s['paperclip_agent_id']}"
        )
    for e in errors:
        print(f"  ✗ user={e['user_id']} error={e['error']}")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

"""Migration script: enable Paperclip heartbeats on all existing agents.

Reads every user with a paperclip_agent_id, PATCHes the agent's runtimeConfig
to enable heartbeat scheduling, replacing the old user_crons + Railway cron
approach.

Usage:
    cd backend
    python -m scripts.enable_heartbeats

Idempotent: re-running on already-enabled agents is a no-op (PATCH is safe).
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SEC = int(os.getenv("PAPERCLIP_HEARTBEAT_INTERVAL_SEC", "3600"))


async def main() -> None:
    from app.database import supabase

    result = (
        supabase.table("users")
        .select("id, paperclip_company_id, paperclip_agent_id")
        .not_.is_("paperclip_agent_id", "null")
        .execute()
    )
    users: list[dict] = result.data or []

    if not users:
        log.info("No users with Paperclip agents found — nothing to migrate.")
        return

    log.info("Enabling heartbeats on %d agent(s)…", len(users))

    paperclip_api_key = os.getenv("PAPERCLIP_API_KEY")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if paperclip_api_key:
        headers["Authorization"] = f"Bearer {paperclip_api_key}"

    ok = 0
    errors = 0

    async with httpx.AsyncClient(
        base_url=settings.paperclip_base_url,
        headers=headers,
        timeout=30.0,
    ) as client:
        for user in users:
            company_id = user["paperclip_company_id"]
            agent_id = user["paperclip_agent_id"]
            user_id = user["id"]

            if not company_id or not agent_id:
                log.warning("Skipping user %s — missing company or agent ID", user_id)
                continue

            try:
                resp = await client.patch(
                    f"/api/companies/{company_id}/agents/{agent_id}",
                    json={
                        "runtimeConfig": {
                            "heartbeat": {
                                "enabled": True,
                                "intervalSec": HEARTBEAT_INTERVAL_SEC,
                            }
                        }
                    },
                )
                resp.raise_for_status()
                log.info("Enabled heartbeat for user %s (agent %s)", user_id, agent_id)
                ok += 1
            except Exception as exc:
                log.error("Failed to enable heartbeat for user %s: %s", user_id, exc)
                errors += 1

    print(f"\n-- Heartbeat migration complete: {ok} OK, {errors} failed --")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

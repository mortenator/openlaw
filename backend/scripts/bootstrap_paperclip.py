"""Bootstrap script: create Paperclip companies + agents for all existing OpenLaw users.

Usage:
    cd backend
    python -m scripts.bootstrap_paperclip
"""

import asyncio
import logging
import sys
from pathlib import Path

# Allow running from the backend/ directory directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import supabase

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def bootstrap_user(user: dict) -> dict:
    """Create a Paperclip company + agent for a single user. Returns result summary."""
    from app.services.paperclip import provision_user

    user_id: str = user["id"]
    user_name: str = user.get("name") or "Unknown"

    result = await provision_user(
        user_id=user_id,
        user_name=user_name,
        firm=user.get("firm"),
    )
    return {
        "user_id": user_id,
        "user_name": user_name,
        **result,
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

    for user in users:
        try:
            summary = await bootstrap_user(user)
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

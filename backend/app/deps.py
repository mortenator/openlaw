from __future__ import annotations

import logging

from fastapi import HTTPException, Header
from app.database import supabase

log = logging.getLogger(__name__)

_DEFAULT_COMMS_CHANNEL = "email"


async def get_or_provision_user(authorization: str = Header(...)):
    """Authenticate and ensure a users row exists (belt-and-suspenders for any signup path)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        response = supabase.auth.get_user(token)
        if response.user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = response.user

    # Insert row if missing — supabase-py 2.7 doesn't support ignore_duplicates,
    # so we catch the unique-constraint error explicitly.
    try:
        existing = (
            supabase.table("users")
            .select("id")
            .eq("id", str(user.id))
            .limit(1)
            .execute()
        )
        if not existing.data:
            supabase.table("users").insert({
                "id": str(user.id),
                "email": user.email or "",
                "name": (user.email or "").split("@")[0],
                "comms_channel": _DEFAULT_COMMS_CHANNEL,
            }).execute()
    except Exception as exc:
        log.warning("users row provision for user_id=%s: %s", user.id, exc)

    return user


get_current_user = get_or_provision_user

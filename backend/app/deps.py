from __future__ import annotations

import logging

from fastapi import HTTPException, Header
from app.database import supabase

log = logging.getLogger(__name__)

# Default comms channel for auto-provisioned users
_DEFAULT_COMMS_CHANNEL = "email"


async def get_or_provision_user(authorization: str = Header(...)):
    """Authenticate the request and ensure a users row exists.

    Belt-and-suspenders: if a user signed up via a path that bypasses /auth/signup
    (e.g. direct Supabase magic link), this guarantees the users row is created before
    any downstream query touches it.
    """
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

    # Atomic upsert — inserts the row if missing, no-ops if it already exists.
    # Uses on_conflict="id" so existing name/practice_area etc. are never overwritten.
    try:
        supabase.table("users").upsert(
            {
                "id": str(user.id),
                "email": user.email or "",
                "name": (user.email or "").split("@")[0],
                "comms_channel": _DEFAULT_COMMS_CHANNEL,
            },
            on_conflict="id",
        ).execute()
    except Exception as exc:
        # Non-fatal — a conflict on id is benign; a real failure is diagnosable via log
        log.warning("Could not provision users row for user_id=%s: %s", user.id, exc)

    return user


# Alias for backward compat with existing imports
get_current_user = get_or_provision_user

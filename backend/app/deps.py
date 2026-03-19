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

    # Insert a minimal users row if one doesn't exist yet.
    # Using PostgREST's ignoreDuplicates (INSERT ... ON CONFLICT DO NOTHING) so we
    # never touch name/practice_area/comms_channel for users who have already onboarded.
    try:
        supabase.table("users").insert(
            {
                "id": str(user.id),
                "email": user.email or "",
                "name": (user.email or "").split("@")[0],
                "comms_channel": _DEFAULT_COMMS_CHANNEL,
            },
        ).execute()
    except Exception as exc:
        # A unique-constraint conflict (row already exists) is the expected happy path.
        # Log at debug so real failures (DB down, schema mismatch) are still visible.
        log.debug("users row provision for user_id=%s: %s", user.id, exc)

    return user


# Alias for backward compat with existing imports
get_current_user = get_or_provision_user

from __future__ import annotations

import logging
import re

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

    # INSERT ... ON CONFLICT DO NOTHING — never overwrites existing profile fields.
    # ignore_duplicates=True is the supabase-py equivalent of PostgREST's
    # Prefer: return=minimal + on_conflict resolution that does nothing on conflict.
    try:
        supabase.table("users").insert(
            {
                "id": str(user.id),
                "email": user.email or "",
                "name": re.sub(r"[^\w\s\-.]", "", (user.email or "").split("@")[0])[:100],
                "comms_channel": _DEFAULT_COMMS_CHANNEL,
            },
            ignore_duplicates=True,
        ).execute()
    except Exception as exc:
        # ignore_duplicates=True means conflicts are handled DB-side.
        # Any exception here is a real failure (DB down, schema mismatch) — warn loudly.
        log.warning("Failed to provision users row for user_id=%s: %s", user.id, exc)

    return user


# Alias for backward compat with existing imports
get_current_user = get_or_provision_user

from __future__ import annotations

import logging

from fastapi import HTTPException, Header
from app.database import supabase

log = logging.getLogger(__name__)


async def get_current_user(authorization: str = Header(...)):
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

    # Ensure a users row exists — safety net for any signup path that bypasses /auth/signup.
    # Uses INSERT ... ON CONFLICT DO NOTHING equivalent: only inserts if missing.
    try:
        existing = supabase.table("users").select("id").eq("id", str(user.id)).execute()
        if not existing.data:
            supabase.table("users").insert({
                "id": str(user.id),
                "email": user.email or "",
                "name": (user.email or "").split("@")[0],
                "comms_channel": "email",
            }).execute()
    except Exception:
        log.warning("Could not provision users row for user_id=%s", user.id)

    return user

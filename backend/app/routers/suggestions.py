from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.database import supabase
from app.deps import get_current_user
from app.services.paperclip import create_outreach_issue

log = logging.getLogger(__name__)

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


class SuggestionUpdate(BaseModel):
    status: str


@router.get("")
async def list_suggestions(
    status: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
) -> list[dict]:
    query = (
        supabase.table("outreach_suggestions")
        .select("*, contact:contacts(*)")
        .eq("user_id", current_user.id)
    )
    if status is not None:
        query = query.eq("status", status)
    result = query.order("created_at", desc=True).execute()
    return result.data or []


@router.put("/{suggestion_id}")
async def update_suggestion(
    suggestion_id: str,
    payload: SuggestionUpdate,
    current_user=Depends(get_current_user),
) -> dict:
    valid_statuses = {"pending", "approved", "dismissed", "sent"}
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {valid_statuses}",
        )

    # ── Fetch the suggestion first (needed for idempotency + issue body) ──
    fetch_result = (
        supabase.table("outreach_suggestions")
        .select("*, contact:contacts(*)")
        .eq("id", suggestion_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    if not fetch_result.data:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion = fetch_result.data[0]

    # ── Approve flow: create Paperclip issue for review ──────────────────
    update_fields: dict = {"status": payload.status}

    if payload.status == "approved":
        # Idempotent: skip if a Paperclip issue already exists
        if not suggestion.get("paperclip_issue_id"):
            # Look up user's Paperclip company
            user_row = (
                supabase.table("users")
                .select("paperclip_company_id")
                .eq("id", str(current_user.id))
                .execute()
            )
            user_data = user_row.data or []
            company_id = user_data[0].get("paperclip_company_id") if user_data else None
            if not company_id:
                raise HTTPException(
                    status_code=422,
                    detail="User has no Paperclip company — complete onboarding first",
                )

            try:
                issue = await create_outreach_issue(company_id, suggestion)
            except Exception:
                log.exception(
                    "Failed to create Paperclip issue for suggestion %s",
                    suggestion_id,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Could not create review issue in Paperclip — please try again",
                )

            try:
                persist_issue_result = (
                    supabase.table("outreach_suggestions")
                    .update({
                        "paperclip_issue_id": issue["issue_id"],
                        "paperclip_issue_identifier": issue.get("issue_identifier"),
                        "paperclip_issue_url": issue["issue_url"],
                    })
                    .eq("id", suggestion_id)
                    .eq("user_id", current_user.id)
                    .execute()
                )
            except Exception:
                log.exception(
                    "Created Paperclip issue %s for suggestion %s but failed to persist the issue id",
                    issue["issue_id"],
                    suggestion_id,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Outreach issue was created in Paperclip but could not be saved — do not retry",
                )

            if not persist_issue_result.data:
                log.error(
                    "Created Paperclip issue %s for suggestion %s but no suggestion row was updated",
                    issue["issue_id"],
                    suggestion_id,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Outreach issue was created in Paperclip but could not be saved — do not retry",
                )
            log.info(
                "Created Paperclip issue %s for suggestion %s, persisting link in OpenLaw",
                issue["issue_id"],
                suggestion_id,
            )

    try:
        result = (
            supabase.table("outreach_suggestions")
            .update(update_fields)
            .eq("id", suggestion_id)
            .eq("user_id", current_user.id)
            .execute()
        )
    except Exception:
        log.exception("Failed to persist updated suggestion state for %s", suggestion_id)
        raise HTTPException(
            status_code=502,
            detail="Failed to persist suggestion update",
        )

    if not result.data:
        raise HTTPException(
            status_code=502,
            detail="Failed to persist suggestion update",
        )
    return result.data[0]

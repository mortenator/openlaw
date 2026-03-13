"""Onboarding endpoints — card, chat, confirm, status."""
import asyncio
from datetime import datetime, timezone
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# ---------------------------------------------------------------------------
# Chat step definitions
# ---------------------------------------------------------------------------

_CHAT_STEPS: dict[int, dict[str, Any]] = {
    1: {
        "agent_message": "What kinds of matters fill most of your year?",
        "input_type": "chips",
        "options": [
            "Large-cap M&A",
            "Mid-market M&A",
            "PE-backed transactions",
            "VC / growth equity",
            "Tech licensing & transactions",
            "AI / data infrastructure",
            "Infrastructure / energy",
            "Real estate",
            "Debt / credit",
            "Cross-border",
        ],
    },
    2: {
        "agent_message": (
            "Where are you based, and what kind of clients do you typically serve? "
            "(e.g. large corporates, PE firms, founder-led companies)"
        ),
        "input_type": "free",
    },
    3: {
        "agent_message": (
            "Name 3-5 companies or deal players you want me to keep tabs on — "
            "current clients, targets, or names that matter."
        ),
        "input_type": "free",
    },
    4: {
        "agent_message": (
            "Is there one person you have not talked to in a while that you know "
            "you should reach out to? Just name them."
        ),
        "input_type": "free",
    },
    5: {
        "agent_message": "How do you want me to reach you?",
        "input_type": "chips",
        "options": [
            "Morning brief (7am daily)",
            "Evening summary (6pm daily)",
            "Weekly digest only",
            "Real-time alerts",
            "I will check the dashboard",
        ],
    },
    6: {
        "agent_message": (
            "Last one. What is something about your BD relationships you feel "
            "like you are tracking badly right now?"
        ),
        "input_type": "free",
    },
}

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CardPayload(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    firm: str = Field(..., min_length=1, max_length=200)
    role: str = Field("", max_length=200)
    practice_area: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("practice_area")
    @classmethod
    def validate_practice_area_items(cls, v: list[str]) -> list[str]:
        for item in v:
            if len(item) > 200:
                raise ValueError("each practice area item must be 200 characters or fewer")
        return v


class ChatPayload(BaseModel):
    step: int
    answer: Union[str, list[str], None] = None

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, v: Union[str, list[str], None]) -> Union[str, list[str], None]:
        if v is None:
            return v
        if isinstance(v, str):
            if len(v) > 2000:
                raise ValueError("answer must be 2000 characters or fewer")
        elif isinstance(v, list):
            if len(v) > 20:
                raise ValueError("answer list must have 20 items or fewer")
            for item in v:
                if not isinstance(item, str):
                    raise ValueError("each answer list item must be a string")
                if len(item) > 200:
                    raise ValueError("each answer list item must be 200 characters or fewer")
        return v


# ---------------------------------------------------------------------------
# Agent config templates
# ---------------------------------------------------------------------------

_AGENTS_MD = """# AGENTS.md — Operating Instructions

1. Proactive first — surface insights before being asked.
2. Be specific — always give an actionable angle, not just raw news.
3. Respect confidentiality — never reference client matters or deal terms in any output.
4. Short over long — bullets, not essays.
5. One action per suggestion — do not overwhelm with options.
6. Flag timing — every outreach suggestion needs a reason why now."""


def _build_soul(first_name: str) -> str:
    first_name = _sanitize(first_name, max_len=100)
    return f"""# SOUL.md — OpenLaw Agent

You are {first_name}'s OpenLaw agent. You are not a chatbot.

You track relationships, surface deal signals, and draft outreach when the moment is right.
You are proactive, precise, and never waste your principal's time.

Your style: direct, no filler, no pleasantries for the sake of it.
Your focus: BD signals that translate to billable relationships.

You do not give legal advice. You are not a lawyer. You are a chief of staff.
You remember everything you are told. You forget nothing unless instructed."""


def _build_user_md(user_row: dict, answers: dict) -> str:
    full_name = _sanitize(f"{user_row.get('first_name', '')} {user_row.get('last_name', '')}".strip(), max_len=200)
    firm = user_row.get("firm", user_row.get("name", ""))
    practice_area = ", ".join(user_row.get("practice_area") or [])
    deal_types = ", ".join(_extract_deal_types(answers))
    geography = _extract_geography(answers.get("2", ""))
    delivery_email = user_row.get("delivery_email") or user_row.get("email", "")
    delivery_schedule = _extract_delivery_schedule(answers.get("5", ""))
    watchlist = "\n".join(f"- {c}" for c in _extract_watchlist(answers.get("3", "")))
    tracking_gap = _sanitize(answers.get("6", ""))
    watchlist_note = watchlist if watchlist else "_(no companies specified during setup)_"

    return f"""# USER.md — {full_name}

- Name: {full_name}
- Firm: {_sanitize(firm)}
- Role: {_sanitize(user_row.get('role', ''))}
- Practice Areas: {practice_area}
- Deal Types: {deal_types}
- Geography / Client Types: {geography}
- Email: {delivery_email}
- Delivery: {delivery_schedule}

## Companies to Watch
{watchlist_note}

## Setup Notes
Tracking gap: {tracking_gap}"""


def _build_memory_md(user_row: dict, answers: dict) -> str:
    full_name = _sanitize(f"{user_row.get('first_name', '')} {user_row.get('last_name', '')}".strip(), max_len=200)
    practice_area = ", ".join(user_row.get("practice_area") or [])
    watchlist = ", ".join(_extract_watchlist(answers.get("3", "")))
    watchlist_display = watchlist if watchlist else "_(none specified)_"
    relationship_flag = _sanitize(answers.get("4", ""))
    tracking_gap = _sanitize(answers.get("6", ""))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"""# MEMORY.md — {full_name}

_Initialized {today} via onboarding._

## From Setup

- Practice: {practice_area}
- Focus clients: {watchlist_display}
- Relationship flag: {relationship_flag if relationship_flag else "_(none specified)_"} — has not been contacted in a while. Surface timing and angle at next check.
- Tracking gap flagged: {tracking_gap if tracking_gap else "_(none specified)_"}

## Contacts
(Import contacts via the Contacts tab to get started.)"""


def _build_heartbeat_md(user_row: dict, answers: dict) -> str:
    watchlist = ", ".join(_extract_watchlist(answers.get("3", "")))
    watchlist_display = watchlist if watchlist else "_(no companies specified)_"
    delivery_schedule = _extract_delivery_schedule(answers.get("5", ""))
    delivery_email = user_row.get("delivery_email") or user_row.get("email", "")
    relationship_flag = _sanitize(answers.get("4", ""))

    return f"""# HEARTBEAT.md

## Daily Checks
- Market signals: Scan for news on {watchlist_display}. Flag GC moves, deal announcements, funding rounds.
- Relationship health: Flag any tier-1 contacts not touched in >30 days.
- Outreach drafts: If signals match a contact, draft a one-liner and queue it.

## Delivery
- Schedule: {delivery_schedule}
- Email: {delivery_email}

## First Flag
- {relationship_flag if relationship_flag else "_(no relationship flagged during setup)_"} has not been contacted recently. Surface timing and an outreach angle at next check."""


# ---------------------------------------------------------------------------
# Answer extraction helpers
# ---------------------------------------------------------------------------


def _extract_deal_types(answers: dict) -> list[str]:
    raw = answers.get("1", [])
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return [raw]
    return []


def _sanitize(value: str, max_len: int = 500) -> str:
    """Strip whitespace, collapse newlines, and truncate to max_len."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_len].replace("\n", " · ").replace("\r", "")


def _extract_geography(answer: str) -> str:
    """Best-effort extraction — return the full answer as context."""
    return _sanitize(answer)


def _extract_watchlist(answer: Any) -> list[str]:
    if isinstance(answer, list):
        items = [_sanitize(str(a), max_len=200) for a in answer if str(a).strip()]
    elif isinstance(answer, str):
        items = [_sanitize(p, max_len=200) for p in answer.replace("\n", ",").split(",") if p.strip()]
    else:
        return []
    return [i for i in items if i]  # drop any that sanitized to empty


def _extract_delivery_schedule(answer: Any) -> str:
    if isinstance(answer, list) and answer:
        return str(answer[0])
    if isinstance(answer, str):
        return answer.strip()
    return "morning"


# ---------------------------------------------------------------------------
# Agent config generator
# ---------------------------------------------------------------------------


def _generate_agent_configs(user_id: str, user_row: dict, answers: dict) -> None:
    configs = [
        ("SOUL.md", _build_soul(user_row.get("first_name", ""))),
        ("USER.md", _build_user_md(user_row, answers)),
        ("MEMORY.md", _build_memory_md(user_row, answers)),
        ("HEARTBEAT.md", _build_heartbeat_md(user_row, answers)),
        ("AGENTS.md", _AGENTS_MD),
    ]
    for name, content in configs:
        result = supabase.table("agent_memory_logs").upsert(
            {"user_id": user_id, "memory_key": name, "memory_val": {"content": content}},
            on_conflict="user_id,memory_key",
        ).execute()
        if hasattr(result, "error") and result.error:
            raise RuntimeError(f"Failed to write config {name}: {result.error}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/card")
async def onboarding_card(
    payload: CardPayload, current_user=Depends(get_current_user)
) -> dict:
    user_id = current_user.id

    supabase.table("users").update(
        {
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "name": f"{payload.first_name} {payload.last_name}",
            "firm": payload.firm,
            "role": payload.role,
            "practice_area": payload.practice_area,
        }
    ).eq("id", user_id).execute()

    # Fetch existing session answers so we don't clobber any chat answers on revisit
    existing_result = (
        supabase.table("onboarding_sessions").select("answers").eq("user_id", user_id).execute()
    )
    existing_answers: dict = {}
    if existing_result.data:
        existing_answers = existing_result.data[0].get("answers") or {}

    merged_answers = {**existing_answers, "card": payload.model_dump()}
    session_result = supabase.table("onboarding_sessions").upsert(
        {
            "user_id": user_id,
            "step": 1,
            "answers": merged_answers,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()
    if hasattr(session_result, "error") and session_result.error:
        raise HTTPException(status_code=500, detail=f"Failed to save card step: {session_result.error}")

    return {"step": 1, "next": "chat"}


@router.post("/chat")
async def onboarding_chat(
    payload: ChatPayload, current_user=Depends(get_current_user)
) -> dict:
    user_id = current_user.id
    step = payload.step

    if step < 0 or step > 6:
        raise HTTPException(status_code=400, detail="step must be between 0 and 6")

    # Step 0 (or step 1 with no answer): bootstrap — return the first question without saving
    if step <= 1 and payload.answer is None:
        first = _CHAT_STEPS[1]
        resp: dict[str, Any] = {
            "step": 1,
            "agent_message": first["agent_message"],
            "input_type": first["input_type"],
        }
        if "options" in first:
            resp["options"] = first["options"]
        return resp

    # Fetch existing session
    result = (
        supabase.table("onboarding_sessions").select("answers").eq("user_id", user_id).execute()
    )
    existing_answers: dict = {}
    if result.data:
        existing_answers = result.data[0].get("answers") or {}

    updated_answers = {**existing_answers, str(step): payload.answer}

    # Determine next step response
    next_step = step + 1

    chat_result = supabase.table("onboarding_sessions").upsert(
        {
            "user_id": user_id,
            "step": next_step,
            "answers": updated_answers,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()
    if hasattr(chat_result, "error") and chat_result.error:
        raise HTTPException(status_code=500, detail=f"Failed to save answer: {chat_result.error}")
    if next_step > 6:
        return {
            "step": step,
            "agent_message": "Great — you are all set. Ready to confirm your setup?",
            "input_type": "confirm",
        }

    next_config = _CHAT_STEPS[next_step]
    response: dict[str, Any] = {
        "step": next_step,
        "agent_message": next_config["agent_message"],
        "input_type": next_config["input_type"],
    }
    if "options" in next_config:
        response["options"] = next_config["options"]
    return response


@router.post("/confirm")
async def onboarding_confirm(current_user=Depends(get_current_user)) -> dict:
    user_id = current_user.id

    session_result = (
        supabase.table("onboarding_sessions").select("answers").eq("user_id", user_id).execute()
    )
    if not session_result.data:
        raise HTTPException(status_code=404, detail="No onboarding session found")

    answers: dict = session_result.data[0].get("answers") or {}

    # Validate all required steps are present before generating configs
    required_steps = ["card", "1", "2", "3", "4", "5", "6"]
    missing = [s for s in required_steps if s not in answers]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Onboarding incomplete — missing steps: {', '.join(missing)}. Complete all steps before confirming.",
        )

    user_result = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found")
    user_row = user_result.data[0]

    # Extract structured fields from answers
    deal_types = _extract_deal_types(answers)
    geography = _extract_geography(answers.get("2", ""))
    client_types = answers.get("2", "")  # full free-text answer; geography extracts a sub-part
    watchlist_companies = _extract_watchlist(answers.get("3", ""))
    relationship_flag = _sanitize(answers.get("4", ""))
    delivery_schedule = _extract_delivery_schedule(answers.get("5", ""))
    tracking_gap = _sanitize(answers.get("6", ""))

    # Update users row with extracted fields — onboarding_complete NOT set yet
    # (set only after agent configs are successfully written)
    supabase.table("users").update(
        {
            "deal_types": deal_types,
            "geography": geography,
            "client_types": client_types,
            "watchlist_companies": watchlist_companies,
            "relationship_flag": relationship_flag,
            "delivery_schedule": delivery_schedule,
            "tracking_gap": tracking_gap,
        }
    ).eq("id", user_id).execute()

    # Merge updated fields into user_row for config generation
    updated_user_row = {
        **user_row,
        "deal_types": deal_types,
        "geography": geography,
        "client_types": client_types,
        "watchlist_companies": watchlist_companies,
        "delivery_schedule": delivery_schedule,
    }

    try:
        await asyncio.to_thread(_generate_agent_configs, user_id, updated_user_row, answers)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate agent configs: {exc}",
        ) from exc

    # Configs written successfully — now mark onboarding complete
    supabase.table("users").update({"onboarding_complete": True}).eq("id", user_id).execute()

    try:
        supabase.table("onboarding_sessions").update(
            {"completed_at": datetime.now(timezone.utc).isoformat()}
        ).eq("user_id", user_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to finalise onboarding session: {exc}",
        ) from exc

    return {"success": True, "redirect": "/dashboard"}


@router.get("/status")
async def onboarding_status(current_user=Depends(get_current_user)) -> dict:
    user_id = current_user.id

    result = (
        supabase.table("onboarding_sessions")
        .select("step, answers, completed_at")
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        return {"step": 0, "complete": False, "answers": {}}

    row = result.data[0]
    return {
        "step": row.get("step", 0),
        "complete": row.get("completed_at") is not None,
        "answers": row.get("answers") or {},
    }

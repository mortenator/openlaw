"""Onboarding endpoints — multi-step flow with CSV contact import.

Endpoints:
  GET  /onboarding/status  — current onboarding state
  POST /onboarding/step    — submit answer for a step
  POST /onboarding/card    — (legacy) profile card submission
  POST /onboarding/chat    — (legacy) chat-based Q&A
  POST /onboarding/confirm — (legacy) finalize onboarding
"""

import asyncio
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Union

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.database import supabase
from app.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOTAL_STEPS = 5

PRACTICE_AREA_OPTIONS = [
    "M&A",
    "Tech Transactions",
    "PE/VC",
    "Infrastructure",
    "Real Estate",
    "Finance & Credit",
    "Litigation",
    "Cross-border",
    "AI / Data",
    "Other",
]

# Max CSV size: 500 KB (generous for contact lists)
MAX_CSV_SIZE = 500_000

# Max number of contacts parsed from a single CSV upload
MAX_CSV_ROWS = 500

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StepPayload(BaseModel):
    step: int = Field(..., ge=1, le=TOTAL_STEPS)
    answer: Any = None

    @field_validator("answer")
    @classmethod
    def validate_answer_size(cls, v: Any) -> Any:
        if v is None:
            return v
        if isinstance(v, str) and len(v) > MAX_CSV_SIZE:
            raise ValueError(f"answer must be {MAX_CSV_SIZE} characters or fewer")
        if isinstance(v, list) and len(v) > 50:
            raise ValueError("answer list must have 50 items or fewer")
        return v


# Legacy models (kept for backward compat with existing frontend)
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
# Sanitization / extraction helpers
# ---------------------------------------------------------------------------


def _sanitize(value: Any, max_len: int = 500) -> str:
    """Coerce to str, strip control chars + newlines, then truncate."""
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    if not isinstance(value, str):
        return ""
    return (
        value.strip()
        .replace("\x00", "")
        .replace("\n", " · ")
        .replace("\r", "")
        .replace("\t", " ")
    )[:max_len]


def _extract_watchlist(answer: Any) -> list[str]:
    if isinstance(answer, list):
        items = [_sanitize(str(a), max_len=200) for a in answer if str(a).strip()]
    elif isinstance(answer, str):
        items = [_sanitize(p, max_len=200) for p in answer.replace("\n", ",").split(",") if p.strip()]
    else:
        return []
    return [i for i in items if i]


def _extract_deal_types(answers: dict) -> list[str]:
    raw = answers.get("1", [])
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return [raw]
    return []


def _extract_delivery_schedule(answer: Any) -> str:
    if isinstance(answer, list) and answer:
        return _sanitize(str(answer[0]), max_len=200)
    if isinstance(answer, str):
        return _sanitize(answer, max_len=200)
    return "morning"


def _extract_geography(answer: str) -> str:
    return _sanitize(answer)


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
    sanitized_name = _sanitize(first_name, max_len=100)
    return f"""# SOUL.md — OpenLaw Agent

You are {sanitized_name}'s OpenLaw agent. You are not a chatbot.

You track relationships, surface deal signals, and draft outreach when the moment is right.
You are proactive, precise, and never waste your principal's time.

Your style: direct, no filler, no pleasantries for the sake of it.
Your focus: BD signals that translate to billable relationships.

You do not give legal advice. You are not a lawyer. You are a chief of staff.
You remember everything you are told. You forget nothing unless instructed."""


def _build_user_md(user_row: dict, answers: dict) -> str:
    full_name = _sanitize(
        f"{user_row.get('first_name', '')} {user_row.get('last_name', '')}".strip(),
        max_len=200,
    )
    firm = user_row.get("firm") or ""
    practice_areas = answers.get("step_2", [])
    if isinstance(practice_areas, list):
        practice_area_str = ", ".join(_sanitize(p, max_len=200) for p in practice_areas)
    else:
        practice_area_str = _sanitize(practice_areas)

    companies_raw = answers.get("step_3", "")
    if isinstance(companies_raw, list):
        watchlist = "\n".join(f"- {_sanitize(c, max_len=200)}" for c in companies_raw)
    elif isinstance(companies_raw, str):
        watchlist = "\n".join(
            f"- {_sanitize(c, max_len=200)}"
            for c in companies_raw.replace("\n", ",").split(",")
            if c.strip()
        )
    else:
        watchlist = ""
    watchlist_note = watchlist if watchlist else "_(no companies specified during setup)_"

    delivery_email = _sanitize(user_row.get("delivery_email") or user_row.get("email", ""), max_len=200)

    return f"""# USER.md — {full_name}

- Name: {full_name}
- Firm: {_sanitize(firm)}
- Role: {_sanitize(user_row.get('role', ''))}
- Practice Areas: {practice_area_str}
- Email: {delivery_email}

## Companies to Watch
{watchlist_note}"""


def _build_memory_md(user_row: dict, answers: dict) -> str:
    full_name = _sanitize(
        f"{user_row.get('first_name', '')} {user_row.get('last_name', '')}".strip(),
        max_len=200,
    )
    practice_areas = answers.get("step_2", [])
    if isinstance(practice_areas, list):
        practice_str = ", ".join(_sanitize(p, max_len=200) for p in practice_areas)
    else:
        practice_str = _sanitize(practice_areas)

    companies_raw = answers.get("step_3", "")
    watchlist = ", ".join(_extract_watchlist(companies_raw)) if companies_raw else "_(none specified)_"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"""# MEMORY.md — {full_name}

_Initialized {today} via onboarding._

## From Setup

- Practice: {practice_str}
- Focus clients: {watchlist}

## Contacts
(Contacts imported during onboarding are available in the Contacts tab.)"""


def _build_heartbeat_md(user_row: dict, answers: dict) -> str:
    companies_raw = answers.get("step_3", "")
    watchlist = ", ".join(_extract_watchlist(companies_raw)) if companies_raw else "_(no companies specified)_"
    delivery_email = _sanitize(user_row.get("delivery_email") or user_row.get("email", ""), max_len=200)

    return f"""# HEARTBEAT.md

## Daily Checks
- Market signals: Scan for news on {watchlist}. Flag GC moves, deal announcements, funding rounds.
- Relationship health: Flag any tier-1 contacts not touched in >30 days.
- Outreach drafts: If signals match a contact, draft a one-liner and queue it.

## Delivery
- Email: {delivery_email}"""


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
# CSV parsing
# ---------------------------------------------------------------------------


def _parse_contact_csv(csv_text: str, max_rows: int = MAX_CSV_ROWS) -> list[dict[str, str]]:
    """Parse CSV text with columns: Name, Email, Company, Role.

    Returns a list of dicts with lowercase keys. Skips rows missing name.
    Raises ValueError if the CSV exceeds *max_rows* valid contacts."""
    reader = csv.DictReader(io.StringIO(csv_text))
    contacts: list[dict[str, str]] = []
    for row in reader:
        # Normalize keys to lowercase for case-insensitive header matching
        normalized = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        name = normalized.get("name", "")
        if not name:
            continue
        contacts.append(
            {
                "name": name[:200],
                "email": normalized.get("email", "")[:200],
                "company": normalized.get("company", "")[:200],
                "role": normalized.get("role", "")[:200],
            }
        )
        if len(contacts) >= max_rows:
            raise ValueError(f"CSV exceeds the maximum of {max_rows} contacts")
    return contacts


# ---------------------------------------------------------------------------
# Background task: final data ingestion
# ---------------------------------------------------------------------------


def _run_onboarding_ingestion(user_id: str) -> None:
    """Background task that processes onboarding answers into real data."""
    try:
        # Atomic claim: only proceed if is_complete is currently false.
        # This prevents double-ingestion from concurrent step-5 submissions.
        claim_result = (
            supabase.table("onboarding_sessions")
            .update({"is_complete": True})
            .eq("user_id", user_id)
            .eq("is_complete", False)
            .select("answers")
            .execute()
        )
        if not claim_result.data:
            # Either no session exists or another task already claimed it
            logger.info("Ingestion: session already claimed or missing for user %s, skipping", user_id)
            return

        answers: dict = claim_result.data[0].get("answers") or {}

        user_result = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_result.data:
            logger.error("Ingestion: user %s not found", user_id)
            return
        user_row = user_result.data[0]

        # 1. Seed tracked_firms from step 3 (target companies)
        companies_raw = answers.get("step_3", "")
        company_names = _extract_watchlist(companies_raw)
        company_name_to_id: dict[str, str] = {}
        for name in company_names:
            firm_result = supabase.table("tracked_firms").upsert(
                {
                    "user_id": user_id,
                    "name": name,
                    "is_watchlist": True,
                },
                on_conflict="user_id,name",
            ).execute()
            if firm_result.data:
                company_name_to_id[name.lower()] = firm_result.data[0]["id"]

        # 2. Parse and seed contacts from step 4 (CSV)
        csv_text = answers.get("step_4", "")
        if isinstance(csv_text, str) and csv_text.strip():
            parsed_contacts = _parse_contact_csv(csv_text)

            # Resolve company IDs (create missing firms first)
            contact_rows: list[dict[str, Any]] = []
            for contact in parsed_contacts:
                company_id = company_name_to_id.get(contact["company"].lower())

                # If contact references a company not yet tracked, create it
                if contact["company"] and not company_id:
                    new_firm = supabase.table("tracked_firms").upsert(
                        {
                            "user_id": user_id,
                            "name": contact["company"][:200],
                            "is_watchlist": False,
                        },
                        on_conflict="user_id,name",
                    ).execute()
                    if new_firm.data:
                        company_id = new_firm.data[0]["id"]
                        company_name_to_id[contact["company"].lower()] = company_id

                row: dict[str, Any] = {
                    "user_id": user_id,
                    "name": contact["name"],
                    "email": contact["email"] or None,
                    "role": contact["role"] or None,
                    "tier": 2,  # default: active
                }
                if company_id:
                    row["company_id"] = company_id
                contact_rows.append(row)

            # Split: upsert rows that have emails (dedup on user_id,email),
            # plain insert rows without email (NULL email would collide on upsert key)
            if contact_rows:
                rows_with_email = [r for r in contact_rows if r.get("email")]
                rows_no_email = [r for r in contact_rows if not r.get("email")]
                if rows_with_email:
                    supabase.table("contacts").upsert(
                        rows_with_email,
                        on_conflict="user_id,email",
                    ).execute()
                if rows_no_email:
                    supabase.table("contacts").insert(rows_no_email).execute()

        # 3. Generate USER.md and other agent configs
        _generate_agent_configs(user_id, user_row, answers)

        # 4. Update practice_area on user row
        practice_areas = answers.get("step_2", [])
        if isinstance(practice_areas, list):
            clean_areas = [_sanitize(p, max_len=200) for p in practice_areas]
            supabase.table("users").update(
                {"practice_area": clean_areas}
            ).eq("id", user_id).execute()

        # 5. Clear CSV PII from session answers now that contacts are imported
        if "step_4" in answers:
            cleared_answers = {**answers, "step_4": "(imported)"}
            supabase.table("onboarding_sessions").update(
                {"answers": cleared_answers}
            ).eq("user_id", user_id).execute()

        # 6. Mark onboarding complete (is_complete already set atomically at task start;
        # only update completed_at + updated_at timestamp here)
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("onboarding_sessions").update(
            {"completed_at": now, "updated_at": now}
        ).eq("user_id", user_id).execute()

        supabase.table("users").update(
            {"onboarding_complete": True}
        ).eq("id", user_id).execute()

        logger.info("Onboarding ingestion complete for user %s", user_id)

    except Exception:
        logger.exception("Onboarding ingestion failed for user %s", user_id)


# ---------------------------------------------------------------------------
# Step definitions (for the new multi-step flow)
# ---------------------------------------------------------------------------

_STEP_QUESTIONS: dict[int, dict[str, Any]] = {
    1: {
        "title": "Welcome",
        "description": "Welcome to OpenLaw! Let's get your agent set up in a few quick steps.",
    },
    2: {
        "title": "Practice Area",
        "description": "What are your practice areas?",
        "input_type": "chips",
        "options": PRACTICE_AREA_OPTIONS,
    },
    3: {
        "title": "Target Companies",
        "description": "List 5-10 companies you want to monitor. Separate with commas.",
        "input_type": "free",
    },
    4: {
        "title": "Contact Import",
        "description": "Upload a CSV of your contacts (columns: Name, Email, Company, Role).",
        "input_type": "csv",
    },
    5: {
        "title": "Confirmation",
        "description": "Review your setup and click Complete to finish.",
        "input_type": "confirm",
    },
}

# ---------------------------------------------------------------------------
# New step-based endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
async def onboarding_status(current_user=Depends(get_current_user)) -> dict:
    user_id = current_user.id

    result = (
        supabase.table("onboarding_sessions")
        .select("step, answers, completed_at, is_complete")
        .eq("user_id", user_id)
        .execute()
    )
    if hasattr(result, "error") and result.error:
        raise HTTPException(status_code=500, detail=f"Failed to read session: {result.error}")

    if not result.data:
        return {"step": 0, "complete": False, "answers": {}}

    row = result.data[0]
    is_complete = row.get("is_complete", False) or row.get("completed_at") is not None
    return {
        "step": row.get("step", 0),
        "complete": is_complete,
        "answers": row.get("answers") or {},
    }


@router.post("/step")
async def onboarding_step(
    payload: StepPayload,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
) -> dict:
    user_id = current_user.id
    step = payload.step

    # Fetch or initialize session
    result = (
        supabase.table("onboarding_sessions")
        .select("step, answers, is_complete")
        .eq("user_id", user_id)
        .execute()
    )
    if hasattr(result, "error") and result.error:
        raise HTTPException(status_code=500, detail=f"Failed to read session: {result.error}")

    existing_answers: dict = {}
    current_step: int = 0
    is_complete: bool = False
    if result.data:
        existing_answers = result.data[0].get("answers") or {}
        current_step = result.data[0].get("step") or 0
        is_complete = result.data[0].get("is_complete", False)

    if is_complete:
        raise HTTPException(status_code=400, detail="Onboarding already complete")

    # Enforce step ordering: submitted step must be the current session step
    # (or step 1 for a fresh session where current_step == 0)
    expected_step = current_step if current_step >= 1 else 1
    if step != expected_step:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot submit step {step} — current session is at step {expected_step}. Complete steps in order.",
        )

    # Step 1 (welcome) requires no answer — just acknowledge and advance
    if step == 1:
        updated_answers = {**existing_answers, "step_1": True}
        _upsert_session(user_id, step=2, answers=updated_answers)
        return {
            "step": 2,
            "complete": False,
            "question": _STEP_QUESTIONS[2],
        }

    # Validate answer is present for steps 2-4
    if step in (2, 3, 4) and payload.answer is None:
        raise HTTPException(status_code=422, detail=f"Answer is required for step {step}")

    # Step 2: Practice area — validate chips
    if step == 2:
        answer = payload.answer
        if isinstance(answer, list):
            invalid = [a for a in answer if a not in PRACTICE_AREA_OPTIONS]
            if invalid:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid practice area(s): {invalid}",
                )
        elif isinstance(answer, str):
            answer = [answer]
        else:
            raise HTTPException(status_code=422, detail="Expected a list of practice areas")

        updated_answers = {**existing_answers, "step_2": answer}
        _upsert_session(user_id, step=3, answers=updated_answers)
        return {
            "step": 3,
            "complete": False,
            "question": _STEP_QUESTIONS[3],
        }

    # Step 3: Target companies
    if step == 3:
        answer = payload.answer
        if not isinstance(answer, str):
            raise HTTPException(status_code=422, detail="Expected a comma-separated string of company names")
        companies = [c.strip() for c in answer.split(",") if c.strip()]
        if not companies:
            raise HTTPException(status_code=422, detail="Please provide at least one company name")

        updated_answers = {**existing_answers, "step_3": answer}
        _upsert_session(user_id, step=4, answers=updated_answers)
        return {
            "step": 4,
            "complete": False,
            "question": _STEP_QUESTIONS[4],
        }

    # Step 4: Contact CSV import
    if step == 4:
        answer = payload.answer
        # Answer can be empty string (skip) or CSV text
        if answer is not None and not isinstance(answer, str):
            raise HTTPException(status_code=422, detail="Expected CSV text as a string")

        csv_text = answer or ""
        # Basic validation if CSV provided
        if csv_text.strip():
            try:
                parsed = _parse_contact_csv(csv_text)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to parse CSV: {exc}",
                ) from exc
            if not parsed:
                raise HTTPException(
                    status_code=422,
                    detail="CSV parsed but no valid contacts found. Ensure columns: Name, Email, Company, Role.",
                )

        updated_answers = {**existing_answers, "step_4": csv_text}
        _upsert_session(user_id, step=5, answers=updated_answers)

        # Build summary for confirmation
        summary = _build_summary(updated_answers)
        return {
            "step": 5,
            "complete": False,
            "question": {**_STEP_QUESTIONS[5], "summary": summary},
        }

    # Step 5: Confirmation — trigger background ingestion
    if step == 5:
        # Validate all prior steps are present
        required = ["step_1", "step_2", "step_3"]
        missing = [s for s in required if s not in existing_answers]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Incomplete onboarding — missing: {', '.join(missing)}",
            )

        background_tasks.add_task(_run_onboarding_ingestion, user_id)

        return {
            "step": 5,
            "complete": True,
            "message": "Onboarding complete! Your agent is being set up.",
        }

    raise HTTPException(status_code=400, detail=f"Unknown step: {step}")


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _upsert_session(user_id: str, step: int, answers: dict) -> None:
    result = supabase.table("onboarding_sessions").upsert(
        {
            "user_id": user_id,
            "step": step,
            "answers": answers,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()
    if hasattr(result, "error") and result.error:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {result.error}")


def _build_summary(answers: dict) -> dict:
    """Build a human-readable summary of onboarding answers for the confirmation step."""
    practice_areas = answers.get("step_2", [])
    companies_raw = answers.get("step_3", "")
    csv_text = answers.get("step_4", "")

    companies = _extract_watchlist(companies_raw) if companies_raw else []
    contact_count = 0
    if isinstance(csv_text, str) and csv_text.strip():
        try:
            contact_count = len(_parse_contact_csv(csv_text))
        except Exception:
            pass

    return {
        "practice_areas": practice_areas if isinstance(practice_areas, list) else [practice_areas],
        "target_companies": companies,
        "contacts_count": contact_count,
    }


# ---------------------------------------------------------------------------
# Legacy endpoints (backward compat with existing frontend)
# ---------------------------------------------------------------------------

# Chat step definitions for legacy flow
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


@router.post("/card")
async def onboarding_card(
    payload: CardPayload, current_user=Depends(get_current_user)
) -> dict:
    user_id = current_user.id

    clean_first = _sanitize(payload.first_name, max_len=100)
    clean_last = _sanitize(payload.last_name, max_len=100)
    clean_firm = _sanitize(payload.firm, max_len=200)
    clean_role = _sanitize(payload.role, max_len=200)
    clean_practice = [_sanitize(p, max_len=200) for p in payload.practice_area]

    card_update = supabase.table("users").update(
        {
            "first_name": clean_first,
            "last_name": clean_last,
            "name": f"{clean_first} {clean_last}".strip(),
            "firm": clean_firm,
            "role": clean_role,
            "practice_area": clean_practice,
        }
    ).eq("id", user_id).execute()
    if hasattr(card_update, "error") and card_update.error:
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {card_update.error}")

    existing_result = (
        supabase.table("onboarding_sessions").select("answers").eq("user_id", user_id).execute()
    )
    if hasattr(existing_result, "error") and existing_result.error:
        raise HTTPException(status_code=500, detail=f"Failed to read session: {existing_result.error}")
    existing_answers: dict = {}
    if existing_result.data:
        existing_answers = existing_result.data[0].get("answers") or {}

    merged_answers = {**existing_answers, "card": payload.model_dump()}
    _upsert_session(user_id, step=1, answers=merged_answers)

    return {"step": 1, "next": "chat"}


@router.post("/chat")
async def onboarding_chat(
    payload: ChatPayload, current_user=Depends(get_current_user)
) -> dict:
    user_id = current_user.id
    step = payload.step

    if step < 0 or step > 6:
        raise HTTPException(status_code=400, detail="step must be between 0 and 6")

    if step == 0 and payload.answer is not None:
        raise HTTPException(status_code=400, detail="step=0 is a bootstrap call and must not include an answer")

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

    if payload.answer is None:
        raise HTTPException(status_code=422, detail=f"Answer is required for step {step}")

    step_config = _CHAT_STEPS.get(step, {})
    if step_config.get("input_type") == "chips" and "options" in step_config:
        valid_options = set(step_config["options"])
        submitted = payload.answer if isinstance(payload.answer, list) else [payload.answer]
        invalid = [a for a in submitted if a not in valid_options]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid option(s) for step {step}: {invalid}. Must be one of the provided choices.",
            )

    result = (
        supabase.table("onboarding_sessions").select("answers", "step").eq("user_id", user_id).execute()
    )
    if hasattr(result, "error") and result.error:
        raise HTTPException(status_code=500, detail=f"Failed to read session: {result.error}")
    existing_answers: dict = {}
    session_step: int = 0
    if result.data:
        existing_answers = result.data[0].get("answers") or {}
        session_step = result.data[0].get("step") or 0

    if step > session_step + 1:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot jump to step {step} — current session is at step {session_step}. Complete steps in order.",
        )

    updated_answers = {**existing_answers, str(step): payload.answer}
    next_step = step + 1

    _upsert_session(user_id, step=next_step, answers=updated_answers)

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
    if hasattr(session_result, "error") and session_result.error:
        raise HTTPException(status_code=500, detail=f"Failed to read session: {session_result.error}")
    if not session_result.data:
        raise HTTPException(status_code=404, detail="No onboarding session found")

    answers: dict = session_result.data[0].get("answers") or {}

    user_check = supabase.table("users").select("onboarding_complete").eq("id", user_id).execute()
    if hasattr(user_check, "error") and user_check.error:
        raise HTTPException(status_code=500, detail=f"Failed to check onboarding status: {user_check.error}")
    if user_check.data and user_check.data[0].get("onboarding_complete"):
        return {"success": True, "redirect": "/dashboard", "idempotent": True}

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

    deal_types = [_sanitize(d, max_len=200) for d in _extract_deal_types(answers)]
    geography = _extract_geography(answers.get("2", ""))
    client_types = _sanitize(answers.get("2", ""), max_len=500)
    watchlist_companies = _extract_watchlist(answers.get("3", ""))
    relationship_flag = _sanitize(answers.get("4", ""))
    delivery_schedule = _extract_delivery_schedule(answers.get("5", ""))
    tracking_gap = _sanitize(answers.get("6", ""))

    structured_update = supabase.table("users").update(
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
    if hasattr(structured_update, "error") and structured_update.error:
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {structured_update.error}")

    updated_user_row = {
        **user_row,
        "deal_types": deal_types,
        "geography": geography,
        "client_types": client_types,
        "watchlist_companies": watchlist_companies,
        "delivery_schedule": delivery_schedule,
    }

    # Legacy flow uses old-style _build_user_md that reads from different answer keys
    legacy_configs = [
        ("SOUL.md", _build_soul(user_row.get("first_name", ""))),
        ("AGENTS.md", _AGENTS_MD),
    ]
    for name, content in legacy_configs:
        supabase.table("agent_memory_logs").upsert(
            {"user_id": user_id, "memory_key": name, "memory_val": {"content": content}},
            on_conflict="user_id,memory_key",
        ).execute()

    # Translate legacy answer keys to the step_N format expected by _generate_agent_configs
    legacy_answers = {
        "step_2": answers.get("1", []),   # practice/deal types → step_2
        "step_3": answers.get("3", ""),   # watchlist companies → step_3
    }

    try:
        await asyncio.to_thread(_generate_agent_configs, user_id, updated_user_row, legacy_answers)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate agent configs: {exc}",
        ) from exc

    complete_update = supabase.table("users").update({"onboarding_complete": True}).eq("id", user_id).execute()
    if hasattr(complete_update, "error") and complete_update.error:
        raise HTTPException(status_code=500, detail=f"Failed to mark onboarding complete: {complete_update.error}")

    try:
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("onboarding_sessions").update(
            {"completed_at": now, "is_complete": True}
        ).eq("user_id", user_id).execute()
    except Exception:
        pass

    return {"success": True, "redirect": "/dashboard"}

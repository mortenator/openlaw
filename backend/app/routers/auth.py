from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import supabase

router = APIRouter(prefix="/auth", tags=["auth"])

_DEFAULT_CONFIGS = [
    (
        "SOUL.md",
        "# SOUL.md - Your AI Chief of Staff\n\nYou are a proactive, strategic AI assistant for a senior deal lawyer. Your job is to help manage business development by tracking relationships, surfacing market intelligence, and identifying opportunities.\n\nBe professional, concise, and action-oriented. Surface what matters. Skip what does not.",
    ),
    (
        "USER.md",
        "# USER.md - About You\n\n- Name: (update this)\n- Firm: (update this)\n- Practice Areas: (e.g., M&A, Tech Transactions, AI Infrastructure)\n- Target Companies: (list key companies to track)\n- Email: (update this)\n- Timezone: America/New_York",
    ),
    (
        "AGENTS.md",
        "# AGENTS.md - Operating Instructions\n\n1. Proactive first - surface insights before being asked\n2. Be specific - always give an actionable angle, not just raw news\n3. Respect confidentiality - never reference client matters or deal terms\n4. Short over long - bullets, not essays",
    ),
    (
        "HEARTBEAT.md",
        "# HEARTBEAT.md - Check Cadence\n\n## Daily (morning)\n- Scan market signals for watchlist companies\n- Check relationship health scores - flag anyone below 60\n\n## Weekly\n- Compile top 5 warm-up candidates\n- Send weekly digest email",
    ),
    (
        "MEMORY.md",
        "# MEMORY.md\n\n_Long-term context about your contacts and market will accumulate here._",
    ),
]


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _provision_defaults(user_id: str) -> None:
    rows = [
        {"user_id": user_id, "file_name": name, "content": content}
        for name, content in _DEFAULT_CONFIGS
    ]
    supabase.table("agent_configs").upsert(rows, on_conflict="user_id,file_name").execute()


@router.post("/signup")
async def signup(payload: SignupRequest) -> dict:
    try:
        result = supabase.auth.admin.create_user(
            {"email": payload.email, "password": payload.password, "email_confirm": True}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user = result.user
    if user is None:
        raise HTTPException(status_code=400, detail="Failed to create user")

    _provision_defaults(user.id)

    # Sign in to get access token
    try:
        session = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "access_token": session.session.access_token,
        "user": {"id": user.id, "email": user.email},
    }


@router.post("/login")
async def login(payload: LoginRequest) -> dict:
    try:
        session = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    if session.session is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = session.user
    return {
        "access_token": session.session.access_token,
        "user": {"id": user.id, "email": user.email},
    }

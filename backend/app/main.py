import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run pending migrations on startup, then start the cron scheduler."""
    from app.database import supabase

    # Migration: trigger_summary on outreach_suggestions
    try:
        supabase.table("outreach_suggestions").select("trigger_summary").limit(1).execute()
    except Exception:
        log.warning("outreach_suggestions.trigger_summary missing — applying migration")
        try:
            supabase.rpc("exec_sql", {"sql": "ALTER TABLE outreach_suggestions ADD COLUMN IF NOT EXISTS trigger_summary TEXT"}).execute()
        except Exception:
            log.warning("Could not apply trigger_summary migration via RPC — apply migration 006 manually")

    # Migration: onboarding_sessions.is_complete
    try:
        supabase.table("onboarding_sessions").select("is_complete").limit(1).execute()
    except Exception:
        log.warning("onboarding_sessions.is_complete missing — migration needed")

    # Start in-process cron scheduler
    from app.scheduler import start_scheduler, stop_scheduler
    start_scheduler()

    yield

    stop_scheduler()

from app.routers import (
    deliveries,
)
from app.routers import (
    agent_configs,
    auth,
    companies_auth,
    contacts_auth,
    crons_auth,
    deliveries_auth,
    internal,
    jobs,
    onboarding,
    query,
    signals_auth,
    suggestions,
)

app = FastAPI(
    title="OpenLaw API",
    description="AI chief of staff for deal lawyers",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Legacy user-scoped router — routes: GET/PATCH /users/{user_id}/deliveries
# and GET/PATCH /users/{user_id}/outreach-suggestions.
# No prefix set; NO collision with deliveries_auth (prefix=/deliveries) or
# suggestions (prefix=/suggestions). Kept for backward compat only.
app.include_router(deliveries.router)

# Auth-based routes (Bearer token)
app.include_router(auth.router)
app.include_router(agent_configs.router)
app.include_router(suggestions.router)
app.include_router(query.router)
app.include_router(jobs.router)
app.include_router(contacts_auth.router)
app.include_router(companies_auth.router)
app.include_router(signals_auth.router)
app.include_router(crons_auth.router)
app.include_router(deliveries_auth.router)
app.include_router(onboarding.router)
app.include_router(internal.router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "openlaw-api"}

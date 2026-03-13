from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    companies,
    contacts,
    crons,
    deliveries,
    signals,
    users,
)
from app.routers import (
    agent_configs,
    auth,
    companies_auth,
    contacts_auth,
    crons_auth,
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

# Legacy user-scoped routes
app.include_router(users.router)
app.include_router(contacts.router)
app.include_router(companies.router)
app.include_router(signals.router)
app.include_router(crons.router)
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
app.include_router(onboarding.router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "openlaw-api"}

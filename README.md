# OpenLaw

**AI chief of staff for deal lawyers.**

OpenLaw is a SaaS platform that acts as an intelligent relationship manager and market monitor for transactional attorneys. It automatically scans for signals (news, funding rounds, regulatory filings) relevant to a lawyer's contacts and deal flow, scores relationship health, and drafts personalized outreach — delivering a weekly briefing so lawyers stay top-of-mind with clients and counterparties without spending hours on manual research.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/mortenator/openlaw.git
cd openlaw
```

### 2. Install Python dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set environment variables

```bash
cp .env.example .env
# Edit .env and fill in your real keys:
#   SUPABASE_URL
#   SUPABASE_SERVICE_ROLE_KEY
#   RESEND_API_KEY
#   BRAVE_API_KEY
```

### 4. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and create a new project.
2. Copy the **Project URL** and **service_role key** into `.env`.

### 5. Run migrations

Open the Supabase SQL editor (or use `psql`) and run:

```sql
-- 1. Full schema
\i migrations/001_initial_schema.sql

-- 2. Seed Brian as customer #0
\i migrations/002_seed_brian.sql
```

### 6. Start the API server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

---

## Architecture

```
openlaw/
  backend/
    app/
      main.py          # FastAPI app — mounts all routers
      config.py        # Pydantic-settings env var loader
      database.py      # Supabase client singleton
      routers/         # One file per resource (users, contacts, companies, …)
      services/
        health_score.py   # Relationship health scoring (0–100)
        market_scan.py    # Brave Search wrapper for signal ingestion
        email.py          # Resend transactional email
      models/
        schema.py      # All Pydantic request/response models
    migrations/
      001_initial_schema.sql   # Full 9-table schema with indexes & triggers
      002_seed_brian.sql       # Brian Hamilton seed row (customer #0)
```

**Data flow:**
1. Cron jobs (stored in `user_crons`) trigger market scans via Brave Search.
2. Raw results are stored as `signals`, linked to contacts/companies.
3. The AI layer (coming Week 3) reads signals and generates `outreach_suggestions`.
4. Approved suggestions are sent via Resend and logged in `deliveries`.
5. Each touch updates `contacts.last_contacted_at`, re-scoring `health_score`.

---

## Week 1–2 Status

### Built
- [x] Full Supabase schema — 9 tables: `users`, `agent_configs`, `agent_memory_logs`, `contacts`, `companies`, `signals`, `outreach_suggestions`, `user_crons`, `deliveries`
- [x] All foreign keys, indexes on `user_id + created_at`, auto-`updated_at` triggers
- [x] FastAPI backend with all routes (typed stubs, Supabase-wired)
- [x] Relationship health scoring engine (`services/health_score.py`)
- [x] Resend email wrapper (`services/email.py`)
- [x] Brave Search market scan wrapper (`services/market_scan.py`)
- [x] Brian Hamilton seed data (user row + agent config)
- [x] `.env.example` — no real secrets committed

### Next (Week 3–4)
- [ ] Create Supabase project + run migrations
- [ ] Brian onboarding call — collect contact CSV, firm name, real email
- [ ] Bulk contact import script
- [ ] Claude-powered outreach suggestion generation
- [ ] Weekly briefing email template
- [ ] Cron job runner (APScheduler or Supabase Edge Functions)
- [ ] Auth (Supabase Auth + JWT middleware)

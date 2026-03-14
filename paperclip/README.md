# Paperclip — OpenLaw Execution Backend

This directory contains Railway deployment configuration for [Paperclip](https://github.com/paperclipai/paperclip), the agent execution backbone for OpenLaw.

## What is Paperclip?

Paperclip is a self-hostable agent execution platform. OpenLaw uses it to manage per-user agent instances, scheduling, and heartbeat delivery.

## Deploying to Railway

### 1. Create a new Railway service

In your Railway project, add a new service and point it at this repository. Set the **Root Directory** to `paperclip/` so Railway picks up `railway.toml`.

### 2. Provision a Postgres database

Attach a Railway Postgres plugin (or an external Postgres instance) to the service. Copy the `DATABASE_URL` from the plugin's connection tab.

### 3. Set required environment variables

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Railway Postgres connection string | `postgresql://user:pass@host:5432/db` |
| `PAPERCLIP_JWT_SECRET` | Random secret for signing JWTs — generate with `openssl rand -base64 48` | `<output of openssl rand -base64 48>` |
| `PAPERCLIP_INSTANCE_NAME` | Human-readable name for this deployment | `openlaw` |

### 4. Deploy

Trigger a deploy. Railway will run:

```
npx paperclipai@0.3.1 onboard --yes --headless
```

The service listens on port **3100** and exposes a `/health` endpoint.

### 5. Wire back to OpenLaw backend

Set the following env vars on your OpenLaw backend Railway service:

```
PAPERCLIP_BASE_URL=https://<your-paperclip-service>.up.railway.app
PAPERCLIP_INTERNAL_KEY=<shared secret for X-Internal-Key header>
```

Then run `backend/scripts/bootstrap_paperclip.py` once to create Paperclip companies and agents for all existing users.

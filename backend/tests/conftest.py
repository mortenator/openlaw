"""Shared pytest fixtures and environment stubs for unit tests.

We stub out app.database and app.config BEFORE any test module imports them,
so pydantic-settings and supabase-py never try to validate real env vars or
connect to real hosts.
"""
from __future__ import annotations

import os
import sys
from types import ModuleType
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Stub required env vars (needed so pydantic-settings validation passes
#    for other modules that import settings at import time).
# ---------------------------------------------------------------------------

os.environ.setdefault("SUPABASE_URL", "https://stub.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.stub.stub")
os.environ.setdefault("RESEND_API_KEY", "re_stub")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-stub")
os.environ.setdefault("BRAVE_API_KEY", "bsa-stub")
os.environ.setdefault("CRON_SECRET", "stub-cron-secret")
os.environ.setdefault("PAPERCLIP_INTERNAL_KEY", "stub-paperclip-internal-key-at-least-32-chars!")
os.environ.setdefault("PAPERCLIP_BASE_URL", "http://localhost:3100")

# ---------------------------------------------------------------------------
# 2. Inject a stub app.database module so supabase-py is never initialised.
#    Tests that care about DB calls will swap the `supabase` attribute per-test.
# ---------------------------------------------------------------------------

_db_stub = ModuleType("app.database")
_db_stub.supabase = MagicMock()          # type: ignore[attr-defined]
_db_stub.supabase_admin = _db_stub.supabase  # type: ignore[attr-defined]
_db_stub.get_supabase_client = MagicMock(return_value=_db_stub.supabase)  # type: ignore[attr-defined]
sys.modules.setdefault("app.database", _db_stub)

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr


# ── Users ──────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    firm: Optional[str] = None
    practice_area: list[str] = []
    comms_channel: str = "email"
    timezone: str = "UTC"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    firm: Optional[str] = None
    practice_area: Optional[list[str]] = None
    comms_channel: Optional[str] = None
    timezone: Optional[str] = None


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    firm: Optional[str]
    practice_area: list[str]
    comms_channel: str
    timezone: str
    created_at: datetime
    updated_at: datetime


# ── Agent Config ───────────────────────────────────────────────────────────

class AgentConfigCreate(BaseModel):
    scan_frequency: str = "weekly"
    outreach_tone: str = "professional"
    max_weekly_outreach: int = 5
    focus_keywords: list[str] = []


class AgentConfigOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    scan_frequency: str
    outreach_tone: str
    max_weekly_outreach: int
    focus_keywords: list[str]
    created_at: datetime
    updated_at: datetime


# ── Contacts ───────────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
    tier: int = 2  # 1=VIP, 2=active, 3=dormant
    tags: list[str] = []
    notes: Optional[str] = None
    last_contacted_at: Optional[datetime] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
    tier: Optional[int] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    last_contacted_at: Optional[datetime] = None


class ContactOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: Optional[str]
    phone: Optional[str]
    company_id: Optional[uuid.UUID]
    role: Optional[str]
    tier: int
    tags: list[str]
    notes: Optional[str]
    last_contacted_at: Optional[datetime]
    health_score: int
    created_at: datetime
    updated_at: datetime


# ── Companies ──────────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    tags: list[str] = []
    notes: Optional[str] = None


class CompanyOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    domain: Optional[str]
    industry: Optional[str]
    tags: list[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── Signals ────────────────────────────────────────────────────────────────

class SignalOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    contact_id: Optional[uuid.UUID]
    company_id: Optional[uuid.UUID]
    source: str
    headline: str
    url: Optional[str]
    summary: Optional[str]
    relevance_score: Optional[float]
    raw_data: Optional[dict[str, Any]]
    created_at: datetime


# ── Outreach Suggestions ───────────────────────────────────────────────────

class OutreachSuggestionUpdate(BaseModel):
    status: Optional[str] = None  # pending | approved | sent | dismissed
    edited_body: Optional[str] = None


class OutreachSuggestionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    contact_id: uuid.UUID
    signal_id: Optional[uuid.UUID]
    subject: str
    body: str
    edited_body: Optional[str]
    status: str
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# ── Crons ──────────────────────────────────────────────────────────────────

class CronCreate(BaseModel):
    name: str
    cron_expression: str
    job_type: str
    config: dict[str, Any] = {}
    is_active: bool = True


class CronUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    job_type: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class CronOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    cron_expression: str
    job_type: str
    config: dict[str, Any]
    is_active: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# ── Deliveries ─────────────────────────────────────────────────────────────

class DeliveryOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    delivery_type: str
    channel: str
    status: str
    payload: Optional[dict[str, Any]]
    error_message: Optional[str]
    delivered_at: Optional[datetime]
    created_at: datetime

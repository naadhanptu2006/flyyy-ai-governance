from datetime import datetime, timezone
from typing import Optional, Any, Annotated

from pydantic import BaseModel, BeforeValidator


def _ensure_utc(v):
    """Guarantees every outgoing timestamp carries an explicit UTC
    offset, regardless of whether the underlying DB driver returned a
    naive or aware datetime (SQLite drops tz info; Postgres keeps it).
    Without this, a naive datetime serializes without an offset and
    browsers parse it as local time instead of UTC — silently shifting
    every displayed timestamp by the viewer's UTC offset."""
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


UTCDateTime = Annotated[datetime, BeforeValidator(_ensure_utc)]


# ---------- Agents ----------
class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None


class AgentOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    active_profile_id: Optional[str]
    created_at: UTCDateTime

    class Config:
        from_attributes = True


# ---------- Profiles ----------
class GuardrailConfig(BaseModel):
    limit: int
    warning_pct: int = 80
    critical_pct: int = 90


class ProfileCreate(BaseModel):
    agent_id: str
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    environment: str = "production"
    allowed_tools: list[str] = []
    allowed_data_sources: list[str] = []
    allowed_actions: list[str] = []
    guardrails: dict[str, GuardrailConfig] = {}


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    environment: Optional[str] = None
    allowed_tools: Optional[list[str]] = None
    allowed_data_sources: Optional[list[str]] = None
    allowed_actions: Optional[list[str]] = None
    guardrails: Optional[dict[str, GuardrailConfig]] = None


class ProfileOut(BaseModel):
    id: str
    agent_id: str
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    environment: str = "production"
    allowed_tools: list[str]
    allowed_data_sources: list[str]
    allowed_actions: list[str]
    guardrails: dict
    is_active: bool
    created_at: UTCDateTime

    class Config:
        from_attributes = True


# ---------- Execution ----------
class RunRequest(BaseModel):
    agent_id: str
    scenario: str = "normal"  # "normal" | "deviation"


class RunOut(BaseModel):
    run_id: str
    status: str
    trace: list[dict[str, Any]]


class LiveStartRequest(BaseModel):
    agent_id: str


class LiveTickRequest(BaseModel):
    run_id: str


class LiveTickOut(BaseModel):
    run_id: str
    status: str
    step: Optional[dict[str, Any]] = None


# ---------- Findings ----------
class FindingOut(BaseModel):
    id: str
    run_id: str
    agent_id: str
    event_id: str
    deviation_type: str
    expected_behavior: str
    actual_behavior: str
    severity: str
    detected_at: UTCDateTime

    class Config:
        from_attributes = True


# ---------- Responses ----------
class ResponseActionOut(BaseModel):
    id: str
    finding_id: str
    action_type: str
    status: str
    triggered_at: UTCDateTime
    resolved_at: Optional[UTCDateTime]
    approver: Optional[str]
    decision_reason: Optional[str]

    class Config:
        from_attributes = True


class ApprovalDecision(BaseModel):
    approver: str
    reason: Optional[str] = None


# ---------- Audit log ----------
class AuditLogOut(BaseModel):
    id: str
    event_type: str
    actor: str
    agent_id: Optional[str]
    details: dict
    timestamp: UTCDateTime

    class Config:
        from_attributes = True

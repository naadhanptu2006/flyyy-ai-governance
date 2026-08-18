"""
Core database models for the AI Agent Governance system.

Design rationale (for README):
- `AgentProfile` is the "approved behaviour" baseline — allowed tools, data
  sources, and actions, plus optional numeric guardrails (e.g. rate limits).
- `ExecutionRun` represents one end-to-end invocation of an agent (a "session").
- `ExecutionEvent` is every individual action the agent attempts DURING a run —
  logged by the governance wrapper BEFORE the underlying tool executes.
- `Finding` is created when an ExecutionEvent falls outside the agent's active
  profile. It carries full evidence for auditability.
- `ResponseAction` models the enforcement state machine: notify -> require
  approval -> block/resume. One Finding can trigger one ResponseAction.
- `AuditLogEntry` is an append-only record of every governance-relevant event
  in the system (deviation, warning, approval, block, resume) for compliance.
"""
import enum
import uuid
from datetime import datetime, timezone

def utcnow():
    """Timezone-aware UTC now — critical so serialized timestamps carry
    a '+00:00' offset. A naive datetime (no offset) gets serialized
    without one, and browsers then parse it as LOCAL time instead of
    UTC, silently shifting every displayed timestamp by the viewer's
    UTC offset (e.g. 5:30 early/late for IST)."""
    return datetime.now(timezone.utc)

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Enum, Text, Integer, Boolean, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class EventType(str, enum.Enum):
    TOOL_CALL = "tool_call"
    DATA_ACCESS = "data_access"
    ACTION = "action"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResponseActionType(str, enum.Enum):
    NOTIFY = "notify"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


class ResponseStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_RESOLVED = "auto_resolved"


class RunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    PAUSED_FOR_APPROVAL = "paused_for_approval"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    active_profile_id = Column(String, ForeignKey("agent_profiles.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    active_profile = relationship("AgentProfile", foreign_keys=[active_profile_id])
    runs = relationship("ExecutionRun", back_populates="agent")


class AgentProfile(Base):
    """The approved behaviour baseline for an agent."""
    __tablename__ = "agent_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    name = Column(String, nullable=False)

    # Commercial/operational detail — who owns this profile, what
    # environment it governs, and free-text notes on scope/rationale.
    # None of these affect enforcement logic; they exist so a real
    # governance team has enough context to audit *why* a profile
    # looks the way it does, not just *what* it allows.
    description = Column(Text, nullable=True)
    owner = Column(String, nullable=True)          # e.g. "Platform Security Team"
    environment = Column(String, default="production")  # production | staging | development

    allowed_tools = Column(JSON, default=list)          # ["faq_search", "email_sender"]
    allowed_data_sources = Column(JSON, default=list)    # ["faq_database"]
    allowed_actions = Column(JSON, default=list)         # ["read", "send_email"]

    # Guardrails: numeric limits with warning thresholds, e.g.
    # {"max_calls_per_day": {"limit": 1000, "warning_pct": 80, "critical_pct": 90}}
    guardrails = Column(JSON, default=dict)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    agent = relationship("Agent", foreign_keys=[agent_id])


class ExecutionRun(Base):
    """One end-to-end invocation ('session') of an agent."""
    __tablename__ = "execution_runs"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    profile_id_at_run = Column(String, nullable=True)  # snapshot of which profile applied
    status = Column(Enum(RunStatus), default=RunStatus.RUNNING)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("Agent", back_populates="runs")
    events = relationship("ExecutionEvent", back_populates="run")


class ExecutionEvent(Base):
    """A single action the agent attempted, logged BEFORE execution by the wrapper."""
    __tablename__ = "execution_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    run_id = Column(String, ForeignKey("execution_runs.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    event_type = Column(Enum(EventType), nullable=False)
    resource_name = Column(String, nullable=False)   # e.g. "file_delete", "customer_db"
    payload = Column(JSON, default=dict)              # arguments / context of the call
    was_permitted = Column(Boolean, nullable=False)   # decided by the governance wrapper
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    run = relationship("ExecutionRun", back_populates="events")


class Finding(Base):
    """A recorded deviation: an event that fell outside the approved profile."""
    __tablename__ = "findings"

    id = Column(String, primary_key=True, default=gen_uuid)
    run_id = Column(String, ForeignKey("execution_runs.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    event_id = Column(String, ForeignKey("execution_events.id"), nullable=False)

    deviation_type = Column(String, nullable=False)   # "unauthorized_tool" | "unauthorized_data" | "unauthorized_action" | "guardrail_exceeded"
    expected_behavior = Column(Text, nullable=False)
    actual_behavior = Column(Text, nullable=False)
    severity = Column(Enum(Severity), nullable=False)
    detected_at = Column(DateTime(timezone=True), default=utcnow)

    response = relationship("ResponseAction", back_populates="finding", uselist=False)


class ResponseAction(Base):
    """The enforcement action triggered by a Finding."""
    __tablename__ = "response_actions"

    id = Column(String, primary_key=True, default=gen_uuid)
    finding_id = Column(String, ForeignKey("findings.id"), nullable=False)

    action_type = Column(Enum(ResponseActionType), nullable=False)
    status = Column(Enum(ResponseStatus), default=ResponseStatus.PENDING)
    triggered_at = Column(DateTime(timezone=True), default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    approver = Column(String, nullable=True)
    decision_reason = Column(Text, nullable=True)

    finding = relationship("Finding", back_populates="response")


class AuditLogEntry(Base):
    """Append-only audit trail of every governance-relevant event in the system."""
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=gen_uuid)
    event_type = Column(String, nullable=False)  # e.g. "deviation_detected", "agent_blocked", "approval_granted"
    actor = Column(String, nullable=False)        # "system" | "governance_engine" | approver name
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime(timezone=True), default=utcnow)

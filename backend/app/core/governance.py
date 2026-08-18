"""
Governance Engine — the heart of the system.

This module implements the WRAPPER/MIDDLEWARE interception pattern:
every time the simulated agent wants to call a tool, touch a data source,
or perform an action, it must go through `GovernanceEngine.check_and_log()`
FIRST. That call:

  1. Logs the attempted event (ExecutionEvent) regardless of outcome —
     this gives us a complete, tamper-evident record of everything the
     agent tried to do, not just the violations.
  2. Evaluates the event against the agent's active AgentProfile.
  3. If it's outside the approved profile, creates a Finding with full
     evidence, decides severity, and creates a ResponseAction.
  4. Returns a permit/deny decision the caller MUST respect — this is
     what makes it real-time enforcement rather than after-the-fact
     log analysis.

Guardrails (numeric limits like "max calls/day") are checked separately
via `check_guardrails()`, since they're a different kind of governance
concern (usage/rate, not identity/permission) and can fire warnings
*before* any single call is itself a violation.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.models import (
    Agent, AgentProfile, ExecutionEvent, Finding, ResponseAction,
    AuditLogEntry, EventType, Severity, ResponseActionType, ResponseStatus,
    utcnow,
)


class GovernanceBlockedError(Exception):
    """Raised when the governance engine denies an action outright."""
    def __init__(self, message, finding_id=None):
        super().__init__(message)
        self.finding_id = finding_id


class GovernanceEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Core interception point
    # ------------------------------------------------------------------
    def check_and_log(self, run_id: str, agent_id: str, event_type: EventType,
                       resource_name: str, payload: dict | None = None):
        """
        Called by the governance wrapper BEFORE a tool actually executes.
        Returns the ExecutionEvent. Raises GovernanceBlockedError if the
        active ResponseAction policy says this call must be blocked.
        """
        payload = payload or {}
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        profile = agent.active_profile if agent else None

        permitted = self._is_permitted(profile, event_type, resource_name)

        event = ExecutionEvent(
            run_id=run_id,
            agent_id=agent_id,
            event_type=event_type,
            resource_name=resource_name,
            payload=payload,
            was_permitted=permitted,
        )
        self.db.add(event)
        self.db.flush()  # get event.id without committing yet

        if not permitted:
            finding = self._create_finding(agent_id, run_id, event, profile)
            response = self._trigger_response(finding)
            self.db.commit()

            if response.action_type == ResponseActionType.BLOCK:
                raise GovernanceBlockedError(
                    f"Blocked: '{resource_name}' is outside the approved profile "
                    f"for agent '{agent.name}'.",
                    finding_id=finding.id,
                )
            # NOTIFY / REQUIRE_APPROVAL: event is logged & flagged, but the
            # caller may choose to proceed depending on business logic —
            # in our reference agent, REQUIRE_APPROVAL also halts execution
            # until an approver acts (see /responses/{id}/approve).
            if response.action_type == ResponseActionType.REQUIRE_APPROVAL:
                raise GovernanceBlockedError(
                    f"Paused pending approval: '{resource_name}' requires "
                    f"human sign-off before it can proceed.",
                    finding_id=finding.id,
                )
        else:
            self.db.commit()

        return event

    # ------------------------------------------------------------------
    # Permission evaluation
    # ------------------------------------------------------------------
    def _is_permitted(self, profile: AgentProfile | None, event_type: EventType,
                       resource_name: str) -> bool:
        if profile is None:
            # No profile = no approved behaviour at all -> deny by default.
            # (Fail-closed, not fail-open — a deliberate design decision.)
            return False

        if event_type == EventType.TOOL_CALL:
            return resource_name in (profile.allowed_tools or [])
        if event_type == EventType.DATA_ACCESS:
            return resource_name in (profile.allowed_data_sources or [])
        if event_type == EventType.ACTION:
            return resource_name in (profile.allowed_actions or [])
        return False

    # ------------------------------------------------------------------
    # Finding creation
    # ------------------------------------------------------------------
    def _create_finding(self, agent_id: str, run_id: str, event: ExecutionEvent,
                         profile: AgentProfile | None) -> Finding:
        deviation_map = {
            EventType.TOOL_CALL: "unauthorized_tool",
            EventType.DATA_ACCESS: "unauthorized_data",
            EventType.ACTION: "unauthorized_action",
        }
        allowed_summary = "no active profile" if profile is None else {
            EventType.TOOL_CALL: profile.allowed_tools,
            EventType.DATA_ACCESS: profile.allowed_data_sources,
            EventType.ACTION: profile.allowed_actions,
        }[event.event_type]

        severity = self._score_severity(event.resource_name)

        finding = Finding(
            run_id=run_id,
            agent_id=agent_id,
            event_id=event.id,
            deviation_type=deviation_map[event.event_type],
            expected_behavior=f"Approved {event.event_type.value} set: {allowed_summary}",
            actual_behavior=f"Attempted {event.event_type.value}: '{event.resource_name}' "
                             f"with payload {event.payload}",
            severity=severity,
        )
        self.db.add(finding)
        self.db.flush()

        self._log_audit(
            "deviation_detected", "governance_engine", agent_id,
            {"finding_id": finding.id, "resource": event.resource_name,
             "severity": severity.value},
        )
        return finding

    def _score_severity(self, resource_name: str) -> Severity:
        """
        Simple, explainable severity heuristic — deliberately simple per
        the assignment's 'depth over breadth' guidance. Documented in
        README as a key assumption/limitation: a production system would
        use a configurable risk-scoring policy per resource.
        """
        high_risk_keywords = ["delete", "drop", "payment", "transfer", "admin", "credential"]
        if any(k in resource_name.lower() for k in high_risk_keywords):
            return Severity.HIGH
        medium_risk_keywords = ["write", "update", "customer", "database"]
        if any(k in resource_name.lower() for k in medium_risk_keywords):
            return Severity.MEDIUM
        return Severity.LOW

    # ------------------------------------------------------------------
    # Response / enforcement policy
    # ------------------------------------------------------------------
    def _trigger_response(self, finding: Finding) -> ResponseAction:
        """
        Severity -> action mapping. This is the 'Notify -> Require Approval
        -> Block' progression from the assignment, made concrete:
          LOW    -> NOTIFY only (logged, agent continues)
          MEDIUM -> REQUIRE_APPROVAL (agent paused until a human decides)
          HIGH   -> BLOCK (agent halted immediately, no auto-resume)
        """
        action_map = {
            Severity.LOW: ResponseActionType.NOTIFY,
            Severity.MEDIUM: ResponseActionType.REQUIRE_APPROVAL,
            Severity.HIGH: ResponseActionType.BLOCK,
        }
        action_type = action_map[finding.severity]
        status = (ResponseStatus.AUTO_RESOLVED if action_type == ResponseActionType.NOTIFY
                  else ResponseStatus.PENDING)

        response = ResponseAction(
            finding_id=finding.id,
            action_type=action_type,
            status=status,
            resolved_at=utcnow() if status == ResponseStatus.AUTO_RESOLVED else None,
        )
        self.db.add(response)
        self.db.flush()

        self._log_audit(
            f"response_{action_type.value}", "governance_engine", finding.agent_id,
            {"finding_id": finding.id, "response_id": response.id, "status": status.value},
        )
        return response

    # ------------------------------------------------------------------
    # Guardrails (numeric / rate-based limits)
    # ------------------------------------------------------------------
    def check_guardrails(self, agent_id: str, profile: AgentProfile):
        """
        Evaluate configured numeric guardrails (e.g. max_calls_per_day)
        against actual usage in the current window. Returns a list of
        warning dicts (possibly empty). Called after each event, or on
        demand via GET /guardrails/status.
        """
        from app.models.models import ExecutionEvent  # local import avoids cycle

        warnings = []
        guardrails = profile.guardrails or {}
        for name, cfg in guardrails.items():
            limit = cfg.get("limit")
            if not limit:
                continue
            window_start = utcnow() - timedelta(days=1)
            usage = (
                self.db.query(ExecutionEvent)
                .filter(ExecutionEvent.agent_id == agent_id)
                .filter(ExecutionEvent.timestamp >= window_start)
                .count()
            )
            pct = (usage / limit) * 100
            level = None
            if pct >= 100:
                level = "limit_exceeded"
            elif pct >= cfg.get("critical_pct", 90):
                level = "critical"
            elif pct >= cfg.get("warning_pct", 80):
                level = "warning"

            if level:
                warnings.append({
                    "guardrail": name, "usage": usage, "limit": limit,
                    "pct": round(pct, 1), "level": level,
                })
                self._log_audit(
                    f"guardrail_{level}", "governance_engine", agent_id,
                    {"guardrail": name, "usage": usage, "limit": limit, "pct": pct},
                )
        if warnings:
            self.db.commit()
        return warnings

    # ------------------------------------------------------------------
    def _log_audit(self, event_type: str, actor: str, agent_id: str | None, details: dict):
        entry = AuditLogEntry(
            event_type=event_type, actor=actor, agent_id=agent_id, details=details,
        )
        self.db.add(entry)

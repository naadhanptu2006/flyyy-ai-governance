
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.governance import GovernanceEngine
from app.models import models
from app.models.models import utcnow
from app.schemas import schemas

router = APIRouter(tags=["governance"])


# ---------------- Findings ----------------
@router.get("/findings", response_model=list[schemas.FindingOut])
def list_findings(agent_id: str | None = None, severity: str | None = None,
                   db: Session = Depends(get_db)):
    q = db.query(models.Finding)
    if agent_id:
        q = q.filter(models.Finding.agent_id == agent_id)
    if severity:
        q = q.filter(models.Finding.severity == severity)
    return q.order_by(models.Finding.detected_at.desc()).all()


@router.get("/findings/{finding_id}", response_model=schemas.FindingOut)
def get_finding(finding_id: str, db: Session = Depends(get_db)):
    finding = db.query(models.Finding).filter(models.Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    return finding


# ---------------- Responses / approvals ----------------
@router.get("/responses", response_model=list[schemas.ResponseActionOut])
def list_responses(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.ResponseAction)
    if status:
        q = q.filter(models.ResponseAction.status == status)
    return q.order_by(models.ResponseAction.triggered_at.desc()).all()


@router.post("/responses/{response_id}/approve", response_model=schemas.ResponseActionOut)
def approve_response(response_id: str, payload: schemas.ApprovalDecision,
                      db: Session = Depends(get_db)):
    return _decide(response_id, payload, approve=True, db=db)


@router.post("/responses/{response_id}/reject", response_model=schemas.ResponseActionOut)
def reject_response(response_id: str, payload: schemas.ApprovalDecision,
                     db: Session = Depends(get_db)):
    return _decide(response_id, payload, approve=False, db=db)


def _decide(response_id: str, payload: schemas.ApprovalDecision, approve: bool, db: Session):
    response = db.query(models.ResponseAction).filter(
        models.ResponseAction.id == response_id
    ).first()
    if not response:
        raise HTTPException(404, "Response action not found")
    if response.status != models.ResponseStatus.PENDING:
        raise HTTPException(400, f"Response already resolved with status={response.status.value}")

    response.status = models.ResponseStatus.APPROVED if approve else models.ResponseStatus.REJECTED
    response.approver = payload.approver
    response.decision_reason = payload.reason
    response.resolved_at = utcnow()
    db.commit()
    db.refresh(response)

    finding = db.query(models.Finding).filter(models.Finding.id == response.finding_id).first()
    engine = GovernanceEngine(db)
    engine._log_audit(
        "approval_granted" if approve else "approval_rejected",
        payload.approver, finding.agent_id if finding else None,
        {"response_id": response.id, "finding_id": response.finding_id,
         "reason": payload.reason},
    )
    db.commit()
    return response


# ---------------- Guardrails ----------------
@router.get("/guardrails/status")
def guardrail_status(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if not agent.active_profile:
        return {"agent_id": agent_id, "warnings": [], "note": "No active profile"}

    engine = GovernanceEngine(db)
    warnings = engine.check_guardrails(agent_id, agent.active_profile)
    return {"agent_id": agent_id, "warnings": warnings}


# ---------------- Audit log ----------------
@router.get("/audit-log", response_model=list[schemas.AuditLogOut])
def get_audit_log(agent_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.AuditLogEntry)
    if agent_id:
        q = q.filter(models.AuditLogEntry.agent_id == agent_id)
    return q.order_by(models.AuditLogEntry.timestamp.desc()).all()

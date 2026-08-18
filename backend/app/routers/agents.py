from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=schemas.AgentOut)
def create_agent(payload: schemas.AgentCreate, db: Session = Depends(get_db)):
    agent = models.Agent(name=payload.name, description=payload.description)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("", response_model=list[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.query(models.Agent).all()


@router.get("/{agent_id}", response_model=schemas.AgentOut)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.post("/{agent_id}/activate-profile/{profile_id}", response_model=schemas.AgentOut)
def activate_profile(agent_id: str, profile_id: str, db: Session = Depends(get_db)):
    """Associate a profile with an agent — it becomes the baseline for runtime monitoring."""
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    profile = db.query(models.AgentProfile).filter(
        models.AgentProfile.id == profile_id, models.AgentProfile.agent_id == agent_id
    ).first()
    if not profile:
        raise HTTPException(404, "Profile not found for this agent")

    agent.active_profile_id = profile.id
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """
    Removes an agent's case file entirely, including every record that
    references it: profiles, execution runs/events, findings, response
    actions, and audit log entries. Done as explicit cascading deletes
    (rather than DB-level ON DELETE CASCADE) so the deletion itself is
    visible, testable application logic — appropriate for a governance
    tool where "what happened to this data" should never be a mystery.
    """
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Break the agent -> active_profile FK first to avoid a constraint
    # conflict while deleting profiles below.
    agent.active_profile_id = None
    db.flush()

    run_ids = [r.id for r in db.query(models.ExecutionRun.id).filter(models.ExecutionRun.agent_id == agent_id)]
    finding_ids = [f.id for f in db.query(models.Finding.id).filter(models.Finding.agent_id == agent_id)]

    if finding_ids:
        db.query(models.ResponseAction).filter(models.ResponseAction.finding_id.in_(finding_ids)).delete(synchronize_session=False)
    db.query(models.Finding).filter(models.Finding.agent_id == agent_id).delete(synchronize_session=False)
    if run_ids:
        db.query(models.ExecutionEvent).filter(models.ExecutionEvent.run_id.in_(run_ids)).delete(synchronize_session=False)
    db.query(models.ExecutionRun).filter(models.ExecutionRun.agent_id == agent_id).delete(synchronize_session=False)
    db.query(models.AgentProfile).filter(models.AgentProfile.agent_id == agent_id).delete(synchronize_session=False)
    db.query(models.AuditLogEntry).filter(models.AuditLogEntry.agent_id == agent_id).delete(synchronize_session=False)

    db.delete(agent)
    db.commit()
    return {"deleted": True, "agent_id": agent_id}

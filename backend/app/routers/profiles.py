from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=schemas.ProfileOut)
def create_profile(payload: schemas.ProfileCreate, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")

    profile = models.AgentProfile(
        agent_id=payload.agent_id,
        name=payload.name,
        description=payload.description,
        owner=payload.owner,
        environment=payload.environment,
        allowed_tools=payload.allowed_tools,
        allowed_data_sources=payload.allowed_data_sources,
        allowed_actions=payload.allowed_actions,
        guardrails={k: v.model_dump() for k, v in payload.guardrails.items()},
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    # Convenience: if the agent has no active profile yet, auto-activate this one.
    if not agent.active_profile_id:
        agent.active_profile_id = profile.id
        db.commit()

    return profile


@router.get("", response_model=list[schemas.ProfileOut])
def list_profiles(agent_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.AgentProfile)
    if agent_id:
        q = q.filter(models.AgentProfile.agent_id == agent_id)
    return q.all()


@router.get("/{profile_id}", response_model=schemas.ProfileOut)
def get_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = db.query(models.AgentProfile).filter(models.AgentProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


@router.put("/{profile_id}", response_model=schemas.ProfileOut)
def update_profile(profile_id: str, payload: schemas.ProfileUpdate, db: Session = Depends(get_db)):
    profile = db.query(models.AgentProfile).filter(models.AgentProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")

    data = payload.model_dump(exclude_unset=True)
    if "guardrails" in data and data["guardrails"] is not None:
        data["guardrails"] = {k: v for k, v in data["guardrails"].items()}
    for field, value in data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}")
def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = db.query(models.AgentProfile).filter(models.AgentProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    db.delete(profile)
    db.commit()
    return {"deleted": True}

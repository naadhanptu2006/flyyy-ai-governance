from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.governance import GovernanceEngine
from app.models import models
from app.models.models import utcnow
from app.schemas import schemas
from app.agent.simulated_agent import run_scenario, run_live_tick

router = APIRouter(prefix="/executions", tags=["executions"])


@router.post("/run", response_model=schemas.RunOut)
def trigger_run(payload: schemas.RunRequest, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if not agent.active_profile_id:
        raise HTTPException(400, "Agent has no active behaviour profile assigned")

    run = models.ExecutionRun(
        agent_id=agent.id,
        profile_id_at_run=agent.active_profile_id,
        status=models.RunStatus.RUNNING,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    trace = run_scenario(db, agent.id, run.id, scenario=payload.scenario)

    # Determine final run status from the trace
    if any(step["result"] == "BLOCKED" and "Blocked:" in step.get("reason", "") for step in trace):
        run.status = models.RunStatus.BLOCKED
    elif any(step["result"] == "BLOCKED" for step in trace):
        run.status = models.RunStatus.PAUSED_FOR_APPROVAL
    else:
        run.status = models.RunStatus.COMPLETED

    run.ended_at = utcnow()
    db.commit()

    # Evaluate guardrails after the run (usage-based, e.g. daily call count)
    engine = GovernanceEngine(db)
    if agent.active_profile:
        engine.check_guardrails(agent.id, agent.active_profile)

    return schemas.RunOut(run_id=run.id, status=run.status.value, trace=trace)


@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(models.ExecutionRun).filter(models.ExecutionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Run not found")
    events = db.query(models.ExecutionEvent).filter(models.ExecutionEvent.run_id == run_id).all()
    return {
        "id": run.id, "agent_id": run.agent_id, "status": run.status.value,
        "started_at": run.started_at, "ended_at": run.ended_at,
        "events": [
            {
                "id": e.id, "event_type": e.event_type.value, "resource_name": e.resource_name,
                "payload": e.payload, "was_permitted": e.was_permitted, "timestamp": e.timestamp,
            } for e in events
        ],
    }


# ---------------------------------------------------------------------
# Live monitoring — a continuously-running session where the frontend
# calls /live/tick on an interval. Each tick is ONE real action through
# the real governance engine (see simulated_agent.run_live_tick), so
# this is genuine ongoing detection/enforcement, not replayed demo data.
# ---------------------------------------------------------------------

@router.post("/live/start", response_model=schemas.RunOut)
def start_live_session(payload: schemas.LiveStartRequest, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if not agent.active_profile_id:
        raise HTTPException(400, "Agent has no active behaviour profile assigned")

    run = models.ExecutionRun(
        agent_id=agent.id,
        profile_id_at_run=agent.active_profile_id,
        status=models.RunStatus.RUNNING,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return schemas.RunOut(run_id=run.id, status=run.status.value, trace=[])


@router.post("/live/tick", response_model=schemas.LiveTickOut)
def live_tick(payload: schemas.LiveTickRequest, db: Session = Depends(get_db)):
    """
    One tick = one real, independently-evaluated action. Unlike a
    scripted /run, ticks don't represent a sequential workflow where one
    step blocks the next — they represent ongoing live traffic. So an
    individual finding (even a block) does NOT halt the session; it's
    recorded as a finding/response exactly like any other deviation, and
    the session keeps ticking until the caller explicitly stops it. This
    mirrors how a real production agent keeps running while individual
    disallowed calls get caught and enforced.
    """
    run = db.query(models.ExecutionRun).filter(models.ExecutionRun.id == payload.run_id).first()
    if not run:
        raise HTTPException(404, "Live session not found")
    if run.status != models.RunStatus.RUNNING:
        raise HTTPException(400, f"Session already stopped (status={run.status.value})")

    step = run_live_tick(db, run.agent_id, run.id)

    engine = GovernanceEngine(db)
    agent = db.query(models.Agent).filter(models.Agent.id == run.agent_id).first()
    if agent and agent.active_profile:
        engine.check_guardrails(agent.id, agent.active_profile)

    return schemas.LiveTickOut(run_id=run.id, status=run.status.value, step=step)


@router.post("/live/stop", response_model=schemas.RunOut)
def stop_live_session(payload: schemas.LiveTickRequest, db: Session = Depends(get_db)):
    run = db.query(models.ExecutionRun).filter(models.ExecutionRun.id == payload.run_id).first()
    if not run:
        raise HTTPException(404, "Live session not found")
    if run.status == models.RunStatus.RUNNING:
        run.status = models.RunStatus.COMPLETED
    run.ended_at = utcnow()
    db.commit()
    return schemas.RunOut(run_id=run.id, status=run.status.value, trace=[])

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.core.automigrate import run_auto_migrate
from app.models import models  # noqa: F401 - ensures models are registered on Base
from app.routers import agents, profiles, executions, governance_routes

# Create tables on startup. For a longer-lived production system this would
# be replaced with Alembic migrations; create_all() is a deliberate
# simplification given the 4-day scope (documented in README).
Base.metadata.create_all(bind=engine)

# Adds any columns a model has gained since a table was first created —
# closes the specific gap create_all() leaves on an existing database
# (see app/core/automigrate.py for why this exists and its limits).
run_auto_migrate(engine, Base)

app = FastAPI(
    title="FLYYY.AI - AI Agent Governance API",
    description="Defines, monitors, detects, and enforces AI agent behaviour "
                "against an approved profile.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened via env-based allow-list in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(profiles.router)
app.include_router(executions.router)
app.include_router(governance_routes.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "flyyy-ai-governance"}


@app.get("/health")
def health():
    return {"status": "healthy"}

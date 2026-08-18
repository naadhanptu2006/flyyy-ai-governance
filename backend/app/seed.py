"""
Seed the database with a demo 'Customer Support Agent' and its approved
behaviour profile, matching the assignment's own example exactly:

  Allowed Tools:   FAQ Search, Email Sender
  Allowed Data:    FAQ Database
  Allowed Actions: Read, Send Email
  Guardrail:       max 1000 model calls/day (80% warning, 90% critical)

Run with: python -m app.seed
"""
from app.core.database import SessionLocal, Base, engine
from app.models import models

Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()
    try:
        existing = db.query(models.Agent).filter(models.Agent.name == "Customer Support Agent").first()
        if existing:
            print(f"Demo agent already exists: {existing.id}")
            return existing

        agent = models.Agent(
            name="Customer Support Agent",
            description="Handles customer FAQs and sends follow-up emails.",
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)

        profile = models.AgentProfile(
            agent_id=agent.id,
            name="Customer Support - v1",
            description="Handles tier-1 customer FAQ lookups and follow-up email confirmations only. No access to billing, account, or internal admin systems.",
            owner="Platform Security Team",
            environment="production",
            allowed_tools=["faq_search", "email_sender"],
            allowed_data_sources=["faq_database"],
            allowed_actions=["read", "send_email"],
            guardrails={
                "max_calls_per_day": {"limit": 1000, "warning_pct": 80, "critical_pct": 90}
            },
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        agent.active_profile_id = profile.id
        db.commit()

        print(f"Seeded agent: {agent.id}")
        print(f"Seeded profile: {profile.id}")
        return agent
    finally:
        db.close()


if __name__ == "__main__":
    seed()

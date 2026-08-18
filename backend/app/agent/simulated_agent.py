"""
Simulated agent environment — now generic across ANY agent's profile.

Per the assignment: "The primary focus is the governance and enforcement
mechanism, rather than building a complex AI agent itself." So this agent
is intentionally simple, but it is NOT hardcoded to one specific agent's
tool names — it reads whatever profile is active for the agent it's
running against, so this works correctly for the seeded "Customer Support
Agent" AND for any new agent + profile a user creates through the UI.

Every action still goes through GovernanceEngine.check_and_log() BEFORE
it runs, exactly as a real LangChain/LangGraph agent's tool-calling layer
would be wrapped in production.

Two scenarios:
  "normal"    -> the agent exercises exactly the tools/data
                 sources/actions listed in its OWN active profile. Since
                 these are, by definition, all permitted, this always
                 completes cleanly for any agent.
  "deviation" -> runs the normal steps above, then additionally attempts
                 three fixed, deliberately out-of-scope actions
                 (an "admin"-flavoured tool call, a "customer"-flavoured
                 data access, and a "delete"-flavoured action). These
                 resource names are chosen so the severity heuristic in
                 governance.py reliably classifies them as medium/high,
                 giving a consistent demo of both response tiers
                 regardless of what the agent's own profile contains.
"""
from sqlalchemy.orm import Session

from app.core.governance import GovernanceEngine, GovernanceBlockedError
from app.models.models import Agent, EventType

# Fixed, deliberately out-of-scope probes used in the "deviation" scenario.
# Chosen so the keyword-based severity scorer in governance.py reliably
# classifies them (see GovernanceEngine._score_severity):
#   "admin" / "delete"  -> high severity  -> BLOCK
#   "customer"          -> medium severity -> REQUIRE_APPROVAL
ROGUE_TOOL = "system_admin_override"
ROGUE_DATA_SOURCE = "customer_records_archive"
ROGUE_ACTION = "bulk_delete_records"


class SimulatedAgent:
    """
    Wraps every attempted action through the GovernanceEngine. This class
    stands in for "the agent framework's tool-execution layer" — in a real
    LangGraph/LangChain integration, this same interception would happen
    inside a custom Tool wrapper or callback handler. Because tool
    implementations aren't known ahead of time (they come from whatever
    the user typed into the profile editor), execution of a *permitted*
    call is a generic, clearly-labelled simulation rather than a real
    side effect — the point being demonstrated is the governance decision,
    not the tool's business logic.
    """

    def __init__(self, db: Session, agent_id: str, run_id: str):
        self.db = db
        self.agent_id = agent_id
        self.run_id = run_id
        self.engine = GovernanceEngine(db)
        self.trace = []  # human-readable execution trace for the demo/API response

    def _attempt(self, event_type: EventType, resource_name: str, step_label: str, **kwargs):
        try:
            self.engine.check_and_log(
                run_id=self.run_id, agent_id=self.agent_id,
                event_type=event_type, resource_name=resource_name,
                payload=kwargs,
            )
        except GovernanceBlockedError as e:
            self.trace.append({"step": step_label, "result": "BLOCKED",
                                "reason": str(e), "finding_id": e.finding_id})
            return {"status": "blocked", "reason": str(e), "finding_id": e.finding_id}

        output = f"[SIMULATED] {event_type.value} '{resource_name}' completed with {kwargs or '{}'}"
        self.trace.append({"step": step_label, "result": "executed", "output": output})
        return {"status": "executed", "output": output}

    def call_tool(self, tool_name: str, **kwargs):
        return self._attempt(EventType.TOOL_CALL, tool_name, f"call_tool({tool_name})", **kwargs)

    def access_data(self, source_name: str, **kwargs):
        return self._attempt(EventType.DATA_ACCESS, source_name, f"access_data({source_name})", **kwargs)

    def perform_action(self, action_name: str, **kwargs):
        return self._attempt(EventType.ACTION, action_name, f"perform_action({action_name})", **kwargs)


def run_scenario(db: Session, agent_id: str, run_id: str, scenario: str = "normal"):
    """
    Drives a SimulatedAgent using the AGENT'S OWN active profile — works
    for any agent, not just a hardcoded one.
    """
    agent_row = db.query(Agent).filter(Agent.id == agent_id).first()
    profile = agent_row.active_profile if agent_row else None

    sim = SimulatedAgent(db, agent_id, run_id)

    if profile:
        # Exercise every tool/data-source/action the profile actually
        # approves — by construction, all of these should succeed.
        for tool in (profile.allowed_tools or []):
            sim.call_tool(tool, query="sample request")
        for source in (profile.allowed_data_sources or []):
            sim.access_data(source, query="sample lookup")
        for action in (profile.allowed_actions or []):
            sim.perform_action(action, context="routine")
    else:
        # No profile at all -> nothing is permitted; record one attempt
        # so the run isn't silently empty, and let governance deny it
        # (fail-closed default, see governance._is_permitted).
        sim.call_tool("any_tool", query="no profile assigned")

    if scenario == "deviation":
        sim.access_data(ROGUE_DATA_SOURCE, query="SELECT * FROM customers")
        sim.call_tool(ROGUE_TOOL, reason="unscheduled maintenance")
        sim.perform_action(ROGUE_ACTION, target="archived_records")

    return sim.trace


def run_live_tick(db: Session, agent_id: str, run_id: str):
    """
    Executes ONE action for a continuous "Live Monitor" session, chosen
    randomly each call rather than following a fixed script. This is what
    backs the Run Console's "Live monitor" mode: real calls through the
    real governance engine at real intervals, not pre-baked demo data.

    Mix: mostly draws from the agent's own approved profile (so most
    ticks are clean, like real traffic), occasionally draws one of the
    rogue probes (so the live feed periodically demonstrates detection
    and enforcement too) — the same probes used by the "deviation"
    scenario, for the same severity-classification reasons.
    """
    import random

    agent_row = db.query(Agent).filter(Agent.id == agent_id).first()
    profile = agent_row.active_profile if agent_row else None
    sim = SimulatedAgent(db, agent_id, run_id)

    allowed_pool = []
    if profile:
        allowed_pool += [(EventType.TOOL_CALL, "call_tool", t) for t in (profile.allowed_tools or [])]
        allowed_pool += [(EventType.DATA_ACCESS, "access_data", d) for d in (profile.allowed_data_sources or [])]
        allowed_pool += [(EventType.ACTION, "perform_action", a) for a in (profile.allowed_actions or [])]

    rogue_pool = [
        (EventType.DATA_ACCESS, "access_data", ROGUE_DATA_SOURCE),
        (EventType.TOOL_CALL, "call_tool", ROGUE_TOOL),
        (EventType.ACTION, "perform_action", ROGUE_ACTION),
    ]

    # 75% chance of drawing normal traffic (if any exists), else a probe.
    pool = allowed_pool if (allowed_pool and random.random() < 0.75) else rogue_pool
    _, method_name, resource = random.choice(pool)
    getattr(sim, method_name)(resource, tick="live")

    return sim.trace[-1] if sim.trace else None


"""
Automated tests for the AI Agent Governance system.

Run with:  pytest tests/ -v
(from the backend/ directory, with DATABASE_URL unset — these tests use
an isolated in-memory SQLite database so they never touch Postgres.)
"""
import os
import uuid

os.environ["DATABASE_URL"] = f"sqlite:///./_test_{uuid.uuid4().hex}.db"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app

Base.metadata.create_all(bind=engine)
client = TestClient(app)


@pytest.fixture
def agent_with_profile():
    """Creates a fresh agent + profile with a small, arbitrary tool set."""
    r = client.post("/agents", json={"name": f"Test Agent {uuid.uuid4().hex[:6]}"})
    assert r.status_code == 200
    agent = r.json()

    r = client.post("/profiles", json={
        "agent_id": agent["id"], "name": "v1",
        "allowed_tools": ["lookup_order", "send_notification"],
        "allowed_data_sources": ["orders_db"],
        "allowed_actions": ["read", "notify"],
        "guardrails": {"max_calls_per_day": {"limit": 5, "warning_pct": 60, "critical_pct": 80}},
    })
    assert r.status_code == 200
    return agent


class TestAgentAndProfileCRUD:
    def test_create_and_list_agents(self):
        r = client.post("/agents", json={"name": "CRUD Test Agent"})
        assert r.status_code == 200
        r = client.get("/agents")
        assert r.status_code == 200
        assert any(a["name"] == "CRUD Test Agent" for a in r.json())

    def test_create_profile_auto_activates_first_profile(self, agent_with_profile):
        agent = agent_with_profile
        r = client.get(f"/agents/{agent['id']}")
        assert r.json()["active_profile_id"] is not None

    def test_update_profile(self, agent_with_profile):
        agent = agent_with_profile
        profiles = client.get("/profiles", params={"agent_id": agent["id"]}).json()
        profile_id = profiles[0]["id"]

        r = client.put(f"/profiles/{profile_id}", json={"allowed_tools": ["lookup_order"]})
        assert r.status_code == 200
        assert r.json()["allowed_tools"] == ["lookup_order"]

    def test_delete_agent_cascades_related_records(self, agent_with_profile):
        agent = agent_with_profile
        client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})
        findings_before = client.get("/findings", params={"agent_id": agent["id"]}).json()
        assert len(findings_before) > 0

        r = client.delete(f"/agents/{agent['id']}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True

        assert client.get(f"/agents/{agent['id']}").status_code == 404
        assert client.get("/findings", params={"agent_id": agent["id"]}).json() == []
        assert client.get("/profiles", params={"agent_id": agent["id"]}).json() == []

    def test_delete_nonexistent_agent_404s(self):
        r = client.delete("/agents/does-not-exist")
        assert r.status_code == 404


class TestGovernanceEnforcement:
    def test_normal_run_completes_cleanly(self, agent_with_profile):
        agent = agent_with_profile
        r = client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "normal"})
        assert r.status_code == 200
        result = r.json()
        assert result["status"] == "completed"
        assert all(step["result"] == "executed" for step in result["trace"])

    def test_deviation_run_is_blocked(self, agent_with_profile):
        agent = agent_with_profile
        r = client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})
        result = r.json()
        assert result["status"] == "blocked"
        blocked_steps = [s for s in result["trace"] if s["result"] == "BLOCKED"]
        assert len(blocked_steps) == 3  # rogue tool, data source, and action

    def test_deviation_creates_findings_with_evidence(self, agent_with_profile):
        agent = agent_with_profile
        client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})
        findings = client.get("/findings", params={"agent_id": agent["id"]}).json()

        assert len(findings) == 3
        for f in findings:
            assert f["expected_behavior"]
            assert f["actual_behavior"]
            assert f["severity"] in ("low", "medium", "high")
            assert f["run_id"]
            assert f["detected_at"]

    def test_severity_maps_to_correct_response_tier(self, agent_with_profile):
        agent = agent_with_profile
        client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})
        findings = client.get("/findings", params={"agent_id": agent["id"]}).json()
        responses = client.get("/responses").json()

        by_finding = {r["finding_id"]: r for r in responses}
        for f in findings:
            resp = by_finding[f["id"]]
            if f["severity"] == "high":
                assert resp["action_type"] == "block"
            elif f["severity"] == "medium":
                assert resp["action_type"] == "require_approval"
            else:
                assert resp["action_type"] == "notify"

    def test_agent_with_no_profile_denies_everything(self):
        r = client.post("/agents", json={"name": "No Profile Agent"})
        agent = r.json()
        r = client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "normal"})
        assert r.status_code == 400  # enforced at the API layer: run requires an active profile


class TestApprovalWorkflow:
    def test_approve_pending_response(self, agent_with_profile):
        agent = agent_with_profile
        client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})
        responses = client.get("/responses", params={"status": "pending"}).json()
        approval = next(r for r in responses if r["action_type"] == "require_approval")

        r = client.post(f"/responses/{approval['id']}/approve",
                         json={"approver": "test@flyyy.ai", "reason": "confirmed safe"})
        assert r.status_code == 200
        assert r.json()["status"] == "approved"
        assert r.json()["approver"] == "test@flyyy.ai"

    def test_cannot_approve_twice(self, agent_with_profile):
        agent = agent_with_profile
        client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})
        responses = client.get("/responses", params={"status": "pending"}).json()
        approval = next(r for r in responses if r["action_type"] == "require_approval")

        client.post(f"/responses/{approval['id']}/approve", json={"approver": "a@b.com"})
        r = client.post(f"/responses/{approval['id']}/approve", json={"approver": "a@b.com"})
        assert r.status_code == 400  # already resolved


class TestGuardrails:
    def test_guardrail_warning_fires_at_threshold(self, agent_with_profile):
        agent = agent_with_profile
        # Guardrail limit is 5 calls/day (fixture above); a deviation run
        # generates 2 normal tool calls + 1 rogue tool call = 3 events,
        # well under 5 but let's run twice to push over threshold.
        client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})
        client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})

        r = client.get("/guardrails/status", params={"agent_id": agent["id"]})
        assert r.status_code == 200
        warnings = r.json()["warnings"]
        assert len(warnings) >= 1
        assert warnings[0]["guardrail"] == "max_calls_per_day"


class TestAuditTrail:
    def test_every_deviation_and_response_is_audited(self, agent_with_profile):
        agent = agent_with_profile
        client.post("/executions/run", json={"agent_id": agent["id"], "scenario": "deviation"})

        audit = client.get("/audit-log", params={"agent_id": agent["id"]}).json()
        event_types = {e["event_type"] for e in audit}

        assert "deviation_detected" in event_types
        assert any(t.startswith("response_") for t in event_types)
        for entry in audit:
            assert entry["actor"]
            assert entry["timestamp"]


class TestLiveMonitor:
    def test_live_session_survives_blocked_ticks(self, agent_with_profile):
        agent = agent_with_profile
        r = client.post("/executions/live/start", json={"agent_id": agent["id"]})
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        assert r.json()["status"] == "running"

        for _ in range(15):
            r = client.post("/executions/live/tick", json={"run_id": run_id})
            assert r.status_code == 200
            assert r.json()["status"] == "running"  # session never dies mid-tick
            assert r.json()["step"] is not None

        r = client.post("/executions/live/stop", json={"run_id": run_id})
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_live_ticks_accumulate_real_findings(self, agent_with_profile):
        agent = agent_with_profile
        run_id = client.post("/executions/live/start", json={"agent_id": agent["id"]}).json()["run_id"]
        for _ in range(20):
            client.post("/executions/live/tick", json={"run_id": run_id})
        client.post("/executions/live/stop", json={"run_id": run_id})

        findings = client.get("/findings", params={"agent_id": agent["id"]}).json()
        assert len(findings) > 0  # with 20 ticks at 25% rogue rate, virtually certain

    def test_cannot_tick_after_stop(self, agent_with_profile):
        agent = agent_with_profile
        run_id = client.post("/executions/live/start", json={"agent_id": agent["id"]}).json()["run_id"]
        client.post("/executions/live/stop", json={"run_id": run_id})

        r = client.post("/executions/live/tick", json={"run_id": run_id})
        assert r.status_code == 400

    def test_live_start_requires_active_profile(self):
        r = client.post("/agents", json={"name": "No Profile Live Agent"})
        agent = r.json()
        r = client.post("/executions/live/start", json={"agent_id": agent["id"]})
        assert r.status_code == 400

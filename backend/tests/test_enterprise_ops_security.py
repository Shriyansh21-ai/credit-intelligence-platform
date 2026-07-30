"""Track 4 M7 (Operations) + M8 (Security) tests."""

from backend.tests._enterprise_platform_helpers import admin_client, fresh_session, seed_rbac, make_user, client_for, seed_company


def test_operations_health_and_incidents():
    Session, client = admin_client()
    db = Session()
    seed_company(db, company_name="OpsCo")
    db.close()
    r = client.get("/api/ent/operations/dashboard")
    assert r.json()["overall_status"] in ("healthy", "warning", "degraded", "critical", "down", "unknown")
    assert "components" in r.json() and "telemetry" in r.json()
    client.post("/api/ent/operations/runbooks/seed")
    r = client.get("/api/ent/operations/runbooks")
    assert len(r.json()["runbooks"]) >= 3
    r = client.post("/api/ent/operations/incidents", json={"title": "AI latency spike", "component": "ai",
                                                          "severity": "sev2", "runbook_key": "ai-provider-outage"})
    iid = r.json()["incident_id"]
    # opening a sev2 incident degrades the ai component health
    r = client.get("/api/ent/operations/dashboard")
    assert r.json()["components"]["ai"]["open_incidents"] >= 1
    r = client.get(f"/api/ent/operations/incidents/{iid}/rca")
    assert "hypotheses" in r.json() and r.json()["recommended_runbook"] == "ai-provider-outage"
    r = client.post("/api/ent/operations/incidents/update", json={"incident_id": iid, "status": "resolved",
                                                                "root_cause": "provider outage"})
    assert r.json()["status"] == "resolved"


def test_security_center():
    _, client = admin_client()
    r = client.post("/api/ent/security/analyze-session", json={"subject_ref": "user@x.com",
                                                             "failed_logins": 6, "new_device": True,
                                                             "impossible_travel": True})
    assert r.json()["decision"] == "block" and r.json()["risk_score"] > 0.8
    r = client.post("/api/ent/security/escalation-check", json={"subject_ref": "user@x.com",
                                                             "granted_permissions": ["roles.manage", "users.manage"]})
    assert r.json()["escalation_detected"] is True
    r = client.get("/api/ent/security/events")
    assert len(r.json()["events"]) >= 2
    r = client.get("/api/ent/security/dashboard")
    assert "security_score" in r.json() and "zero_trust" in r.json()


def test_access_reviews():
    _, client = admin_client()
    r = client.post("/api/ent/security/access-reviews", json={"scope": "role:administrator"})
    rid = r.json()["review_id"]
    assert isinstance(r.json()["findings"], list)
    r = client.post("/api/ent/security/access-reviews/complete", json={"review_id": rid, "decision": "approved"})
    assert r.json()["status"] == "approved"
    r = client.get("/api/ent/security/key-rotation")
    assert "posture" in r.json()

""" M9 (Customer Success) + M10 (Deployment) tests."""

from backend.tests._enterprise_platform_helpers import admin_client


def test_customer_lifecycle():
    _, client = admin_client()
    r = client.post("/api/ent/success", json={"name": "Bank One", "segment": "enterprise",
                                            "tier": "strategic", "arr": 250000})
    cid = r.json()["customer_id"]
    assert r.json()["status"] == "onboarding"
    # advance onboarding to go-live
    for _ in range(5):
        client.post("/api/ent/success/onboarding/advance", json={"customer_id": cid})
    r = client.get(f"/api/ent/success/{cid}")
    assert r.json()["status"] == "live"
    # open a ticket → health drops
    client.post("/api/ent/success/events", json={"customer_id": cid, "event_type": "ticket",
                                               "title": "integration bug", "status": "open"})
    r = client.get(f"/api/ent/success/{cid}/recommendations")
    assert r.json()["confidence"] >= 0 and "reasoning" in r.json() and r.json()["citations"]
    r = client.get("/api/ent/success/dashboard")
    assert r.json()["customers"] == 1 and r.json()["total_arr"] == 250000


def test_deployment_and_rollback():
    _, client = admin_client()
    client.post("/api/ent/deployment/environments/seed")
    r = client.get("/api/ent/deployment/environments")
    envs = {e["name"]: e["environment_id"] for e in r.json()["environments"]}
    assert "production" in envs
    prod = envs["production"]
    r = client.post("/api/ent/deployment/deploy", json={"environment_id": prod, "version": "1.0.0",
                                                       "strategy": "blue_green", "release_notes": "GA"})
    assert r.json()["status"] == "succeeded" and len(r.json()["steps"]) >= 4
    r = client.post("/api/ent/deployment/deploy", json={"environment_id": prod, "version": "1.1.0",
                                                       "strategy": "canary", "canary_percent": 10})
    assert r.json()["strategy"] == "canary"
    r = client.post("/api/ent/deployment/rollback", json={"environment_id": prod})
    assert r.json()["now_at"] == "1.0.0" and r.json()["status"] == "rolled_back"
    r = client.get("/api/ent/deployment/versions")
    assert r.json()["environments"]["production"] == "1.0.0"
    r = client.get("/api/ent/deployment/history")
    assert len(r.json()["deployments"]) >= 3

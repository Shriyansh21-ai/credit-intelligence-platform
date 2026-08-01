""" M3 (Developer) + M4 (Marketplace) tests."""

from backend.tests._enterprise_platform_helpers import admin_client


def test_api_keys_and_rate_limit():
    _, client = admin_client()
    r = client.post("/api/ent/developer/keys", json={"name": "CI key", "environment": "sandbox",
                                                    "rate_limit_per_min": 100})
    j = r.json()
    assert j["secret"].startswith("sk_test_") and "prefix" in j
    kid = j["api_key_id"]
    r = client.get("/api/ent/developer/keys")
    assert len(r.json()["api_keys"]) == 1
    # secret must not be persisted/returned in listing
    assert "secret" not in r.json()["api_keys"][0]
    r = client.post("/api/ent/developer/keys/rate-limit-test", json={"api_key_id": kid, "requests": 250})
    assert r.json()["allowed"] == 100 and r.json()["throttled"] == 150
    r = client.post(f"/api/ent/developer/keys/{kid}/revoke")
    assert r.json()["status"] == "revoked"


def test_webhooks_test_and_replay():
    _, client = admin_client()
    r = client.post("/api/ent/developer/webhooks", json={"url": "https://x.test/hook",
                                                        "events": ["assessment.created"]})
    wid = r.json()["webhook_id"]
    assert r.json()["signing_secret"].startswith("whsec_")
    r = client.post("/api/ent/developer/webhooks/test", json={"webhook_id": wid})
    did = r.json()["delivery_id"]
    assert r.json()["status"] == "delivered"
    r = client.post(f"/api/ent/developer/webhooks/deliveries/{did}/replay")
    assert r.json()["replay_of"] == did
    r = client.get("/api/ent/developer/webhooks/deliveries")
    assert len(r.json()["deliveries"]) == 2


def test_sandbox_and_explorer():
    _, client = admin_client()
    r = client.post("/api/ent/developer/sandbox", json={"method": "POST", "path": "/api/fin/treasury/kpis"})
    assert r.json()["status_code"] == 200 and r.json()["response"]["sandbox"] is True
    r = client.get("/api/ent/developer/requests")
    assert len(r.json()["requests"]) == 1
    r = client.get("/api/ent/developer/explorer")
    assert r.json()["total_paths"] > 0


def test_marketplace_lifecycle():
    _, client = admin_client()
    r = client.post("/api/ent/marketplace/publish", json={"key": "risk-connector", "name": "Risk Connector",
                                                         "version": "1.0.0", "category": "risk",
                                                         "billing_model": "subscription"})
    pid = r.json()["plugin_id"]
    assert r.json()["status"] == "submitted"
    # version approval
    plugin = client.get(f"/api/ent/marketplace/{pid}").json()
    vid = None
    # need version id — list via detail; approve latest by fetching versions is not exposed, so approve via review needs version_id
    # fetch the version id through a fresh add path: approve the initial submission
    # (initial version was created at publish; find it by re-submitting review on version 1)
    # We expose review by version_id; retrieve it from the DB-less API by publishing a new version
    r = client.post("/api/ent/marketplace/versions", json={"plugin_id": pid, "version": "1.1.0",
                                                          "changelog": "improvements"})
    vid = r.json()["version_id"]
    r = client.post("/api/ent/marketplace/review", json={"version_id": vid, "approve": True})
    assert r.json()["status"] == "approved"
    r = client.post(f"/api/ent/marketplace/{pid}/publish")
    assert r.json()["status"] == "published"
    r = client.get(f"/api/ent/marketplace/{pid}/compatibility")
    assert r.json()["compatible"] is True
    r = client.post(f"/api/ent/marketplace/{pid}/install")
    assert r.json()["status"] == "active"
    r = client.get("/api/ent/marketplace/analytics/summary")
    assert r.json()["published"] >= 1 and r.json()["total_installs"] >= 1

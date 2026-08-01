""" M11 (Monitoring) + M12 (BI) + M13 (Launch Readiness) tests."""

from backend.tests._enterprise_platform_helpers import admin_client, fresh_session, seed_rbac, make_user, client_for, seed_company


def test_monitoring_tracing_and_sla():
    _, client = admin_client()
    spans = [{"id": "a", "service": "gateway", "op": "handle", "duration_ms": 20},
             {"id": "b", "service": "assessment", "op": "score", "duration_ms": 80, "parent": "a"},
             {"id": "c", "service": "db", "op": "query", "duration_ms": 15, "parent": "b"}]
    r = client.post("/api/ent/monitoring/traces", json={"root_service": "gateway", "operation": "assess",
                                                      "spans": spans})
    assert r.json()["span_count"] == 3
    r = client.get("/api/ent/monitoring/dependency-graph")
    assert r.json()["service_count"] >= 3 and len(r.json()["edges"]) >= 2
    r = client.get("/api/ent/monitoring/latency")
    assert "p99_ms" in r.json()
    client.post("/api/ent/monitoring/sla", json={"service": "gateway", "metric": "availability",
                                               "target": 0.999, "actual": 0.995})
    r = client.get("/api/ent/monitoring/sla")
    assert r.json()["breached"] >= 1
    r = client.get("/api/ent/monitoring/cost")
    assert "total_usd" in r.json()
    r = client.get("/api/ent/monitoring/dashboard")
    assert "latency" in r.json() and "cost" in r.json()


def test_bi_analytics_and_board_report():
    Session, client = admin_client()
    db = Session()
    seed_company(db, company_name="BiCo")
    db.close()
    client.post("/api/ent/success", json={"name": "Cust", "arr": 100000})
    r = client.get("/api/ent/bi/analytics", params={"category": "revenue"})
    assert r.json()["metrics"]["total_arr"] == 100000
    r = client.get("/api/ent/bi/analytics", params={"category": "executive"})
    assert "revenue" in r.json()["metrics"]
    r = client.get("/api/ent/bi/board-report")
    assert "headline" in r.json() and "sections" in r.json()
    r = client.post("/api/ent/bi/dashboards", json={"name": "Exec View", "category": "executive",
                                                  "widgets": [{"type": "kpi", "metric": "arr"}]})
    assert r.json()["key"] == "exec-view"
    r = client.get("/api/ent/bi/dashboards")
    assert len(r.json()["dashboards"]) == 1


def test_launch_readiness():
    _, client = admin_client()
    r = client.get("/api/ent/launch/checklist-types")
    assert "security" in r.json()["checklist_types"]
    r = client.post("/api/ent/launch/generate", json={"checklist_type": "security"})
    cid = r.json()["checklist_id"]
    assert r.json()["total"] > 0 and 0 <= r.json()["readiness_score"] <= 100
    # complete a pending item
    r = client.post("/api/ent/launch/items/update", json={"checklist_id": cid, "item_key": "pentest",
                                                        "status": "done"})
    assert r.json()["readiness_score"] >= 0
    r = client.post("/api/ent/launch/generate-all")
    assert r.json()["checklists"] == 10 and "overall_readiness_score" in r.json()
    r = client.get("/api/ent/launch/readiness")
    assert "commercial_ready" in r.json()

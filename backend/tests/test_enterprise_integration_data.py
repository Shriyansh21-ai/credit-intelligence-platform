""" M5 (Integration) + M6 (Data Management) tests."""

from backend.tests._enterprise_platform_helpers import admin_client

GRAPH = {
    "nodes": [
        {"id": "s1", "type": "source"},
        {"id": "t1", "type": "transform", "config": {"multiply": 2}},
        {"id": "k1", "type": "sink"},
    ],
    "edges": [{"from": "s1", "to": "t1"}, {"from": "t1", "to": "k1"}],
}


def test_pipeline_validate_save_run():
    _, client = admin_client()
    r = client.post("/api/ent/integration/validate", json={"name": "x", "graph": GRAPH})
    assert r.json()["valid"] is True
    r = client.post("/api/ent/integration/validate", json={"name": "x", "graph": {"nodes": [], "edges": []}})
    assert r.json()["valid"] is False
    r = client.post("/api/ent/integration", json={"name": "ETL One", "graph": GRAPH})
    pid = r.json()["pipeline_id"]
    r = client.post("/api/ent/integration/run", json={"pipeline_id": pid, "sample_input": {"id": 1, "value": 50}})
    assert r.json()["status"] == "succeeded" and r.json()["output"]["value"] == 100
    r = client.get(f"/api/ent/integration/{pid}/runs")
    assert len(r.json()["runs"]) == 1


def test_mdm_golden_and_duplicates():
    _, client = admin_client()
    client.post("/api/ent/data/golden", json={"entity_type": "customer", "natural_key": "c1",
                                             "record": {"name": "Acme Industries Ltd", "country": "IN"}})
    client.post("/api/ent/data/golden", json={"entity_type": "customer", "natural_key": "c2",
                                             "record": {"name": "Acme Industries Limited", "country": "IN"}})
    client.post("/api/ent/data/golden", json={"entity_type": "customer", "natural_key": "c3",
                                             "record": {"name": "Zenith Corp"}})
    r = client.get("/api/ent/data/golden", params={"entity_type": "customer"})
    assert len(r.json()["records"]) == 3
    r = client.post("/api/ent/data/duplicates", json={"entity_type": "customer", "threshold": 0.5})
    assert r.json()["candidates"] >= 1
    # entity resolution finds the match
    r = client.post("/api/ent/data/resolve", json={"entity_type": "customer",
                                                  "record": {"name": "Acme Industries Ltd"}, "threshold": 0.7})
    assert r.json()["matched"] is True


def test_data_quality_and_bulk():
    _, client = admin_client()
    client.post("/api/ent/data/rules", json={"name": "name required", "dimension": "completeness",
                                            "entity_type": "vendor", "field": "name"})
    r = client.post("/api/ent/data/import", json={"entity_type": "vendor", "key_field": "id",
                                                "records": [{"id": "v1", "name": "Vendor A"},
                                                            {"id": "v2", "name": ""}]})
    assert r.json()["imported"] == 2
    r = client.post("/api/ent/data/quality-scan", params={"entity_type": "vendor"})
    assert r.json()["rules_run"] >= 1 and r.json()["quality_score"] <= 100
    r = client.get("/api/ent/data/catalog")
    assert "vendor" in r.json()["entities"]
    r = client.get("/api/ent/data/export", params={"entity_type": "vendor"})
    assert r.json()["count"] == 2
    r = client.get("/api/ent/data/jobs")
    assert len(r.json()["jobs"]) >= 2

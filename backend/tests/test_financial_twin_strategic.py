"""Track 3 M13 (Digital Twin) + M14 (Strategic Intelligence) tests."""

from backend.tests._financial_intelligence_helpers import admin_client, seed_company, seed_portfolio_companies


def test_twin_create_and_simulate():
    Session, client = admin_client()
    db = Session()
    seed_company(db, company_name="TwinCo", industry="manufacturing")
    db.close()
    r = client.get("/api/fin/twin/types")
    assert "company" in r.json()["twin_types"]
    r = client.post("/api/fin/twin", json={"key": "twin1", "name": "TwinCo Model",
                                          "twin_type": "company", "subject_ref": "TwinCo"})
    tid = r.json()["twin_id"]
    assert "revenue" in r.json()["state"]
    r = client.post(f"/api/fin/twin/{tid}/simulate", json={"horizon": 5})
    j = r.json()
    assert len(j["path"]) == 6  # t=0..5
    assert "terminal_state" in j and "deltas" in j
    # scenario shock reduces growth
    r2 = client.post(f"/api/fin/twin/{tid}/simulate", json={"horizon": 5, "scenario": {"revenue": -0.10}})
    assert r2.json()["terminal_state"]["revenue"] < j["terminal_state"]["revenue"]
    r = client.get(f"/api/fin/twin/{tid}/simulations")
    assert len(r.json()["simulations"]) == 2


def test_twin_duplicate_key_rejected():
    _, client = admin_client()
    client.post("/api/fin/twin", json={"key": "dup", "name": "A", "twin_type": "economy"})
    r = client.post("/api/fin/twin", json={"key": "dup", "name": "B", "twin_type": "economy"})
    assert r.status_code == 400


def test_strategic_reports():
    Session, client = admin_client()
    db = Session()
    seed_portfolio_companies(db, n=4)
    seed_company(db, company_name="StratCo", industry="technology")
    db.close()
    client.post("/api/fin/economic/seed")
    r = client.get("/api/fin/strategic/types")
    assert "executive_briefing" in r.json()["report_types"]
    r = client.post("/api/fin/strategic/generate", json={"report_type": "executive_briefing"})
    j = r.json()
    assert j["sections"] and "checksum" in j
    # every section carries evidence/citation
    for s in j["sections"]:
        assert "evidence" in s and "checksum" in s["evidence"]
    r = client.post("/api/fin/strategic/generate", json={"report_type": "competitor", "subject_ref": "StratCo"})
    assert r.json()["report_id"] > 0
    r = client.get("/api/fin/strategic/list")
    assert len(r.json()["reports"]) >= 2

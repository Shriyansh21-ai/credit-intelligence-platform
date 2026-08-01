""" M10 (Benchmarking) + M11 (Executive) + M12 (Optimization) tests."""

from backend.tests._financial_intelligence_helpers import admin_client, seed_company, seed_portfolio_companies


def test_benchmark():
    Session, client = admin_client()
    db = Session()
    seed_company(db, company_name="Target", industry="manufacturing", score=720)
    seed_company(db, company_name="Peer1", industry="manufacturing", score=600)
    seed_company(db, company_name="Peer2", industry="manufacturing", score=650)
    db.close()
    r = client.post("/api/fin/benchmark/run", json={"subject_ref": "Target"})
    j = r.json()
    assert j["peer_count"] >= 2
    assert "competitive_position" in j and "rankings" in j
    assert 0 <= j["overall_percentile"] <= 100


def test_executive_personas():
    Session, client = admin_client()
    db = Session()
    seed_portfolio_companies(db, n=5)
    db.close()
    r = client.get("/api/fin/executive/personas")
    assert "ceo" in r.json()["personas"]
    for persona in ("ceo", "cfo", "cro", "treasurer", "regulator", "rm"):
        r = client.post("/api/fin/executive/dashboard", json={"persona": persona})
        assert r.status_code == 200
        assert r.json()["kpis"] and r.json()["summary"]
    r = client.post("/api/fin/executive/dashboard", json={"persona": "nonexistent"})
    assert r.status_code == 400


def test_optimization_suite():
    Session, client = admin_client()
    db = Session()
    seed_company(db, company_name="Borrower", industry="retail", pd=0.06)
    db.close()
    r = client.post("/api/fin/optimize/loan-pricing", json={"subject_ref": "Borrower"})
    assert r.json()["solution"]["recommended_rate_pct"] > r.json()["solution"]["breakeven_rate_pct"]
    r = client.post("/api/fin/optimize/credit-limit", json={"subject_ref": "Borrower"})
    assert r.json()["solution"]["recommended_limit"] > 0
    r = client.post("/api/fin/optimize/portfolio-allocation", json={
        "budget": 10_000_000, "candidates": [
            {"name": "a", "spread": 0.05, "pd": 0.02, "lgd": 0.4},
            {"name": "b", "spread": 0.03, "pd": 0.08, "lgd": 0.5}]})
    assert r.json()["solution"]["deployed"] > 0
    r = client.post("/api/fin/optimize/capital-allocation", json={
        "total_capital": 100_000_000, "business_units": [
            {"name": "sme", "raroc": 0.18, "capital_demand": 40_000_000},
            {"name": "corp", "raroc": 0.12, "capital_demand": 60_000_000}]})
    assert "blended_raroc_pct" in r.json()["solution"]
    r = client.post("/api/fin/optimize/collateral", json={
        "exposure": 1_000_000, "collateral_options": [
            {"type": "cash", "value": 400_000, "haircut": 0.0, "cost": 0.01},
            {"type": "property", "value": 1_000_000, "haircut": 0.3, "cost": 0.02}]})
    assert r.json()["solution"]["coverage_ratio_pct"] is not None

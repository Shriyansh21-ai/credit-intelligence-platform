""" M2 — Enterprise Portfolio Intelligence tests."""

from backend.tests._financial_intelligence_helpers import (
    admin_client, fresh_session, seed_rbac, make_user, client_for, seed_portfolio_companies,
)


def _portfolio_with_positions():
    Session, client = admin_client()
    r = client.post("/api/fin/portfolio", json={"key": "book1", "name": "Commercial Book"})
    pid = r.json()["id"]
    for i, (ind, ead, pd, rating) in enumerate([
        ("manufacturing", 5_000_000, 0.04, "BBB"),
        ("manufacturing", 3_000_000, 0.06, "BB"),
        ("technology", 2_000_000, 0.02, "A"),
        ("retail", 1_000_000, 0.12, "B"),
        ("energy", 4_000_000, 0.08, "BB")]):
        client.post("/api/fin/portfolio/positions", json={
            "portfolio_id": pid, "company_ref": f"C{i}", "ead": ead, "pd": pd,
            "lgd": 0.45, "industry": ind, "country": "IN", "rating": rating})
    return client, pid


def test_create_and_positions():
    client, pid = _portfolio_with_positions()
    r = client.get(f"/api/fin/portfolio/{pid}/positions")
    assert len(r.json()["positions"]) == 5


def test_summary_and_concentration():
    client, pid = _portfolio_with_positions()
    r = client.post(f"/api/fin/portfolio/{pid}/summary")
    assert r.json()["position_count"] == 5
    assert r.json()["expected_loss"] > 0
    r = client.post(f"/api/fin/portfolio/{pid}/concentration")
    j = r.json()
    assert "sector" in j and j["single_largest_exposure_pct"] > 0
    assert "heatmap" in j


def test_loss_raroc_simulate():
    client, pid = _portfolio_with_positions()
    r = client.post(f"/api/fin/portfolio/{pid}/loss", json={"confidence": 0.999})
    assert r.json()["credit_var"] >= r.json()["expected_loss"]
    r = client.post(f"/api/fin/portfolio/{pid}/raroc", json={})
    assert "raroc_pct" in r.json()
    r = client.post(f"/api/fin/portfolio/{pid}/simulate", json={"iterations": 800, "seed": 1})
    j = r.json()
    assert j["loss_var"] >= 0 and j["expected_shortfall"] >= j["loss_var"] - 1e-6


def test_optimize_migration_ews_insights():
    client, pid = _portfolio_with_positions()
    r = client.post(f"/api/fin/portfolio/{pid}/optimize", json={"max_single_exposure_pct": 0.1})
    assert "actions" in r.json() and r.json()["hhi_after"] <= r.json()["hhi_before"] + 1e-9
    r = client.post(f"/api/fin/portfolio/{pid}/migration")
    assert "projected_default_ead" in r.json()
    r = client.post(f"/api/fin/portfolio/{pid}/ews", params={"pd_threshold": 0.1})
    assert r.json()["watchlist_count"] >= 1
    r = client.post(f"/api/fin/portfolio/{pid}/insights")
    assert isinstance(r.json()["insights"], list)


def test_sync_from_platform():
    Session, client = admin_client()
    db = Session()
    seed_portfolio_companies(db, n=5)
    db.close()
    pid = client.post("/api/fin/portfolio", json={"key": "live", "name": "Live"}).json()["id"]
    r = client.post(f"/api/fin/portfolio/{pid}/sync")
    assert r.json()["positions_added"] == 5
    r = client.post(f"/api/fin/portfolio/{pid}/summary")
    assert r.json()["position_count"] == 5

""" M8 (Forecasting) + M9 (Quantitative Risk) tests."""

from backend.tests._financial_intelligence_helpers import admin_client, seed_company


def test_forecast_run_and_multi_horizon():
    _, client = admin_client()
    r = client.post("/api/fin/forecast/run", json={"forecast_type": "revenue",
                                                   "history": [100, 110, 121, 133, 146], "horizon": 6})
    j = r.json()
    assert len(j["series"]) == 6
    # confidence bands present and widening
    assert j["series"][-1]["upper"] > j["series"][-1]["lower"]
    r = client.post("/api/fin/forecast/multi-horizon", json={"forecast_type": "cashflow",
                                                            "history": [50, 55, 60], "horizons": [3, 6, 12]})
    assert set(r.json()["horizons"].keys()) == {"3", "6", "12"}


def test_forecast_from_company_profile():
    Session, client = admin_client()
    db = Session()
    seed_company(db, company_name="FcastCo", industry="technology")
    db.close()
    r = client.post("/api/fin/forecast/run", json={"forecast_type": "revenue", "subject_ref": "FcastCo"})
    assert r.json()["metrics"]["terminal_value"] is not None


def test_var_and_montecarlo():
    _, client = admin_client()
    r = client.post("/api/fin/quant/var", json={"volatility": 0.02, "confidence": 0.99,
                                               "portfolio_value": 1_000_000})
    j = r.json()
    assert j["var_amount"] > 0 and j["es_amount"] >= j["var_amount"]
    r = client.post("/api/fin/quant/montecarlo", json={
        "positions": [{"name": "a", "mean": 0.0, "vol": 0.1, "exposure": 1.0},
                      {"name": "b", "mean": 0.0, "vol": 0.15, "exposure": 1.0}],
        "iterations": 1000, "seed": 3})
    assert "var" in r.json() and "expected_shortfall" in r.json()


def test_montecarlo_reproducible():
    _, client = admin_client()
    body = {"positions": [{"name": "a", "mean": 0.0, "vol": 0.1, "exposure": 1.0}],
            "iterations": 500, "seed": 42}
    a = client.post("/api/fin/quant/montecarlo", json=body).json()["var"]
    b = client.post("/api/fin/quant/montecarlo", json=body).json()["var"]
    assert a == b  # deterministic RNG


def test_stress_sensitivity_tree_attribution():
    _, client = admin_client()
    r = client.post("/api/fin/quant/stress", json={"base_value": 1_000_000,
                                                  "factors": {"rates": -5_000_000, "equity": 200_000}})
    assert "worst_case" in r.json()
    r = client.post("/api/fin/quant/sensitivity", json={"base_value": 1000, "factors": {"rate": -50, "fx": 20}})
    assert r.json()["dominant_factor"] in ("rate", "fx")
    r = client.post("/api/fin/quant/scenario-tree", json={"base_value": 100, "stages": 3})
    assert "expected_terminal_value" in r.json()
    r = client.post("/api/fin/quant/attribution", json={
        "positions": [{"name": "a", "exposure": 1.0, "vol": 0.1},
                      {"name": "b", "exposure": 2.0, "vol": 0.2}]})
    assert len(r.json()["components"]) == 2


def test_correlation_volatility_tail():
    _, client = admin_client()
    r = client.post("/api/fin/quant/correlation", json={"series": {
        "a": [1, 2, 3, 4, 5], "b": [2, 4, 6, 8, 10], "c": [5, 4, 3, 2, 1]}})
    assert r.json()["matrix"]["a"]["b"] > 0.9
    r = client.post("/api/fin/quant/volatility", json={"returns": [0.01, -0.02, 0.015, -0.01, 0.02]})
    assert r.json()["annualized_ewma_pct"] > 0
    r = client.post("/api/fin/quant/tail", json={"returns": [0.01, -0.05, 0.02, -0.08, 0.03, -0.12]})
    assert "tail_es" in r.json()

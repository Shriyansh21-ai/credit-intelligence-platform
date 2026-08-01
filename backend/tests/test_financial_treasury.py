""" M1 — Treasury Intelligence tests."""

from backend.tests._financial_intelligence_helpers import admin_client


def _seed_funding(client):
    client.post("/api/fin/treasury/funding-sources", json={
        "name": "Retail Deposits", "source_type": "deposit", "amount": 10_000_000,
        "rate": 0.05, "tenor_days": 0})
    client.post("/api/fin/treasury/funding-sources", json={
        "name": "Wholesale", "source_type": "wholesale", "amount": 4_000_000,
        "rate": 0.075, "tenor_days": 90})
    client.post("/api/fin/treasury/funding-sources", json={
        "name": "Bonds", "source_type": "bond", "amount": 3_000_000, "rate": 0.08,
        "tenor_days": 1825})


def test_source_types_and_registry():
    _, client = admin_client()
    r = client.get("/api/fin/treasury/source-types")
    assert r.status_code == 200 and "deposit" in r.json()["source_types"]
    _seed_funding(client)
    r = client.get("/api/fin/treasury/funding-sources")
    assert len(r.json()) == 3


def test_cash_and_liquidity():
    _, client = admin_client()
    r = client.post("/api/fin/treasury/cash-position",
                    json={"balances": {"cash": 500, "central_bank_reserves": 300, "hqla_securities": 200}})
    assert r.json()["total_cash"] == 800
    assert r.json()["total_liquid_assets"] == 1000
    r = client.post("/api/fin/treasury/liquidity-buckets", json={
        "assets": [{"amount": 1000, "tenor_days": 10}, {"amount": 500, "tenor_days": 200}],
        "liabilities": [{"amount": 800, "tenor_days": 5}]})
    assert "cumulative_gap" in r.json()


def test_nim_and_gap():
    _, client = admin_client()
    _seed_funding(client)
    r = client.post("/api/fin/treasury/nim", json={"earning_assets": 20_000_000, "asset_yield": 0.11})
    assert r.json()["net_interest_margin_pct"] is not None
    r = client.post("/api/fin/treasury/funding-gap", json={"funding_need": 20_000_000})
    assert r.json()["status"] == "shortfall"


def test_lcr_nsfr_alm():
    _, client = admin_client()
    _seed_funding(client)
    r = client.post("/api/fin/treasury/lcr", json={"hqla": 5_000_000, "inflows": 500_000})
    assert "lcr_ratio_pct" in r.json() and "compliant" in r.json()
    r = client.post("/api/fin/treasury/nsfr", json={"required_stable_funding": 8_000_000})
    assert "nsfr_ratio_pct" in r.json()
    r = client.post("/api/fin/treasury/alm", json={
        "assets": [{"amount": 5000, "tenor_days": 30}, {"amount": 3000, "tenor_days": 900}],
        "liabilities": [{"amount": 4000, "tenor_days": 60}], "rate_shock_bps": 200})
    assert "eve_impact" in r.json() and "interpretation" in r.json()


def test_forecast_scenario_optimization_kpis():
    _, client = admin_client()
    _seed_funding(client)
    r = client.post("/api/fin/treasury/cash-forecast", json={
        "opening_cash": 1_000_000, "horizon": 6, "monthly_inflow": 200_000, "monthly_outflow": 250_000})
    assert len(r.json()["series"]) == 6
    r = client.post("/api/fin/treasury/scenario", json={"base_hqla": 5_000_000, "base_outflows": 4_000_000})
    assert "worst_case" in r.json()
    r = client.post("/api/fin/treasury/funding-optimization", json={"target_amount": 12_000_000})
    assert r.json()["drawn"] > 0
    r = client.get("/api/fin/treasury/kpis")
    assert r.json()["source_count"] == 3
    r = client.get("/api/fin/treasury/dashboard")
    assert "kpis" in r.json()

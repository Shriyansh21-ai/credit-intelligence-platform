"""Track 3 M5 (ESG) + M6 (Market) + M7 (Alt-Data) tests."""

from backend.tests._financial_intelligence_helpers import admin_client, seed_company, seed_portfolio_companies


def test_esg_assess_and_climate():
    Session, client = admin_client()
    db = Session()
    seed_company(db, company_name="GreenCo", industry="technology")
    seed_company(db, company_name="CarbonCo", industry="energy")
    db.close()
    r = client.post("/api/fin/esg/assess", json={"subject_ref": "GreenCo"})
    assert 0 <= r.json()["esg_score"] <= 100
    r2 = client.post("/api/fin/esg/assess", json={"subject_ref": "CarbonCo"})
    assert r2.json()["transition_risk"] > r.json()["transition_risk"]
    r = client.post("/api/fin/esg/climate-stress", json={"subject_ref": "CarbonCo", "price_shock_multiple": 3})
    assert r.json()["incremental_cost"] > 0


def test_esg_portfolio():
    Session, client = admin_client()
    db = Session()
    seed_portfolio_companies(db, n=5)
    db.close()
    r = client.get("/api/fin/esg/portfolio")
    assert r.json()["exposures"] == 5
    assert r.json()["weighted_esg_score"] is not None


def test_market_seed_quotes_curve_news():
    _, client = admin_client()
    r = client.post("/api/fin/market/seed")
    assert r.json()["instruments"] > 0
    r = client.get("/api/fin/market/quotes")
    assert len(r.json()["quotes"]) > 0
    r = client.post("/api/fin/market/yield-curve", json={})
    assert "slope_2s10s" in r.json()
    client.post("/api/fin/market/news", json={"headline": "Company posts record profit and strong growth",
                                              "category": "corporate"})
    client.post("/api/fin/market/news", json={"headline": "Sector hit by downgrade and default fears",
                                              "category": "industry"})
    r = client.get("/api/fin/market/sentiment")
    assert r.json()["article_count"] == 2
    r = client.get("/api/fin/market/dashboard")
    assert "yield_curve" in r.json() and "calendar" in r.json()


def test_altdata_signals_and_composite():
    _, client = admin_client()
    r = client.get("/api/fin/altdata/signal-types")
    assert "payments" in r.json()["signal_types"]
    client.post("/api/fin/altdata/signals", json={"subject_ref": "X", "signal_type": "payments",
                                                  "raw": {"value": 80}})
    client.post("/api/fin/altdata/signals", json={"subject_ref": "X", "signal_type": "hiring",
                                                  "raw": {"current": 120, "baseline": 100}})
    r = client.get("/api/fin/altdata/signals", params={"subject_ref": "X"})
    assert len(r.json()["signals"]) == 2
    r = client.post("/api/fin/altdata/composite", json={"subject_ref": "X"})
    assert 0 <= r.json()["composite_risk_score"] <= 1
    assert "enterprise_risk_signal" in r.json()

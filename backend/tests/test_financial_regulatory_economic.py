""" M3 (Basel/IFRS9) + M4 (Economic Scenario) tests."""

from backend.tests._financial_intelligence_helpers import admin_client, seed_company, seed_portfolio_companies


def test_ecl_staging():
    _, client = admin_client()
    r = client.post("/api/fin/regulatory/ecl", json={"pd": 0.05, "lgd": 0.45, "ead": 1_000_000, "dpd": 0})
    j = r.json()["results"]
    assert j["stage"] == 1 and j["ecl_lifetime"] >= j["ecl_12m"]
    # 95+ dpd -> stage 3
    r = client.post("/api/fin/regulatory/ecl", json={"pd": 0.05, "lgd": 0.45, "ead": 1_000_000, "dpd": 120})
    assert r.json()["results"]["stage"] == 3


def test_rwa_car_leverage():
    _, client = admin_client()
    r = client.post("/api/fin/regulatory/rwa", json={"approach": "irb", "pd": 0.03, "lgd": 0.45, "ead": 1_000_000})
    assert r.json()["results"]["rwa"] > 0
    r = client.post("/api/fin/regulatory/rwa", json={"approach": "standardized", "pd": 0.03, "lgd": 0.45,
                                                    "ead": 1_000_000})
    assert r.json()["results"]["approach"] == "standardized"
    r = client.post("/api/fin/regulatory/car", json={"cet1": 8_000_000, "additional_tier1": 1_000_000,
                                                    "tier2": 2_000_000, "total_rwa": 80_000_000})
    assert "total_capital_ratio_pct" in r.json()["results"]
    r = client.post("/api/fin/regulatory/leverage", json={"tier1_capital": 9_000_000,
                                                          "total_exposure": 200_000_000})
    assert "leverage_ratio_pct" in r.json()["results"]


def test_regulatory_dashboard_grounded_on_company():
    Session, client = admin_client()
    db = Session()
    seed_company(db, company_name="RegCo", industry="manufacturing")
    db.close()
    r = client.post("/api/fin/regulatory/ecl", json={"subject_ref": "RegCo"})
    assert r.json()["explanation"]["grounded_on_profile"] is True
    r = client.get("/api/fin/regulatory/dashboard")
    assert r.json()["results"]["exposure_count"] >= 1


def test_economic_scenarios_and_propagation():
    Session, client = admin_client()
    db = Session()
    seed_portfolio_companies(db, n=4)
    db.close()
    client.post("/api/fin/economic/seed")
    r = client.get("/api/fin/economic/indicators")
    assert len(r.json()["indicators"]) >= 5
    r = client.post("/api/fin/economic/scenarios", json={"name": "Adverse 3y", "scenario_type": "adverse"})
    sid = r.json()["scenario_id"]
    assert "shocked_levels" in r.json()
    r = client.post("/api/fin/economic/propagate", json={"scenario_id": sid})
    j = r.json()
    assert j["pd_multiplier"] > 1.0 and j["stressed_expected_loss"] >= j["baseline_expected_loss"]


def test_scenario_types_endpoint():
    _, client = admin_client()
    r = client.get("/api/fin/economic/scenario-types")
    assert "severely_adverse" in r.json()["scenario_types"]

"""DataProvider interface + DemoDataProvider contract tests."""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from backend.app.services.providers import (
    CompanyRecord,
    DataProvider,
    available_providers,
    get_data_provider,
)
from backend.app.services.providers.demo import DemoDataProvider
from backend.app.services.providers.production import ProductionDataProvider

_LGD_BY_GRADE = {
    "AAA": 0.20, "AA": 0.25, "A": 0.30, "BBB": 0.35,
    "BB": 0.40, "B": 0.45, "CCC": 0.55, "D": 0.65,
}


def test_registry_selection_and_default():
    assert "demo" in available_providers()
    assert isinstance(get_data_provider("demo"), DemoDataProvider)
    # Unknown name falls back to demo (never crashes seed/demo flows).
    assert isinstance(get_data_provider("does-not-exist"), DemoDataProvider)
    # Default (no name) resolves via DATA_PROVIDER, which defaults to demo.
    assert get_data_provider().name == "demo"


def test_provider_interface_contract():
    p = get_data_provider("demo")
    assert isinstance(p, DataProvider)
    profiles = p.list_companies(10)
    assert len(profiles) == 10
    fin = p.financials_for(profiles[0], years=3)
    assert len(fin) == 3
    credit = p.credit_for(profiles[0], fin)
    assert credit is not None
    pos = p.portfolio_for(profiles[0], credit)
    assert pos is not None


def test_generate_count_and_industry_spread():
    recs = get_data_provider("demo").generate(60, years=3)
    assert len(recs) == 60
    industries = {r.profile.industry for r in recs}
    # Broad industry coverage (Banking, IT, Pharma, Energy, ...).
    assert len(industries) >= 15


def test_financials_are_internally_consistent():
    recs = get_data_provider("demo").generate(80, years=3)
    for r in recs:
        for f in r.financials:
            assert f.revenue > f.ebitda > f.ebit, r.profile.name
            # Balance sheet reconciles: assets == liabilities + equity.
            assert abs(f.total_assets - (f.total_liabilities + f.equity)) < 1.0
            # Margins derived from the statement.
            assert abs(f.operating_margin - f.ebit / f.revenue) < 1e-3
            assert abs(f.net_margin - f.net_income / f.revenue) < 1e-3
            assert f.working_capital == round(f.current_assets - f.current_liabilities, 2) or \
                abs(f.working_capital - (f.current_assets - f.current_liabilities)) < 1.0


def test_credit_metrics_are_consistent():
    recs = get_data_provider("demo").generate(80, years=3)
    for r in recs:
        c = r.credit
        assert 300 <= c.credit_score <= 900
        assert 0.0 < c.probability_of_default < 1.0
        assert c.risk_grade in _LGD_BY_GRADE
        # Expected loss == PD x LGD x exposure.
        expected = c.probability_of_default * _LGD_BY_GRADE[c.risk_grade] * r.portfolio.exposure
        assert abs(expected - c.expected_loss) < 1.0
        assert c.recommended_loan_amount <= c.requested_loan_amount + 1.0
        assert c.approval_status in {"approved", "under_review", "rejected"}


def test_determinism():
    a = get_data_provider("demo").generate(30, years=3)
    b = DemoDataProvider().generate(30, years=3)
    assert [r.profile.name for r in a] == [r.profile.name for r in b]
    assert [r.credit.credit_score for r in a] == [r.credit.credit_score for r in b]


def test_realistic_distribution():
    recs = get_data_provider("demo").generate(50, years=3)
    approved = sum(1 for r in recs if r.credit.approval_status == "approved")
    # A demo book should be favourably skewed but not all-approved.
    assert 0.4 <= approved / len(recs) <= 0.95
    grades = {r.credit.risk_grade for r in recs}
    assert len(grades) >= 4  # a spread, not a single grade


def test_production_provider_raises_until_wired():
    import pytest

    prov = ProductionDataProvider()
    assert prov.is_synthetic is False
    with pytest.raises(NotImplementedError):
        prov.list_companies(5)

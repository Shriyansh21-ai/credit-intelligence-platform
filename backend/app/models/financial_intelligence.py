"""Advanced Financial Intelligence Platform persistence.

Every table here is **additive** — nothing from Phases 1-11 / Tracks 1-2 is
altered or dropped. Schema is created by the Alembic migration
``a1b2c3d4e5f6_financial_intelligence_track3`` (the app never calls
``create_all`` at import time).

 sits on top of every previous phase. To stay loosely coupled (and avoid
cross-model FK-ordering pain in targeted test schemas) rows reference domain
objects by stable string refs (``company_ref``, ``subject_ref``) and optionally
carry an ``assessment_id`` when derived from a concrete
:class:`EnterpriseAssessment`. Multi-tenancy is preserved by an optional
nullable ``tenant_id`` column so legacy single-tenant flows keep working.

Table groups (all prefixed ``fin_``)
    M1 Treasury — fin_funding_sources, fin_treasury_snapshots
    M2 Portfolio — fin_portfolios, fin_portfolio_positions, fin_portfolio_analyses
    M3 Regulatory — fin_regulatory_calcs
    M4 Economic — fin_economic_indicators, fin_economic_scenarios
    M5 ESG/Climate — fin_esg_assessments
    M6 Market — fin_market_instruments, fin_market_quotes, fin_market_news
    M7 Alt Data — fin_alt_signals
    M8 Forecasting — fin_forecasts
    M9 Quant Risk — fin_risk_simulations
    M10 Benchmarking — fin_benchmarks
    M11 Executive — fin_exec_dashboards
    M12 Optimization — fin_optimizations
    M13 Digital Twin — fin_twins, fin_twin_simulations
    M14 Strategic — fin_strategic_reports
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


# ===========================================================================
# M1 — Treasury Intelligence Platform
# ===========================================================================
class FinFundingSource(Base):
    __tablename__ = "fin_funding_sources"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False, index=True)  # deposit|wholesale|repo|bond|equity|central_bank
    currency = Column(String, nullable=False, default="INR")
    amount = Column(Float, nullable=False, default=0.0)
    rate = Column(Float, nullable=False, default=0.0)           # annual funding rate (fraction)
    tenor_days = Column(Integer, nullable=False, default=0)     # 0 = non-maturing / on-demand
    stability_factor = Column(Float, nullable=False, default=0.5)  # NSFR ASF weight proxy
    is_secured = Column(Boolean, nullable=False, default=False)
    meta = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FinTreasurySnapshot(Base):
    __tablename__ = "fin_treasury_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    kind = Column(String, nullable=False, index=True)  # cash|liquidity|alm|lcr|nsfr|forecast|scenario|dashboard|kpis|yield
    label = Column(String, nullable=True)
    as_of = Column(String, nullable=True)              # ISO date the snapshot represents
    inputs = Column(JSON, nullable=False, default=dict)
    results = Column(JSON, nullable=False, default=dict)
    narrative = Column(Text, nullable=True)
    checksum = Column(String, nullable=True, index=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M2 — Enterprise Portfolio Intelligence
# ===========================================================================
class FinPortfolio(Base):
    __tablename__ = "fin_portfolios"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    portfolio_type = Column(String, nullable=False, default="commercial")  # commercial|sme|corporate|retail
    currency = Column(String, nullable=False, default="INR")
    description = Column(Text, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_fin_portfolio_key"),)


class FinPortfolioPosition(Base):
    __tablename__ = "fin_portfolio_positions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("fin_portfolios.id"), nullable=False, index=True)
    company_ref = Column(String, nullable=False, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    industry = Column(String, nullable=True, index=True)
    country = Column(String, nullable=True, index=True)
    region = Column(String, nullable=True)
    rating = Column(String, nullable=True)
    ead = Column(Float, nullable=False, default=0.0)
    pd = Column(Float, nullable=False, default=0.05)
    lgd = Column(Float, nullable=False, default=0.45)
    maturity_years = Column(Float, nullable=False, default=3.0)
    spread = Column(Float, nullable=False, default=0.03)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class FinPortfolioAnalysis(Base):
    __tablename__ = "fin_portfolio_analyses"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    portfolio_id = Column(Integer, nullable=True, index=True)
    analysis_type = Column(String, nullable=False, index=True)  # summary|concentration|loss|raroc|optimization|simulation|migration|ews|insights
    inputs = Column(JSON, nullable=False, default=dict)
    results = Column(JSON, nullable=False, default=dict)
    narrative = Column(Text, nullable=True)
    checksum = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M3 — Basel III / IFRS 9 Platform
# ===========================================================================
class FinRegulatoryCalc(Base):
    __tablename__ = "fin_regulatory_calcs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    calc_type = Column(String, nullable=False, index=True)  # ecl|rwa|car|leverage|provision|stage|dashboard
    framework = Column(String, nullable=False, default="basel3")  # basel3|ifrs9
    subject_ref = Column(String, nullable=True, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    inputs = Column(JSON, nullable=False, default=dict)
    results = Column(JSON, nullable=False, default=dict)
    explanation = Column(JSON, nullable=False, default=dict)
    checksum = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M4 — Economic Scenario Engine
# ===========================================================================
class FinEconomicIndicator(Base):
    __tablename__ = "fin_economic_indicators"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    code = Column(String, nullable=False, index=True)  # gdp|inflation|policy_rate|unemployment|fx|...
    name = Column(String, nullable=False)
    region = Column(String, nullable=False, default="IN", index=True)
    value = Column(Float, nullable=False, default=0.0)
    unit = Column(String, nullable=True)
    as_of = Column(String, nullable=True, index=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class FinEconomicScenario(Base):
    __tablename__ = "fin_economic_scenarios"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    scenario_type = Column(String, nullable=False, default="baseline")  # optimistic|baseline|adverse|severely_adverse|custom
    region = Column(String, nullable=False, default="IN")
    horizon_years = Column(Integer, nullable=False, default=3)
    shocks = Column(JSON, nullable=False, default=dict)     # indicator_code -> shock spec
    results = Column(JSON, nullable=False, default=dict)    # projected paths + propagation
    narrative = Column(Text, nullable=True)
    checksum = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M5 — Climate & ESG Intelligence
# ===========================================================================
class FinESGAssessment(Base):
    __tablename__ = "fin_esg_assessments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    subject_ref = Column(String, nullable=False, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    industry = Column(String, nullable=True, index=True)
    esg_score = Column(Float, nullable=True, index=True)
    environmental_score = Column(Float, nullable=True)
    social_score = Column(Float, nullable=True)
    governance_score = Column(Float, nullable=True)
    carbon_intensity = Column(Float, nullable=True)
    transition_risk = Column(Float, nullable=True)
    physical_risk = Column(Float, nullable=True)
    inputs = Column(JSON, nullable=False, default=dict)
    results = Column(JSON, nullable=False, default=dict)
    recommendations = Column(JSON, nullable=False, default=list)
    narrative = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M6 — Market Intelligence Platform
# ===========================================================================
class FinMarketInstrument(Base):
    __tablename__ = "fin_market_instruments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    asset_class = Column(String, nullable=False, index=True)  # rate|bond|equity|commodity|fx|credit|volatility
    currency = Column(String, nullable=False, default="INR")
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "symbol", name="uq_fin_instrument_symbol"),)


class FinMarketQuote(Base):
    __tablename__ = "fin_market_quotes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    asset_class = Column(String, nullable=True, index=True)
    as_of = Column(String, nullable=True, index=True)
    value = Column(Float, nullable=False, default=0.0)
    change = Column(Float, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)  # curve points, ohlc, spread, vol surface, etc.
    source = Column(String, nullable=False, default="synthetic")
    created_at = Column(DateTime, default=datetime.utcnow)


class FinMarketNews(Base):
    __tablename__ = "fin_market_news"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    headline = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    category = Column(String, nullable=False, default="macro", index=True)  # corporate|industry|macro
    subject_ref = Column(String, nullable=True, index=True)
    sentiment = Column(Float, nullable=True)      # -1..1
    impact = Column(JSON, nullable=False, default=dict)
    summary = Column(Text, nullable=True)
    source = Column(String, nullable=False, default="synthetic")
    published_at = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M7 — Alternative Data Intelligence
# ===========================================================================
class FinAltSignal(Base):
    __tablename__ = "fin_alt_signals"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    subject_ref = Column(String, nullable=False, index=True)
    signal_type = Column(String, nullable=False, index=True)  # satellite|shipping|web_traffic|reviews|social|hiring|payments|footfall|...
    source = Column(String, nullable=False, default="synthetic")
    as_of = Column(String, nullable=True)
    raw = Column(JSON, nullable=False, default=dict)
    risk_signal = Column(JSON, nullable=False, default=dict)  # normalized direction/magnitude/confidence
    score = Column(Float, nullable=True, index=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M8 — Enterprise Forecasting Platform
# ===========================================================================
class FinForecast(Base):
    __tablename__ = "fin_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    subject_ref = Column(String, nullable=True, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    forecast_type = Column(String, nullable=False, index=True)  # revenue|cashflow|working_capital|profit|growth|risk|default|recovery|portfolio|industry
    method = Column(String, nullable=False, default="ensemble")
    horizon = Column(Integer, nullable=False, default=12)
    frequency = Column(String, nullable=False, default="monthly")
    inputs = Column(JSON, nullable=False, default=dict)
    series = Column(JSON, nullable=False, default=list)      # [{t, point, lower, upper}]
    metrics = Column(JSON, nullable=False, default=dict)
    narrative = Column(Text, nullable=True)
    checksum = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M9 — Quantitative Risk Platform
# ===========================================================================
class FinRiskSimulation(Base):
    __tablename__ = "fin_risk_simulations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    sim_type = Column(String, nullable=False, index=True)  # montecarlo|var|es|stress|sensitivity|scenario_tree|attribution|correlation|volatility|tail
    subject_ref = Column(String, nullable=True, index=True)
    portfolio_id = Column(Integer, nullable=True, index=True)
    seed = Column(Integer, nullable=True)
    iterations = Column(Integer, nullable=False, default=10000)
    inputs = Column(JSON, nullable=False, default=dict)
    results = Column(JSON, nullable=False, default=dict)
    narrative = Column(Text, nullable=True)
    checksum = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M10 — Corporate Benchmarking Platform
# ===========================================================================
class FinBenchmark(Base):
    __tablename__ = "fin_benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    subject_ref = Column(String, nullable=False, index=True)
    assessment_id = Column(Integer, nullable=True, index=True)
    industry = Column(String, nullable=True, index=True)
    peer_set = Column(JSON, nullable=False, default=list)
    rankings = Column(JSON, nullable=False, default=dict)
    percentiles = Column(JSON, nullable=False, default=dict)
    competitive_position = Column(String, nullable=True)
    narrative = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M11 — Executive Intelligence Center
# ===========================================================================
class FinExecDashboard(Base):
    __tablename__ = "fin_exec_dashboards"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    persona = Column(String, nullable=False, index=True)  # ceo|cfo|cro|treasurer|portfolio_manager|board|credit_committee|regulator|rm
    title = Column(String, nullable=True)
    kpis = Column(JSON, nullable=False, default=list)
    sections = Column(JSON, nullable=False, default=list)
    summary = Column(Text, nullable=True)
    recommendations = Column(JSON, nullable=False, default=list)
    checksum = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M12 — Decision Optimization Engine
# ===========================================================================
class FinOptimization(Base):
    __tablename__ = "fin_optimizations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    opt_type = Column(String, nullable=False, index=True)  # loan_pricing|credit_limit|collateral|portfolio_allocation|capital|liquidity|recovery|risk_appetite|relationship
    subject_ref = Column(String, nullable=True, index=True)
    objective = Column(String, nullable=True)
    inputs = Column(JSON, nullable=False, default=dict)
    constraints = Column(JSON, nullable=False, default=dict)
    solution = Column(JSON, nullable=False, default=dict)
    explanation = Column(JSON, nullable=False, default=dict)
    objective_value = Column(Float, nullable=True)
    narrative = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M13 — Enterprise Financial Digital Twin
# ===========================================================================
class FinTwin(Base):
    __tablename__ = "fin_twins"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    key = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    twin_type = Column(String, nullable=False, index=True)  # company|industry|portfolio|economy|bank|treasury|market|supply_chain|counterparty
    subject_ref = Column(String, nullable=True, index=True)
    state = Column(JSON, nullable=False, default=dict)
    drivers = Column(JSON, nullable=False, default=dict)
    meta = Column(JSON, nullable=False, default=dict)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_fin_twin_key"),)


class FinTwinSimulation(Base):
    __tablename__ = "fin_twin_simulations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    twin_id = Column(Integer, ForeignKey("fin_twins.id"), nullable=False, index=True)
    scenario_ref = Column(String, nullable=True)
    horizon = Column(Integer, nullable=False, default=8)
    inputs = Column(JSON, nullable=False, default=dict)
    outcomes = Column(JSON, nullable=False, default=dict)
    narrative = Column(Text, nullable=True)
    checksum = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ===========================================================================
# M14 — Strategic Intelligence Platform
# ===========================================================================
class FinStrategicReport(Base):
    __tablename__ = "fin_strategic_reports"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    report_type = Column(String, nullable=False, index=True)  # executive_briefing|market|industry|competitor|economic|regulatory|portfolio|investment|outlook
    subject_ref = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    sections = Column(JSON, nullable=False, default=list)
    citations = Column(JSON, nullable=False, default=list)
    recommendations = Column(JSON, nullable=False, default=list)
    grounding = Column(JSON, nullable=False, default=dict)
    checksum = Column(String, nullable=True, index=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

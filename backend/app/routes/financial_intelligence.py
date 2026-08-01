"""Advanced Financial Intelligence Platform APIs.

Additive routers exposing the whole quantitative financial layer under
``/api/fin/*``. Every route is new; no existing route is modified. RBAC is
enforced with the permission catalog (``fin.*``). Routers are collected
into ``ROUTERS`` and mounted in ``main.py``.

    /api/fin/treasury treasury intelligence (M1)
    /api/fin/portfolio portfolio intelligence (M2)
    /api/fin/regulatory Basel III / IFRS 9 (M3)
    /api/fin/economic economic scenario engine (M4)
    /api/fin/esg climate & ESG intelligence (M5)
    /api/fin/market market intelligence (M6)
    /api/fin/altdata alternative data intelligence (M7)
    /api/fin/forecast enterprise forecasting (M8)
    /api/fin/quant quantitative risk (M9)
    /api/fin/benchmark corporate benchmarking (M10)
    /api/fin/executive executive intelligence center (M11)
    /api/fin/optimize decision optimization (M12)
    /api/fin/twin financial digital twin (M13)
    /api/fin/strategic strategic intelligence (M14)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services.rbac import require_permission
from backend.app.schemas.financial_intelligence import (
    ALMRequest, AllocationRequest, AttributionRequest, BenchmarkRequest,
    CapitalAllocationRequest, CARRequest, CashForecastRequest, CashPositionRequest,
    ClimateStressRequest, CollateralRequest, CompositeRequest, CorrelationRequest,
    CreditLimitRequest, ECLRequest, ESGAssessRequest, ExecDashboardRequest,
    ForecastRequest, FundingGapRequest, FundingOptimizationRequest, FundingSourceCreate,
    IndicatorCreate, InstrumentCreate, LCRRequest, LeverageRequest, LiquidityLadderRequest,
    LiquidityScenarioRequest, LiquidityStressRequest, LoanPricingRequest, LossParams,
    MonteCarloRequest, MultiHorizonRequest, NewsCreate, NIMRequest, NSFRRequest,
    OptimizeParams, PortfolioCreate, PositionCreate, PropagateRequest, QuantStressRequest,
    QuoteCreate, RarocParams, RWARequest, ScenarioGenerate, ScenarioTreeRequest,
    SensitivityRequest, SignalIngest, SimulateParams, StrategicReportRequest, TailRequest,
    TwinCreate, TwinSimulateRequest, TwinUpdateRequest, VaRRequest, VolatilityRequest,
    YieldCurveRequest, YieldRequest,
)
from backend.app.services.financial_intelligence import (
    altdata as altdata_svc, benchmarking as benchmarking_svc, digital_twin as twin_svc,
    economic as economic_svc, esg as esg_svc, executive as executive_svc,
    forecasting as forecasting_svc, market as market_svc, optimization as optimization_svc,
    portfolio as portfolio_svc, quant as quant_svc, regulatory as regulatory_svc,
    strategic as strategic_svc, treasury as treasury_svc,
)


def _tenant(explicit: Optional[int] = None) -> Optional[int]:
    if explicit is not None:
        return explicit
    try:
        from backend.app.services.saas import context as tenant_ctx
        return tenant_ctx.current_tenant_id()
    except Exception:
        return None


def _uref(user: Optional[User]) -> Optional[str]:
    return getattr(user, "email", None) if user else None


def _bad(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


# ===========================================================================
# M1 — Treasury Intelligence Platform
# ===========================================================================
treasury_router = APIRouter(prefix="/api/fin/treasury", tags=["FIN: Treasury"])


@treasury_router.get("/source-types")
def treasury_source_types(_u=Depends(require_permission("fin.treasury.view"))):
    return {"source_types": treasury_svc.FUNDING_SOURCE_TYPES,
            "liquidity_buckets": [b["key"] for b in treasury_svc.LIQUIDITY_BUCKETS]}


@treasury_router.get("/funding-sources")
def list_funding_sources(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                         _u=Depends(require_permission("fin.treasury.view"))):
    return [{"id": s.id, "name": s.name, "source_type": s.source_type, "amount": s.amount,
             "rate": s.rate, "tenor_days": s.tenor_days, "currency": s.currency,
             "stability_factor": s.stability_factor, "is_secured": s.is_secured}
            for s in treasury_svc.list_funding_sources(db, tenant_id=_tenant(tenant_id))]


@treasury_router.post("/funding-sources")
def create_funding_source(body: FundingSourceCreate, tenant_id: Optional[int] = None,
                          db: Session = Depends(get_db), user=Depends(get_current_user),
                          _u=Depends(require_permission("fin.treasury.manage"))):
    try:
        s = treasury_svc.register_funding_source(
            db, name=body.name, source_type=body.source_type, amount=body.amount, rate=body.rate,
            tenor_days=body.tenor_days, currency=body.currency, stability_factor=body.stability_factor,
            is_secured=body.is_secured, meta=body.meta, tenant_id=_tenant(tenant_id),
            created_by=_uref(user))
    except ValueError as e:
        _bad(e)
    return {"id": s.id, "name": s.name, "source_type": s.source_type, "amount": s.amount}


@treasury_router.post("/cash-position")
def cash_position(body: CashPositionRequest, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user),
                  _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.cash_position(db, balances=body.balances, as_of=body.as_of,
                                      tenant_id=_tenant(tenant_id), created_by=_uref(user))


@treasury_router.post("/liquidity-buckets")
def liquidity_buckets(body: LiquidityLadderRequest, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db), user=Depends(get_current_user),
                      _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.liquidity_buckets(db, assets=body.assets, liabilities=body.liabilities,
                                          as_of=body.as_of, tenant_id=_tenant(tenant_id),
                                          created_by=_uref(user))


@treasury_router.post("/funding-gap")
def funding_gap(body: FundingGapRequest, tenant_id: Optional[int] = None,
                db: Session = Depends(get_db), user=Depends(get_current_user),
                _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.funding_gap_analysis(db, funding_need=body.funding_need,
                                             tenant_id=_tenant(tenant_id), created_by=_uref(user))


@treasury_router.post("/nim")
def net_interest_margin(body: NIMRequest, tenant_id: Optional[int] = None,
                        db: Session = Depends(get_db), user=Depends(get_current_user),
                        _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.net_interest_margin(db, earning_assets=body.earning_assets,
                                            asset_yield=body.asset_yield, tenant_id=_tenant(tenant_id),
                                            created_by=_uref(user))


@treasury_router.post("/yield")
def yield_analysis(body: YieldRequest, tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db), user=Depends(get_current_user),
                   _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.yield_analysis(db, positions=body.positions, tenant_id=_tenant(tenant_id),
                                       created_by=_uref(user))


@treasury_router.post("/alm")
def alm_report(body: ALMRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               user=Depends(get_current_user), _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.alm_report(db, assets=body.assets, liabilities=body.liabilities,
                                   rate_shock_bps=body.rate_shock_bps, tenant_id=_tenant(tenant_id),
                                   created_by=_uref(user))


@treasury_router.post("/lcr")
def lcr(body: LCRRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
        user=Depends(get_current_user), _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.lcr(db, hqla=body.hqla, outflows=body.outflows, inflows=body.inflows,
                            use_registry=body.use_registry, tenant_id=_tenant(tenant_id),
                            created_by=_uref(user))


@treasury_router.post("/nsfr")
def nsfr(body: NSFRRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
         user=Depends(get_current_user), _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.nsfr(db, required_stable_funding=body.required_stable_funding,
                             available_stable_funding=body.available_stable_funding,
                             use_registry=body.use_registry, tenant_id=_tenant(tenant_id),
                             created_by=_uref(user))


@treasury_router.post("/cash-forecast")
def cash_forecast(body: CashForecastRequest, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user),
                  _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.cash_forecast(db, opening_cash=body.opening_cash, horizon=body.horizon,
                                      monthly_inflow=body.monthly_inflow, monthly_outflow=body.monthly_outflow,
                                      growth=body.growth, volatility=body.volatility,
                                      tenant_id=_tenant(tenant_id), created_by=_uref(user))


@treasury_router.post("/scenario")
def treasury_scenario(body: LiquidityScenarioRequest, tenant_id: Optional[int] = None,
                      db: Session = Depends(get_db), user=Depends(get_current_user),
                      _u=Depends(require_permission("fin.treasury.manage"))):
    return treasury_svc.scenario_analysis(db, base_hqla=body.base_hqla, base_outflows=body.base_outflows,
                                          shocks=body.shocks, tenant_id=_tenant(tenant_id),
                                          created_by=_uref(user))


@treasury_router.post("/stress")
def treasury_stress(body: LiquidityStressRequest, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), user=Depends(get_current_user),
                    _u=Depends(require_permission("fin.treasury.manage"))):
    return treasury_svc.stress_liquidity(db, hqla=body.hqla, base_outflows=body.base_outflows,
                                         survival_days=body.survival_days, tenant_id=_tenant(tenant_id),
                                         created_by=_uref(user))


@treasury_router.post("/funding-optimization")
def funding_optimization(body: FundingOptimizationRequest, tenant_id: Optional[int] = None,
                         db: Session = Depends(get_db), user=Depends(get_current_user),
                         _u=Depends(require_permission("fin.treasury.manage"))):
    return treasury_svc.funding_optimization(db, target_amount=body.target_amount, max_cost=body.max_cost,
                                             min_stability=body.min_stability, tenant_id=_tenant(tenant_id),
                                             created_by=_uref(user))


@treasury_router.get("/kpis")
def treasury_kpis(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.treasury_kpis(db, tenant_id=_tenant(tenant_id))


@treasury_router.get("/dashboard")
def treasury_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       _u=Depends(require_permission("fin.treasury.view"))):
    return treasury_svc.dashboard(db, tenant_id=_tenant(tenant_id))


@treasury_router.get("/snapshots")
def treasury_snapshots(kind: Optional[str] = None, limit: int = 50, tenant_id: Optional[int] = None,
                       db: Session = Depends(get_db), _u=Depends(require_permission("fin.treasury.view"))):
    return {"snapshots": treasury_svc.list_snapshots(db, kind=kind, limit=limit,
                                                     tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M2 — Enterprise Portfolio Intelligence
# ===========================================================================
portfolio_router = APIRouter(prefix="/api/fin/portfolio", tags=["FIN: Portfolio"])


@portfolio_router.get("")
def list_portfolios(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("fin.portfolio.view"))):
    return [{"id": p.id, "key": p.key, "name": p.name, "portfolio_type": p.portfolio_type,
             "currency": p.currency}
            for p in portfolio_svc.list_portfolios(db, tenant_id=_tenant(tenant_id))]


@portfolio_router.post("")
def create_portfolio(body: PortfolioCreate, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db), user=Depends(get_current_user),
                     _u=Depends(require_permission("fin.portfolio.manage"))):
    try:
        p = portfolio_svc.create_portfolio(db, key=body.key, name=body.name,
                                           portfolio_type=body.portfolio_type, currency=body.currency,
                                           description=body.description, meta=body.meta,
                                           tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)
    return {"id": p.id, "key": p.key, "name": p.name}


@portfolio_router.post("/positions")
def add_position(body: PositionCreate, tenant_id: Optional[int] = None,
                 db: Session = Depends(get_db), _u=Depends(require_permission("fin.portfolio.manage"))):
    try:
        p = portfolio_svc.add_position(
            db, portfolio_id=body.portfolio_id, company_ref=body.company_ref, ead=body.ead,
            pd=body.pd, lgd=body.lgd, industry=body.industry, country=body.country, region=body.region,
            rating=body.rating, maturity_years=body.maturity_years, spread=body.spread,
            assessment_id=body.assessment_id, meta=body.meta, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)
    return {"id": p.id, "portfolio_id": p.portfolio_id, "company_ref": p.company_ref, "ead": p.ead}


@portfolio_router.post("/{portfolio_id}/sync")
def sync_portfolio(portfolio_id: int, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("fin.portfolio.manage"))):
    try:
        return portfolio_svc.sync_from_platform(db, portfolio_id=portfolio_id, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@portfolio_router.get("/{portfolio_id}/positions")
def list_positions(portfolio_id: int, db: Session = Depends(get_db),
                   _u=Depends(require_permission("fin.portfolio.view"))):
    return {"positions": [
        {"id": p.id, "company_ref": p.company_ref, "industry": p.industry, "country": p.country,
         "rating": p.rating, "ead": p.ead, "pd": p.pd, "lgd": p.lgd}
        for p in portfolio_svc.list_positions(db, portfolio_id=portfolio_id)]}


@portfolio_router.post("/{portfolio_id}/summary")
def portfolio_summary(portfolio_id: int, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      user=Depends(get_current_user), _u=Depends(require_permission("fin.portfolio.view"))):
    try:
        return portfolio_svc.summary(db, portfolio_id=portfolio_id, tenant_id=_tenant(tenant_id),
                                     created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.post("/{portfolio_id}/concentration")
def portfolio_concentration(portfolio_id: int, top_n: int = 10, tenant_id: Optional[int] = None,
                            db: Session = Depends(get_db), user=Depends(get_current_user),
                            _u=Depends(require_permission("fin.portfolio.view"))):
    try:
        return portfolio_svc.concentration(db, portfolio_id=portfolio_id, top_n=top_n,
                                           tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.post("/{portfolio_id}/loss")
def portfolio_loss(portfolio_id: int, body: LossParams = LossParams(), tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db), user=Depends(get_current_user),
                   _u=Depends(require_permission("fin.portfolio.view"))):
    try:
        return portfolio_svc.loss_analysis(db, portfolio_id=portfolio_id, confidence=body.confidence,
                                           tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.post("/{portfolio_id}/raroc")
def portfolio_raroc(portfolio_id: int, body: RarocParams = RarocParams(), tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), user=Depends(get_current_user),
                    _u=Depends(require_permission("fin.portfolio.view"))):
    try:
        return portfolio_svc.raroc(db, portfolio_id=portfolio_id, cost_of_capital=body.cost_of_capital,
                                   opex_rate=body.opex_rate, confidence=body.confidence,
                                   tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.post("/{portfolio_id}/simulate")
def portfolio_simulate(portfolio_id: int, body: SimulateParams = SimulateParams(),
                       tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       user=Depends(get_current_user), _u=Depends(require_permission("fin.portfolio.manage"))):
    try:
        return portfolio_svc.simulate(db, portfolio_id=portfolio_id, iterations=body.iterations,
                                      seed=body.seed, confidence=body.confidence,
                                      tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.post("/{portfolio_id}/optimize")
def portfolio_optimize(portfolio_id: int, body: OptimizeParams = OptimizeParams(),
                       tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       user=Depends(get_current_user), _u=Depends(require_permission("fin.portfolio.manage"))):
    try:
        return portfolio_svc.optimize(db, portfolio_id=portfolio_id,
                                      max_single_exposure_pct=body.max_single_exposure_pct,
                                      max_sector_pct=body.max_sector_pct,
                                      tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.post("/{portfolio_id}/migration")
def portfolio_migration(portfolio_id: int, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                        user=Depends(get_current_user), _u=Depends(require_permission("fin.portfolio.view"))):
    try:
        return portfolio_svc.migration_analysis(db, portfolio_id=portfolio_id,
                                                tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.post("/{portfolio_id}/ews")
def portfolio_ews(portfolio_id: int, pd_threshold: float = 0.10, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), user=Depends(get_current_user),
                  _u=Depends(require_permission("fin.portfolio.view"))):
    try:
        return portfolio_svc.early_warning(db, portfolio_id=portfolio_id, pd_threshold=pd_threshold,
                                           tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.post("/{portfolio_id}/insights")
def portfolio_insights(portfolio_id: int, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       user=Depends(get_current_user), _u=Depends(require_permission("fin.portfolio.view"))):
    try:
        return portfolio_svc.ai_insights(db, portfolio_id=portfolio_id, tenant_id=_tenant(tenant_id),
                                         created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@portfolio_router.get("/analyses")
def portfolio_analyses(portfolio_id: Optional[int] = None, analysis_type: Optional[str] = None,
                       limit: int = 50, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                       _u=Depends(require_permission("fin.portfolio.view"))):
    return {"analyses": portfolio_svc.list_analyses(db, portfolio_id=portfolio_id,
                                                    analysis_type=analysis_type, limit=limit,
                                                    tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M3 — Basel III / IFRS 9 Platform
# ===========================================================================
regulatory_router = APIRouter(prefix="/api/fin/regulatory", tags=["FIN: Regulatory"])


@regulatory_router.post("/ecl")
def reg_ecl(body: ECLRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
            user=Depends(get_current_user), _u=Depends(require_permission("fin.regulatory.run"))):
    try:
        return regulatory_svc.ecl(db, subject_ref=body.subject_ref, assessment_id=body.assessment_id,
                                  pd=body.pd, lgd=body.lgd, ead=body.ead, dpd=body.dpd,
                                  original_pd=body.original_pd, lifetime_years=body.lifetime_years,
                                  eir=body.eir, tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@regulatory_router.post("/rwa")
def reg_rwa(body: RWARequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
            user=Depends(get_current_user), _u=Depends(require_permission("fin.regulatory.run"))):
    try:
        return regulatory_svc.rwa(db, approach=body.approach, subject_ref=body.subject_ref,
                                  assessment_id=body.assessment_id, pd=body.pd, lgd=body.lgd,
                                  ead=body.ead, maturity=body.maturity, tenant_id=_tenant(tenant_id),
                                  created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@regulatory_router.post("/car")
def reg_car(body: CARRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
            user=Depends(get_current_user), _u=Depends(require_permission("fin.regulatory.run"))):
    return regulatory_svc.capital_adequacy(db, cet1=body.cet1, additional_tier1=body.additional_tier1,
                                           tier2=body.tier2, total_rwa=body.total_rwa,
                                           tenant_id=_tenant(tenant_id), created_by=_uref(user))


@regulatory_router.post("/leverage")
def reg_leverage(body: LeverageRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 user=Depends(get_current_user), _u=Depends(require_permission("fin.regulatory.run"))):
    return regulatory_svc.leverage_ratio(db, tier1_capital=body.tier1_capital,
                                         total_exposure=body.total_exposure,
                                         tenant_id=_tenant(tenant_id), created_by=_uref(user))


@regulatory_router.get("/dashboard")
def reg_dashboard(cet1: float = 0.0, additional_tier1: float = 0.0, tier2: float = 0.0,
                  tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  user=Depends(get_current_user), _u=Depends(require_permission("fin.regulatory.view"))):
    return regulatory_svc.portfolio_dashboard(db, tenant_id=_tenant(tenant_id), cet1=cet1,
                                              additional_tier1=additional_tier1, tier2=tier2,
                                              created_by=_uref(user))


@regulatory_router.get("/calcs")
def reg_calcs(calc_type: Optional[str] = None, framework: Optional[str] = None, limit: int = 50,
              tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("fin.regulatory.view"))):
    return {"calcs": regulatory_svc.list_calcs(db, calc_type=calc_type, framework=framework,
                                               limit=limit, tenant_id=_tenant(tenant_id))}


@regulatory_router.get("/calcs/{calc_id}")
def reg_calc(calc_id: int, db: Session = Depends(get_db),
             _u=Depends(require_permission("fin.regulatory.view"))):
    out = regulatory_svc.get_calc(db, calc_id)
    if not out:
        raise HTTPException(status_code=404, detail="calc not found")
    return out


# ===========================================================================
# M4 — Economic Scenario Engine
# ===========================================================================
economic_router = APIRouter(prefix="/api/fin/economic", tags=["FIN: Economic"])


@economic_router.get("/scenario-types")
def econ_types(_u=Depends(require_permission("fin.economic.view"))):
    return {"scenario_types": economic_svc.SCENARIO_TYPES, "indicator_codes": economic_svc.INDICATOR_CODES}


@economic_router.get("/indicators")
def econ_indicators(region: Optional[str] = None, tenant_id: Optional[int] = None,
                    db: Session = Depends(get_db), _u=Depends(require_permission("fin.economic.view"))):
    return {"indicators": economic_svc.list_indicators(db, region=region, tenant_id=_tenant(tenant_id))}


@economic_router.post("/indicators")
def econ_upsert(body: IndicatorCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("fin.economic.manage"))):
    i = economic_svc.upsert_indicator(db, code=body.code, name=body.name, value=body.value,
                                      region=body.region, unit=body.unit, as_of=body.as_of,
                                      meta=body.meta, tenant_id=_tenant(tenant_id))
    return {"id": i.id, "code": i.code, "value": i.value}


@economic_router.post("/seed")
def econ_seed(region: str = "IN", tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("fin.economic.manage"))):
    return economic_svc.seed_defaults(db, region=region, tenant_id=_tenant(tenant_id))


@economic_router.post("/scenarios")
def econ_generate(body: ScenarioGenerate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  user=Depends(get_current_user), _u=Depends(require_permission("fin.economic.manage"))):
    try:
        return economic_svc.generate_scenario(db, name=body.name, scenario_type=body.scenario_type,
                                              region=body.region, horizon_years=body.horizon_years,
                                              custom_shocks=body.custom_shocks, key=body.key,
                                              tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@economic_router.post("/propagate")
def econ_propagate(body: PropagateRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("fin.economic.view"))):
    try:
        return economic_svc.propagate(db, scenario_id=body.scenario_id, scenario_type=body.scenario_type,
                                      region=body.region, tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@economic_router.get("/scenarios")
def econ_list(scenario_type: Optional[str] = None, limit: int = 50, tenant_id: Optional[int] = None,
              db: Session = Depends(get_db), _u=Depends(require_permission("fin.economic.view"))):
    return {"scenarios": economic_svc.list_scenarios(db, scenario_type=scenario_type, limit=limit,
                                                     tenant_id=_tenant(tenant_id))}


@economic_router.get("/scenarios/{scenario_id}")
def econ_get(scenario_id: int, db: Session = Depends(get_db),
             _u=Depends(require_permission("fin.economic.view"))):
    out = economic_svc.get_scenario(db, scenario_id)
    if not out:
        raise HTTPException(status_code=404, detail="scenario not found")
    return out


# ===========================================================================
# M5 — Climate & ESG Intelligence
# ===========================================================================
esg_router = APIRouter(prefix="/api/fin/esg", tags=["FIN: ESG"])


@esg_router.post("/assess")
def esg_assess(body: ESGAssessRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               user=Depends(get_current_user), _u=Depends(require_permission("fin.esg.manage"))):
    return esg_svc.assess(db, subject_ref=body.subject_ref, assessment_id=body.assessment_id,
                          revenue=body.revenue, industry=body.industry, overrides=body.overrides,
                          tenant_id=_tenant(tenant_id), created_by=_uref(user))


@esg_router.post("/climate-stress")
def esg_climate(body: ClimateStressRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                user=Depends(get_current_user), _u=Depends(require_permission("fin.esg.manage"))):
    return esg_svc.climate_stress(db, subject_ref=body.subject_ref, carbon_price=body.carbon_price,
                                  price_shock_multiple=body.price_shock_multiple, revenue=body.revenue,
                                  industry=body.industry, tenant_id=_tenant(tenant_id), created_by=_uref(user))


@esg_router.get("/portfolio")
def esg_portfolio(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("fin.esg.view"))):
    return esg_svc.portfolio_esg(db, tenant_id=_tenant(tenant_id))


@esg_router.get("/list")
def esg_list(subject_ref: Optional[str] = None, limit: int = 50, tenant_id: Optional[int] = None,
             db: Session = Depends(get_db), _u=Depends(require_permission("fin.esg.view"))):
    return {"assessments": esg_svc.list_assessments(db, subject_ref=subject_ref, limit=limit,
                                                    tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M6 — Market Intelligence Platform
# ===========================================================================
market_router = APIRouter(prefix="/api/fin/market", tags=["FIN: Market"])


@market_router.post("/seed")
def market_seed(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("fin.market.manage"))):
    return market_svc.seed_defaults(db, tenant_id=_tenant(tenant_id))


@market_router.get("/instruments")
def market_instruments(asset_class: Optional[str] = None, tenant_id: Optional[int] = None,
                       db: Session = Depends(get_db), _u=Depends(require_permission("fin.market.view"))):
    return {"instruments": market_svc.list_instruments(db, asset_class=asset_class,
                                                       tenant_id=_tenant(tenant_id))}


@market_router.post("/instruments")
def market_add_instrument(body: InstrumentCreate, tenant_id: Optional[int] = None,
                          db: Session = Depends(get_db), _u=Depends(require_permission("fin.market.manage"))):
    try:
        i = market_svc.register_instrument(db, symbol=body.symbol, name=body.name,
                                           asset_class=body.asset_class, currency=body.currency,
                                           meta=body.meta, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)
    return {"id": i.id, "symbol": i.symbol, "asset_class": i.asset_class}


@market_router.post("/quotes")
def market_add_quote(body: QuoteCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("fin.market.manage"))):
    q = market_svc.record_quote(db, symbol=body.symbol, value=body.value, asset_class=body.asset_class,
                                change=body.change, payload=body.payload, as_of=body.as_of,
                                source=body.source, tenant_id=_tenant(tenant_id))
    return {"id": q.id, "symbol": q.symbol, "value": q.value}


@market_router.get("/quotes")
def market_quotes(asset_class: Optional[str] = None, tenant_id: Optional[int] = None,
                  db: Session = Depends(get_db), _u=Depends(require_permission("fin.market.view"))):
    return {"quotes": market_svc.latest_quotes(db, asset_class=asset_class, tenant_id=_tenant(tenant_id))}


@market_router.post("/yield-curve")
def market_yield_curve(body: YieldCurveRequest = YieldCurveRequest(), tenant_id: Optional[int] = None,
                       db: Session = Depends(get_db), _u=Depends(require_permission("fin.market.view"))):
    return market_svc.yield_curve(db, curve=body.curve, query_tenors=body.query_tenors,
                                  tenant_id=_tenant(tenant_id))


@market_router.post("/news")
def market_add_news(body: NewsCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                    _u=Depends(require_permission("fin.market.manage"))):
    try:
        return market_svc.add_news(db, headline=body.headline, category=body.category, body=body.body,
                                   subject_ref=body.subject_ref, source=body.source,
                                   published_at=body.published_at, tenant_id=_tenant(tenant_id))
    except ValueError as e:
        _bad(e)


@market_router.get("/news")
def market_news(category: Optional[str] = None, subject_ref: Optional[str] = None, limit: int = 50,
                tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("fin.market.view"))):
    return {"news": market_svc.list_news(db, category=category, subject_ref=subject_ref, limit=limit,
                                         tenant_id=_tenant(tenant_id))}


@market_router.get("/sentiment")
def market_sentiment(category: Optional[str] = None, subject_ref: Optional[str] = None,
                     tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("fin.market.view"))):
    return market_svc.market_sentiment(db, category=category, subject_ref=subject_ref,
                                       tenant_id=_tenant(tenant_id))


@market_router.get("/calendar")
def market_calendar(region: str = "IN", weeks: int = 4, db: Session = Depends(get_db),
                    _u=Depends(require_permission("fin.market.view"))):
    return market_svc.economic_calendar(db, region=region, weeks=weeks)


@market_router.get("/dashboard")
def market_dashboard(tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     _u=Depends(require_permission("fin.market.view"))):
    return market_svc.dashboard(db, tenant_id=_tenant(tenant_id))


# ===========================================================================
# M7 — Alternative Data Intelligence
# ===========================================================================
altdata_router = APIRouter(prefix="/api/fin/altdata", tags=["FIN: Alt-Data"])


@altdata_router.get("/signal-types")
def alt_types(_u=Depends(require_permission("fin.altdata.view"))):
    return {"signal_types": {k: v["label"] for k, v in altdata_svc.SIGNAL_TYPES.items()}}


@altdata_router.post("/signals")
def alt_ingest(body: SignalIngest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               user=Depends(get_current_user), _u=Depends(require_permission("fin.altdata.manage"))):
    try:
        return altdata_svc.ingest_signal(db, subject_ref=body.subject_ref, signal_type=body.signal_type,
                                         raw=body.raw, source=body.source, as_of=body.as_of,
                                         tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@altdata_router.get("/signals")
def alt_signals(subject_ref: Optional[str] = None, signal_type: Optional[str] = None, limit: int = 100,
                tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                _u=Depends(require_permission("fin.altdata.view"))):
    return {"signals": altdata_svc.list_signals(db, subject_ref=subject_ref, signal_type=signal_type,
                                                limit=limit, tenant_id=_tenant(tenant_id))}


@altdata_router.post("/composite")
def alt_composite(body: CompositeRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  user=Depends(get_current_user), _u=Depends(require_permission("fin.altdata.view"))):
    return altdata_svc.composite(db, subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                 created_by=_uref(user))


# ===========================================================================
# M8 — Enterprise Forecasting Platform
# ===========================================================================
forecast_router = APIRouter(prefix="/api/fin/forecast", tags=["FIN: Forecasting"])


@forecast_router.get("/types")
def forecast_types(_u=Depends(require_permission("fin.forecast.view"))):
    return {"forecast_types": forecasting_svc.FORECAST_TYPES}


@forecast_router.post("/run")
def forecast_run(body: ForecastRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 user=Depends(get_current_user), _u=Depends(require_permission("fin.forecast.run"))):
    try:
        return forecasting_svc.forecast(db, forecast_type=body.forecast_type, subject_ref=body.subject_ref,
                                        assessment_id=body.assessment_id, horizon=body.horizon,
                                        history=body.history, frequency=body.frequency, drift=body.drift,
                                        tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@forecast_router.post("/multi-horizon")
def forecast_multi(body: MultiHorizonRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("fin.forecast.run"))):
    try:
        return forecasting_svc.multi_horizon(db, forecast_type=body.forecast_type, subject_ref=body.subject_ref,
                                             assessment_id=body.assessment_id, horizons=body.horizons,
                                             history=body.history, tenant_id=_tenant(tenant_id),
                                             created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@forecast_router.get("/list")
def forecast_list(forecast_type: Optional[str] = None, subject_ref: Optional[str] = None, limit: int = 50,
                  tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  _u=Depends(require_permission("fin.forecast.view"))):
    return {"forecasts": forecasting_svc.list_forecasts(db, forecast_type=forecast_type,
                                                        subject_ref=subject_ref, limit=limit,
                                                        tenant_id=_tenant(tenant_id))}


@forecast_router.get("/{forecast_id}")
def forecast_get(forecast_id: int, db: Session = Depends(get_db),
                 _u=Depends(require_permission("fin.forecast.view"))):
    out = forecasting_svc.get_forecast(db, forecast_id)
    if not out:
        raise HTTPException(status_code=404, detail="forecast not found")
    return out


# ===========================================================================
# M9 — Quantitative Risk Platform
# ===========================================================================
quant_router = APIRouter(prefix="/api/fin/quant", tags=["FIN: Quant Risk"])


@quant_router.get("/types")
def quant_types(_u=Depends(require_permission("fin.quant.view"))):
    return {"sim_types": quant_svc.SIM_TYPES}


@quant_router.post("/montecarlo")
def quant_mc(body: MonteCarloRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
             user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    try:
        return quant_svc.monte_carlo(db, positions=body.positions, iterations=body.iterations,
                                     seed=body.seed, correlation_matrix=body.correlation_matrix,
                                     confidence=body.confidence, subject_ref=body.subject_ref,
                                     tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@quant_router.post("/var")
def quant_var(body: VaRRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    return quant_svc.value_at_risk(db, returns=body.returns, portfolio_value=body.portfolio_value,
                                   mean_return=body.mean_return, volatility=body.volatility,
                                   confidence=body.confidence, method=body.method,
                                   horizon_days=body.horizon_days, subject_ref=body.subject_ref,
                                   tenant_id=_tenant(tenant_id), created_by=_uref(user))


@quant_router.post("/stress")
def quant_stress(body: QuantStressRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                 user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    return quant_svc.stress_test(db, base_value=body.base_value, factors=body.factors,
                                 scenarios=body.scenarios, subject_ref=body.subject_ref,
                                 tenant_id=_tenant(tenant_id), created_by=_uref(user))


@quant_router.post("/sensitivity")
def quant_sensitivity(body: SensitivityRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    return quant_svc.sensitivity(db, base_value=body.base_value, factors=body.factors, shock=body.shock,
                                 subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                 created_by=_uref(user))


@quant_router.post("/scenario-tree")
def quant_tree(body: ScenarioTreeRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    return quant_svc.scenario_tree(db, base_value=body.base_value, stages=body.stages, up=body.up,
                                   down=body.down, prob_up=body.prob_up, subject_ref=body.subject_ref,
                                   tenant_id=_tenant(tenant_id), created_by=_uref(user))


@quant_router.post("/attribution")
def quant_attribution(body: AttributionRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    try:
        return quant_svc.risk_attribution(db, positions=body.positions, confidence=body.confidence,
                                          subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                          created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@quant_router.post("/correlation")
def quant_correlation(body: CorrelationRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                      user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    return quant_svc.correlation_matrix(db, series=body.series, subject_ref=body.subject_ref,
                                        tenant_id=_tenant(tenant_id), created_by=_uref(user))


@quant_router.post("/volatility")
def quant_volatility(body: VolatilityRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    try:
        return quant_svc.volatility(db, returns=body.returns, lam=body.lam, subject_ref=body.subject_ref,
                                    tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@quant_router.post("/tail")
def quant_tail(body: TailRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
               user=Depends(get_current_user), _u=Depends(require_permission("fin.quant.run"))):
    try:
        return quant_svc.tail_risk(db, returns=body.returns, threshold=body.threshold,
                                   subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                   created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@quant_router.get("/list")
def quant_list(sim_type: Optional[str] = None, limit: int = 50, tenant_id: Optional[int] = None,
               db: Session = Depends(get_db), _u=Depends(require_permission("fin.quant.view"))):
    return {"simulations": quant_svc.list_simulations(db, sim_type=sim_type, limit=limit,
                                                      tenant_id=_tenant(tenant_id))}


@quant_router.get("/{simulation_id}")
def quant_get(simulation_id: int, db: Session = Depends(get_db),
              _u=Depends(require_permission("fin.quant.view"))):
    out = quant_svc.get_simulation(db, simulation_id)
    if not out:
        raise HTTPException(status_code=404, detail="simulation not found")
    return out


# ===========================================================================
# M10 — Corporate Benchmarking Platform
# ===========================================================================
benchmark_router = APIRouter(prefix="/api/fin/benchmark", tags=["FIN: Benchmarking"])


@benchmark_router.post("/run")
def benchmark_run(body: BenchmarkRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  user=Depends(get_current_user), _u=Depends(require_permission("fin.benchmark.run"))):
    try:
        return benchmarking_svc.benchmark(db, subject_ref=body.subject_ref, assessment_id=body.assessment_id,
                                          industry=body.industry, tenant_id=_tenant(tenant_id),
                                          created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@benchmark_router.get("/list")
def benchmark_list(subject_ref: Optional[str] = None, limit: int = 50, tenant_id: Optional[int] = None,
                   db: Session = Depends(get_db), _u=Depends(require_permission("fin.benchmark.view"))):
    return {"benchmarks": benchmarking_svc.list_benchmarks(db, subject_ref=subject_ref, limit=limit,
                                                           tenant_id=_tenant(tenant_id))}


@benchmark_router.get("/{benchmark_id}")
def benchmark_get(benchmark_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("fin.benchmark.view"))):
    out = benchmarking_svc.get_benchmark(db, benchmark_id)
    if not out:
        raise HTTPException(status_code=404, detail="benchmark not found")
    return out


# ===========================================================================
# M11 — Executive Intelligence Center
# ===========================================================================
executive_router = APIRouter(prefix="/api/fin/executive", tags=["FIN: Executive"])


@executive_router.get("/personas")
def exec_personas(_u=Depends(require_permission("fin.exec.view"))):
    return {"personas": executive_svc.PERSONAS, "labels": executive_svc.PERSONA_LABELS}


@executive_router.post("/dashboard")
def exec_dashboard(body: ExecDashboardRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("fin.exec.view"))):
    try:
        return executive_svc.build_dashboard(db, persona=body.persona, tenant_id=_tenant(tenant_id),
                                             created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@executive_router.get("/list")
def exec_list(persona: Optional[str] = None, limit: int = 50, tenant_id: Optional[int] = None,
              db: Session = Depends(get_db), _u=Depends(require_permission("fin.exec.view"))):
    return {"dashboards": executive_svc.list_dashboards(db, persona=persona, limit=limit,
                                                       tenant_id=_tenant(tenant_id))}


@executive_router.get("/{dashboard_id}")
def exec_get(dashboard_id: int, db: Session = Depends(get_db),
             _u=Depends(require_permission("fin.exec.view"))):
    out = executive_svc.get_dashboard(db, dashboard_id)
    if not out:
        raise HTTPException(status_code=404, detail="dashboard not found")
    return out


# ===========================================================================
# M12 — Decision Optimization Engine
# ===========================================================================
optimize_router = APIRouter(prefix="/api/fin/optimize", tags=["FIN: Optimization"])


@optimize_router.get("/types")
def opt_types(_u=Depends(require_permission("fin.optimize.view"))):
    return {"opt_types": optimization_svc.OPT_TYPES}


@optimize_router.post("/loan-pricing")
def opt_loan_pricing(body: LoanPricingRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     user=Depends(get_current_user), _u=Depends(require_permission("fin.optimize.run"))):
    return optimization_svc.loan_pricing(db, subject_ref=body.subject_ref, assessment_id=body.assessment_id,
                                         pd=body.pd, lgd=body.lgd, ead=body.ead, cost_of_funds=body.cost_of_funds,
                                         opex_rate=body.opex_rate, target_roe=body.target_roe,
                                         capital_ratio=body.capital_ratio, tenant_id=_tenant(tenant_id),
                                         created_by=_uref(user))


@optimize_router.post("/credit-limit")
def opt_credit_limit(body: CreditLimitRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                     user=Depends(get_current_user), _u=Depends(require_permission("fin.optimize.run"))):
    return optimization_svc.credit_limit(db, subject_ref=body.subject_ref, assessment_id=body.assessment_id,
                                         pd=body.pd, single_name_cap=body.single_name_cap,
                                         total_capital=body.total_capital, risk_appetite_el=body.risk_appetite_el,
                                         tenant_id=_tenant(tenant_id), created_by=_uref(user))


@optimize_router.post("/portfolio-allocation")
def opt_allocation(body: AllocationRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("fin.optimize.run"))):
    try:
        return optimization_svc.portfolio_allocation(db, candidates=body.candidates, budget=body.budget,
                                                     cost_of_capital=body.cost_of_capital, max_weight=body.max_weight,
                                                     subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                                     created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@optimize_router.post("/capital-allocation")
def opt_capital(body: CapitalAllocationRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                user=Depends(get_current_user), _u=Depends(require_permission("fin.optimize.run"))):
    try:
        return optimization_svc.capital_allocation(db, business_units=body.business_units,
                                                   total_capital=body.total_capital, tenant_id=_tenant(tenant_id),
                                                   created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@optimize_router.post("/collateral")
def opt_collateral(body: CollateralRequest, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   user=Depends(get_current_user), _u=Depends(require_permission("fin.optimize.run"))):
    return optimization_svc.collateral_optimization(db, exposure=body.exposure,
                                                    collateral_options=body.collateral_options,
                                                    subject_ref=body.subject_ref, tenant_id=_tenant(tenant_id),
                                                    created_by=_uref(user))


@optimize_router.get("/list")
def opt_list(opt_type: Optional[str] = None, limit: int = 50, tenant_id: Optional[int] = None,
             db: Session = Depends(get_db), _u=Depends(require_permission("fin.optimize.view"))):
    return {"optimizations": optimization_svc.list_optimizations(db, opt_type=opt_type, limit=limit,
                                                                tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M13 — Enterprise Financial Digital Twin
# ===========================================================================
twin_router = APIRouter(prefix="/api/fin/twin", tags=["FIN: Digital Twin"])


@twin_router.get("/types")
def twin_types(_u=Depends(require_permission("fin.twin.view"))):
    return {"twin_types": twin_svc.TWIN_TYPES}


@twin_router.post("")
def twin_create(body: TwinCreate, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                user=Depends(get_current_user), _u=Depends(require_permission("fin.twin.manage"))):
    try:
        return twin_svc.create_twin(db, key=body.key, name=body.name, twin_type=body.twin_type,
                                    subject_ref=body.subject_ref, state=body.state, drivers=body.drivers,
                                    meta=body.meta, tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@twin_router.get("")
def twin_list(twin_type: Optional[str] = None, tenant_id: Optional[int] = None, db: Session = Depends(get_db),
              _u=Depends(require_permission("fin.twin.view"))):
    return {"twins": twin_svc.list_twins(db, twin_type=twin_type, tenant_id=_tenant(tenant_id))}


@twin_router.get("/{twin_id}")
def twin_get(twin_id: int, db: Session = Depends(get_db), _u=Depends(require_permission("fin.twin.view"))):
    out = twin_svc.get_twin(db, twin_id)
    if not out:
        raise HTTPException(status_code=404, detail="twin not found")
    return out


@twin_router.post("/{twin_id}/update")
def twin_update(twin_id: int, body: TwinUpdateRequest, db: Session = Depends(get_db),
                _u=Depends(require_permission("fin.twin.manage"))):
    try:
        return twin_svc.update_state(db, twin_id=twin_id, state=body.state, drivers=body.drivers)
    except ValueError as e:
        _bad(e)


@twin_router.post("/{twin_id}/simulate")
def twin_simulate(twin_id: int, body: TwinSimulateRequest = TwinSimulateRequest(),
                  tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                  user=Depends(get_current_user), _u=Depends(require_permission("fin.twin.manage"))):
    try:
        return twin_svc.simulate(db, twin_id=twin_id, horizon=body.horizon, scenario=body.scenario,
                                 scenario_ref=body.scenario_ref, tenant_id=_tenant(tenant_id),
                                 created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@twin_router.get("/{twin_id}/simulations")
def twin_simulations(twin_id: int, limit: int = 50, tenant_id: Optional[int] = None,
                     db: Session = Depends(get_db), _u=Depends(require_permission("fin.twin.view"))):
    return {"simulations": twin_svc.list_simulations(db, twin_id=twin_id, limit=limit,
                                                     tenant_id=_tenant(tenant_id))}


# ===========================================================================
# M14 — Strategic Intelligence Platform
# ===========================================================================
strategic_router = APIRouter(prefix="/api/fin/strategic", tags=["FIN: Strategic"])


@strategic_router.get("/types")
def strategic_types(_u=Depends(require_permission("fin.strategic.view"))):
    return {"report_types": strategic_svc.REPORT_TYPES}


@strategic_router.post("/generate")
def strategic_generate(body: StrategicReportRequest, tenant_id: Optional[int] = None,
                       db: Session = Depends(get_db), user=Depends(get_current_user),
                       _u=Depends(require_permission("fin.strategic.generate"))):
    try:
        return strategic_svc.generate(db, report_type=body.report_type, subject_ref=body.subject_ref,
                                      assessment_id=body.assessment_id, title=body.title,
                                      tenant_id=_tenant(tenant_id), created_by=_uref(user))
    except ValueError as e:
        _bad(e)


@strategic_router.get("/list")
def strategic_list(report_type: Optional[str] = None, subject_ref: Optional[str] = None, limit: int = 50,
                   tenant_id: Optional[int] = None, db: Session = Depends(get_db),
                   _u=Depends(require_permission("fin.strategic.view"))):
    return {"reports": strategic_svc.list_reports(db, report_type=report_type, subject_ref=subject_ref,
                                                 limit=limit, tenant_id=_tenant(tenant_id))}


@strategic_router.get("/{report_id}")
def strategic_get(report_id: int, db: Session = Depends(get_db),
                  _u=Depends(require_permission("fin.strategic.view"))):
    out = strategic_svc.get_report(db, report_id)
    if not out:
        raise HTTPException(status_code=404, detail="report not found")
    return out


# ===========================================================================
# ROUTERS — mounted in main.py.
# ===========================================================================
ROUTERS = [
    treasury_router,
    portfolio_router,
    regulatory_router,
    economic_router,
    esg_router,
    market_router,
    altdata_router,
    forecast_router,
    quant_router,
    benchmark_router,
    executive_router,
    optimize_router,
    twin_router,
    strategic_router,
]

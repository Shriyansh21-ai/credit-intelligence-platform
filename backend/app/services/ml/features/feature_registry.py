"""Feature registry — the versioned catalogue of enterprise features.

The registry is the single source of truth for *what* features exist, how they
are computed and which category and data source they belong to. Model training,
inference and explainability all read feature order and metadata from here, so a
model trained against ``FEATURE_SET_VERSION`` can always be reconciled with the
features presented at inference time.

Every definition is a pure, deterministic function of a :class:`FeatureContext`
(a normalised statement, its computed ratios, the assessment's qualitative
context and, optionally, a prior period). Missing inputs yield ``None`` rather
than a fabricated number — the confidence of an absent feature is ``0``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

from backend.app.services.financial_analysis.ratio_engine import Ratio
from backend.app.services.financial_analysis.statement import FinancialStatement

# Bump when the catalogue's semantics change so persisted vectors and trained
# models can be versioned against the exact feature contract they used.
FEATURE_SET_VERSION = "1.0"

Number = Optional[float]


# ---------------------------------------------------------------------------
# Feature categories (the 16 the phase brief enumerates)
# ---------------------------------------------------------------------------

LIQUIDITY = "liquidity"
LEVERAGE = "leverage"
PROFITABILITY = "profitability"
CASH_FLOW = "cash_flow"
EFFICIENCY = "efficiency"
GROWTH = "growth"
WORKING_CAPITAL = "working_capital"
BANKING_BEHAVIOUR = "banking_behaviour"
COLLATERAL = "collateral"
BUSINESS_STABILITY = "business_stability"
REVENUE_QUALITY = "revenue_quality"
CUSTOMER_CONCENTRATION = "customer_concentration"
OPERATIONAL = "operational_metrics"
RISK = "risk_metrics"
HISTORICAL = "historical_performance"
TREND = "trend_metrics"

CATEGORIES = (
    LIQUIDITY, LEVERAGE, PROFITABILITY, CASH_FLOW, EFFICIENCY, GROWTH,
    WORKING_CAPITAL, BANKING_BEHAVIOUR, COLLATERAL, BUSINESS_STABILITY,
    REVENUE_QUALITY, CUSTOMER_CONCENTRATION, OPERATIONAL, RISK,
    HISTORICAL, TREND,
)

# Data provenance for each feature (drives confidence and audit trails).
SRC_STATEMENT = "financial_statement"
SRC_RATIO = "ratio_engine"
SRC_BANKING = "banking_conduct"
SRC_QUALITATIVE = "qualitative_risk"
SRC_PRIOR_PERIOD = "prior_period"

# Units drive frontend formatting and downstream scaling.
UNIT_RATIO = "ratio"
UNIT_PERCENT = "percent"      # stored as a fraction (0.18 -> 18%)
UNIT_CURRENCY = "currency"
UNIT_DAYS = "days"
UNIT_COUNT = "count"
UNIT_YEARS = "years"
UNIT_SCORE = "score"          # normalised 0..1


# ---------------------------------------------------------------------------
# Categorical -> numeric encoders (shared, deterministic)
# ---------------------------------------------------------------------------

RISK_BAND_SCORE = {"low": 0.20, "moderate": 0.50, "high": 0.85}
CONCENTRATION_SCORE = {"diversified": 0.20, "balanced": 0.50, "concentrated": 0.85}
COMPLIANCE_SCORE = {
    "compliant": 1.0, "consistent": 1.0, "clean": 1.0, "good": 1.0,
    "partial": 0.5, "inconsistent": 0.5, "moderate": 0.5,
    "non_compliant": 0.0, "pending": 0.0, "poor": 0.0,
}
STAGE_SCORE = {
    "mature": 0.90, "expansion": 0.78, "growth": 0.70,
    "startup": 0.40, "decline": 0.25,
}
PRESENT_TOKENS = {"present", "yes", "true", "1"}


def safe_div(numerator: Number, denominator: Number) -> Number:
    """Divide, returning ``None`` when either operand is missing or the
    denominator is zero — an undefined ratio is never a fabricated number."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


# ---------------------------------------------------------------------------
# Feature computation context
# ---------------------------------------------------------------------------

@dataclass
class FeatureContext:
    """Everything a feature definition may read, in normalised form."""

    statement: FinancialStatement
    ratios: Mapping[str, Ratio]
    engine_input: Mapping[str, Any] = field(default_factory=dict)
    previous: Optional[FinancialStatement] = None
    previous_ratios: Mapping[str, Ratio] = field(default_factory=dict)

    # -- accessors -------------------------------------------------------
    def ratio(self, key: str) -> Number:
        r = self.ratios.get(key)
        return None if r is None else r.value

    def prev_ratio(self, key: str) -> Number:
        r = self.previous_ratios.get(key)
        return None if r is None else r.value

    def num(self, *keys: str) -> Number:
        for key in keys:
            if key in self.engine_input and self.engine_input[key] is not None:
                try:
                    return float(self.engine_input[key])
                except (TypeError, ValueError):
                    continue
        return None

    def text(self, *keys: str) -> str:
        for key in keys:
            if key in self.engine_input and self.engine_input[key] is not None:
                return str(self.engine_input[key]).strip().lower()
        return ""


# ---------------------------------------------------------------------------
# Feature definition & materialised feature
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    category: str
    description: str
    source: str
    compute: Callable[[FeatureContext], Number]
    unit: str = UNIT_RATIO
    base_confidence: float = 0.90
    # Features whose denominator relies on an *estimated* total-assets figure
    # get their confidence discounted when that estimate is in play.
    depends_on_assets: bool = False
    version: str = FEATURE_SET_VERSION

    def metadata(self) -> dict:
        return {
            "feature_name": self.name,
            "category": self.category,
            "description": self.description,
            "source": self.source,
            "unit": self.unit,
            "version": self.version,
        }


@dataclass
class Feature:
    """A materialised feature value with full provenance."""

    feature_name: str
    category: str
    description: str
    value: Number
    unit: str
    version: str
    source: str
    confidence: float
    generated_time: str

    def as_dict(self) -> dict:
        return {
            "feature_name": self.feature_name,
            "category": self.category,
            "description": self.description,
            "value": None if self.value is None else round(self.value, 6),
            "unit": self.unit,
            "version": self.version,
            "source": self.source,
            "confidence": round(self.confidence, 3),
            "generated_time": self.generated_time,
        }


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

def _catalogue() -> List[FeatureDefinition]:
    d = FeatureDefinition  # local alias for readability
    return [
        # -- Liquidity ---------------------------------------------------
        d("current_ratio", LIQUIDITY, "Current assets over current liabilities.",
          SRC_RATIO, lambda c: c.ratio("current_ratio")),
        d("quick_ratio", LIQUIDITY, "Acid-test liquidity excluding inventory.",
          SRC_RATIO, lambda c: c.ratio("quick_ratio")),
        d("cash_ratio", LIQUIDITY, "Cash and equivalents over current liabilities.",
          SRC_RATIO, lambda c: c.ratio("cash_ratio")),
        d("net_working_capital_ratio", LIQUIDITY,
          "Working capital scaled by current liabilities.", SRC_STATEMENT,
          lambda c: safe_div(c.statement.working_capital, c.statement.current_liabilities)),

        # -- Leverage ----------------------------------------------------
        d("debt_to_equity", LEVERAGE, "Total debt over total equity.",
          SRC_RATIO, lambda c: c.ratio("debt_to_equity")),
        d("debt_ratio", LEVERAGE, "Share of assets funded by debt.",
          SRC_RATIO, lambda c: c.ratio("debt_ratio"), depends_on_assets=True),
        d("debt_to_ebitda", LEVERAGE, "Total debt relative to cash earnings.",
          SRC_STATEMENT, lambda c: safe_div(c.statement.total_debt, c.statement.ebitda)),
        d("interest_coverage", LEVERAGE, "EBIT over interest expense.",
          SRC_RATIO, lambda c: c.ratio("interest_coverage")),
        d("equity_ratio", LEVERAGE, "Owners' capital as a share of assets.",
          SRC_STATEMENT,
          lambda c: safe_div(c.statement.total_equity, c.statement.effective_total_assets),
          depends_on_assets=True),

        # -- Profitability ----------------------------------------------
        d("gross_margin", PROFITABILITY, "Gross profit as a fraction of revenue.",
          SRC_RATIO, lambda c: c.ratio("gross_margin"), unit=UNIT_PERCENT),
        d("operating_margin", PROFITABILITY, "Operating income as a fraction of revenue.",
          SRC_RATIO, lambda c: c.ratio("operating_margin"), unit=UNIT_PERCENT),
        d("ebitda_margin", PROFITABILITY, "EBITDA as a fraction of revenue.",
          SRC_RATIO, lambda c: c.ratio("ebitda_margin"), unit=UNIT_PERCENT),
        d("net_margin", PROFITABILITY, "Net profit as a fraction of revenue.",
          SRC_RATIO, lambda c: c.ratio("net_margin"), unit=UNIT_PERCENT),
        d("return_on_assets", PROFITABILITY, "Net profit over total assets.",
          SRC_RATIO, lambda c: c.ratio("return_on_assets"), unit=UNIT_PERCENT,
          depends_on_assets=True),
        d("return_on_equity", PROFITABILITY, "Net profit over total equity.",
          SRC_RATIO, lambda c: c.ratio("return_on_equity"), unit=UNIT_PERCENT),

        # -- Cash flow ---------------------------------------------------
        d("operating_cash_flow_ratio", CASH_FLOW,
          "Operating cash flow over current liabilities.", SRC_RATIO,
          lambda c: c.ratio("operating_cash_flow_ratio")),
        d("free_cash_flow", CASH_FLOW, "Cash left after reinvestment.",
          SRC_RATIO, lambda c: c.ratio("free_cash_flow"), unit=UNIT_CURRENCY),
        d("operating_cash_flow_margin", CASH_FLOW,
          "Operating cash flow as a fraction of revenue.", SRC_STATEMENT,
          lambda c: safe_div(c.statement.operating_cash_flow, c.statement.revenue),
          unit=UNIT_PERCENT),
        d("free_cash_flow_margin", CASH_FLOW,
          "Free cash flow as a fraction of revenue.", SRC_STATEMENT,
          lambda c: safe_div(c.statement.free_cash_flow_value, c.statement.revenue),
          unit=UNIT_PERCENT),
        d("cash_flow_to_debt", CASH_FLOW,
          "Operating cash flow available against total debt.", SRC_STATEMENT,
          lambda c: safe_div(c.statement.operating_cash_flow, c.statement.total_debt)),

        # -- Efficiency --------------------------------------------------
        d("asset_turnover", EFFICIENCY, "Revenue generated per unit of assets.",
          SRC_RATIO, lambda c: c.ratio("asset_turnover"), depends_on_assets=True),
        d("inventory_turnover", EFFICIENCY, "Times inventory is sold in the period.",
          SRC_RATIO, lambda c: c.ratio("inventory_turnover")),
        d("receivable_turnover", EFFICIENCY, "Efficiency of collecting credit sales.",
          SRC_RATIO, lambda c: c.ratio("receivable_turnover")),
        d("payable_turnover", EFFICIENCY, "Speed of paying suppliers.",
          SRC_RATIO, lambda c: c.ratio("payable_turnover")),

        # -- Growth (needs a prior period) -------------------------------
        d("revenue_growth", GROWTH, "Period-over-period revenue growth.",
          SRC_PRIOR_PERIOD, unit=UNIT_PERCENT,
          compute=lambda c: _growth(c.statement.revenue, _prev(c, "revenue"))),
        d("net_profit_growth", GROWTH, "Period-over-period net profit growth.",
          SRC_PRIOR_PERIOD, unit=UNIT_PERCENT,
          compute=lambda c: _growth(c.statement.net_profit, _prev(c, "net_profit"))),
        d("ebitda_growth", GROWTH, "Period-over-period EBITDA growth.",
          SRC_PRIOR_PERIOD, unit=UNIT_PERCENT,
          compute=lambda c: _growth(c.statement.ebitda, _prev(c, "ebitda"))),

        # -- Working capital ---------------------------------------------
        d("working_capital", WORKING_CAPITAL, "Absolute short-term liquidity cushion.",
          SRC_STATEMENT, lambda c: c.statement.working_capital, unit=UNIT_CURRENCY),
        d("working_capital_to_revenue", WORKING_CAPITAL,
          "Working capital intensity of the business.", SRC_STATEMENT,
          lambda c: safe_div(c.statement.working_capital, c.statement.revenue)),
        d("receivable_days", WORKING_CAPITAL, "Average collection period.",
          SRC_STATEMENT, lambda c: _days(c.ratio("receivable_turnover")), unit=UNIT_DAYS),
        d("inventory_days", WORKING_CAPITAL, "Average days inventory is held.",
          SRC_STATEMENT, lambda c: _days(c.ratio("inventory_turnover")), unit=UNIT_DAYS),
        d("payable_days", WORKING_CAPITAL, "Average days to pay suppliers.",
          SRC_STATEMENT, lambda c: _days(c.ratio("payable_turnover")), unit=UNIT_DAYS),
        d("cash_conversion_cycle", WORKING_CAPITAL,
          "Days to convert working-capital investment back into cash.", SRC_STATEMENT,
          compute=_cash_conversion_cycle, unit=UNIT_DAYS),

        # -- Banking behaviour -------------------------------------------
        d("avg_monthly_balance", BANKING_BEHAVIOUR, "Average monthly bank balance.",
          SRC_BANKING, lambda c: c.num("average_monthly_balance"), unit=UNIT_CURRENCY),
        d("inflow_outflow_ratio", BANKING_BEHAVIOUR,
          "Monthly cash inflow relative to outflow.", SRC_BANKING,
          lambda c: safe_div(c.num("average_monthly_inflow"), c.num("average_monthly_outflow"))),
        d("credit_utilization", BANKING_BEHAVIOUR, "Working-capital limit utilisation.",
          SRC_BANKING, lambda c: c.num("credit_utilization"), unit=UNIT_PERCENT,
          base_confidence=0.85),
        d("emi_to_inflow", BANKING_BEHAVIOUR, "Existing EMI burden on monthly inflow.",
          SRC_BANKING, lambda c: safe_div(c.num("existing_emi"), c.num("average_monthly_inflow"))),
        d("cheque_bounce_count", BANKING_BEHAVIOUR, "Number of cheque bounces.",
          SRC_BANKING, lambda c: c.num("cheque_bounce_count"), unit=UNIT_COUNT),
        d("balance_to_outflow", BANKING_BEHAVIOUR,
          "Months of outflow covered by the average balance.", SRC_BANKING,
          lambda c: safe_div(c.num("average_monthly_balance"), c.num("average_monthly_outflow"))),

        # -- Collateral --------------------------------------------------
        d("collateral_coverage", COLLATERAL,
          "Recoverable base (net worth + current assets) over total debt.", SRC_STATEMENT,
          compute=lambda c: safe_div(
              _sum(c.num("net_worth", "total_equity"), c.statement.current_assets),
              c.statement.total_debt)),
        d("net_worth", COLLATERAL, "Owners' net worth (total equity).",
          SRC_STATEMENT, lambda c: c.num("net_worth", "total_equity"), unit=UNIT_CURRENCY),
        d("tangible_asset_coverage", COLLATERAL,
          "Current assets available against total debt.", SRC_STATEMENT,
          lambda c: safe_div(c.statement.current_assets, c.statement.total_debt)),

        # -- Business stability ------------------------------------------
        d("years_in_business", BUSINESS_STABILITY, "Operating history in years.",
          SRC_QUALITATIVE, lambda c: c.num("years_in_business"), unit=UNIT_YEARS,
          base_confidence=1.0),
        d("employee_count", BUSINESS_STABILITY, "Headcount.",
          SRC_QUALITATIVE, lambda c: c.num("employee_count"), unit=UNIT_COUNT,
          base_confidence=1.0),
        d("expansion_stage_score", BUSINESS_STABILITY,
          "Lifecycle stage encoded to a stability score.", SRC_QUALITATIVE,
          lambda c: STAGE_SCORE.get(c.text("business_expansion_stage"), None),
          unit=UNIT_SCORE),

        # -- Revenue quality ---------------------------------------------
        d("revenue", REVENUE_QUALITY, "Annual revenue.",
          SRC_STATEMENT, lambda c: c.statement.revenue, unit=UNIT_CURRENCY),
        d("receivable_intensity", REVENUE_QUALITY,
          "Receivables as a fraction of revenue (lower is cleaner).", SRC_STATEMENT,
          lambda c: safe_div(c.statement.accounts_receivable, c.statement.revenue)),
        d("cash_realization_ratio", REVENUE_QUALITY,
          "Operating cash flow relative to reported net profit.", SRC_STATEMENT,
          lambda c: safe_div(c.statement.operating_cash_flow, c.statement.net_profit)),

        # -- Customer concentration --------------------------------------
        d("customer_concentration_score", CUSTOMER_CONCENTRATION,
          "Customer concentration encoded to a risk score.", SRC_QUALITATIVE,
          lambda c: CONCENTRATION_SCORE.get(c.text("customer_concentration"), None),
          unit=UNIT_SCORE),
        d("supplier_concentration_score", CUSTOMER_CONCENTRATION,
          "Supplier concentration encoded to a risk score.", SRC_QUALITATIVE,
          lambda c: CONCENTRATION_SCORE.get(c.text("supplier_concentration"), None),
          unit=UNIT_SCORE),

        # -- Operational metrics -----------------------------------------
        d("opex_ratio", OPERATIONAL, "Operating expenses as a fraction of revenue.",
          SRC_STATEMENT,
          lambda c: safe_div(c.num("operating_expenses") or c.statement.operating_expenses,
                             c.statement.revenue),
          unit=UNIT_PERCENT),
        d("revenue_per_employee", OPERATIONAL, "Revenue generated per employee.",
          SRC_STATEMENT, lambda c: safe_div(c.statement.revenue, c.num("employee_count")),
          unit=UNIT_CURRENCY),
        d("ebitda_per_employee", OPERATIONAL, "EBITDA generated per employee.",
          SRC_STATEMENT, lambda c: safe_div(c.statement.ebitda, c.num("employee_count")),
          unit=UNIT_CURRENCY),

        # -- Risk metrics ------------------------------------------------
        d("industry_risk_score", RISK, "Industry risk band encoded to a score.",
          SRC_QUALITATIVE, lambda c: RISK_BAND_SCORE.get(c.text("industry_risk"), None),
          unit=UNIT_SCORE),
        d("geographical_risk_score", RISK, "Geographic risk band encoded to a score.",
          SRC_QUALITATIVE, lambda c: RISK_BAND_SCORE.get(c.text("geographical_risk"), None),
          unit=UNIT_SCORE),
        d("prior_defaults_flag", RISK, "Whether prior defaults are on record.",
          SRC_QUALITATIVE,
          lambda c: 1.0 if c.text("previous_defaults", "past_defaults") in PRESENT_TOKENS else 0.0,
          unit=UNIT_SCORE, base_confidence=1.0),
        d("compliance_score", RISK, "Average of tax and GST compliance standing.",
          SRC_QUALITATIVE, compute=_compliance_score, unit=UNIT_SCORE),

        # -- Historical performance (needs a prior period) ---------------
        d("previous_revenue", HISTORICAL, "Revenue in the prior period.",
          SRC_PRIOR_PERIOD, lambda c: _prev(c, "revenue"), unit=UNIT_CURRENCY),
        d("previous_net_profit", HISTORICAL, "Net profit in the prior period.",
          SRC_PRIOR_PERIOD, lambda c: _prev(c, "net_profit"), unit=UNIT_CURRENCY),
        d("previous_net_margin", HISTORICAL, "Net margin in the prior period.",
          SRC_PRIOR_PERIOD, unit=UNIT_PERCENT,
          compute=lambda c: safe_div(_prev(c, "net_profit"), _prev(c, "revenue"))),

        # -- Trend metrics (needs a prior period) ------------------------
        d("net_margin_trend", TREND, "Change in net margin versus the prior period.",
          SRC_PRIOR_PERIOD, unit=UNIT_PERCENT,
          compute=lambda c: _delta(c.ratio("net_margin"), c.prev_ratio("net_margin"))),
        d("leverage_trend", TREND, "Change in debt-to-equity versus the prior period.",
          SRC_PRIOR_PERIOD,
          compute=lambda c: _delta(c.ratio("debt_to_equity"), c.prev_ratio("debt_to_equity"))),
        d("dscr_trend", TREND, "Change in debt-service coverage versus the prior period.",
          SRC_PRIOR_PERIOD,
          compute=lambda c: _delta(c.ratio("dscr"), c.prev_ratio("dscr"))),
    ]


# ---------------------------------------------------------------------------
# Shared compute helpers (module-level so definitions stay one-liners)
# ---------------------------------------------------------------------------

def _sum(*values: Number) -> Number:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _prev(ctx: FeatureContext, attr: str) -> Number:
    if ctx.previous is None:
        return None
    return getattr(ctx.previous, attr, None)


def _growth(current: Number, previous: Number) -> Number:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


def _delta(current: Number, previous: Number) -> Number:
    if current is None or previous is None:
        return None
    return current - previous


def _days(turnover: Number) -> Number:
    if turnover is None or turnover == 0:
        return None
    return 365.0 / turnover


def _cash_conversion_cycle(ctx: FeatureContext) -> Number:
    dso = _days(ctx.ratio("receivable_turnover"))
    dio = _days(ctx.ratio("inventory_turnover"))
    dpo = _days(ctx.ratio("payable_turnover"))
    if dso is None or dio is None or dpo is None:
        return None
    return dso + dio - dpo


def _compliance_score(ctx: FeatureContext) -> Number:
    tax = COMPLIANCE_SCORE.get(ctx.text("tax_compliance", "tax_filing_status"))
    gst = COMPLIANCE_SCORE.get(ctx.text("gst_compliance", "gst_filing_consistency"))
    present = [v for v in (tax, gst) if v is not None]
    return sum(present) / len(present) if present else None


# ---------------------------------------------------------------------------
# Public registry accessors
# ---------------------------------------------------------------------------

_REGISTRY: List[FeatureDefinition] = _catalogue()
_BY_NAME: Dict[str, FeatureDefinition] = {defn.name: defn for defn in _REGISTRY}


def get_registry() -> List[FeatureDefinition]:
    """The ordered feature catalogue. Order is stable and is the canonical
    feature order for model training/inference against this version."""
    return list(_REGISTRY)


def get_definition(name: str) -> Optional[FeatureDefinition]:
    return _BY_NAME.get(name)


def feature_names() -> List[str]:
    return [defn.name for defn in _REGISTRY]


def definitions_by_category() -> Dict[str, List[FeatureDefinition]]:
    grouped: Dict[str, List[FeatureDefinition]] = {}
    for defn in _REGISTRY:
        grouped.setdefault(defn.category, []).append(defn)
    return grouped


def registry_metadata() -> dict:
    """A serialisable snapshot of the catalogue, persisted alongside every
    feature vector so historical vectors remain self-describing."""
    return {
        "feature_set_version": FEATURE_SET_VERSION,
        "feature_count": len(_REGISTRY),
        "categories": list(CATEGORIES),
        "features": [defn.metadata() for defn in _REGISTRY],
    }

"""Enterprise credit scoring engine.

A transparent, factor-based commercial scorecard. It converts a company's
financial, banking and qualitative-risk inputs into

    * an enterprise credit score (300-900)
    * a letter risk grade (AAA .. CC)
    * calibrated Probability of Default (PD), Loss Given Default (LGD) and
      Expected Loss (EL)
    * four health dimensions (liquidity, debt, working capital, stability)
    * a recommended loan amount / interest rate / tenure / collateral posture
    * a plain-language narrative

Design goals
------------
* **Deterministic & explainable** - the score is a weighted blend of six
  category health scores; every category exposes a 0-100 sub-score and a
  one-line rationale. No black box.
* **Real commercial ratios** - including DSCR (debt-service coverage), the
  single most important metric in business lending, which the previous
  implementation omitted.
* **Calibrated risk** - PD follows a realistic exponential curve
  (strong grades ~<0.5%, weak grades ~20-30%) instead of the previous linear
  ``(900 - score) / 900`` that priced a AAA borrower at ~13% PD.
* **Backward compatible** - accepts both the new flat keys and the legacy
  keys used by other callers, and returns every legacy response key plus the
  new structured fields.

The public entrypoint remains ``evaluate_enterprise_assessment(data) -> dict``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple


# ---------------------------------------------------------------------------
# Category weights (must sum to 1.0). These drive the composite score and are
# the single place to tune the scorecard's emphasis.
# ---------------------------------------------------------------------------

CATEGORY_WEIGHTS: Dict[str, float] = {
    "profitability": 0.20,
    "liquidity": 0.16,
    "debt": 0.20,
    "working_capital": 0.12,
    "cash_flow": 0.16,
    "stability": 0.08,
    "conduct": 0.08,
}

SCORE_MIN, SCORE_MAX = 300, 900

# PD calibration constants (exponential decay across the score band).
PD_AT_FLOOR = 0.30      # PD at the minimum score
PD_DECAY_K = 6.40       # decay rate -> PD ~0.05% at the maximum score
PD_ABS_FLOOR = 0.0005

# Debt-capacity multiples of EBITDA by creditworthiness (for loan sizing).
MAX_LEVERAGE_MULTIPLE = 4.5   # best grade
MIN_LEVERAGE_MULTIPLE = 0.5   # weakest grade


# ---------------------------------------------------------------------------
# Input helpers (tolerant of both new and legacy key names)
# ---------------------------------------------------------------------------

def _num(data: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in data and data[key] is not None:
            try:
                return float(data[key])
            except (TypeError, ValueError):
                continue
    return default


def _cat(data: Dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        if key in data and data[key] is not None:
            return str(data[key]).strip().lower()
    return default


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


def scale(value: float, lo: float, hi: float) -> float:
    """Linearly map ``value`` to 0-100 where ``lo`` -> 0 and ``hi`` -> 100.

    Works in both directions: pass ``lo > hi`` for "lower is better" metrics.
    """
    if hi == lo:
        return 50.0
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


def _label(score: float) -> str:
    if score >= 70:
        return "Strong"
    if score >= 45:
        return "Adequate"
    return "Weak"


# ---------------------------------------------------------------------------
# Ratio engine
# ---------------------------------------------------------------------------

def compute_ratios(data: Dict[str, Any]) -> Dict[str, float]:
    revenue = _num(data, "annual_revenue", "annual_turnover", default=0.0)
    gross_profit = _num(data, "gross_profit")
    net_profit = _num(data, "net_profit")
    ebitda = _num(data, "ebitda")
    cash = _num(data, "cash_and_cash_equivalents")
    inventory = _num(data, "inventory")
    receivables = _num(data, "accounts_receivable")
    current_assets = _num(data, "current_assets")
    current_liabilities = _num(data, "current_liabilities")
    long_term_debt = _num(data, "long_term_debt")
    short_term_debt = _num(data, "short_term_debt")
    net_worth = _num(data, "net_worth")
    interest_expense = _num(data, "interest_expense")
    existing_emi = _num(data, "existing_emi")
    operating_cash_flow = _num(data, "operating_cash_flow")
    free_cash_flow = _num(data, "free_cash_flow")
    working_capital = _num(
        data, "working_capital", default=current_assets - current_liabilities
    )

    total_debt = long_term_debt + short_term_debt
    # EMI is an Equated Monthly Installment -> annualise for debt service.
    annual_debt_service = interest_expense + existing_emi * 12.0
    total_assets_est = current_assets + long_term_debt  # proxy in absence of fixed assets

    ratios = {
        "gross_margin": safe_divide(gross_profit, revenue),
        "operating_margin": safe_divide(ebitda, revenue),
        "net_margin": safe_divide(net_profit, revenue),
        "current_ratio": safe_divide(current_assets, current_liabilities),
        "quick_ratio": safe_divide(current_assets - inventory, current_liabilities),
        "cash_ratio": safe_divide(cash, current_liabilities),
        "debt_to_equity": safe_divide(total_debt, net_worth, default=total_debt and 10.0),
        "debt_to_ebitda": safe_divide(total_debt, ebitda, default=total_debt and 12.0),
        "interest_coverage": safe_divide(ebitda, interest_expense, default=ebitda and 15.0),
        "dscr": safe_divide(ebitda, annual_debt_service, default=ebitda and 5.0),
        "operating_cash_flow_margin": safe_divide(operating_cash_flow, revenue),
        "free_cash_flow_margin": safe_divide(free_cash_flow, revenue),
        "return_on_assets": safe_divide(net_profit, total_assets_est),
        "return_on_equity": safe_divide(net_profit, net_worth),
        "working_capital": working_capital,
        "working_capital_to_revenue": safe_divide(working_capital, revenue),
        "receivable_days": min(
            365.0,
            _num(data, "average_collection_period", default=safe_divide(receivables, revenue) * 365.0),
        ),
        "leverage_load": safe_divide(total_debt, revenue),
        "total_debt": total_debt,
    }
    return ratios


# ---------------------------------------------------------------------------
# Category scorers -> (0-100 score, rationale)
# ---------------------------------------------------------------------------

def _score_profitability(r: Dict[str, float]) -> Tuple[float, str]:
    parts = [
        scale(r["net_margin"], -0.05, 0.20),
        scale(r["gross_margin"], 0.05, 0.45),
        scale(r["operating_margin"], 0.0, 0.25),
    ]
    score = sum(parts) / len(parts)
    return score, (
        f"Net margin {r['net_margin'] * 100:.1f}% and gross margin "
        f"{r['gross_margin'] * 100:.1f}% indicate {_label(score).lower()} earnings quality."
    )


def _score_liquidity(r: Dict[str, float]) -> Tuple[float, str]:
    parts = [
        scale(r["current_ratio"], 0.8, 2.5),
        scale(r["quick_ratio"], 0.5, 1.5),
        scale(r["cash_ratio"], 0.05, 0.5),
    ]
    score = sum(parts) / len(parts)
    return score, (
        f"Current ratio {r['current_ratio']:.2f}x and quick ratio {r['quick_ratio']:.2f}x "
        f"show {_label(score).lower()} short-term solvency."
    )


def _score_debt(r: Dict[str, float]) -> Tuple[float, str]:
    parts = [
        scale(r["debt_to_ebitda"], 6.0, 1.0),   # lower is better
        scale(r["debt_to_equity"], 3.0, 0.3),   # lower is better
        scale(r["interest_coverage"], 1.0, 8.0),
    ]
    score = sum(parts) / len(parts)
    return score, (
        f"Debt/EBITDA {r['debt_to_ebitda']:.2f}x with interest coverage "
        f"{r['interest_coverage']:.2f}x reflects {_label(score).lower()} leverage."
    )


def _score_working_capital(r: Dict[str, float]) -> Tuple[float, str]:
    wc_positive = 100.0 if r["working_capital"] > 0 else 0.0
    parts = [
        wc_positive,
        scale(r["working_capital_to_revenue"], 0.0, 0.30),
        scale(r["receivable_days"], 120.0, 20.0),  # fewer days is better
    ]
    score = sum(parts) / len(parts)
    return score, (
        f"Working capital of {r['working_capital']:,.0f} and collection cycle of "
        f"{r['receivable_days']:.0f} days are {_label(score).lower()}."
    )


def _score_cash_flow(r: Dict[str, float]) -> Tuple[float, str]:
    parts = [
        scale(r["dscr"], 1.0, 2.5),
        scale(r["operating_cash_flow_margin"], -0.05, 0.20),
        scale(r["free_cash_flow_margin"], -0.05, 0.15),
    ]
    score = sum(parts) / len(parts)
    return score, (
        f"DSCR {r['dscr']:.2f}x and operating cash-flow margin "
        f"{r['operating_cash_flow_margin'] * 100:.1f}% give {_label(score).lower()} debt-servicing capacity."
    )


_STAGE_SCORE = {
    "mature": 90.0,
    "expansion": 78.0,
    "growth": 70.0,
    "startup": 40.0,
    "decline": 25.0,
}


def _score_stability(data: Dict[str, Any]) -> Tuple[float, str]:
    years = _num(data, "years_in_business")
    employees = _num(data, "employee_count")
    stage = _cat(data, "business_expansion_stage", default="growth")
    parts = [
        scale(years, 0.0, 15.0),
        scale(math.log10(max(employees, 1.0)), 0.0, math.log10(500.0)),
        _STAGE_SCORE.get(stage, 60.0),
    ]
    score = sum(parts) / len(parts)
    return score, (
        f"{int(years)} years in business, {int(employees)} employees and a "
        f"'{stage}' stage make operational stability {_label(score).lower()}."
    )


_RISK_BAND_PENALTY = {"low": 0.0, "moderate": 10.0, "high": 25.0}
_CONCENTRATION_PENALTY = {"diversified": 0.0, "balanced": 8.0, "concentrated": 22.0}


def _compliance_penalty(value: str) -> float:
    if value in {"compliant", "consistent", "good", "clean"}:
        return 0.0
    if value in {"partial", "inconsistent", "moderate"}:
        return 12.0
    return 25.0  # non_compliant / pending / poor / unknown


def _score_conduct(data: Dict[str, Any]) -> Tuple[float, str]:
    score = 100.0
    utilization = _num(data, "credit_utilization")
    if utilization > 40.0:
        score -= min(25.0, (utilization - 40.0) * 0.5)
    score -= min(25.0, _num(data, "cheque_bounce_count") * 6.0)
    score -= min(15.0, _num(data, "existing_bank_loans", "existing_loans") * 3.0)
    score -= _RISK_BAND_PENALTY.get(_cat(data, "industry_risk", default="moderate"), 10.0)
    score -= _RISK_BAND_PENALTY.get(_cat(data, "geographical_risk", default="low"), 0.0)
    score -= _CONCENTRATION_PENALTY.get(_cat(data, "supplier_concentration", default="balanced"), 8.0)
    score -= _CONCENTRATION_PENALTY.get(_cat(data, "customer_concentration", default="balanced"), 8.0)
    score -= _compliance_penalty(_cat(data, "tax_compliance", "tax_filing_status", default="compliant"))
    score -= _compliance_penalty(_cat(data, "gst_compliance", "gst_filing_consistency", default="compliant"))
    score = max(0.0, min(100.0, score))
    return score, (
        f"Credit utilisation {utilization:.0f}% with "
        f"{int(_num(data, 'cheque_bounce_count'))} cheque bounce(s) yields "
        f"{_label(score).lower()} credit conduct."
    )


# ---------------------------------------------------------------------------
# Grade / recommendation mapping (300-900 scale)
# ---------------------------------------------------------------------------

def map_grade(score: int) -> str:
    for threshold, grade in (
        (820, "AAA"), (760, "AA"), (700, "A"), (640, "BBB"),
        (580, "BB"), (520, "B"), (460, "CCC"),
    ):
        if score >= threshold:
            return grade
    return "CC"


def map_tenure(score: int) -> str:
    if score >= 760:
        return "Up to 10 years"
    if score >= 700:
        return "Up to 7 years"
    if score >= 640:
        return "Up to 5 years"
    if score >= 580:
        return "Up to 3 years"
    return "Up to 2 years"


def map_collateral(score: int) -> str:
    if score >= 760:
        return "Standard business collateral; clean-up covenants sufficient"
    if score >= 640:
        return "Collateral secured by property or receivables required"
    return "Strong collateral coverage plus personal/promoter guarantees required"


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate_enterprise_assessment(data: Dict[str, Any]) -> Dict[str, Any]:
    ratios = compute_ratios(data)

    categories = {
        "profitability": _score_profitability(ratios),
        "liquidity": _score_liquidity(ratios),
        "debt": _score_debt(ratios),
        "working_capital": _score_working_capital(ratios),
        "cash_flow": _score_cash_flow(ratios),
        "stability": _score_stability(data),
        "conduct": _score_conduct(data),
    }
    scores = {name: value for name, (value, _rationale) in categories.items()}

    composite = sum(scores[name] * weight for name, weight in CATEGORY_WEIGHTS.items())
    raw_score = SCORE_MIN + (composite / 100.0) * (SCORE_MAX - SCORE_MIN)

    # Hard red-flag penalties (severe adverse history).
    penalties = 0.0
    if _cat(data, "previous_defaults", "past_defaults") in {"present", "yes", "true"}:
        penalties += 60.0
    if _cat(data, "wilful_default") in {"present", "yes", "true"}:
        penalties += 80.0
    if _cat(data, "legal_cases") in {"present", "yes", "true"}:
        penalties += 25.0
    if _cat(data, "director_credit_history") in {"poor", "weak", "bad"}:
        penalties += 25.0

    score = int(max(SCORE_MIN, min(SCORE_MAX, round(raw_score - penalties))))
    grade = map_grade(score)

    # --- Calibrated PD / LGD / EL ---------------------------------------
    norm = (score - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)
    probability_of_default = max(PD_ABS_FLOOR, PD_AT_FLOOR * math.exp(-PD_DECAY_K * norm))

    # LGD driven by collateral posture: net worth + current assets act as a
    # recoverable base against total debt; more coverage -> lower loss.
    recoverable_base = _num(data, "net_worth") + _num(data, "current_assets")
    coverage = safe_divide(recoverable_base, ratios["total_debt"], default=2.0)
    loss_given_default = float(max(0.10, min(0.90, 0.90 - 0.55 * min(coverage, 1.5) / 1.5)))
    expected_loss = round(probability_of_default * loss_given_default, 4)

    # --- Loan sizing & pricing ------------------------------------------
    leverage_multiple = MIN_LEVERAGE_MULTIPLE + norm * (MAX_LEVERAGE_MULTIPLE - MIN_LEVERAGE_MULTIPLE)
    ebitda = _num(data, "ebitda")
    debt_capacity = max(0.0, ebitda) * leverage_multiple
    headroom = debt_capacity - ratios["total_debt"]
    recommended_loan_amount = float(max(0.0, round(headroom / 1000.0) * 1000.0))

    recommended_interest_rate = round(8.0 + (1.0 - norm) * 10.0, 1)  # 8% best -> 18% weakest

    # --- Decision & recommendation --------------------------------------
    if penalties >= 60.0:
        decision = "Decline"
    elif score >= 700:
        decision = "Approve"
    elif score >= 580:
        decision = "Approve with conditions"
    else:
        decision = "Decline"

    if decision == "Approve":
        loan_recommendation = (
            "Recommend a standard secured working-capital / term facility with routine monitoring."
        )
    elif decision == "Approve with conditions":
        loan_recommendation = (
            "Recommend a conservatively sized secured facility with tightened covenants and enhanced monitoring."
        )
    else:
        loan_recommendation = (
            "Do not extend new credit at this time; adverse indicators outweigh repayment capacity."
        )

    monitoring = "Standard monitoring" if score >= 700 else "Enhanced monitoring"

    # --- Health dimensions (Task 3) -------------------------------------
    def health(name: str) -> Dict[str, Any]:
        value, rationale = categories[name]
        return {"score": int(round(value)), "label": _label(value), "rationale": rationale}

    health_metrics = {
        "liquidity_health": health("liquidity"),
        "debt_health": health("debt"),
        "working_capital_health": health("working_capital"),
        "business_stability": health("stability"),
    }

    # --- Explainability (deterministic ratio drivers) -------------------
    explanations = {
        "Gross Margin %": round(ratios["gross_margin"] * 100.0, 2),
        "Net Margin %": round(ratios["net_margin"] * 100.0, 2),
        "Current Ratio": round(ratios["current_ratio"], 2),
        "Quick Ratio": round(ratios["quick_ratio"], 2),
        "DSCR": round(ratios["dscr"], 2),
        "Interest Coverage": round(ratios["interest_coverage"], 2),
        "Debt / EBITDA": round(ratios["debt_to_ebitda"], 2),
        "Operating Cash Flow Margin %": round(ratios["operating_cash_flow_margin"] * 100.0, 2),
    }
    key_ratios = {k: round(v, 4) for k, v in ratios.items()}

    strongest = max(scores, key=scores.get)
    weakest = min(scores, key=scores.get)
    label_map = {
        "profitability": "profitability", "liquidity": "liquidity", "debt": "leverage",
        "working_capital": "working capital", "cash_flow": "cash flow",
        "stability": "operational stability", "conduct": "credit conduct",
    }
    narrative = (
        f"{data.get('company_name', 'The company')} scores {score} ({grade}), implying a "
        f"{probability_of_default * 100:.2f}% probability of default. The strongest driver is "
        f"{label_map[strongest]}, while {label_map[weakest]} is the primary area of concern. "
        f"Recommended decision: {decision.lower()}."
    )

    summary = {
        "enterprise_credit_score": score,
        "risk_grade": grade,
        "probability_of_default": round(probability_of_default, 4),
        "recommended_loan_amount": recommended_loan_amount,
        "recommended_interest_rate": recommended_interest_rate,
    }
    risk_metrics = {
        "probability_of_default": round(probability_of_default, 4),
        "loss_given_default": round(loss_given_default, 4),
        "expected_loss": expected_loss,
    }
    recommendation = {
        "decision": decision,
        "loan_recommendation": loan_recommendation,
        "interest_rate_recommendation": f"{recommended_interest_rate:.1f}%",
        "loan_tenure_recommendation": map_tenure(score),
        "collateral_recommendation": map_collateral(score),
        "monitoring": monitoring,
    }

    return {
        # Structured result
        "summary": summary,
        "risk_metrics": risk_metrics,
        "health_metrics": health_metrics,
        "recommendation": recommendation,
        "key_ratios": key_ratios,
        "narrative": narrative,
        # Backward-compatible flat fields
        "enterprise_credit_score": score,
        "probability_of_default": round(probability_of_default, 4),
        "loss_given_default": round(loss_given_default, 4),
        "expected_loss": expected_loss,
        "risk_rating": grade,
        "loan_recommendation": loan_recommendation,
        "interest_rate_recommendation": f"{recommended_interest_rate:.1f}%",
        "loan_tenure_recommendation": map_tenure(score),
        "collateral_recommendation": map_collateral(score),
        "ai_analysis": narrative,
        "explanations": explanations,
    }
